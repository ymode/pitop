from setuptools import setup, find_packages

with open("requirements.txt") as f:
    requirements = [
        line.strip()
        for line in f
        if line.strip() and not line.startswith("#")
    ]

setup(
    name="pitop",
    version="0.2.0",
    author="ymode",
    author_email="contact@vectordynamics.com.au",
    description="A terminal system monitor with adaptive TUI",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    url="https://github.com/ymode/pitop",
    packages=find_packages(),
    install_requires=requirements,
    license="GPL-3.0",
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: GNU General Public License v3 (GPLv3)",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.9",
    entry_points={
        "console_scripts": [
            "pitop=pitop.app:main",
        ],
    },
    include_package_data=True,
    package_data={
        "pitop": ["*.toml"],
    },
)
