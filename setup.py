from setuptools import setup, find_packages

with open('README.md', 'r', encoding='utf-8') as fh:
    long_description = fh.read()

setup(
    name='rns-page-node',
    version='0.1.2',
    author='Sudo-Ivan',
    author_email='',
    description='A simple way to serve pages and files over the Reticulum network.',
    long_description=long_description,
    long_description_content_type='text/markdown',
    url='https://github.com/Sudo-Ivan/rns-page-node',
    packages=find_packages(),
    python_requires='>=3.9',
    install_requires=[
        'rns>=0.9.6,<0.10.0',
    ],
    entry_points={
        'console_scripts': [
            'rns-page-node=rns_page_node.main:main',
        ],
    },
    license='GPL-3.0',
    classifiers=[
        'Programming Language :: Python :: 3',
        'License :: OSI Approved :: GNU General Public License v3 (GPLv3)',
        'Operating System :: OS Independent',
    ],
)
