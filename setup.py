import setuptools

with open('SunGather/version.py', encoding='utf-8') as _version_file:
    exec(_version_file.read())  # pylint: disable=exec-used

with open("README.md", "r", encoding='utf-8') as fh:
    long_description = fh.read()

setuptools.setup(
    name="SunGather",
    version=__version__,  # pylint: disable=undefined-variable
    author="Bohdan Flower",
    author_email="github@bohdan.net",
    maintainer="Anthony Spruyt",
    description=(
        "Collect data from Sungrow Inverters and feed to various locations "
        "(MQTT, PVOutput, Home Assistant)"
    ),
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/anthony-spruyt/SunGather",
    packages=setuptools.find_packages(),
    install_requires=[
        'PyYAML~=6.0',
        'paho-mqtt~=2.0',
        'requests~=2.0',
        'influxdb-client~=1.0',
        'pymodbus>=3.6.0,<4.0.0',
        'pycryptodomex',
        'websocket-client>=1.2.1',
    ],
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: GNU General Public License v3 (GPLv3)",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.10',
)
