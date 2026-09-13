#!/usr/bin/env python3
"""Bounded by the parent subprocess; writes only the temporary candidate."""
import json
import sys
from media_common import *
spec = json.loads(sys.argv[1])
img = image_open(Path(spec['input']))
if spec.get('width'):
    from PIL import Image
    img.thumbnail((spec['width'], spec['height']), Image.Resampling.LANCZOS)
info = save_image(img, Path(spec['output']), spec['format'], spec['quality'], spec.get('background'))
print(json.dumps(info))
