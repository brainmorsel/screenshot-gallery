import os
import json
import ipaddress
import logging
from datetime import datetime

import aiohttp
from aiohttp import web
from aiohttp_session import get_session
from aiohttp_jinja2 import template

from . import metmet
from . import util


handlers = metmet.MetaCollector()


@handlers('/')
@template('index.html')
async def index(request):
    session = await get_session(request)
    username = session.get('username')
    if not username:
        return web.HTTPFound('/login')
    return {}


@handlers('/login', methods=['GET', 'POST'])
@template('login.html')
async def login(request):
    await request.post()
    username = request.POST.get('username')
    password = request.POST.get('password')

    if not (username or password):
        return {}

    with open(request.app.credentials_file) as creds:
        for line in creds:
            c_username, c_password, c_allowed = line.split(':', maxsplit=2)
            if c_username == username and c_password == password:
                session = await get_session(request)
                session['username'] = username
                session['allowed'] = [s.strip() for s in c_allowed.split(',')]
                return web.HTTPFound('/')
    return {}


@handlers('/logout')
async def logout(request):
    session = await get_session(request)
    session.invalidate()

    return web.HTTPFound('/login')


async def _get_meta_data(request, name):
    meta_data = None
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(request.app.som_url_format.format(ip_addr=name)) as resp:
                r = await resp.json()
                if r['success']:
                    meta_data = r['result']
                    request.app.meta_data_cache[name] = meta_data
    except AttributeError:
        pass  # no som_url_format in config
    return meta_data


@handlers('/dirs')
async def get_dirs_list(request):
    session = await get_session(request)
    username = session.get('username')
    allowed = session.get('allowed')
    result = []
    groups = {}

    if not allowed:
        return web.json_response(result)

    for name in os.listdir(request.app.data_dir):
        path = os.path.join(request.app.data_dir, name)
        if os.path.isdir(path):
            item = {
                'name': name,
                'display_name': name,
                'group': 'default',
                'avatar_url': 'noavatar.png',
            }
            meta_data = await _get_meta_data(request, name)
            if meta_data:
                item['display_name'] = meta_data['lname'] + ' ' + meta_data['fname']
                item['group'] = meta_data['group_name']

            if name in allowed or '*' in allowed or item['group'] in allowed:
                result.append(item)

    return web.json_response(result)


@handlers('/images')
async def get_images_list(request):
    session = await get_session(request)
    username = session.get('username')
    allowed = session.get('allowed')
    dirname = request.GET['dir']
    date = request.GET.get('date')

    if not allowed:
        return web.json_response([])

    group_name = (request.app.meta_data_cache.get(dirname) or {}).get('group_name')
    can_proceed = dirname in allowed or '*' in allowed or group_name in allowed
    if not can_proceed:
        return web.json_response([])

    dirpath = os.path.join(request.app.data_dir, dirname, date)
    url_prefix = os.path.join('/images', dirname, date)
    images = await request.app.ioloop.run_in_executor(None, util.list_images, dirpath, url_prefix)
    return web.json_response(images)


@handlers('/upload', methods=['POST'])
async def upload_image(request):
    peername = request.transport.get_extra_info('peername')
    can_proceed = False
    if peername is not None:
        host, port = peername
        for net in request.app.net_whitelist:
            if ipaddress.ip_address(host) in net:
                can_proceed = True
                break

    if not can_proceed:
        return web.json_response({"status": "FAIL"})


    name = request.GET.get('dir')
    dir_date = datetime.now().strftime('%Y-%m-%d')

    path = os.path.join(request.app.data_dir, host, dir_date)
    await request.post()
    data_stream = request.POST['file'].file
    await request.app.ioloop.run_in_executor(None, util.save_image, data_stream, path, name)

    return web.json_response({"status": "OK"})


@handlers('/last-uploads')
@template('last-uploads.html')
async def get_last_uploads(request):
    result = await request.app.ioloop.run_in_executor(None, util.list_last_uploads, request.app.data_dir)
    for item in result:
        meta_data = await _get_meta_data(request, item['name'])
        if meta_data:
            item['display_name'] = '{} {} ({})'.format(meta_data['lname'], meta_data['fname'], meta_data['group_name'])
    return {'items': result}
