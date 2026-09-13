#!/usr/bin/env python3
from pathlib import Path
from media_common import *

def main(spec):
    ensure_keys(spec, ['items', 'operation', 'width', 'height', 'box', 'quality', 'background'])
    items = spec.get('items')
    if not isinstance(items, list) or not 1 <= len(items) <= 100:
        raise Failure('items must contain between 1 and 100 input/output pairs')
    op = spec.get('operation')
    if op not in ('resize', 'crop', 'convert', 'thumbnail'):
        raise Failure('operation must be resize, crop, convert or thumbnail')
    quality = integer(spec.get('quality', 82), 'quality', 1, 100)
    if op in ('resize', 'thumbnail'):
        width = integer(spec.get('width'), 'width', 1, 16384)
        height = integer(spec.get('height'), 'height', 1, 16384)
    elif 'width' in spec or 'height' in spec:
        raise Failure('width/height are valid only for resize/thumbnail')
    if op == 'crop':
        box = spec.get('box')
        if not isinstance(box, list) or len(box) != 4:
            raise Failure('box requires [left, top, right, bottom]')
        for x in box:
            integer(x, 'box coordinate', 0, 100000)
        if box[2] <= box[0] or box[3] <= box[1]:
            raise Failure('crop box is empty or inverted')
    elif 'box' in spec:
        raise Failure('box is valid only for crop')
    # Preflight the whole batch before publishing any image.
    for item in items:
        ensure_keys(item, ['input', 'output'])
    inputs = [source(i['input']) for i in items]
    outputs = [destination(i['output'], inputs) for i in items]
    if len(set(outputs)) != len(outputs):
        raise Failure('duplicate output paths in batch')
    for dst in outputs:
        image_format(dst)
    staged = []
    results = []
    try:
        from PIL import Image
        for src, dst in zip(inputs, outputs):
            img = image_open(src)
            if op == 'resize':
                img = img.resize((width, height), Image.Resampling.LANCZOS)
            elif op == 'thumbnail':
                img.thumbnail((width, height), Image.Resampling.LANCZOS)
            elif op == 'crop':
                if box[2] > img.width or box[3] > img.height:
                    raise Failure('crop is outside oriented image dimensions')
                img = img.crop(tuple(box))
            tmp = temporary(dst)
            staged.append((tmp, dst))
            info = save_image(img, tmp, image_format(dst), quality, spec.get('background'))
            results.append({'input': str(src), 'output': str(dst), 'bytes_before': src.stat().st_size,
                            'bytes_after': tmp.stat().st_size, **info})
        published = []
        try:
            for tmp, dst in staged:
                publish(tmp, dst)
                published.append(str(dst))
        except OSError as exc:
            return {'ok': False, 'status': 'partial', 'error': str(exc), 'published': published}
        return {'ok': True, 'status': 'ok', 'count': len(results), 'results': results,
                'metadata': 'EXIF orientation normalized; EXIF removed; ICC retained when available'}
    finally:
        for tmp, _ in staged:
            tmp.unlink(missing_ok=True)

if __name__ == '__main__':
    raise SystemExit(entry(main))
