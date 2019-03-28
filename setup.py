import os
import sys
import shutil
from setuptools import setup

with open('README.md', 'rt') as f:
    long_description = f.read()

RELEASE = '--release' in sys.argv
if RELEASE:
    sys.argv.remove('--release')

namespaces = 'ontquery/plugins/namespaces.py'
scigraph_client = 'ontquery/plugins/scigraph_client.py'

files = [
    'ontquery/__init__.py',
    'ontquery/exceptions.py',
    'ontquery/plugin.py',
    'ontquery/plugins/__init__.py',
    'ontquery/plugins/interlex_client.py',
    'ontquery/plugins/services.py',
    'ontquery/query.py',
    'ontquery/services.py',
    'ontquery/terms.py',
    'ontquery/trie.py',
    'ontquery/utils.py',
]

if RELEASE:
    # namespaces
    from pyontutils.namespaces import PREFIXES

    lines = ['CURIE_MAP = {\n'] + [f'    {k!r}: {v!r},\n'
                                   for k, v in sorted(PREFIXES.items())] + ['}']
    with open(namespaces, 'wt') as f:
        f.writelines(lines)

    # scigraph_client
    status_code = os.system(('scigraph-codegen '
                            '-a https://scicrunch.org/api/1/scigraph -o ')
                            + scigraph_client)
    if status_code:
        raise OSError(f'scigraph-codegen failed with status {status_code}')

    # append to files
    files.append(namespaces)
    files.append(scigraph_client)

try:
    os.mkdir('export')
    os.mkdir('export/plugins')
    for f in files:
        shutil.copyfile(f, f.replace('ontquery', 'export'))
    setup(
        name='ontquery',
        version='0.0.6',
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
        ],
        keywords='ontology terminology scigraph interlex term lookup ols',
        package_dir={'ontquery':'export'},
        packages=['ontquery', 'ontquery.plugins'],
        python_requires='>=3.6',
        setup_requires=['pytest-runner'],
        tests_require=['pytest', 'rdflib', 'requests'],
        install_requires=[
        ],
        extras_require={'dev':['pyontutils',],
                        'services':['rdflib', 'requests']},
        entry_points={
            'console_scripts': [
            ],
        },
    )

finally:
    shutil.rmtree('export')
    if RELEASE:
        os.remove(namespaces)
        os.remove(scigraph_client)
