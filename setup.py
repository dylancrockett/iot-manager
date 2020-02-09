from setuptools import setup

with open("README.md", "r") as fh:
    long_description = fh.read()

setup(
    name="iot-manager",
    version="0.0.5",
    packages=["iot-manager"],
    author="Dylan Crockett",
    author_email="dylanrcrockett@gmail.com",
    description="A management API for connecting and managing Clients via TCP Sockets",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/dylancrockett/iot-manager",
    project_urls={
        "Documentation": "https://iotmanager.readthedocs.io/",
        "Source Code": "https://github.com/dylancrockett/iot-manager"
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent"
    ],
    python_requires='>=3.8'
)
