#!/usr/bin/env python3
from media_common import *

def main(spec):
    ensure_keys(spec, ['operation', 'input', 'output', 'start_seconds', 'duration_seconds', 'timeout_seconds',
                       'crf', 'audio_bitrate_kbps', 'width', 'height', 'fps', 'audio_channels', 'sample_rate_hz'])
    op = spec.get('operation')
    if op not in ('probe', 'trim', 'extract-audio', 'convert'):
        raise Failure('operation must be probe, trim, extract-audio or convert')
    budget = Budget(spec.get('timeout_seconds', 120))
    src = source(spec['input'])
    info = probe(src, budget)
    if op == 'probe':
        if set(spec) - {'operation', 'input', 'timeout_seconds'}:
            raise Failure('probe accepts input and timeout_seconds only')
        return {'ok': True, 'status': 'ok', 'input': str(src), 'bytes': src.stat().st_size, 'probe': info}
    dst = destination(spec['output'], [src])
    input_duration = duration(info)
    expected = input_duration
    start = 0
    if op == 'trim':
        start = spec.get('start_seconds', 0)
        if not isinstance(start, (float, int)) or isinstance(start, bool) or not math.isfinite(start) or not 0 <= start < input_duration:
            raise Failure('start_seconds is outside media duration')
        expected = positive(spec.get('duration_seconds'), 'duration_seconds')
        if start + expected > input_duration + .01:
            raise Failure('trim extends past media end')
    elif 'start_seconds' in spec or 'duration_seconds' in spec:
        raise Failure('start_seconds/duration_seconds are valid only for trim')
    video = stream(info, 'video')
    audio = stream(info, 'audio')
    video_output = video is not None and op != 'extract-audio'
    if op == 'extract-audio' and not audio:
        raise Failure('input has no audio stream')
    if op == 'extract-audio':
        expected = stream_duration(info, 'audio')
    cmd = ffmpeg_start(src)
    if op == 'trim':
        cmd += ['-ss', str(start), '-t', str(expected)]
    expected_audio = expected_video = None
    decisions = ['Only first video/audio streams are selected; subtitles, attachments and metadata are excluded.']
    bitrate = integer(spec.get('audio_bitrate_kbps', 128), 'audio_bitrate_kbps', 8, 320)
    if video_output:
        if dst.suffix.lower() != '.mp4':
            raise Failure('video output must be .mp4 (H.264/AAC)')
        encoder('libx264', budget)
        crf = integer(spec.get('crf', 23), 'crf', 0, 51)
        cmd += ['-map', '0:v:0', '-c:v', 'libx264', '-preset', 'fast', '-crf', str(crf), '-pix_fmt', 'yuv420p']
        expected_video = 'h264'
        filters = []
        if 'width' in spec or 'height' in spec:
            w = integer(spec.get('width'), 'width', 2, 8192)
            h = integer(spec.get('height'), 'height', 2, 8192)
            if w % 2 or h % 2:
                raise Failure('H.264 width/height must be even')
            filters += [letterbox_filter(w, h)]
            decisions += ['Requested bounding dimensions use letterboxing with square pixels.']
        else:
            filters += ['pad=ceil(iw/2)*2:ceil(ih/2)*2']
            decisions += ['Rotation is rendered by FFmpeg autorotate; SAR preserved; odd dimensions padded at most 1 pixel.']
        cmd += ['-vf', ','.join(filters)]
        if audio:
            encoder('aac', budget)
            cmd += ['-map', '0:a:0', '-c:a', 'aac', '-b:a', str(bitrate) + 'k']
            expected_audio = 'aac'
        else:
            cmd += ['-an']
        cmd += ['-movflags', '+faststart']
    else:
        if any(k in spec for k in ['crf', 'width', 'height', 'fps']):
            raise Failure('video options cannot be used for audio output')
        if not audio:
            raise Failure('input has no audio stream')
        enc, expected_audio = audio_codec(dst, budget)
        cmd += ['-map', '0:a:0', '-vn', '-c:a', enc]
        if enc != 'pcm_s16le':
            cmd += ['-b:a', str(bitrate) + 'k']
    cmd += extra_encoding_options(spec, audio is not None, video_output)
    tmp = temporary(dst)
    try:
        cmd += ['-map_metadata', '-1', '-map_chapters', '-1', str(tmp)]
        run(cmd, budget)
        result = verify_media(tmp, budget, expected, expected_video, expected_audio)
        verify_requested_options(result, spec)
        publish(tmp, dst)
        return {'ok': True, 'status': 'ok', 'input': str(src), 'output': str(dst),
                'bytes_before': src.stat().st_size, 'bytes_after': dst.stat().st_size,
                'probe': result, 'decisions': decisions}
    finally:
        tmp.unlink(missing_ok=True)

if __name__ == '__main__':
    raise SystemExit(entry(main))
