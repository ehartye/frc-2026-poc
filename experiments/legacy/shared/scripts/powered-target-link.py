"""Continuous powered-guide exit velocity -> explicitly hypothetical local target frames."""
import pathlib,json,math,hashlib,importlib.util,re
ROOT=pathlib.Path(__file__).resolve().parents[1]
def module(name,file):
 s=importlib.util.spec_from_file_location(name,ROOT/file);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
b=module('ballistic','scripts/target-local-ballistics.py');registration=module('registration','scripts/mechanism-exit-registration.py');runner=module('runner','scripts/run-powered-guide.py')
PINS=['scripts/powered-target-link.py','scripts/target-local-ballistics.py','scripts/mechanism-exit-registration.py','scripts/run-powered-guide.py','case-studies/target-frame-evidence.json','case-studies/2026/intake-fixture-nominal.json','case-studies/2025/coral-fixture-nominal.json']
def parse(line):
 if not isinstance(line,str) or not line.startswith('POWERED_EXIT '):raise ValueError('powered exit record required')
 prefix,sample=line.removeprefix('POWERED_EXIT ').split(' Sample[')
 pairs=[x.split('=') for x in prefix.split()];fields=[x.split('=') for x in sample.removesuffix(']').split(', ')]
 if len(pairs)!=8 or len(fields)!=9 or any(len(p)!=2 for p in pairs+fields):raise ValueError('duplicate or missing fields')
 d={k:float(v) for k,v in pairs};s={k:v for k,v in fields}
 if set(d)!={'year','volts','dt','angleRad','massKg','guideLengthM','radiusM','inertiaEach'} or set(s)!={'time','x','speed','omega','motorWork','frictionLoss','feedEnergy','energyResidual','exited'} or s.pop('exited')!='true':raise ValueError('runtime exit schema')
 s={k:float(v) for k,v in s.items()}
 for v in list(d.values())+list(s.values()):b.finite(v)
 if not d['year'].is_integer():raise ValueError('integer year')
 d['year']=registration.season(int(d['year']))
 if d['volts'] not in (9,12) or d['dt']!=.00005 or s['speed']<=0 or abs(s['x']-d['guideLengthM'])>1e-12 or abs(s['energyResidual'])>2e-5:raise ValueError('runtime exit domain')
 return dict(**d,**s)
def embed_exit(row,distance):
 y=row['year'];a=row['angleRad'];sign=-1 if y==2024 else 1;axis=(sign*math.cos(a),0,math.sin(a));lateral=(0,sign,0);normal=b.cross(axis,lateral)
 # Explicit pose hypothesis places the measured guide endpoint at p; never changes speed.
 if y==2025:
  geom=json.loads((ROOT/'case-studies/2025/coral-fixture-nominal.json').read_text())['pieceSource']['geometryMm'];p=(distance,.08,geom['outerDiameter']/2000+.01)
 else:p=(distance,0,.7)
 origin=[p[i]-row['x']*axis[i] for i in range(3)]
 r=dict(season=y,basis='hypothetical-rigid-registration',units='m',**{'from':'MECHANISM_1D','to':f'TARGET_LOCAL_{y}'},originM=origin,axes=[list(axis),list(lateral),list(normal)])
 return registration.embed(y,row['x'],row['speed'],r),r

def target(row,distance,e):
 y=row['year'];state,transform=embed_exit(row,distance);p,v=state['positionM'],state['velocityMps'];center=None;margin=None;full=None
 if y==2024:
  sp=e['speaker'];low=sp['lowEdgeAboveAssemblyBottomInch']*.0254;rise=(sp['highEdgeAboveAssemblyBottomInch']-sp['lowEdgeAboveAssemblyBottomInch'])*.0254;reach=sp['horizontalReachInch']*.0254;a=math.atan2(rise,reach);u=(math.cos(a),0,math.sin(a));axes=[u,(0,1,0),b.cross(u,(0,1,0))];origin=(0,0,low)
  center=next((c for c in b.crossing(p,v,origin,axes[2]) if c['normalVelocityMps']>0),None)
  if center:
   c=b.to_local(center['positionM'],origin,axes);margin=min(c[0],math.hypot(reach,rise)-c[0],sp['widthInch']*.0254/2-abs(c[1]))
 elif y==2026:
  h=e['hub']['controlledHeightInch']*.0254;r=json.loads((ROOT/'case-studies/2026/intake-fixture-nominal.json').read_text())['pieceSource']['geometryMm']['diameter']/2000;ap=e['hub']['innerReferenceAcrossFlatsInch']*.0254/2
  cross=lambda height:next((c for c in b.crossing(p,v,(0,0,height),(0,0,1)) if c['normalVelocityMps']<0),None)
  first,center,last=[cross(z) for z in (h+r,h,h-r)]
  if first and last:margin=min(b.hex_projection_margin(c['positionM'][0],c['positionM'][1],ap,r) for c in (first,last));full=margin>0
 else:
  ro=json.loads((ROOT/'case-studies/2025/coral-fixture-nominal.json').read_text())['pieceSource']['geometryMm']['outerDiameter']/2000
  center=next((c for c in b.crossing(p,v,(0,0,ro),(0,0,1)) if c['normalVelocityMps']<0),None)
 if center:center['absolutePlantTimeS']=row['time']+center['timeS']
 return dict(season=y,supplyVolts=row['volts'],sourceExit=row,registrationHypothesis=transform,embeddedExit=state,targetCenterCrossing=center,projectionMarginM=margin,conditionalWholeSphereThinPlaneClearance=full,wholeNoteClearance=None,coralInstalledContact=None,targetSensorPassage=None,nominalComponentPoints=None)
def report():
 r=json.loads((ROOT/'case-studies/powered-guide-run.json').read_text());e=json.loads((ROOT/'case-studies/target-frame-evidence.json').read_text())
 if set(r['sourceCodeSha256'])!=set(runner.CODE):raise ValueError('native dependency set')
 for p,h in r['sourceCodeSha256'].items():
  if hashlib.sha256((ROOT/p).read_text(encoding='utf-8-sig').encode()).hexdigest()!=h:raise ValueError('stale native input')
 rows=[parse(l) for l in r['observations']]
 if len(rows)!=6 or {(x['year'],x['volts']) for x in rows}!={(y,v) for y in (2024,2025,2026) for v in (9,12)}:raise ValueError('native exit inventory')
 return dict(schema='frc-powered-target-link/v1',runId=r['runId'],cases=[target(row,d,e) for row in rows for d in ({2024:[1.5,2,2.5],2025:[.15,.2,.45],2026:[-2,-4.5,-5]}[row['year']])],sourceCodeSha256={p:hashlib.sha256((ROOT/p).read_text(encoding='utf-8-sig').encode()).hexdigest() for p in PINS},limitations=['Separate synthetic opposed-roller guide; not connected to previous catcher or selected mechanical bank','Two equal NEO models, direct drive, each inertia0.004 kg m2, constant15 N normal per roller and mu0.8 are hypotheses','Piece translation constrained to straight guide, equal roller speeds, no independent spin, compliance, pad motion or load calibration','Motor work includes two-second spin-up; initial0.2 m/s feed energy declared, no exit-speed reset or release impulse','Guide endpoint pose and orientation are explicit sweeps, not installed or field-registered transforms','NOTE center crossing excludes torus extent, orientation and roof geometry','FUEL conservative sphere plane projection excludes funnel/rim/sensor geometry and tolerance propagation','CORAL descent to isolated floor-height plane excludes finite patch collision, installed mating, settling and robot-contact exclusions','No score or engineering acceptance'],engineeringAcceptance='blocked')
if __name__=='__main__':
 import argparse
 a=argparse.ArgumentParser();a.add_argument('--output',required=True);p=pathlib.Path(a.parse_args().output)
 with p.open('x',encoding='utf-8') as f:json.dump(report(),f,indent=2,allow_nan=False);f.write('\n')
