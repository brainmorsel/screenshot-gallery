import os
import json
from datetime import datetime, timedelta
from stat import S_ISREG, ST_CTIME, ST_MODE

from PIL import Image


def save_image(data_stream, dirname):
    if not os.path.exists(dirname):
        os.makedirs(dirname)
        with open(os.path.join(dirname, '.meta.json'), 'w') as f:
            json.dump({
                'display_name': dirname,
                'avatar_url': 'noavatar.png'
            }, f)
    fn = datetime.now().strftime('%Y-%m-%d_%H-%M-%S.png')
    filename = os.path.join(dirname, fn)
    with open(filename, 'bw') as f:
        f.write(data_stream.read())
    img = Image.open(data_stream)
    img.thumbnail((200, 200))
    img.save(filename + ".thumbnail.jpeg", "JPEG")


def list_images(dirname, date_from=None, date_to=None):
    entries = (os.path.join(dirname, fn) for fn in os.listdir(dirname))
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
    return images

def date_of_last_image(dirname):
    entries = (os.path.join(dirname, fn) for fn in os.listdir(dirname))
    entries = ((os.stat(path), path) for path in entries)
    # leave only regular files, insert creation date
    entries = ((stat[ST_CTIME], os.path.basename(path))
           for stat, path in entries if S_ISREG(stat[ST_MODE]))

    entries = (((ctime, path) for ctime, path in entries if path.endswith('.png')))
    entries = sorted(entries)
    if entries:
        return entries[-1][0]  # ctime of last item
    return None

def list_last_uploads(dirname):
    result = []
    date_now = datetime.now()
    for name in os.listdir(dirname):
        path = os.path.join(dirname, name)
        metadata_file = os.path.join(path, '.meta.json')
        if os.path.isdir(path) and os.path.isfile(metadata_file):
            with open(metadata_file) as f:
                item = json.load(f)
                item['name'] = name
            item['last_upload'] = date_of_last_image(path)
            item['last_upload_date'] = datetime.fromtimestamp(item['last_upload'])
            item['marked'] = date_now - item['last_upload_date'] >= timedelta(days=7)
            result.append(item)
    result.sort(key=lambda item: item['last_upload'])
    return result
