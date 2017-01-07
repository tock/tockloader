from setuptools import setup

import re
VERSIONFILE="tockloader/_version.py"
verstrline = open(VERSIONFILE, "rt").read()
VSRE = r"^__version__ = ['\"]([^'\"]*)['\"]"
mo = re.search(VSRE, verstrline, re.M)
if mo:
    verstr = mo.group(1)
else:
    raise RuntimeError("Unable to find version string in %s." % (VERSIONFILE,))

setup(name='tockloader',
      version=verstr,
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
