from setuptools import setup, find_packages


setup(
    name='TNT_pipeline_2',
    version='dev',
    packages=find_packages('TNT_pipeline_2'),
    install_requires=[
        'nipype @ https://github.com/stilley2/nipype/archive/1.2.3-mod.zip',
        'pybids>=0.9.4',
        'pndniworkflows @ git+https://github.com/pndni/pndniworkflows.git@7e4a9711be61ad984d0e1b2207f790bfa716cd52',
        'pndni_utils @ git+https://github.com/pndni/pndni_utils.git@66e93dde3d2d9dffd5926e6ee804c5adce6608ed',
        'PipelineQC @ https://github.com/pndni/PipelineQC/archive/0.9.0.zip',
    ],
    setup_requires=['pytest-runner'],
    tests_require=['pytest'],
    extra_require={
        'doc': ['Sphinx', 'sphinx-argparse', 'sphinx-rtd-theme']
    },
    entry_points={
        'console_scripts': [
            'TNT_pipeline_2 = TNT_pipeline_2.cli:main',
        ],
    },
    package_data={
        '': ['data/*']
    }
)
