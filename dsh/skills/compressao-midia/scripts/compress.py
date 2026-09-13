#!/usr/bin/env python3
import sys
from media_common import *

def main(spec):
    ensure_keys(spec, ['kind', 'input', 'output', 'quality', 'target_bytes', 'target_mb', 'max_attempts',
                       'timeout_seconds', 'background', 'width', 'height', 'audio_bitrate_kbps', 'fps', 'audio_channels', 'sample_rate_hz'])
    kind = spec.get('kind')
    if kind not in ('image', 'audio', 'video'):
        raise Failure('kind must be image, audio or video')
    budget = Budget(spec.get('timeout_seconds', 180))
    src = source(spec['input'])
    dst = destination(spec['output'], [src])
    before = src.stat().st_size
    if before == 0:
        raise Failure('input is empty')
    attempts = integer(spec.get('max_attempts', 3), 'max_attempts', 1, 6)
    quality = integer(spec.get('quality', 82), 'quality', 1, 100)
    if 'target_bytes' in spec and 'target_mb' in spec:
        raise Failure('use target_bytes OR target_mb')
    target = None
    if 'target_bytes' in spec:
        target = integer(spec['target_bytes'], 'target_bytes', 1, 10**12)
    if 'target_mb' in spec:
        target = int(positive(spec['target_mb'], 'target_mb', 10**6) * 1000000)
        if target < 1:
            raise Failure('target_mb rounds below one byte')
    if 'width' in spec or 'height' in spec:
        integer(spec.get('width'), 'width', 1, 8192)
        integer(spec.get('height'), 'height', 1, 8192)
    if kind != 'image' and 'background' in spec:
        raise Failure('background is an image option')
    if kind == 'audio' and ('width' in spec or 'height' in spec):
        raise Failure('width/height are not audio options')
    if kind == 'image' and any(k in spec for k in ('audio_bitrate_kbps', 'audio_channels', 'sample_rate_hz', 'fps')):
        raise Failure('audio_bitrate_kbps is not an image option')
    if target is None:
        attempts = 1
    decisions = []
    info = None
    expected_video = expected_audio = None
    if kind == 'image':
        fmt = image_format(dst)
        if fmt == 'PNG':
            attempts = 1
            decisions.append('PNG is lossless; pixel dimensions are only reduced when width/height are specified.')
        decisions.append('EXIF orientation normalized; EXIF removed; ICC retained when available.')
    else:
        info = probe(src, budget)
        media_duration = stream_duration(info, 'audio') if kind == 'audio' else duration(info)
        video, audio = stream(info, 'video'), stream(info, 'audio')
        if kind == 'video':
            if not video:
                raise Failure('input has no video stream')
            if dst.suffix.lower() != '.mp4':
                raise Failure('video compression output must be .mp4')
            encoder('libx264', budget)
            expected_video = 'h264'
            if 'width' in spec and (spec['width'] % 2 or spec['height'] % 2):
                raise Failure('video width and height must be even')
            if audio:
                encoder('aac', budget)
                expected_audio = 'aac'
            if 'width' in spec:
                decisions.append('Explicit dimensions use letterboxing and square pixels.')
            else:
                decisions.append('Rotation rendered by FFmpeg autorotate; SAR retained; odd dimensions padded at most 1 pixel.')
        else:
            if not audio:
                raise Failure('input has no audio stream')
            enc, expected_audio = audio_codec(dst, budget)
            if enc == 'pcm_s16le':
                raise Failure('compressed audio output must be .m4a or .mp3')
        encoding_extra = extra_encoding_options(spec, audio is not None, kind == 'video')
        decisions.append('First video/audio streams only; metadata, chapters, subtitles and attachments excluded.')
        audio_rate = integer(spec.get('audio_bitrate_kbps', 128 if 'quality' not in spec else max(32, round(32 + quality * 2.24))),
                             'audio_bitrate_kbps', 8, 320)
        rate = None
        if target:
            total_rate = int(target * 8 * .92 / media_duration)
            if kind == 'audio':
                rate = max(8000, min(audio_rate * 1000, total_rate))
            else:
                if audio and 'audio_bitrate_kbps' not in spec:
                    audio_rate = max(8, min(audio_rate, int(total_rate * .2 / 1000)))
                rate = max(8000, total_rate - (audio_rate * 1000 if audio else 0))
    best = None
    best_bytes = None
    best_info = None
    history = []
    temps = []
    try:
        for attempt in range(attempts):
            budget.remaining()
            tmp = temporary(dst)
            temps.append(tmp)
            if kind == 'image':
                q = quality if attempts == 1 else max(1, round(quality - attempt * (quality - 5) / (attempts - 1)))
                task = {'input': str(src), 'output': str(tmp), 'format': fmt, 'quality': q,
                        'background': spec.get('background'), 'width': spec.get('width'), 'height': spec.get('height')}
                actual = json.loads(run([sys.executable, str(Path(__file__).with_name('image_attempt.py')), json.dumps(task)], budget, True))
                parameters = {'quality': q, 'format': fmt}
            else:
                cmd = ffmpeg_start(src)
                if kind == 'video':
                    cmd += ['-map', '0:v:0', '-c:v', 'libx264', '-preset', 'fast', '-pix_fmt', 'yuv420p']
                    if rate:
                        cmd += ['-b:v', str(rate), '-maxrate', str(rate), '-bufsize', str(rate * 2)]
                        parameters = {'video_bitrate_bps': rate, 'audio_bitrate_kbps': audio_rate if audio else None}
                    else:
                        crf = round(40 - quality * .22)
                        cmd += ['-crf', str(crf)]
                        parameters = {'crf': crf, 'audio_bitrate_kbps': audio_rate if audio else None}
                    if 'width' in spec:
                        w, h = spec['width'], spec['height']
                        vf = letterbox_filter(w, h)
                    else:
                        vf = 'pad=ceil(iw/2)*2:ceil(ih/2)*2'
                    cmd += ['-vf', vf]
                    if audio:
                        cmd += ['-map', '0:a:0', '-c:a', 'aac', '-b:a', str(audio_rate) + 'k']
                    else:
                        cmd += ['-an']
                    cmd += ['-movflags', '+faststart']
                else:
                    cmd += ['-map', '0:a:0', '-vn', '-c:a', enc, '-b:a', str(rate or audio_rate * 1000)]
                    parameters = {'audio_bitrate_bps': rate or audio_rate * 1000}
                cmd += encoding_extra
                cmd += ['-map_metadata', '-1', '-map_chapters', '-1', str(tmp)]
                run(cmd, budget)
                actual = verify_media(tmp, budget, media_duration, expected_video, expected_audio)
                verify_requested_options(actual, spec)
            size = tmp.stat().st_size
            history.append({'attempt': attempt + 1, 'bytes': size, **parameters})
            if best_bytes is None or size < best_bytes:
                if best:
                    best.unlink(missing_ok=True)
                best, best_bytes, best_info = tmp, size, actual
            else:
                tmp.unlink(missing_ok=True)
            if target is None or size <= target:
                break
            if kind != 'image':
                adjusted = max(8000, int(rate * target / size * .85))
                if adjusted >= rate:
                    break
                rate = adjusted
        target_met = target is None or best_bytes <= target
        smaller = best_bytes < before
        status = 'target_unmet' if not target_met else ('ok' if smaller else 'not_smaller')
        output = None
        if smaller:
            budget.remaining()
            publish(best, dst)
            output = str(dst)
        return {'ok': status == 'ok', 'status': status, 'input': str(src), 'output': output,
                'bytes_before': before, 'bytes_after': best_bytes, 'reduction_percent': round((before - best_bytes) * 100 / before, 2),
                'target_bytes': target, 'target_met': target_met if target else None,
                'attempts': history, 'validation': best_info, 'decisions': decisions}
    finally:
        for tmp in temps:
            tmp.unlink(missing_ok=True)

if __name__ == '__main__':
    raise SystemExit(entry(main))
