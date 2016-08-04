import os
import json
import ipaddress
import logging

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
            c_username, c_password, c_allowed = line.split(':')
            if c_username == username and c_password == password:
                session = await get_session(request)
                session['username'] = username
                session['allowed'] = c_allowed.split()
                return web.HTTPFound('/')
    return {}


@handlers('/logout')
async def logout(request):
    session = await get_session(request)
    session.invalidate()

    return web.HTTPFound('/login')


@handlers('/dirs')
async def get_dirs_list(request):
    session = await get_session(request)
    username = session.get('username')
    allowed = session.get('allowed')
    result = []
    groups = {}

    if not allowed:
        return web.json_response(result)

    try:
        with open(os.path.join(request.app.data_dir, 'groups.json')) as f:
            groups = json.load(f)
    except:
        pass

    for name in os.listdir(request.app.data_dir):
        if not (name in allowed or '*' in allowed):
            continue

        path = os.path.join(request.app.data_dir, name)
        if os.path.isdir(path):
            metadata_file = os.path.join(path, '.meta.json')
            with open(metadata_file) as f:
                item = json.load(f)
                item['name'] = name
                item['group_title'] = groups.get(item.get('group'))
                result.append(item)

    return web.json_response(result)


@handlers('/images')
async def get_images_list(request):
    session = await get_session(request)
    username = session.get('username')
    allowed = session.get('allowed')
    dirname = request.GET['dir']
    date_from = request.GET.get('from')
    date_to = request.GET.get('to')

    if not allowed:
        return web.json_response([])
    if not (dirname in allowed or '*' in allowed):
        return web.json_response([])

    dirpath = os.path.join(request.app.data_dir, dirname)
    images = await request.app.ioloop.run_in_executor(None, util.list_images, dirpath, date_from, date_to)
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

    dirname = request.GET['dir']
    path = os.path.join(request.app.data_dir, dirname)
    await request.post()
    data_stream = request.POST['file'].file
    await request.app.ioloop.run_in_executor(None, util.save_image, data_stream, path)

    return web.json_response({"status": "OK"})


@handlers('/last-uploads')
@template('last-uploads.html')
async def get_last_uploads(request):
    result = await request.app.ioloop.run_in_executor(None, util.list_last_uploads, request.app.data_dir)
    return {'items': result}
