# -*- coding: utf-8 -*-
"""
QtPlaskin

A graphical tool to explore ZdPlaskin Results

https://github.com/aluque/qtplaskin

Written by Alejandro Luque

---

Updated by Erwan Pannier, 2016 to turn it into an app

Note: you still have to install PyQt4 manually as it cannot be installed
from pip. Read Alejandro's INSTALL.txt file to see how to install PyQt4. 
Note that although PyQt cannot be installed through pip, you can install
if with "conda install pyqt" if you're using the Anaconda distribution of 
Python


"""

import os
from setuptools import setup
import codecs

long_description = 'A graphical tool to explore ZdPlaskin Results'
if os.path.exists('README.md'):
    long_description = codecs.open('README.md', encoding="utf-8").read()
        
setup(name='qtplaskin',
      version='1.0.1',
      description='A graphical tool to explore ZdPlaskin Results',
    	long_description=long_description,
      url='https://github.com/erwanp/publib',
      author='Alejandro Luque. Updated by Erwan Pannier',
      author_email='erwan.pannier@gmail.com',
      packages=['qtplaskin'],
      install_requires=[
          'future',  # for builtins
          'numpy',
          'scipy',
          'matplotlib',
          'h5py',
          'mpldatacursor',
          # 'pyqt'      # cannot be installed through pip. Install PyQt4 manually
		  ],
      classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Science/Research',
        'Topic :: Scientific/Engineering',
        'Topic :: Text Processing',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
        "Operating System :: OS Independent"],
      scripts=[
          'scripts/qtplaskin'],
	  include_package_data=True,
      zip_safe=False)