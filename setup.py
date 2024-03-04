#!/usr/bin/python3
# -*- coding: utf-8 -*-
from pkg_resources import parse_requirements
from setuptools import setup

readme = open('README.md', 'r').read()
with open('requirements.txt') as handle:
    requirements = [str(req) for req in parse_requirements(handle)]

setup(
    name='django_searchquery',
    version='1.0',
    description='Simple query search module for Django',
    author='Michael Shepanski',
    author_email='michael.shepanski@gmail.com',
    url='https://github.com/pkkid/django-searchquery',
    packages=['django_searchquery'],
    install_requires=requirements,
    python_requires='>=3.7',
    long_description=readme,
    keywords=['django', 'search', 'query', 'orm'],
    classifiers=[
        'Operating System :: OS Independent',
        'Programming Language :: Python :: 3',
        'License :: OSI Approved :: BSD License',
    ]
)
