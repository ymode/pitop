from setuptools import setup, find_packages

# Read requirements.txt and use it to populate install_requires
with open('requirements.txt') as f:
    requirements = f.read().splitlines()

setup(
    name="pitop",
    version="0.1.0",
    author="ymode",
    author_email="contact@vectordynamics.com.au",
    description="A small python based TUI application",
    long_description=open('README.md').read(),
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
    python_requires='>=3.6',
    entry_points={
        'console_scripts': [
            'pitop=pitop.pitop:main',
        ],
    },
    include_package_data=True,
    package_data={
        "pitop": ["*.py"],  # This will include all .py files in the pitop package
    },
)