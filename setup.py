#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from setuptools import setup, find_packages

with open('README.rst') as fd:
    README = fd.read()

CLASSIFIERS = [
    'Environment :: Web Environment',
    'Framework :: Django',
    'Intended Audience :: Developers',
    'License :: OSI Approved :: BSD License',
    'Operating System :: OS Independent',
    'Programming Language :: Python :: 2.7',
    'Programming Language :: Python :: 3.5',
    'Topic :: Internet :: WWW/HTTP',
]

setup(
    author="Richard Case",
    author_email="rich@racitup.com",
    name="static-ranges",
    packages=find_packages(exclude=['docs']),
    version='0.2.0',
    description="WSGI middleware for handling HTTP byte-ranges",
    long_description=README,
    url='https://github.com/racitup/static-ranges',
    license='BSD License',
    platforms=['OS Independent'],
    classifiers=CLASSIFIERS,
    keywords= ['WSGI'],
    include_package_data=True,
    zip_safe=False,
    install_requires=[
    ],
    py_modules=['static_ranges'],
)
