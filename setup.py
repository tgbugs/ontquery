import os
import sys
import shutil
from setuptools import setup

RELEASE = '--release' in sys.argv
if RELEASE:
    sys.argv.remove('--release')

scigraph_client = 'ontquery/plugins/scigraph_client.py'

files = [
    'ontquery/__init__.py',
    'ontquery/exceptions.py',
    'ontquery/plugin.py',
    'ontquery/plugins/__init__.py',
    'ontquery/plugins/services.py',
    'ontquery/query.py',
    'ontquery/services.py',
    'ontquery/terms.py',
    'ontquery/utils.py',
]

if RELEASE:
    os.system('scigraph-codegen -a https://scicrunch.org/api/1/scigraph -o ' + scigraph_client)
    files.append(scigraph_client)

try:
    os.mkdir('export')
    os.mkdir('export/plugins')
    for f in files:
        shutil.copyfile(f, f.replace('ontquery','export'))
    setup(
        name='ontquery',
        version='0.0.3',
        description='a framework querying ontology terms',
        long_description=' ',
        url='https://github.com/tgbugs/ontquery',
        author='Tom Gillespie',
        author_email='tgbugs@gmail.com',
        license='MIT',
        classifiers=[],
        keywords='ontology scigraph interlex',
        package_dir={'ontquery':'export'},
        packages=['ontquery', 'ontquery.plugins'],
        install_requires=[
        ],
        extras_require={'dev':['pyontutils',
        ]},
        entry_points={
            'console_scripts': [
            ],
        },
    )

finally:
    shutil.rmtree('export')
    if RELEASE:
        os.remove(scigraph_client)
