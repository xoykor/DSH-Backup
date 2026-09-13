import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/file_manifest.py"


class FilesTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / 'dest').mkdir()
        (self.root / 'a.txt').write_text('conteúdo á 123')
        (self.root / 'b.txt').write_text('conteúdo á 123')

    def tearDown(self): self.tmp.cleanup()

    def command(self, mode, spec, output):
        return subprocess.run([sys.executable, str(SCRIPT), mode, '--spec', str(spec), '--output', str(output)],
                              capture_output=True, text=True, timeout=5)

    def plan(self, operations):
        spec = self.root / 'spec.json'
        spec.write_text(json.dumps({'root': str(self.root), 'operations': operations}))
        plan = self.root / 'plan.json'
        result = self.command('plan', spec, plan)
        return result, plan

    def test_plan_copy_rename_duplicates_and_hash_verification(self):
        proc, plan = self.plan([{'op':'copy','source':'a.txt','destination':'dest/a.txt'},
                                {'op':'rename','source':'b.txt','destination':'dest/b.txt'}])
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertFalse((self.root/'dest/a.txt').exists())
        self.assertEqual(json.loads(plan.read_text())['duplicates_by_content'], [['a.txt','b.txt']])
        proc = self.command('apply',plan,self.root/'journal.jsonl')
        self.assertEqual(proc.returncode, 0, proc.stderr+proc.stdout)
        self.assertEqual((self.root/'dest/a.txt').read_bytes(),(self.root/'a.txt').read_bytes())
        self.assertEqual((self.root/'dest/b.txt').read_bytes(),(self.root/'a.txt').read_bytes())
        self.assertFalse((self.root/'b.txt').exists())
        events=[json.loads(l) for l in (self.root/'journal.jsonl').read_text().splitlines()]
        self.assertEqual(sum(e['event']=='completed' for e in events),2)

    def test_changed_source_prevents_all_operations(self):
        proc, plan = self.plan([{'op':'copy','source':'a.txt','destination':'dest/a.txt'}])
        self.assertEqual(proc.returncode,0,proc.stderr)
        (self.root/'a.txt').write_text('changed')
        proc = self.command('apply',plan,self.root/'journal.jsonl')
        self.assertEqual(proc.returncode,2)
        self.assertFalse((self.root/'dest/a.txt').exists())

    def test_collision_symlink_hardlink_and_escape_are_rejected(self):
        cases=[{'op':'copy','source':'a.txt','destination':'b.txt'},
               {'op':'copy','source':'a.txt','destination':'../escape'},
               {'op':'copy','source':'link.txt','destination':'dest/link.txt'},
               {'op':'copy','source':'hard.txt','destination':'dest/hard.txt'}]
        (self.root/'link.txt').symlink_to(self.root/'a.txt')
        (self.root/'hard-original').write_text('hard')
        os.link(self.root/'hard-original', self.root/'hard.txt')
        for operation in cases:
            proc,_=self.plan([operation])
            self.assertEqual(proc.returncode,2,proc.stdout)
        self.assertEqual(list((self.root/'dest').iterdir()),[])

    def test_existing_destination_created_after_plan_is_preserved(self):
        proc,plan=self.plan([{'op':'rename','source':'a.txt','destination':'dest/a.txt'}])
        self.assertEqual(proc.returncode,0,proc.stderr)
        (self.root/'dest/a.txt').write_text('do not overwrite')
        proc=self.command('apply',plan,self.root/'journal.jsonl')
        self.assertEqual(proc.returncode,2)
        self.assertEqual((self.root/'dest/a.txt').read_text(),'do not overwrite')
        self.assertTrue((self.root/'a.txt').exists())

if __name__=='__main__': unittest.main()
