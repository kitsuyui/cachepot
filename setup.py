from setuptools import setup

setup(
    name='cachepot',
    version='0.1.2',
    description='Yet another Python cache library',
    long_description=open('README.md').read(),
    long_description_content_type='text/markdown',
    author='Yui Kitsu',
    author_email='kitsuyui+github@kitsuyui.com',
    url='https://github.com/kitsuyui/cachepot',
    packages=[
        'cachepot',
        'cachepot.backend',
        'cachepot.serializer',
        'cachepot.store',
    ],
    package_dir={
        'cachepot': 'cachepot',
    },
    package_data={
        '': ['README.md', 'LICENSE'],
        'cachepot': ['py.typed'],
    },
    install_requires=[
        'typing-extensions',
    ],
    tests_require=[],
    classifiers=[
        'Development Status :: 3 - Alpha',
        'License :: OSI Approved :: BSD License',
        'Intended Audience :: Developers',
    ],
    test_suite='tests',
    license='BSD-3-Clause',
)
