SCRIPT_NAME = 'media.py'
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts' / SCRIPT_NAME

class Checks(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
    def call(self, spec, env=None):
        path = self.root / 'spec.json'
        path.write_text(json.dumps(spec))
        proc = subprocess.run([sys.executable, str(SCRIPT), '--spec', str(path)], capture_output=True, text=True, env=env, timeout=30)
        self.assertIn(proc.returncode, (0, 2), proc.stderr)
        result = json.loads(proc.stdout)
        self.assertEqual(proc.returncode == 0, result['ok'], result)
        return result
    def ffmpeg(self, *args):
        subprocess.run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y', *args], check=True, timeout=20)
    def audio(self):
        src = self.root / 'source.wav'
        self.ffmpeg('-f', 'lavfi', '-i', 'sine=frequency=440:sample_rate=44100', '-t', '2', str(src))
        return src
    def video(self, audio=False):
        src = self.root / 'source.mp4'
        args = ['-f', 'lavfi', '-i', 'testsrc2=size=128x96:rate=12']
        if audio:
            args += ['-f', 'lavfi', '-i', 'sine=frequency=440:sample_rate=44100']
        self.ffmpeg(*args, '-t', '2', '-c:v', 'libx264', '-crf', '0', '-pix_fmt', 'yuv420p', *(['-c:a', 'aac'] if audio else ['-an']), str(src))
        return src
    def assert_original(self, path, digest):
        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), digest)
    def digest(self, path):
        return hashlib.sha256(path.read_bytes()).hexdigest()
    def assert_no_temps(self):
        self.assertEqual([p.name for p in self.root.iterdir() if p.name.startswith('.')], [])

    def test_probe_trim_and_original(self):
        src = self.video()
        digest = self.digest(src)
        info = self.call({'operation':'probe','input':str(src)})
        self.assertEqual(info['probe']['streams'][0]['codec_name'],'h264')
        dst = self.root/'trim.mp4'
        result = self.call({'operation':'trim','input':str(src),'output':str(dst),'start_seconds':.5,'duration_seconds':1})
        self.assertTrue(result['ok'],result)
        self.assertAlmostEqual(float(result['probe']['format']['duration']),1,delta=.2)
        self.assertFalse(any(s['codec_type']=='audio' for s in result['probe']['streams']))
        self.assert_original(src,digest)
    def test_audio_extraction_and_conversion(self):
        src = self.video(True)
        mp3 = self.root/'audio.mp3'
        result = self.call({'operation':'extract-audio','input':str(src),'output':str(mp3)})
        self.assertTrue(result['ok'],result)
        self.assertEqual(result['probe']['streams'][0]['codec_name'],'mp3')
        result = self.call({'operation':'convert','input':str(mp3),'output':str(self.root/'audio.m4a')})
        self.assertTrue(result['ok'],result)

    def test_audio_cover_art_is_not_treated_as_video(self):
        from PIL import Image
        src = self.audio()
        cover = self.root / 'cover.jpg'
        Image.new('RGB', (64,64), 'red').save(cover)
        tagged = self.root / 'with-cover.mp3'
        self.ffmpeg('-i',str(src),'-i',str(cover),'-map','0:a:0','-map','1:v:0',
                    '-c:a','libmp3lame','-c:v','copy','-disposition:v:0','attached_pic',str(tagged))
        before = self.digest(tagged)
        result = self.call({'operation':'convert','input':str(tagged),'output':str(self.root/'converted.m4a')})
        self.assertTrue(result['ok'], result)
        self.assertFalse(any(s['codec_type']=='video' for s in result['probe']['streams']))
        self.assert_original(tagged,before)
    def test_no_audio_existing_and_invalid_trim(self):
        src = self.video()
        self.assertFalse(self.call({'operation':'extract-audio','input':str(src),'output':str(self.root/'audio.mp3')})['ok'])
        self.assertFalse(self.call({'operation':'convert','input':str(src),'output':str(src)})['ok'])
        self.assertFalse(self.call({'operation':'trim','input':str(src),'output':str(self.root/'long.mp4'),'duration_seconds':20})['ok'])
        self.assert_no_temps()
    def test_corrupt_and_timeout(self):
        import shutil
        corrupt = self.root/'bad.mp4'
        corrupt.write_bytes(b'bad')
        self.assertFalse(self.call({'operation':'probe','input':str(corrupt)})['ok'])
        src = self.video()
        fake = self.root/'bin'
        fake.mkdir()
        script = fake/'ffmpeg'
        script.write_text('#!/usr/bin/python3\nimport time\ntime.sleep(10)\n')
        script.chmod(0o755)
        env = dict(os.environ, PATH=str(fake)+os.pathsep+os.environ['PATH'])
        result = self.call({'operation':'convert','input':str(src),'output':str(self.root/'timeout.mp4'),'timeout_seconds':1},env)
        self.assertFalse(result['ok'])
        self.assertIn('timeout',result['error'])
        self.assertFalse((self.root/'timeout.mp4').exists())
        self.assert_no_temps()

    def test_rotation_and_anamorphic_letterbox(self):
        from PIL import Image
        src = self.root/'sar.mp4'
        rotated = self.root/'rotated.mp4'
        dst = self.root/'square.mp4'
        self.ffmpeg('-f','lavfi','-i','color=white:size=160x120:rate=10','-vf','setsar=2','-t','1','-c:v','libx264',str(src))
        self.ffmpeg('-display_rotation','90','-i',str(src),'-c','copy',str(rotated))
        result = self.call({'operation':'convert','input':str(rotated),'output':str(dst),'width':200,'height':200})
        self.assertTrue(result['ok'],result)
        vs = result['probe']['streams'][0]
        self.assertEqual((vs['width'],vs['height'],vs['sample_aspect_ratio']),(200,200,'1:1'))
        self.assertFalse(any(s.get('rotation',0) for s in vs.get('side_data_list',[])))
        frame = self.root/'frame.png'
        self.ffmpeg('-i',str(dst),'-frames:v','1',str(frame))
        with Image.open(frame) as image:
            box = image.convert('L').point(lambda x: 255 if x > 220 else 0).getbbox()
        self.assertEqual(box[3]-box[1],200)
        self.assertAlmostEqual((box[2]-box[0])/200, .375, delta=.02)

if __name__ == '__main__':
    unittest.main()
