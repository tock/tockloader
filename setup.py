from setuptools import setup

setup(name='tockloader',
      version='0.2.0',
      description='TockOS Support Tool',
      author='Tock Project Developers',
      author_email='tock-dev@googlegroups.com',
      url='https://github.com/helena-project/tockloader',
      packages=['tockloader'],
      entry_points={
        'console_scripts': [
          'tockloader = tockloader.main:main'
        ]
      },
      install_requires=["crcmod >= 1.7", "pyserial >= 3.0.1"],
     )
