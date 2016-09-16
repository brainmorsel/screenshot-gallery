import os
import json
import logging
from datetime import datetime, timedelta
from stat import S_ISREG, ST_CTIME, ST_MODE

from PIL import Image


def save_image(data_stream, path, name):
    logger = logging.getLogger(__name__)
    if name:
        name = '_' + name
    fn = datetime.now().strftime('%Y-%m-%d_%H-%M-%S{0}.png'.format(name))
    filename = os.path.join(path, fn)
    try:
        if not os.path.exists(path):
            os.makedirs(path)
        with open(filename, 'bw') as f:
            f.write(data_stream.read())
        img = Image.open(data_stream)
        img.thumbnail((200, 200))
        img.save(filename + ".thumbnail.jpeg", "JPEG")
    except Exception:
        logger.exception('failed to save file "%s"', filename)


def list_images(dirname, url_prefix):
    if not os.path.isdir(dirname):
        return []

    entries = (os.path.join(dirname, fn) for fn in os.listdir(dirname))
    entries = ((os.stat(path), path) for path in entries)
    # leave only regular files, insert creation date
    entries = ((stat[ST_CTIME], os.path.basename(path))
           for stat, path in entries if S_ISREG(stat[ST_MODE]))

    entries = (((ctime, path) for ctime, path in entries if path.endswith('.png')))

    entries = sorted(entries)
    images = []
    for ts, fn in entries:
        filename = os.path.join(url_prefix, fn)
        images.append({'filename': filename, 'timestamp': ts})
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
        pathname = os.path.join(dirname, name)
        if os.path.isdir(pathname):
            item = {
                'name': name,
                'last_upload': 0,
                'last_upload_date': '',
                'marked': True,
            }
            date_dirs = sorted(os.listdir(pathname))
            if date_dirs:
                last_upload_date = date_dirs[-1]
                last_upload = datetime.strptime(last_upload_date, '%Y-%m-%d')
                item['last_upload'] = last_upload.timestamp()
                item['last_upload_date'] = last_upload
                item['marked'] = date_now - last_upload >= timedelta(days=7)
            result.append(item)
    result.sort(key=lambda item: item['last_upload'])
    return result
