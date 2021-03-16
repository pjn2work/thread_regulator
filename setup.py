import setuptools
from thread_regulator import __version__

with open("README.md", "r") as fh:
    long_description = fh.read()


setuptools.setup(
    name="thread_regulator-pjn2work",
    version=__version__,
    author="Pedro Jorge Nunes",
    author_email="pjn2work@google.com",
    description="Thread Regulator with notifications and statistics",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/pjn2work/thread_regulator",
    packages=setuptools.find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.6',
)
