from distutils.core import setup
setup(
    name='foo',
    version='1.0',
    py_modules=['capeval'],
    author='Will Gaggioli',
    author_email='wgaggioli@gmail.com',
    install_requires=[
        'pandas',
        'matplotlib'
    ]
)
