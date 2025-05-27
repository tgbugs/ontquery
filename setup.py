import os
import re
import sys
import shutil
from pathlib import Path
from setuptools import setup


def find_version(filename):
    _version_re = re.compile(r"__version__ = '(.*)'")
    for line in open(filename):
        version_match = _version_re.match(line)
        if version_match:
            return version_match.group(1)


__version__ = find_version('ontquery/__init__.py')

with open('README.md', 'rt') as f:
    long_description = f.read()

RELEASE = '--release' in sys.argv
if RELEASE:
    sys.argv.remove('--release')

    namespaces = Path('ontquery/plugins/namespaces/nifstd.py')
    namespaces__init__ = Path('ontquery/plugins/namespaces/__init__.py')
    scigraph_client = 'ontquery/plugins/services/scigraph_client.py'

    # namespaces
    if not namespaces.exists():
        from pyontutils.namespaces import PREFIXES

        lines = ['CURIE_MAP = {\n'] + [f'    {k!r}: {v!r},\n'
                                       for k, v in sorted(PREFIXES.items())] + ['}']

        if not namespaces.parent.exists():
            namespaces.parent.mkdir()

        with open(namespaces, 'wt') as f:
            f.writelines(lines)

        with open(namespaces__init__, 'wt') as f:
            f.write('')

    # scigraph_client
    if not Path(scigraph_client).exists():
        status_code = os.system(('scigraph-codegen '
                                 '-a https://scicrunch.org/api/1/scigraph -o ')
                                + scigraph_client)
        if status_code:
            raise OSError(f'scigraph-codegen failed with status {status_code}')

services_require = ['orthauth>=0.0.14',
                    'pyontutils>=0.1.27',
                    'rdflib>=6.0.0',
                    'requests',]
tests_require = ['pytest'] + services_require
try:
    setup(
        name='ontquery',
        version=__version__,
        description='a framework querying ontology terms',
        long_description=long_description,
        long_description_content_type='text/markdown',
        url='https://github.com/tgbugs/ontquery',
        author='Tom Gillespie',
        author_email='tgbugs@gmail.com',
        license='MIT',
        classifiers=[
            'Development Status :: 4 - Beta',
            'License :: OSI Approved :: MIT License',
            'Programming Language :: Python :: 3.6',
            'Programming Language :: Python :: 3.7',
            'Programming Language :: Python :: 3.8',
            'Programming Language :: Python :: 3.9',
            'Programming Language :: Python :: 3.10',
            'Programming Language :: Python :: 3.11',
            'Programming Language :: Python :: Implementation :: CPython',
            'Programming Language :: Python :: Implementation :: PyPy',
            'Operating System :: POSIX :: Linux',
            'Operating System :: MacOS :: MacOS X',
            'Operating System :: Microsoft :: Windows',
        ],
        keywords='ontology terminology scigraph interlex term lookup ols',
        packages=['ontquery', 'ontquery.plugins', 'ontquery.plugins.services'],
        python_requires='>=3.6',
        tests_require=tests_require,
        install_requires=[
        ],
        extras_require={'dev': ['pyontutils>=0.1.5',
                                'pytest-cov',
                                'wheel',
                                ],
                        'services': services_require,
                        'test': tests_require},
        entry_points={
            'console_scripts': [
            ],
        },
    )

finally:
    if RELEASE:
        os.remove(namespaces)
        os.remove(scigraph_client)
