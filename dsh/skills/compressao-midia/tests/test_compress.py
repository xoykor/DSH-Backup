SCRIPT_NAME = 'compress.py'
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

    def image(self, simple=False):
        from PIL import Image
        src = self.root/'source.png'
        if simple:
            Image.new('RGB',(1,1),(0,0,0)).save(src,optimize=True)
        else:
            # Deterministic noise gives enough input entropy for lossy compression.
            import random
            rng = random.Random(7)
            Image.frombytes('RGB',(128,96),rng.randbytes(128*96*3)).save(src)
        return src
    def test_image_target_and_original(self):
        src = self.image()
        digest = self.digest(src)
        result = self.call({'kind':'image','input':str(src),'output':str(self.root/'compressed.webp'),'target_bytes':10000,'max_attempts':3})
        self.assertTrue(result['ok'],result)
        self.assertTrue(result['target_met'])
        self.assertLessEqual(Path(result['output']).stat().st_size,10000)
        self.assert_original(src,digest)
    def test_impossible_target_and_not_smaller(self):
        src = self.image()
        dst = self.root/'impossible.webp'
        result = self.call({'kind':'image','input':str(src),'output':str(dst),'target_bytes':1,'max_attempts':2})
        self.assertEqual(result['status'],'target_unmet',result)
        self.assertFalse(result['target_met'])
        self.assertLessEqual(len(result['attempts']),2)
        self.assertTrue(dst.exists())
        src.unlink()
        src = self.image(True)
        out = self.root/'larger.jpg'
        result = self.call({'kind':'image','input':str(src),'output':str(out)})
        self.assertEqual(result['status'],'not_smaller',result)
        self.assertIsNone(result['output'])
        self.assertFalse(out.exists())
    def test_audio_target(self):
        src = self.audio()
        result = self.call({'kind':'audio','input':str(src),'output':str(self.root/'compressed.mp3'),'target_bytes':26000,'max_attempts':3})
        self.assertTrue(result['ok'],result)
        self.assertLessEqual(Path(result['output']).stat().st_size,26000)
        self.assertEqual(result['validation']['streams'][0]['codec_name'],'mp3')

    def test_explicit_audio_channels_sample_rate_and_video_fps(self):
        src = self.audio()
        result = self.call({'kind':'audio','input':str(src),'output':str(self.root/'mono.mp3'),
                            'audio_channels':1,'sample_rate_hz':22050,'audio_bitrate_kbps':48})
        self.assertTrue(result['ok'],result)
        audio = next(s for s in result['validation']['streams'] if s['codec_type']=='audio')
        self.assertEqual(audio['channels'],1)
        self.assertEqual(audio['sample_rate'],'22050')
        video = self.video()
        result = self.call({'kind':'video','input':str(video),'output':str(self.root/'fps.mp4'),'fps':6})
        self.assertTrue(result['ok'],result)
        stream = next(s for s in result['validation']['streams'] if s['codec_type']=='video')
        self.assertEqual(stream['avg_frame_rate'],'6/1')
    def test_video_without_audio(self):
        src = self.video()
        result = self.call({'kind':'video','input':str(src),'output':str(self.root/'compressed.mp4'),'target_bytes':23000,'max_attempts':3})
        self.assertTrue(result['ok'],result)
        self.assertLessEqual(Path(result['output']).stat().st_size,23000)
        self.assertFalse(any(s['codec_type']=='audio' for s in result['validation']['streams']))
    def test_transparency_collision_corruption(self):
        from PIL import Image
        src = self.root/'alpha.png'
        Image.new('RGBA',(16,16),(0,0,0,0)).save(src)
        self.assertFalse(self.call({'kind':'image','input':str(src),'output':str(self.root/'alpha.jpg')})['ok'])
        self.assertFalse(self.call({'kind':'image','input':str(src),'output':str(src)})['ok'])
        bad = self.root/'bad.png'
        bad.write_bytes(b'bad')
        self.assertFalse(self.call({'kind':'image','input':str(bad),'output':str(self.root/'out.webp')})['ok'])
        self.assert_no_temps()
    def test_total_timeout(self):
        src = self.video()
        fake = self.root/'bin'
        fake.mkdir()
        script = fake/'ffmpeg'
        script.write_text('#!/usr/bin/python3\nimport time\ntime.sleep(10)\n')
        script.chmod(0o755)
        env = dict(os.environ,PATH=str(fake)+os.pathsep+os.environ['PATH'])
        result = self.call({'kind':'video','input':str(src),'output':str(self.root/'timeout.mp4'),'timeout_seconds':1},env)
        self.assertIn('timeout',result['error'])
        self.assertFalse((self.root/'timeout.mp4').exists())
        self.assert_no_temps()

if __name__ == '__main__':
    unittest.main()
