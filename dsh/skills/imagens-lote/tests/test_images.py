SCRIPT_NAME = 'images.py'
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

    def image(self):
        from PIL import Image
        src = self.root / 'source.png'
        img = Image.new('RGBA', (160, 80), (255, 0, 0, 128))
        img.save(src)
        return src
    def test_thumbnail_transparency_dimensions_original(self):
        src = self.image()
        digest = self.digest(src)
        dst = self.root / 'small.webp'
        result = self.call({'operation':'thumbnail','width':40,'height':40,'items':[{'input':str(src),'output':str(dst)}]})
        self.assertTrue(result['ok'], result)
        self.assertEqual((result['results'][0]['width'],result['results'][0]['height']), (40,20))
        self.assertTrue(result['results'][0]['has_alpha'])
        self.assert_original(src, digest)
    def test_jpeg_requires_background(self):
        src = self.image()
        dst = self.root / 'out.jpg'
        spec = {'operation':'convert','items':[{'input':str(src),'output':str(dst)}]}
        self.assertFalse(self.call(spec)['ok'])
        self.assertFalse(dst.exists())
        self.assert_no_temps()
        spec['background'] = '#ffffff'
        self.assertTrue(self.call(spec)['ok'])
    def test_resize_and_crop(self):
        src = self.image()
        resize = self.call({'operation':'resize','width':20,'height':30,'items':[{'input':str(src),'output':str(self.root/'r.png')}]})
        self.assertEqual((resize['results'][0]['width'],resize['results'][0]['height']), (20,30))
        crop = self.call({'operation':'crop','box':[10,10,40,30],'items':[{'input':str(src),'output':str(self.root/'c.png')}]})
        self.assertEqual((crop['results'][0]['width'],crop['results'][0]['height']), (30,20))
    def test_collision_hardlink_and_corrupt_batch(self):
        src = self.image()
        out = self.root / 'copy.png'
        os.link(src,out)
        result = self.call({'operation':'convert','items':[{'input':str(src),'output':str(out)}]})
        self.assertFalse(result['ok'])
        corrupt = self.root / 'bad.png'
        corrupt.write_bytes(b'invalid')
        fresh = self.root / 'fresh.png'
        result = self.call({'operation':'convert','items':[{'input':str(src),'output':str(fresh)},{'input':str(corrupt),'output':str(self.root/'badout.png')}]})
        self.assertFalse(result['ok'])
        self.assertFalse(fresh.exists())
        self.assert_no_temps()

if __name__ == '__main__':
    unittest.main()
