from setuptools import setup

setup(name='postfix_mta_sts_resolver',
      version='0.1',
      description='Daemon which provides TLS client policy for Postfix via socketmap, according to domain MTA-STS policy',
      url='https://github.com/Snawoot/postfix-mta-sts-resolver',
      author='Vladislav Yarmak',
      author_email='vladislav-ex-src@vm-0.com',
      license='MIT',
      packages=['postfix_mta_sts_resolver'],
      python_requires='>=3.5.3',
      setup_requires=[
          'wheel',
      ],
      install_requires=[
          'pynetstring>=0.1.dev2',
          'aiodns>=1.1.1',
          'aiohttp>=3.4.4',
          'PyYAML>=3.12',
          'uvloop>=0.11.0',
          'pycares>=2.3.0',
      ],
      scripts=[
          'mta-sts-daemon',
          'mta-sts-query',
      ],
      zip_safe=True)
