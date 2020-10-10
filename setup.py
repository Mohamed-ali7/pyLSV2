#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from setuptools import find_packages, setup

setup(
    name='pyLSV2',
    packages=find_packages(include=['pyLSV2']),
    version='0.1.0',
    description='A pure Python3 implementation of the LSV2 protocol',
    long_description=open('README.md').read(),s
    author='drunsinn',
    author_email='dr.unsinn@googlemail.com',
    license='MIT',
    install_requires=[]
)
