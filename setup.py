from setuptools import setup

with open("README.md", "r") as fh:
    long_description = fh.read()

setup(
    name='drone_mobile',
    version='0.2.28',
    author="bjhiltbrand",
    author_email="info@bjhiltbrand.me",
    description="Python wrapper for the DroneMobile API for Firstech/Compustar remote start systems.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/bjhiltbrand/drone_mobile_python",
    license="MIT",
    packages=['drone_mobile'],
    scripts=['drone_mobile/bin/demo.py'],
    classifiers=[
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    install_requires=['requests','filelock']
)