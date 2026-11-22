"""Audit committed public text/metadata without printing matched private values."""
import argparse,hashlib,pathlib,re,subprocess,sys
ROOT=pathlib.Path(__file__).resolve().parents[1]
PATTERNS={
 'personal-absolute-path':r'(?<![A-Za-z])[A-Z]:[\\/](?:Users|Documents and Settings)[\\/]|/(?:Users|home)/[^\s/]+',
 'private-network-address':r'\b(?:192\.168\.\d{1,3}\.\d{1,3}|10\.\d{1,3}\.\d{1,3}\.\d{1,3}|172\.(?:1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3})\b',
 'private-network-url':r'https?://[^/\s]+\.(?:local|lan|home)(?:[:/\s]|$)|\\\\[A-Za-z0-9_-]+\\(?:Users|home|share)',
 'unexplained-machine-alias':r'\b(?:Run on|execution on|tested on|verified on)\s+[A-Z][A-Z0-9_-]{1,}(?=[\s.,;]|$)',
 'internal-coordination':r'/(?:root|user_notes)/|private[-_]workspace|home[ ]network',
 'credential':r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|\bgh[pousr]_[A-Za-z0-9]{20,}|\bgithub_pat_[A-Za-z0-9_]{20,}'
}
# Only the upstream Apache-licensed Gradle wrapper binary is permitted.
WRAPPER='experiments/legacy/shared/examples/java-2026-sim/gradle/wrapper/gradle-wrapper.jar'
WRAPPER_SHA='2db75c40782f5e8ba1fc278a5574bab070adccb2d21ca5a6e5ed840888448046'
SHOWCASE_ASSETS = {
    "cad/showcase-red/ramp-comparison.png": "6f10ddb88a2afac6b8c80ee648f238894a4e1c3fc535f6d9f9b4e0e7c6a6027d",
    "cad/showcase-red/assembly.png": "740c99afb7a9d2317418aaff1bca6f202cc46771d94a26c3f02cdee7e0aff33b",
    "cad/showcase-red/display.f3d": "12a858347903805d7ec784615bf0c2d1c0a7dda3e251eef1acc89da7434d44fa",
    "cad/showcase-red/display.glb": "2e9c46c9fd9a84de807cd36da3a163e38ae5b9103698b16ecc3ac234a68bf031",
    "cad/assembly-release/foundation-still.png": "75be3286c4f9fcc44706c470133d5cb60ee2fede103b5ea20ad7ed6502772b42",
    "cad/assembly-release/foundation-student.f3d": "3e11e4f83ad035d1999aae2b6509fbeef82c5b6d410ce6f5c60b6229d819c6c0",
    "docs/robot/cad/tower-climb.glb": "0de92064047e2e9029445f12b6d95a00083372881ea3267750ad3af4b611e45b",
    "docs/robot/cad/r2c-assembly.png": "9bccbff501b9b70eda2a85619cf2e9314f21ee45198efc256de82275c4417077",
    "cad/tower-lift/tower-l1.f3d": "7c4a6210bcd23540999d3412107e6a8cf72f30596250f113314b35cbf66eb941",
    "cad/own-zone-upper/own-zone-public.f3d": "5bed444ce5dc99caa94e38164be3c5cbfbefa6ed7106d2bb0370cbe1abf16dd3",
    "cad/own-zone/own-zone-public.f3d": "6939cae9d72d53276de8d1105dd9380d3ccba9de232f811499a297ede7997b25",
    "docs/robot/cad/assembly.png": "aed219de41f4735dc78461f0df197c4c506a51fb561e077302b27de5c209b86a",
    "docs/robot/cad/assembly.stl.gz": "c23ca725d96527c41c85379256ff8eba180b829a28ca34237b236cbd65e9d5ed",
    "docs/robot/cad/own-zone.glb": "38d6feebb3bd54729e21e43cdc13d296cb5c30b672aeb2e70243bb6f29bfccb1",
    "docs/robot/historical-fixture/assembly.png": "f8e583a0399eb09b91c684c1783a952716d92ba6c704d0fa9630e09d1b7a0d1f",
    "docs/robot/historical-fixture/assembly.stl.gz": "7a7e69fe256fdbb17dfd6621aa8ade4e804ce9c4dfe1564437eb14e01a0bf81b",
    "docs/robot/r1-chassis/assembly.png": "b94003578b44bb6e9b6150e386549274079cf58dea49992c4c76566a41354c24",
    "docs/robot/r1-chassis/assembly.stl.gz": "ce3878c99378d195d949c62045d6629b45fbfcf26a2f6b41263239b5da8d0247",
    "docs/vendor/model-viewer-4.1.0.min.js": "8367184a607fbe07a78b650c0d359e5ebbd96f7e2b22f95f761f559b63430386"
}
# Agent FRC 0.89.0 preliminary release tree: the plugin's OFL template fonts and the checked release's compressed display geometry (pinned by its receipt).
SHOWCASE_ASSETS['docs/preliminary-design/fonts/barlow-condensed-latin-600-normal.woff2'] = '0b281bf2f4179c06ba68f0a427f2341287c41eacc2ce9d534c6f5c513ac633fb'
SHOWCASE_ASSETS['docs/preliminary-design/fonts/barlow-condensed-latin-700-normal.woff2'] = '8320299532b4b81498d5b3714d49c9d5938883b55f4c2a1efe6f105bf4a942bd'
SHOWCASE_ASSETS['docs/preliminary-design/fonts/source-sans-3-latin-400-normal.woff2'] = '6edbd48bf7fa0e34a5ad9f8da9e73a70d3ae7f51791deb8362c868fed9a7f68c'
SHOWCASE_ASSETS['docs/preliminary-design/fonts/source-sans-3-latin-600-normal.woff2'] = '580c6561987cd9c704bc20c808c2aa7543cbdd4eaca8ec334ae4985e61971333'
SHOWCASE_ASSETS['docs/preliminary-design/fonts/source-sans-3-latin-700-normal.woff2'] = '1fc65bcc7790d534cf67a5e046f3f324aad8cc6dc364ec5ad296a18d42868464'
SHOWCASE_ASSETS['docs/preliminary-design/releases/layout-001/package-motion.geometry.json.gz'] = '461b426e4b6832ffa1970bf9471fdb73c9461e978779595a44c9e2dbff6c3af7'


def findings(data):
 text=data.decode('utf-8',errors='replace')
 return [name for name,p in PATTERNS.items() if re.search(p,text)]
def git(*args):return subprocess.check_output(['git','-C',str(ROOT),*args])
def audit(revision='HEAD'):
 failures=[]
 for raw in git('ls-tree','-rz','--name-only',revision).split(b'\0'):
  if not raw:continue
  path=raw.decode();data=git('show',revision+':'+path)
  if path in SHOWCASE_ASSETS:
   if hashlib.sha256(data).hexdigest()!=SHOWCASE_ASSETS[path]:failures.append((path,['unreviewed-cad-export']))
   continue
  if path==WRAPPER:
   if hashlib.sha256(data).hexdigest()!=WRAPPER_SHA:failures.append((path,['unreviewed-binary']))
   continue
  if b'\0' in data:failures.append((path,['unexpected-binary']));continue
  categories=findings(data)
  if categories:failures.append((path,categories))
 # Commit identity/message metadata, not source history rewriting.
 metadata=git('log','--format=%an <%ae> %cn <%ce> %s',revision)
 if findings(metadata):failures.append(('commit metadata',findings(metadata)))
 return failures
if __name__=='__main__':
 a=argparse.ArgumentParser();a.add_argument('--revision',default='HEAD');v=a.parse_args();errors=audit(v.revision)
 for path,categories in errors:print(path+': '+', '.join(categories))
 if errors:sys.exit(1)
 print('Public-content guard passed: committed text, binary allowlist and commit metadata.')
