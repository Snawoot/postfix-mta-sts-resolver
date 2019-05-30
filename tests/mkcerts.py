#!/usr/bin/env python3

import argparse
import datetime
import uuid
import os.path

from cryptography import x509
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID, ExtendedKeyUsageOID

DAY = datetime.timedelta(1, 0, 0)
CA_FILENAME = 'ca'
KEY_EXT = 'key'
CERT_EXT = 'pem'
E = 65537

def parse_args():
    def check_keysize(val):
        def fail():
            raise argparse.ArgumentTypeError("%s is not valid key size" % (repr(val),))
        try:
            ival = int(val)
        except ValueError:
            fail()
        if not 1024 <= ival <= 8192:
            fail()
        return ival

    parser = argparse.ArgumentParser(
        description="Generate RSA certificates signed by common self-signed CA",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("-o", "--output-dir",
                        default='.',
                        help="location of certificates output")
    parser.add_argument("-k", "--key-size",
                        type=check_keysize,
                        default=2048,
                        help="RSA key size used for all certificates")
    parser.add_argument("-D", "--domains",
                        action="append",
                        nargs="+",
                        required=True,
                        help="domain names covered by certificate. "
                        "First one will be set as CN. Option can be used "
                        "multiple times")

    return parser.parse_args()

def ensure_private_key(output_dir, name, key_size):
    key_filename = os.path.join(output_dir, name + '.' + KEY_EXT)
    if os.path.exists(key_filename):
        with open(key_filename, "rb") as key_file:
            private_key = serialization.load_pem_private_key(key_file.read(),
                password=None, backend=default_backend())
    else:
        private_key = rsa.generate_private_key(public_exponent=E,
            key_size=key_size, backend=default_backend())
        with open(key_filename, 'wb') as key_file:
            key_file.write(private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.TraditionalOpenSSL,
                encryption_algorithm=serialization.NoEncryption()))
    return private_key

def ensure_ca_key(output_dir, key_size):
    return ensure_private_key(output_dir, CA_FILENAME, key_size)

def ensure_ca_cert(output_dir, ca_private_key):
    ca_cert_filename = os.path.join(output_dir, CA_FILENAME + '.' + CERT_EXT)
    ca_public_key = ca_private_key.public_key()
    if os.path.exists(ca_cert_filename):
        with open(ca_cert_filename, "rb") as ca_cert_file:
            ca_cert = x509.load_pem_x509_certificate(
                ca_cert_file.read(),
                backend=default_backend())
    else:
        iname = x509.Name([
            x509.NameAttribute(NameOID.COMMON_NAME, 'Test CA'),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME,
                'postfix-mta-sts-resolver dev'),
            x509.NameAttribute(NameOID.ORGANIZATIONAL_UNIT_NAME,
                'postfix-mta-sts-resolver testsuite'),
        ])
        ca_cert = x509.CertificateBuilder().\
            subject_name(iname).\
            issuer_name(iname).\
            not_valid_before(datetime.datetime.today() - DAY).\
            not_valid_after(datetime.datetime.today() + 3650 * DAY).\
            serial_number(x509.random_serial_number()).\
            public_key(ca_public_key).\
            add_extension(
                x509.BasicConstraints(ca=True, path_length=None),
                critical=True).\
            add_extension(
                x509.KeyUsage(digital_signature=False,
                              content_commitment=False,
                              key_encipherment=False,
                              data_encipherment=False,
                              key_agreement=False,
                              key_cert_sign=True,
                              crl_sign=True,
                              encipher_only=False,
                              decipher_only=False),
                critical=True).\
            add_extension(
                x509.SubjectKeyIdentifier.from_public_key(ca_public_key),
                critical=False).\
            sign(
                private_key=ca_private_key,
                algorithm=hashes.SHA256(),
                backend=default_backend()
            )
        with open(ca_cert_filename, "wb") as ca_cert_file:
            ca_cert_file.write(
                ca_cert.public_bytes(encoding=serialization.Encoding.PEM))
    assert isinstance(ca_cert, x509.Certificate)
    return ca_cert

def ensure_end_entity_key(output_dir, name, key_size):
    return ensure_private_key(output_dir, name, key_size)

def ensure_end_entity_cert(output_dir, names, ca_private_key, ca_cert, end_entity_public_key):
    name = names[0]
    end_entity_cert_filename = os.path.join(output_dir, name + '.' + CERT_EXT)
    if os.path.exists(end_entity_cert_filename):
        return
    ca_public_key = ca_private_key.public_key()
    end_entity_cert = x509.CertificateBuilder().\
        subject_name(x509.Name([
            x509.NameAttribute(NameOID.COMMON_NAME, name),
        ])).\
        issuer_name(ca_cert.subject).\
        not_valid_before(datetime.datetime.today() - DAY).\
        not_valid_after(datetime.datetime.today() + 3650 * DAY).\
        serial_number(x509.random_serial_number()).\
        public_key(end_entity_public_key).\
        add_extension(
            x509.BasicConstraints(ca=False, path_length=None),
            critical=True).\
        add_extension(
            x509.KeyUsage(digital_signature=True,
                          content_commitment=False,
                          key_encipherment=True,
                          data_encipherment=False,
                          key_agreement=False,
                          key_cert_sign=False,
                          crl_sign=False,
                          encipher_only=False,
                          decipher_only=False),
            critical=True).\
        add_extension(
            x509.ExtendedKeyUsage([
                ExtendedKeyUsageOID.SERVER_AUTH,
                ExtendedKeyUsageOID.CLIENT_AUTH,
            ]), critical=False).\
        add_extension(
            x509.AuthorityKeyIdentifier.from_issuer_public_key(ca_public_key),
            critical=False).\
        add_extension(
            x509.SubjectKeyIdentifier.from_public_key(end_entity_public_key),
            critical=False).\
        add_extension(
            x509.SubjectAlternativeName(
                [x509.DNSName(name) for name in names]
            ),
            critical=False
        ).\
        sign(
            private_key=ca_private_key,
            algorithm=hashes.SHA256(),
            backend=default_backend()
        )
    with open(end_entity_cert_filename, "wb") as end_entity_cert_file:
        end_entity_cert_file.write(
            end_entity_cert.public_bytes(encoding=serialization.Encoding.PEM))
    return end_entity_cert

def ensure_end_entity_suite(output_dir, names, ca_private_key, ca_cert, key_size):
    name = names[0]
    end_entity_key = ensure_end_entity_key(output_dir, name, key_size)
    end_entity_public_key = end_entity_key.public_key()
    ensure_end_entity_cert(output_dir, names, ca_private_key, ca_cert, end_entity_public_key)

def main():
    args = parse_args()
    ca_private_key = ensure_ca_key(args.output_dir, args.key_size)
    ca_cert = ensure_ca_cert(args.output_dir, ca_private_key)
    for names in args.domains:
        ensure_end_entity_suite(args.output_dir, names, ca_private_key, ca_cert, args.key_size)

if __name__ == '__main__':
    main()
