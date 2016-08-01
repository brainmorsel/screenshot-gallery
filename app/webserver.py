import base64
import logging
import os
import asyncio
import signal

import click
import jinja2
import aiohttp_jinja2
from aiohttp import web
from aiohttp_session import session_middleware
from aiohttp_session.cookie_storage import EncryptedCookieStorage
from cryptography.fernet import Fernet
from concurrent.futures import ThreadPoolExecutor

from . import views


def root_package_name():
    return __name__.split('.')[0]


def root_package_path(relative_path=None):
    root_module = __import__(root_package_name())
    path = os.path.dirname(os.path.abspath(root_module.__file__))
    if relative_path is not None:
        path = os.path.join(path, relative_path)
    return path


class WebServer:
    def __init__(self, loop=None):
        self._loop = loop
        self._srv = None
        self._handler = None
        self._app = None

    async def start(self, host='127.0.0.1', port=8000, *, cookie_secret=None, data_dir=None, credentials_file=None):
        # Fernet key must be 32 bytes.
        if cookie_secret is None:
            cookie_secret = base64.urlsafe_b64decode(Fernet.generate_key())
        middlewares = [
            session_middleware(EncryptedCookieStorage(cookie_secret)),
        ]
        self._app = web.Application(middlewares=middlewares)
        self._app.data_dir = data_dir
        self._app.credentials_file = credentials_file
        self._app.ioloop = self._loop

        self._executor = ThreadPoolExecutor(4)
        self._loop.set_default_executor(self._executor)

        def jinja_url_helper(route_name, *args, **kwargs):
            return self._app.router[route_name].url(*args, **kwargs)

        jinja_env = aiohttp_jinja2.setup(
            self._app,
            loader=jinja2.FileSystemLoader(root_package_path('templates')))
        jinja_env.globals['url'] = jinja_url_helper

        for handler, args, kwargs in views.handlers:
            path, = args
            methods = kwargs.get('methods', ['GET'])
            name = kwargs.get('name')
            for method in methods:
                self._app.router.add_route(method, path, handler, name=name)

        self._app.router.add_static('/images', data_dir)
        self._app.router.add_static('/', root_package_path('web-static'), name='static')

        self._handler = self._app.make_handler()
        self._srv = await self._loop.create_server(self._handler, host, port)

    async def stop(self):
        await self._handler.finish_connections(1.0)
        self._srv.close()
        await self._srv.wait_closed()
        await self._app.finish()


@click.command()
@click.option('-d', '--data-dir', 'data_dir',
              type=click.Path(exists=True, dir_okay=True), required=True)
@click.option('-c', '--credentials', 'credentials_file',
              type=click.Path(exists=True, dir_okay=False), required=True)
@click.option('-b', '--bind', default='127.0.0.1:8000')
def cli(data_dir, bind, credentials_file):
    host, port = bind.split(':')

    loop = asyncio.get_event_loop()
    try:
        loop.add_signal_handler(signal.SIGTERM, loop.stop)
    except NotImplementedError:
        # signals are not available on Windows
        pass

    webserver = WebServer(loop=loop)
    loop.run_until_complete(webserver.start(host, port, data_dir=data_dir, credentials_file=credentials_file))

    try:
        loop.run_forever()
    except KeyboardInterrupt:
        pass
    finally:
        loop.run_until_complete(webserver.stop())
        # дожидаемся завершения всех оставшихся задач и выходим.
        pending = asyncio.Task.all_tasks()
        loop.run_until_complete(asyncio.gather(*pending))
        loop.close()
