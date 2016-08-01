import os
import json
from datetime import datetime
from stat import S_ISREG, ST_CTIME, ST_MODE

from aiohttp import web
from aiohttp_session import get_session
from aiohttp_jinja2 import template
from PIL import Image

from . import metmet


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

    if not (dirname in allowed or '*' in allowed):
        return web.json_response([])

    dirpath = os.path.join(request.app.data_dir, dirname)
    entries = (os.path.join(dirpath, fn) for fn in os.listdir(dirpath))
    entries = ((os.stat(path), path) for path in entries)
    # leave only regular files, insert creation date
    entries = ((stat[ST_CTIME], os.path.basename(path))
           for stat, path in entries if S_ISREG(stat[ST_MODE]))

    entries = (((ctime, path) for ctime, path in entries if path.endswith('.png')))

    if date_from:
        date_from = int(date_from)
        entries = ((ctime, path) for ctime, path in entries if ctime >= date_from)
    if date_to:
        date_to = int(date_to)
        entries = ((ctime, path) for ctime, path in entries if ctime <= date_to)

    entries = sorted(entries)
    images = []
    for ts, fn in entries:
        images.append({'filename': fn, 'timestamp': ts})
    return web.json_response(images)


@handlers('/upload', methods=['POST'])
async def upload_image(request):
    dirname = request.GET['dir']
    path = os.path.join(request.app.data_dir, dirname)
    if not os.path.exists(path):
        os.makedirs(path)
        with open(os.path.join(path, '.meta.json'), 'w') as f:
            json.dump({
                'display_name': dirname,
                'avatar_url': 'noavatar.png'
            }, f)
    fn = datetime.now().strftime('%Y-%m-%d_%H-%M-%S.png')
    filename = os.path.join(path, fn)
    await request.post()
    file_content = request.POST['file'].file.read()
    with open(filename, 'bw') as f:
        f.write(file_content)
    img = Image.open(request.POST['file'].file)
    img.thumbnail((200, 200))
    img.save(filename + ".thumbnail.jpeg", "JPEG")
    return web.json_response({"status": "OK"})
