from setuptools import setup

setup(name='postfix_mta_sts_resolver',
      version='0.1',
      description='Daemon which provides TLS client policy for Postfix via socketmap, according to domain MTA-STS policy',
      url='https://github.com/Snawoot/postfix-mta-sts-resolver',
      author='Vladislav Yarmak',
      author_email='vladislav-ex-src@vm-0.com',
      license='MIT',
      packages=['postfix_mta_sts_resolver'],
      setup_requires=[
          'wheel',
      ],
      install_requires=[
      ],
      scripts=[
          'mta-sts-daemon',
          'mta-sts-query',
      ],
      zip_safe=True)
