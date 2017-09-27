from setuptools import setup, find_packages
from os import path

VERSION = "0.0.6"

here = path.abspath(path.dirname(__file__))

with open(path.join(here, 'README.MD'), encoding='utf-8') as f:
    long_description = f.read()

requirements = [
    "smartsched"
]

setup(name='smartsched.daemon',
      version=VERSION,
      description='Daemon library for smartsched lib. Allows to run strategies in daemon mode.', 
      long_description=long_description,
      author='JINR LIT Cloud Team',
      author_email='gavelock+jinr@gmail.com',
      url='https://github.com/JINR-LIT/SmartScheduler-Core',
      python_requires='~=3.4',

      classifiers=[
          'Development Status :: 3 - Alpha',

          'Intended Audience :: Developers',
          'Topic :: Software Development',

          'Programming Language :: Python :: 3',
          'Programming Language :: Python :: 3.3',
          'Programming Language :: Python :: 3.4',
          'Programming Language :: Python :: 3.5',
      ],

      keywords='cloud api scheduler',

      data_files=[('/usr/bin', ['SmartDaemon']), 
                  ('/etc/init.d', ['smart_daemon'])],
      install_requires=requirements,
      extras_require={
          'dev': [
              'pytest',
              'pytest-pep8',
              'pytest-cov',
              'bumpversion',
              'wheel',
              'twine'
          ]
      },
      packages=['smartsched.daemon']
)
