"""Runtime integrated prototype exits into explicit hypothetical season target frames."""
import pathlib,json,hashlib,importlib.util,re
ROOT=pathlib.Path(__file__).resolve().parents[1]
def module(name,path):
 s=importlib.util.spec_from_file_location(name,ROOT/path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
link=module('link','scripts/powered-target-link.py');runner=module('runner','scripts/run-integrated-prototype.py')
PINS=sorted(set(link.PINS+['scripts/integrated-prototype-targets.py','scripts/run-integrated-prototype.py','case-studies/direct-drive-inertia-inputs.json']))
def parse(line):
 duty=re.search(r' commandedDuty=([0-9.]+) ',line)
 if not duty:raise ValueError('command duty required')
 command=float(duty.group(1));line=line.replace(duty.group(0),' ')
 match=re.search(r' releaseTime=([0-9.]+) ',line)
 if not match:raise ValueError('release time required')
 release=float(match.group(1));row=link.parse(line.replace('PROTOTYPE_EXIT ','POWERED_EXIT ').replace(match.group(0),' '))
 if not 0<release<1 or row['feedEnergy']!=0:raise ValueError('unexpected transfer energy or clock')
 if command!={2024:.6,2025:.08,2026:.6}[row['year']]:raise ValueError('unexpected command duty')
 row['commandedDuty']=command
 row['plantElapsedTimeS']=row['time'];row['releaseTimeS']=release;row['time']+=release;return row

def report(receipt_file=None):
 receipt_path=pathlib.Path(receipt_file) if receipt_file else ROOT/'case-studies/integrated-prototype-run.json'
 receipt=json.loads(receipt_path.read_text())
 if set(receipt['sourceCodeSha256'])!=set(runner.CODE):raise ValueError('dependency set')
 for p,h in receipt['sourceCodeSha256'].items():
  if hashlib.sha256((ROOT/p).read_text(encoding='utf-8-sig').encode()).hexdigest()!=h:raise ValueError('stale execution')
 rows=[parse(l) for l in receipt['observations']]
 if len(rows)!=32 or len({(r['year'],r['massKg'],r['volts'],r['inertiaEach']) for r in rows})!=32:raise ValueError('scenario inventory')
 e=json.loads((ROOT/'case-studies/target-frame-evidence.json').read_text())
 return dict(schema='frc-integrated-prototype-targets/v1',runId=receipt['runId'],sourceExecutionReceiptSha256=hashlib.sha256(receipt_path.read_text(encoding='utf-8-sig').encode()).hexdigest(),cases=[link.target(row,d,e) for row in rows for d in ({2024:[1.5,2,2.5],2025:[.15,.2,.45],2026:[-2,-4.5,-5]}[row['year']])],sourceCodeSha256={p:hashlib.sha256((ROOT/p).read_text(encoding='utf-8-sig').encode()).hexdigest() for p in PINS},simulationReadyScope='Runnable virtual retained pregrip through control, motor-driven guide and local target flight; not complete field robot',assumptions=['Initial body is retained at rest in a separately mounted straight guide; prior floor/side-pad dynamics are not reused','Prescribed0.35s nip closure,15N per side,ideal rigid rail attachments and true virtual feedback; no force-calibrated actuators','Fixed guide pitch50deg NOTE,0 CORAL,60 FUEL; gravity-constrained guide supports and mounting are explicit design assumptions','Rollers start stopped; feed energy0, no spinup reset, source exit speed/time unchanged through target registration','Target transforms are hypothetical design inputs, not installed registration; no official score inference','Fault cases terminate simulation and preserve nonzero motor state, not physically safe stopping'],calibration=None,matchScore=None)
if __name__=='__main__':
 import argparse
 a=argparse.ArgumentParser();a.add_argument('--output',required=True);a.add_argument('--receipt');v=a.parse_args()
 with pathlib.Path(v.output).open('x') as f:json.dump(report(v.receipt),f,indent=2,allow_nan=False);f.write('\n')
