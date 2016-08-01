from setuptools import setup, find_packages

setup(
    name='screenshot-gallery',
    version='0.1',
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        'click==6.6',
        'aiohttp==0.21.6',
        'aiohttp-session==0.5.0',
        'cryptography==1.4',  # for aiohttp-session
        'aiohttp-jinja2==0.7.0',
        'pillow==3.2.0',
    ],
    entry_points='''
        [console_scripts]
        sg-webserver=app.webserver:cli
    ''',
    )
