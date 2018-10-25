from setuptools import setup

from os import path
this_directory = path.abspath(path.dirname(__file__))
with open(path.join(this_directory, 'README.md'), encoding='utf-8') as f:
    long_description = f.read()

setup(name='postfix_mta_sts_resolver',
      version='0.2.1',
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
          'pycares>=2.3.0',
      ],
      scripts=[
          'mta-sts-daemon',
          'mta-sts-query',
      ],
      classifiers=[
          "Programming Language :: Python :: 3.5",
          "License :: OSI Approved :: MIT License",
          "Operating System :: OS Independent",
          "Development Status :: 4 - Beta",
          "Environment :: No Input/Output (Daemon)",
          "Intended Audience :: System Administrators",
          "Natural Language :: English",
          "Topic :: Communications :: Email :: Mail Transport Agents",
          "Topic :: Internet",
          "Topic :: Security",
      ],
	  long_description=long_description,
      long_description_content_type='text/markdown',
      zip_safe=True)
