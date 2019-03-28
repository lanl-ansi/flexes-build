import setuptools

with open('README.rst') as f:
    long_description = f.read()

setuptools.setup(
    name='flexes_build',
    version='0.1.5',
    author='James Arnold',
    author_email='arnold_j@lanl.gov',
    description='Components for building and deploying flexes',
    long_description=long_description,
    long_description_content_type='text/markdown',
    packages=setuptools.find_packages(),
    package_data={'': ['*.css', '*.html', '*.js', '*.json']},
    install_requires=[
        'aiohttp>=3.5.4',
        'boto3>=1.9.117',
        'docker>=3.7.1',
        'flask>=1.0.2',
        'flask-redis>=0.3.0',
        'flask-swagger-ui>=3.20.9',
        'gunicorn>=19.9.0',
        'jsonschema>=3.0.1',
        'redis>=3.2.1',
        'requests>=2.21.0',
        'ujson>=1.35'
    ],
    extras_require={
        'dev': [
            'asynctest',
            'codecov',
            'mock',
            'pytest>=3.6',
            'pytest-cov',
            'pytest-flask'
        ]    
    },
    classifiers=[
        'Programming Language :: Python :: 3',
        'License :: OSI Approved :: BSD License',
        'Operating System :: OS Independent'
    ]    
)
