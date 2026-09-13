"""Local-only media helpers. Copied into each skill for independent distribution."""
import argparse
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time

class Failure(Exception):
    pass

class Budget:
    def __init__(self, seconds):
        if not isinstance(seconds, (int, float)) or isinstance(seconds, bool) or not math.isfinite(seconds) or not 1 <= seconds <= 3600:
            raise Failure("timeout_seconds must be between 1 and 3600")
        self.deadline = time.monotonic() + seconds
    def remaining(self):
        left = self.deadline - time.monotonic()
        if left <= 0:
            raise Failure("total timeout exceeded")
        return left

def run(argv, budget, capture=False):
    if not shutil.which(argv[0]):
        raise Failure("missing dependency: " + argv[0])
    with tempfile.TemporaryFile() as err, tempfile.TemporaryFile() as out:
        try:
            result = subprocess.run(argv, stdin=subprocess.DEVNULL, stdout=out if capture else subprocess.DEVNULL,
                                    stderr=err, timeout=budget.remaining(), check=False)
        except subprocess.TimeoutExpired:
            raise Failure("total timeout exceeded")
        if result.returncode:
            err.seek(0, 2)
            length = err.tell()
            err.seek(max(0, length - 2400))
            raise Failure(argv[0] + ": " + err.read().decode('utf-8', 'replace'))
        if capture:
            if out.tell() > 1000000:
                raise Failure("subprocess response too large")
            out.seek(0)
            return out.read().decode('utf-8', 'replace')

def source(value):
    if not isinstance(value, str) or not value:
        raise Failure("input must be a local file path")
    path = Path(value).expanduser().resolve(strict=True)
    if not path.is_file():
        raise Failure("input is not a regular file")
    return path

def destination(value, inputs):
    if not isinstance(value, str) or not value:
        raise Failure("output must be a local path")
    raw = Path(value).expanduser()
    if raw.exists() or raw.is_symlink():
        raise Failure("output already exists; overwrite and hardlinks are refused")
    parent = raw.parent.resolve(strict=True)
    path = parent / raw.name
    if path in inputs:
        raise Failure("input and output must differ")
    return path

def temporary(dest):
    fd, value = tempfile.mkstemp(prefix='.' + dest.stem + '-', suffix=dest.suffix, dir=dest.parent)
    os.close(fd)
    return Path(value)

def publish(temp, dest):
    # link is an atomic no-clobber publication on the same filesystem.
    os.link(temp, dest)
    temp.unlink()

def probe(path, budget):
    value = run(['ffprobe', '-v', 'error', '-protocol_whitelist', 'file,pipe', '-show_entries',
        'format=duration,size,format_name:stream=index,codec_name,codec_type,width,height,sample_aspect_ratio,display_aspect_ratio,sample_rate,channels,duration,avg_frame_rate:stream_tags=rotate:stream_side_data=rotation:stream_disposition=attached_pic',
        '-of', 'json', str(path)], budget, True)
    info = json.loads(value)
    streams = info.get('streams', [])
    if not streams:
        raise Failure("no readable audio/video streams")
    info['streams'] = streams[:16]
    return info

def duration(info):
    value = float(info.get('format', {}).get('duration', 0))
    if not math.isfinite(value) or value <= 0:
        raise Failure("a positive finite duration is required")
    return value

def stream(info, kind):
    return next((s for s in info['streams'] if s['codec_type'] == kind and not (kind == 'video' and s.get('disposition', {}).get('attached_pic'))), None)

def encoder(name, budget):
    text = run(['ffmpeg', '-hide_banner', '-encoders'], budget, True)
    if not any(len(line.split()) > 1 and line.split()[1] == name for line in text.splitlines()):
        raise Failure('encoder unavailable: ' + name)

def audio_codec(dest, budget):
    choices = {'.m4a': ('aac', 'aac'), '.mp3': ('libmp3lame', 'mp3'), '.wav': ('pcm_s16le', 'pcm_s16le')}
    if dest.suffix.lower() not in choices:
        raise Failure('audio output must be .m4a, .mp3 or .wav')
    enc, codec = choices[dest.suffix.lower()]
    encoder(enc, budget)
    return enc, codec

def ffmpeg_start(src):
    return ['ffmpeg', '-hide_banner', '-loglevel', 'error', '-nostdin', '-y', '-protocol_whitelist', 'file,pipe', '-i', str(src)]

def positive(value, name, maximum=None):
    if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value) or value <= 0 or maximum is not None and value > maximum:
        raise Failure(name + ' must be a positive finite number' + (f' <= {maximum}' if maximum else ''))
    return value

def integer(value, name, low, high):
    if not isinstance(value, int) or isinstance(value, bool) or not low <= value <= high:
        raise Failure(f'{name} must be an integer between {low} and {high}')
    return value

def ensure_keys(spec, keys):
    if not isinstance(spec, dict):
        raise Failure('spec must be a JSON object')
    extra = set(spec) - set(keys)
    if extra:
        raise Failure('unknown fields: ' + ', '.join(sorted(extra)))

def image_open(path):
    from PIL import Image, ImageOps
    with Image.open(path) as img:
        if getattr(img, 'n_frames', 1) != 1:
            raise Failure('animated/multipage images are unsupported')
        img.load()
        return ImageOps.exif_transpose(img).copy()

def image_format(dest):
    choices = {'.jpg': 'JPEG', '.jpeg': 'JPEG', '.png': 'PNG', '.webp': 'WEBP'}
    if dest.suffix.lower() not in choices:
        raise Failure('image output must be .jpg, .jpeg, .png or .webp')
    return choices[dest.suffix.lower()]

def save_image(img, path, fmt, quality=82, background=None):
    from PIL import Image, ImageColor
    icc_profile = img.info.get('icc_profile')
    alpha = 'A' in img.getbands() or 'transparency' in img.info
    if fmt == 'JPEG':
        if alpha:
            if not background:
                raise Failure('JPEG with transparency requires explicit background, e.g. #ffffff')
            rgba = img.convert('RGBA')
            color = ImageColor.getrgb(background)
            if len(color) != 3:
                raise Failure('background must be opaque RGB')
            composed = Image.new('RGB', rgba.size, color)
            composed.paste(rgba, mask=rgba.getchannel('A'))
            img = composed
        else:
            img = img.convert('RGB')
    elif fmt == 'PNG' and img.mode not in ('1', 'L', 'LA', 'P', 'RGB', 'RGBA', 'I', 'I;16'):
        img = img.convert('RGBA' if alpha else 'RGB')
    kwargs = {'format': fmt}
    if fmt == 'PNG':
        kwargs.update(optimize=True, compress_level=9)
    else:
        kwargs.update(quality=quality)
        if fmt == 'JPEG':
            kwargs['optimize'] = True
    # Preserve ICC profile; EXIF is intentionally removed after orientation normalization.
    if icc_profile:
        kwargs['icc_profile'] = icc_profile
    img.save(path, **kwargs)
    with Image.open(path) as actual:
        actual.load()
        if actual.format != fmt or actual.size != img.size:
            raise Failure('image validation failed')
        return {'format': actual.format, 'width': actual.width, 'height': actual.height,
                'has_alpha': 'A' in actual.getbands() or 'transparency' in actual.info}

def decode_check(path, budget):
    run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-xerror', '-nostdin', '-protocol_whitelist', 'file,pipe',
         '-i', str(path), '-map', '0:v:0?', '-map', '0:a:0?', '-f', 'null', '-'], budget)

def verify_media(path, budget, expected_duration, expected_video=None, expected_audio=None):
    info = probe(path, budget)
    actual = duration(info)
    tolerance = max(.35, expected_duration * .03)
    if abs(actual - expected_duration) > tolerance:
        raise Failure(f'duration validation failed: expected {expected_duration}, got {actual}')
    for kind, expected in [('video', expected_video), ('audio', expected_audio)]:
        s = stream(info, kind)
        if expected and (not s or s['codec_name'] != expected):
            raise Failure(kind + ' codec validation failed')
    decode_check(path, budget)
    return info

def entry(function):
    parser = argparse.ArgumentParser(description='Local media helper; see references/contrato.md')
    parser.add_argument('--spec', required=True, help='Path to a JSON object')
    args = parser.parse_args()
    try:
        specpath = Path(args.spec)
        if specpath.stat().st_size > 1000000:
            raise Failure('spec exceeds 1 MB')
        spec = json.loads(specpath.read_text())
        result = function(spec)
        print(json.dumps(result, ensure_ascii=False, allow_nan=False))
        return 0 if result.get('status') in ('ok', 'partial') and result.get('ok', True) else 2
    except Exception as exc:
        # The CLI boundary also normalizes codec/Pillow-specific exceptions.
        print(json.dumps({'ok': False, 'status': 'error', 'error': str(exc)[:2400]}, ensure_ascii=False))
        return 2

def letterbox_filter(width, height):
    # `dar` includes non-square pixels (and autorotation's SAR changes).
    return (f"scale=w='max(2,trunc(min({width},{height}*dar)/2)*2)':"
            f"h='max(2,trunc(min({height},{width}/dar)/2)*2)',setsar=1,"
            f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2")

def stream_duration(info, kind):
    selected = stream(info, kind)
    try:
        value = float((selected or {}).get('duration', 0))
        if math.isfinite(value) and value > 0:
            return value
    except (TypeError, ValueError):
        pass
    return duration(info)

def extra_encoding_options(spec, has_audio, has_video):
    options = []
    if 'fps' in spec:
        if not has_video:
            raise Failure('fps requires video output')
        options += ['-r', str(positive(spec['fps'], 'fps', 120))]
    if 'audio_channels' in spec:
        if not has_audio:
            raise Failure('audio_channels requires an audio stream')
        options += ['-ac', str(integer(spec['audio_channels'], 'audio_channels', 1, 2))]
    if 'sample_rate_hz' in spec:
        if not has_audio:
            raise Failure('sample_rate_hz requires an audio stream')
        rate = integer(spec['sample_rate_hz'], 'sample_rate_hz', 8000, 192000)
        options += ['-ar', str(rate)]
    return options

def verify_requested_options(info, spec):
    audio = stream(info, 'audio')
    video = stream(info, 'video')
    if 'audio_channels' in spec and (not audio or audio.get('channels') != spec['audio_channels']):
        raise Failure('audio channel validation failed')
    if 'sample_rate_hz' in spec and (not audio or int(audio.get('sample_rate', 0)) != spec['sample_rate_hz']):
        raise Failure('audio sample rate validation failed')
    if 'fps' in spec:
        from fractions import Fraction
        if not video or abs(float(Fraction(video.get('avg_frame_rate', '0'))) - spec['fps']) > .01:
            raise Failure('video frame rate validation failed')
