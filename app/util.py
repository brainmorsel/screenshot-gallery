import os
import json
import logging
from datetime import datetime, timedelta
from stat import S_ISREG, ST_CTIME, ST_MODE

from PIL import Image


def save_image(data_stream, path):
    logger = logging.getLogger(__name__)
    fn = datetime.now().strftime('%Y-%m-%d_%H-%M-%S.png')
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
