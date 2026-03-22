from setuptools import setup, find_packages

setup(
    name="greeting",
    version="1.0.0",
    description="A time-aware, colourised greeting application.",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    install_requires=[
        "colorama>=0.4.6",
    ],
    extras_require={
        # Install with: pip install -e ".[docs]"
        "docs": [
            "sphinx>=9.1.0",
            "sphinx-rtd-theme>=3.1.0",
        ],
        # Install with: pip install -e ".[dev]"
        "dev": [
            "pytest>=9.0.2",
            "pip-audit>=2.10.0",
        ],
    },
    python_requires=">=3.10",
    classifiers=[
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Programming Language :: Python :: 3.13",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
)
