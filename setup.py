#!/usr/bin/env python

import os
from setuptools import setup

def read(*p):
    '''Utility function to read files relative to the project root'''
    return open(os.path.join(os.path.dirname(__file__), *p)).read()

def get_version():
    import re
    '''Get __version__ information from __init__.py without importing it'''
    VERSION_RE = r'^__version__\s*=\s*[\'"]([^\'"]+)[\'"]'
    VERSION_PATTERN = re.compile(VERSION_RE, re.MULTILINE)
    m = VERSION_PATTERN.search(read('chronicle', '__init__.py'))
    if m:
        return m.group(1)
    else:
        raise RuntimeError('Could not get __version__ from chronicle/__init__.py')

# Prevent "TypeError: 'NoneType' object is not callable" when running tests.
# (http://www.eby-sarna.com/pipermail/peak/2010-May/003357.html)
try:
    import multiprocessing
except ImportError:
    pass

setup(
    name='django-chronicle',
    version=get_version(),
    description='efficient model history using database triggers',
    long_description=read('README'),
    author='Michael P. Jung',
    author_email='michael.jung@terreon.de',
    license='BSD',
    keywords='django model version history revision',
    url='https://bitbucket.org/terreon/django-chronicle',
    packages=[
        'chronicle',
    ],
    #test_suite='chronicle.tests',
    install_requires=[
        'django',
    ],
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: BSD License',
        'Programming Language :: Python :: 2.7',
        'Topic :: Software Development :: Libraries :: Python Modules',
    ]
)
