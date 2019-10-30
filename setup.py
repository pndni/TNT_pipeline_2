from setuptools import setup, find_packages


setup(
    name='TNT_pipeline_2',
    version='dev',
    packages=find_packages('TNT_pipeline_2'),
    install_requires=[
        'nipype @ https://github.com/stilley2/nipype/archive/1.2.3-mod.zip',
        'pybids>=0.9.4',
        'pndniworkflows @ git+https://github.com/pndni/pndniworkflows.git@054f9ef0fe7dc4550ed491e535df5f048bae600b7',
        'pndni_utils @ git+https://github.com/pndni/pndni_utils.git@e483e37cf9eb39fdbb1d54bbd3585894da85deb5',
        'PipelineQC @ https://github.com/pndni/PipelineQC/archive/0.10.0.zip',
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
