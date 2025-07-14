from setuptools import setup, find_packages

with open('README.md', 'r', encoding='utf-8') as fh:
    long_description = fh.read()

setup(
    name='rns-page-node',
    version='0.2.0',
    author='Sudo-Ivan',
    author_email='',
    description='A simple way to serve pages and files over the Reticulum network.',
    long_description=long_description,
    long_description_content_type='text/markdown',
    url='https://github.com/Sudo-Ivan/rns-page-node',
    packages=find_packages(),
    license="GPL-3.0",
    python_requires='>=3.10',
    install_requires=[
        'rns>=1.0.0,<1.5.0',
    ],
    entry_points={
        'console_scripts': [
            'rns-page-node=rns_page_node.main:main',
        ],
    },
    classifiers=[
        'Programming Language :: Python :: 3',
        'License :: OSI Approved :: GNU General Public License v3 (GPLv3)',
        'Operating System :: OS Independent',
    ],
)
