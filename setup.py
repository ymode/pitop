from setuptools import setup, find_packages

# Read requirements.txt and use it to populate install_requires
with open('requirements.txt') as f:
    requirements = f.read().splitlines()

setup(
    name="pitop",
    version="0.1.0",
    author="ymode",
    author_email="contact@vectordynamics.com.au",  # Replace with your actual email address
    description="A small python based TUI application",
    long_description=open('README.md').read(),
    long_description_content_type="text/markdown",  # If your README is in Markdown
    url="https://github.com/ymode/pitop",  # Replace with the actual URL to your project
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
            'pitop=pitop:main',  # Adjust the entry point to reflect how your application is launched
        ],
    },
    # Include additional files into the package
    include_package_data=True,
    # If any package data to include in packages, specify them here
    package_data={
        # If any package contains *.txt or *.rst files, include them:
        "": ["*.txt", "*.rst"],
        # And include any *.msg files found in the 'hello' package, too:
        "hello": ["*.msg"],
    },
)
