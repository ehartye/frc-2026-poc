import unittest,tempfile,pathlib,shutil,subprocess,json,hashlib,sys
ROOT=pathlib.Path(__file__).resolve().parents[1]
class ReceiptBoundary(unittest.TestCase):
 def test_changed_snapshot_is_rejected_before_execution(self):
  with tempfile.TemporaryDirectory() as d:
   root=pathlib.Path(d);(root/'scripts').mkdir();shutil.copyfile(ROOT/'scripts/run.py',root/'scripts/run.py');shutil.copyfile(ROOT/'config.json',root/'config.json')
   (root/'source.txt').write_text('tampered');(root/'PROVENANCE.json').write_text(json.dumps({'snapshotSha256':{'source.txt':hashlib.sha256(b'original').hexdigest()}}))
   r=subprocess.run([sys.executable,str(root/'scripts/run.py'),'--java-home','absent','--gradle-home','absent'],capture_output=True,text=True)
   self.assertNotEqual(r.returncode,0);self.assertIn('Changed pinned source',r.stderr);self.assertFalse((root/'artifacts').exists())
 def test_snapshot_hashes_match(self):
  for p,h in json.loads((ROOT/'PROVENANCE.json').read_text())['snapshotSha256'].items():self.assertEqual(hashlib.sha256((ROOT/p).read_bytes()).hexdigest(),h,p)
 def test_changed_or_mistyped_config_is_rejected(self):
  for key,value in [('duty',0),('season','2024'),('season',True),('season',2023)]:
   with self.subTest(key=key,value=value),tempfile.TemporaryDirectory() as d:
    root=pathlib.Path(d);(root/'scripts').mkdir();shutil.copyfile(ROOT/'scripts/run.py',root/'scripts/run.py')
    config=json.loads((ROOT/'config.json').read_text());original=(ROOT/'config.json').read_bytes();config[key]=value
    (root/'config.json').write_text(json.dumps(config));(root/'PROVENANCE.json').write_text(json.dumps({'snapshotSha256':{'config.json':hashlib.sha256(original).hexdigest()}}))
    r=subprocess.run([sys.executable,str(root/'scripts/run.py'),'--java-home','absent','--gradle-home','absent'],capture_output=True,text=True)
    self.assertNotEqual(r.returncode,0);self.assertTrue('Integer repository season required' in r.stderr or 'Changed pinned source' in r.stderr);self.assertFalse((root/'artifacts').exists())
if __name__=='__main__':unittest.main()
