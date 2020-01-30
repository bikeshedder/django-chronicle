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
    setup_requires=[
        'wheel',
    ],
    classifiers=[
        'Development Status :: 4 - Beta',
        'Environment :: Web Environment',
        'Framework :: Django',
        'Framework :: Django :: 2.0',
        'Framework :: Django :: 2.1',
        'Framework :: Django :: 2.2',
        'Framework :: Django :: 3.0',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: BSD License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Topic :: Database',
        'Topic :: Software Development :: Libraries',
        'Topic :: Software Development :: Libraries :: Python Modules',
    ]
)
