# -*- coding: utf-8 -*-


"""setup.py: setuptools control."""


import re
from setuptools import setup


version = re.search(
    '^__version__\s*=\s*"(.*)"',
    open('racemgr/racemgr.py').read(),
    re.M
    ).group(1)


with open("README.md", "rb") as f:
    long_descr = f.read().decode("utf-8")

setup(
    name = "startlist",
    packages = ["racemgr",],
    #install_requires = [ "psycopg2", "yattag", "openpyxl", ],
    install_requires = [ "flask", "websocket_server", "websocket-client", ]
    entry_points = {
        "console_scripts": ['racemgr = racemgr.racemgr:raceMain'],
        },
    package_data = { },
    version = version,
    description = "CrossMgr Web Pages",
    long_description = long_descr,
    author = "Stuart Lynne",
    author_email = "stuart.lynne@gmail.com",
    url = "http://bitbucket.org/stuartlynne/qlmux_proxy",
    )
