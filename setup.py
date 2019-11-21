from setuptools import setup, find_packages


setup(
    name='TNT_pipeline_2',
    version='dev',
    packages=find_packages('TNT_pipeline_2'),
    install_requires=[
        'nipype>=1.3.1',
        'pybids>=0.9.4',
        'pndniworkflows @ git+https://github.com/pndni/pndniworkflows.git@741825251b5c2b068cf711e02cc2257cf7a57e61',
        'pndni_utils @ git+https://github.com/pndni/pndni_utils.git@8774cbef065d61761952e9118aa12f9aeda4f07e',
        'PipelineQC @ https://github.com/pndni/PipelineQC/archive/0.13.1.zip',
        'psutil',
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
