import pathlib,json,hashlib,subprocess,sys,argparse,datetime
ROOT=pathlib.Path(__file__).resolve().parents[1]
def main():
 a=argparse.ArgumentParser();a.add_argument('--java-home',required=True);a.add_argument('--gradle-home',required=True);a.add_argument('--output');v=a.parse_args()
 config=json.loads((ROOT/'config.json').read_text());
 if type(config.get('season')) is not int or config['season']!=2026:raise ValueError('Integer repository season required')
 manifest=json.loads((ROOT/'PROVENANCE.json').read_text())
 for p,h in manifest['snapshotSha256'].items():
  if hashlib.sha256((ROOT/p).read_bytes()).hexdigest()!=h:raise ValueError('Changed pinned source: '+p)
 out=pathlib.Path(v.output).resolve() if v.output else ROOT/'artifacts'/datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
 if out.exists():raise ValueError('Output must be fresh')
 out.mkdir(parents=True);shared=ROOT/'experiments'/'legacy'/'shared'
 subprocess.run([sys.executable,str(shared/'scripts/run-season-robot.py'),'--output',str(out/'robot-run'),'--java-home',v.java_home,'--gradle-home',v.gradle_home],check=True,stdout=(out/'runner-output.json').open('w'))
 subprocess.run([sys.executable,str(shared/'scripts/season-robot-targets.py'),'--receipt',str(out/'robot-run/receipt.json'),'--output',str(out/'all-season-targets.json')],check=True)
 report=json.loads((out/'all-season-targets.json').read_text());cases=[r for r in report['cases'] if r['runtime']['year']==config['season']]
 if len(cases)!=(8 if config['season']==2025 else 2):raise ValueError('season case count')
 for row in cases:
  r=row['runtime']
  if (config['season']!=2025 or r['plan']==1) and (abs(r['duty']-config['duty'])>1e-12 or abs(r['inertia']-config['rollerInertiaKgM2'])>1e-12):raise ValueError('Config no longer agrees with pinned plant')
 report['cases']=cases;report['season']=config['season'];report['configurationRole']='Verified description of pinned model, not arbitrary runtime tuning';report['allSeasonRegressionExecuted']=True
 (out/'season-results.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
 (out/'SUMMARY.md').write_text('# Season '+str(config['season'])+' POC run\n\n'+str(len(cases))+' season scenarios selected from fresh shared regression. See season-results.json and robot-run/receipt.json. Official score remains unknown.\n')
 print('Results: '+str(out))
if __name__=='__main__':main()
