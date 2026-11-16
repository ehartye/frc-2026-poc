import importlib.util,pathlib,unittest
ROOT=pathlib.Path(__file__).resolve().parents[1]
s=importlib.util.spec_from_file_location('guard',ROOT/'scripts/check_public_content.py');guard=importlib.util.module_from_spec(s);s.loader.exec_module(guard)
class PublicContent(unittest.TestCase):
 def test_committed_content(self):self.assertEqual(guard.audit(),[])
 def test_synthetic_private_patterns(self):
  examples=['C:'+chr(92)+'Users'+chr(92)+'example'+chr(92)+'file','/ho'+'me/example/file','192'+'.168.10.2','https://device'+'.l'+'an/path','Run on '+'BUILD_NODE','execution on '+'TEST_BOX']
  for value in examples:
   with self.subTest(category=value.split()[0]):self.assertTrue(guard.findings(value.encode()))
 def test_portable_language_and_sources(self):
  self.assertEqual(guard.findings(b'Run on Windows with an existing JDK 17. https://github.com/example/project'),[])
if __name__=='__main__':unittest.main()
