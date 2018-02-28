import os
import shutil
from setuptools import setup, find_packages

# since setuptools cannot actually exclude files so just grab the ones we want

try:
    os.mkdir('export')
    for f in files:
        shutil.copyfile(f, f.replace('ontquery','export'))
    setup(
        name='ontquery',
        version='0.0.1',
        description='a framework querying ontology terms',
        long_description=' ',
        url='https://github.com/tgbugs/ontquery',
        author='Tom Gillespie',
        author_email='tgbugs@gmail.com',
        license='MIT',
        classifiers=[],
        keywords='ontology scigraph',
        package_dir={'ontquery':'export'},
        packages=['ontquery'],
        install_requires=[
        ],
        extras_require={'dev':['pyontutils',
        ]},
        #package_data
        #data_files=[('resources',['pyontutils/resources/chebi-subset-ids.txt',])],  # not part of distro
        entry_points={
            'console_scripts': [
            ],
        },
    )

finally:
    shutil.rmtree('export')
