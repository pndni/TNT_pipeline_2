from setuptools import setup, find_packages


setup(
    name='TNT_pipeline_2',
    version='dev',
    packages=find_packages('TNT_pipeline_2'),
    install_requires=[
        'nipype @ https://github.com/stilley2/nipype/archive/1.2.3-mod.zip',
        'pybids>=0.9.4',
        'pndniworkflows @ git+https://github.com/pndni/pndniworkflows.git@0310e1a03dba6ad40846057314e6ccb5a432009f',
        'pndni_utils @ git+https://github.com/pndni/pndni_utils.git@6ae0a8f2d7174c666d07eed0a4156b713909d83f',
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
