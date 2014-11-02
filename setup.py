# -*- coding: utf-8 -*-
from setuptools import setup, find_packages

NAME = "apicaller"
DESCRIPTION = "APICaller makes the creating API client library easier."
AUTHOR = "Jan Češpivo"
AUTHOR_EMAIL = "jan.cespivo@gmail.com"
URL = "https://github.com/cespivo/apicaller"
VERSION = '0.0.2a'

setup(
    name=NAME,
    version=VERSION,
    description=DESCRIPTION,
    author=AUTHOR,
    author_email=AUTHOR_EMAIL,
    license="Apache 2.0",
    url=URL,
    py_modules=['apicaller'],
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Environment :: Web Environment',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: Apache Software License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Topic :: Internet :: WWW/HTTP',
    ],
    install_requires=[
        "requests",
    ],
)
