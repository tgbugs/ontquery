import os
import shutil
from setuptools import setup

files = [
    'ontquery/__init__.py',
]

try:
    os.mkdir('export')
    for f in files:
        shutil.copyfile(f, f.replace('ontquery','export'))
    setup(
        name='ontquery',
        version='0.0.2',
        description='a framework querying ontology terms',
        long_description=' ',
        url='https://github.com/tgbugs/ontquery',
        author='Tom Gillespie',
        author_email='tgbugs@gmail.com',
        license='MIT',
        classifiers=[],
        keywords='ontology scigraph interlex',
        package_dir={'ontquery':'export'},
        packages=['ontquery'],
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
