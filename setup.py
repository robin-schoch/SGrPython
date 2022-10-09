from setuptools import setup, find_packages
import codecs
import os

VERSION = '0.0.1'
DESCRIPTION = 'SGr demo'

# Setting up
setup(
    name="sgr_demo_v0.0.4",
    version=VERSION,
    author="zupeuc(CLEMAP)",
    author_email="<daniel@clemap.ch>",
    description=DESCRIPTION,
    long_description_content_type="text/markdown",
    packages=find_packages(),
    install_requires=[
        'Jinja2==3.1.2',
        'jmespath==0.10.0',
        'pymodbus==2.5.3',
        'setuptools==58.0.4',
        'xsdata==22.5',
        'numpy==1.20.3'
],
    keywords=['python', 'SGr'],
    classifiers=[
        "Development Status :: 1 - Planning",
        "Intended Audience :: Developers",
        "Programming Language :: Python :: 3",
        "Operating System :: Unix",
        "Operating System :: MacOS :: MacOS X",
        "Operating System :: Microsoft :: Windows",
    ]
)