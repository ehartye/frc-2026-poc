"""Season robot outputs: generated chassis pose -> declared mount -> unchanged powered exit -> finite target."""
import pathlib,json,math,hashlib,importlib.util
ROOT=pathlib.Path(__file__).resolve().parents[1]
def module(name,file):
 s=importlib.util.spec_from_file_location(name,ROOT/file);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
note=module('note','scripts/note-prototype-body.py');coral=module('coral','scripts/coral-placement.py');runner=module('runner','scripts/run-season-robot.py');b=note.b
PINS=sorted(set(note.PINS+coral.PINS+['scripts/season-robot-targets.py','scripts/run-season-robot.py']))
FIELDS={'year','plan','mass','volts','dockTime','chassisX','chassisY','heading','exitX','exitY','exitZ','vx','vy','vz','time','speed','residual','angle','length','radius','inertia','duty'}
def parse(line):
 if not isinstance(line,str) or not line.startswith('ROBOT_EXIT '):raise ValueError('robot runtime record required')
 pairs=[x.split('=') for x in line.removeprefix('ROBOT_EXIT ').split()]
 if len(pairs)!=len(FIELDS) or any(len(x)!=2 for x in pairs):raise ValueError('field count')
 r={k:float(v) for k,v in pairs}
 if set(r)!=FIELDS:raise ValueError('field set')
 for v in r.values():b.finite(v)
 if r['year'] not in (2024,2025,2026) or r['plan'] not in (0,1):raise ValueError('season/plan')
 r['year']=int(r['year']);r['plan']=int(r['plan'])
 h,a=r['heading'],r['angle'];travel=.25+r['length']*math.cos(a)
 expected=[r['chassisX']+math.cos(h)*travel,r['chassisY']+math.sin(h)*travel,.06715 if r['year']==2025 else .7]
 if any(abs(x-r[k])>1e-9 for x,k in zip(expected,['exitX','exitY','exitZ'])):raise ValueError('mount continuity')
 expectedV=[r['speed']*math.cos(a)*math.cos(h),r['speed']*math.cos(a)*math.sin(h),r['speed']*math.sin(a)]
 if any(abs(v-r[k])>1e-9 for v,k in zip(expectedV,['vx','vy','vz'])) or r['time']<=r['dockTime'] or abs(r['residual'])>2e-5:raise ValueError('runtime continuity')
 return r

def assess(r):
 e=json.loads((ROOT/'case-studies/target-frame-evidence.json').read_text());p=[r[k] for k in ['exitX','exitY','exitZ']];v=[r[k] for k in ['vx','vy','vz']];y=r['year'];out=dict(runtime=r,officialScore=None)
 if y==2024:
  sp=e['speaker'];pitch=math.atan2(sp['highEdgeAboveAssemblyBottomInch']-sp['lowEdgeAboveAssemblyBottomInch'],sp['horizontalReachInch']);row=dict(r,chassisPose=[r['chassisX'],r['chassisY'],r['heading']]);axis=[math.sin(pitch)*math.cos(r['heading']),math.sin(pitch)*math.sin(r['heading']),math.cos(pitch)]
  out['note']=note.evaluate(row,p[0],pitch,world_state=dict(positionM=p,velocityMps=v),note_axis=axis)
 elif y==2026:
  radius=json.loads((ROOT/'case-studies/2026/intake-fixture-nominal.json').read_text())['pieceSource']['geometryMm']['diameter']/2000;height=e['hub']['controlledHeightInch']*.0254;ap=e['hub']['innerReferenceAcrossFlatsInch']*.0254/2
  crossings=[next((c for c in b.crossing(p,v,(0,0,z),(0,0,1)) if c['normalVelocityMps']<0),None) for z in [height+radius,height,height-radius]]
  for c in crossings:
   if c:c['absoluteRobotTimeS']=r['time']+c['timeS']
  margin=min(b.hex_projection_margin(c['positionM'][0],c['positionM'][1],ap,radius) for c in [crossings[0],crossings[2]]) if crossings[0] and crossings[2] else None
  out['fuel']=dict(crossings=crossings,wholeSphereThinPlaneMarginM=margin,conditionalClearance=margin is not None and margin>0,sensorPassage=None)
 else:
  polygon=[[x*.0254 for x in point] for point in e['coralFloor']['verticesInch']]
  out['coral']=[]
  for mu in [0,.1,.3,.5]:
   stop=coral.evaluate(p,v,math.degrees(r['heading']),mu,polygon);stop['absoluteLandingTimeS']=r['time']+stop['landingTimeS'];stop['absoluteConditionalStopTimeS']=stop['absoluteLandingTimeS']+math.hypot(v[0],v[1])/(mu*coral.G) if stop['conditionalContainedStop'] and mu>0 else None
   out['coral'].append(dict(muHypothesis=mu,**stop))
 return out

def report(receipt_file=None):
 path=pathlib.Path(receipt_file) if receipt_file else ROOT/'case-studies/season-robot-run.json';r=json.loads(path.read_text())
 if set(r['sourceCodeSha256'])!=set(runner.CODE) or set(r['tests'])!=runner.TESTS:raise ValueError('execution inventory')
 for p,h in r['sourceCodeSha256'].items():
  if hashlib.sha256((ROOT/p).read_text(encoding='utf-8-sig').encode()).hexdigest()!=h:raise ValueError('stale runtime source')
 rows=[parse(line) for line in r['observations']]
 expected={(y,mass,volts,plan) for y,masses,plans in [(2024,[.235],[1]),(2025,[.498951607,.816466266],[0,1]),(2026,[.215],[1])] for mass in masses for volts in [9,12] for plan in plans}
 if len(rows)!=12 or {(x['year'],x['mass'],x['volts'],x['plan']) for x in rows}!=expected:raise ValueError('scenario inventory')
 return dict(schema='frc-season-robot-targets/v1',sourceRunId=r['runId'],sourceExecutionReceiptSha256=hashlib.sha256(path.read_text(encoding='utf-8-sig').encode()).hexdigest(),sourceCodeSha256={p:hashlib.sha256((ROOT/p).read_text(encoding='utf-8-sig').encode()).hexdigest() for p in PINS},cases=[assess(row) for row in rows],assumptions=['Preloaded single piece held rigidly during ideal differential-drive approach; acquisition not modeled','WPILib kinematics and exact simulated pose, not drivetrain traction/energy, odometry error or hardware sensors','Drive is commanded stopped for200ms before mechanism; ideal chassis holds pose during firing, recoil and shared drive/mechanism supply absent','Declared mount0.25m ahead of chassis plus straight guide, endpoint heights0.7m orCORAL0.06715m in target-part-local coordinates','Actual simulated dock pose and actual powered speed are retained, with global drive+mechanism clock','NOTE fixed attitude relative chassis; CORAL perfect vertical impact and hypothetical axial friction; no complete field collisions or official scores'],handoffScope='Three runnable preloaded robot slices, not full competition robots',officialScore=None)
if __name__=='__main__':
 import argparse
 a=argparse.ArgumentParser();a.add_argument('--receipt');a.add_argument('--output',required=True);v=a.parse_args()
 with pathlib.Path(v.output).open('x') as f:json.dump(report(v.receipt),f,indent=2,allow_nan=False);f.write('\n')
