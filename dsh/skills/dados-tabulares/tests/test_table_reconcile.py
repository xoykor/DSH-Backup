import json
import subprocess
import tempfile
import unittest
from pathlib import Path

SCRIPT=Path(__file__).resolve().parents[1]/'scripts/table_reconcile'

class ReconcileTest(unittest.TestCase):
    def run_case(self,left,right,spec):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            a=root/'left.json'; b=root/'right.json'; s=root/'spec.json'; out=root/'out.json'
            a.write_text(json.dumps(left)); b.write_text(json.dumps(right)); s.write_text(json.dumps(spec))
            before=(a.read_bytes(),b.read_bytes())
            proc=subprocess.run([str(SCRIPT),'--left',str(a),'--right',str(b),'--spec',str(s),'--output',str(out)],capture_output=True,text=True,timeout=5)
            self.assertEqual(before,(a.read_bytes(),b.read_bytes()))
            return proc,json.loads(out.read_text()) if out.exists() else None

    def test_every_row_accounted_with_duplicate_groups(self):
        left=[{'id':'1','v':'same'},{'id':'2','v':'left'},{'id':'3','v':'a'},{'id':'3','v':'b'},{'id':'4','v':'only'}]
        right=[{'id':'1','v':'same'},{'id':'2','v':'right'},{'id':'3','v':'c'},{'id':'5','v':'only'}]
        proc,result=self.run_case(left,right,{'keys':['id']})
        self.assertEqual(proc.returncode,0,proc.stderr)
        expected={'equal_pairs':1,'different_pairs':1,'only_left_rows':1,'only_right_rows':1,'ambiguous_left_rows':2,'ambiguous_right_rows':1,'left_duplicate_groups':1}
        for k,v in expected.items(): self.assertEqual(result['counts'][k],v,k)
        self.assertTrue(result['counts_validated'])

    def test_types_and_missing_fields_are_distinct(self):
        proc,result=self.run_case([{'id':1,'v':True},{'id':'1','v':None}],[{'id':1,'v':1},{'id':'1'}],{'keys':['id']})
        self.assertEqual(proc.returncode,0,proc.stderr)
        self.assertEqual(result['counts']['different_pairs'],2)

    def test_expected_counts_mismatch_is_nonzero(self):
        proc,result=self.run_case([{'id':'1'}],[{'id':'1'}],{'keys':['id'],'expected_counts':{'equal_pairs':0}})
        self.assertEqual(proc.returncode,3,proc.stderr)
        self.assertEqual(result['status'],'mismatch')

    def test_invalid_keys_rejected(self):
        proc,result=self.run_case([{'id':''}],[{'id':'1'}],{'keys':['id']})
        self.assertEqual(proc.returncode,2)
        self.assertIsNone(result)

    def test_csv_ids_and_examples_limit(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); a=root/'a.csv'; b=root/'b.csv'; s=root/'spec.json'; out=root/'out.json'
            a.write_text('id,value\n001,café\n002,old\n003,old\n'); b.write_text('id,value\n001,café\n002,new\n003,new\n')
            s.write_text('{"keys":["id"],"max_examples":1}')
            proc=subprocess.run([str(SCRIPT),'--left',str(a),'--right',str(b),'--spec',str(s),'--output',str(out)],capture_output=True,text=True)
            self.assertEqual(proc.returncode,0,proc.stderr)
            result=json.loads(out.read_text())
            self.assertEqual(result['counts']['different_pairs'],2)
            self.assertEqual(result['examples']['differences'][0]['key']['id'],'002')
            self.assertTrue(result['examples_truncated'])

if __name__=='__main__': unittest.main()
