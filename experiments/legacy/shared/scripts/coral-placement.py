"""Conditional finite CORAL placement on an isolated, unperforated local floor patch."""
import hashlib, importlib.util, json, math, pathlib
ROOT=pathlib.Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('integrated',ROOT/'scripts/integrated-prototype-targets.py');integrated=importlib.util.module_from_spec(spec);spec.loader.exec_module(integrated)
PINS=list(dict.fromkeys(['scripts/coral-placement.py','scripts/pose-clearance-contract.py','case-studies/target-frame-evidence.json']+integrated.PINS))
def load_geometry():
 s=importlib.util.spec_from_file_location('pose',ROOT/PINS[1]);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
 return tuple(v/1000 for v in m.GEOMETRY[2025])
HALF,RADIUS=load_geometry();G=9.80665

def finite(x):
 if isinstance(x,bool) or not isinstance(x,(int,float)) or not math.isfinite(x):raise ValueError('finite number required')
 return x

def margin(point,yaw,polygon):
 x,y=map(finite,point);a=math.radians(finite(yaw));axis=(math.cos(a),math.sin(a));out=[]
 for p,q in zip(polygon,polygon[1:]+polygon[:1]):
  dx,dy=q[0]-p[0],q[1]-p[1];length=math.hypot(dx,dy)
  nx,ny=-dy/length,dx/length
  dot=nx*axis[0]+ny*axis[1]
  support=HALF*abs(dot)+RADIUS*math.sqrt(max(0,1-dot*dot))
  out.append(nx*(x-p[0])+ny*(y-p[1])-support)
 return min(out)

def evaluate(position,velocity,yaw,mu,polygon):
 p=list(map(finite,position));v=list(map(finite,velocity));finite(mu);finite(yaw)
 if mu<0 or p[2]<RADIUS:raise ValueError('nonnegative friction and center above plane required')
 t=(v[2]+math.sqrt(v[2]**2+2*G*(p[2]-RADIUS)))/G
 landing=[p[i]+v[i]*t for i in range(2)]
 speed=math.hypot(*v[:2]);a=math.radians(yaw)
 axial=abs(-math.sin(a)*v[0]+math.cos(a)*v[1])<1e-10
 result=dict(landingTimeS=t,landingCenterM=landing,landingMarginM=margin(landing,yaw,polygon),axialModelApplicable=axial,stopDistanceM=None,stopCenterM=None,sweptMarginM=None,conditionalContainedStop=False)
 if not axial or (mu==0 and speed>0):return result
 distance=0 if speed==0 else speed*speed/(2*mu*G)
 stop=[landing[i]+(v[i]/speed*distance if speed else 0) for i in range(2)]
 # A fixed projection translated along a segment lies in a convex polygon iff both endpoint projections do.
 swept=min(margin(landing,yaw,polygon),margin(stop,yaw,polygon))
 result.update(stopDistanceM=distance,stopCenterM=stop,sweptMarginM=swept,conditionalContainedStop=swept>=0)
 return result

def report(target_file=None,receipt_file=None):
 target=pathlib.Path(target_file) if target_file else ROOT/'case-studies/integrated-prototype-targets.json'
 evidence=json.loads((ROOT/PINS[2]).read_text());runtime=json.loads(target.read_text())
 if runtime!=integrated.report(receipt_file):raise ValueError('stale runtime targets')
 polygon=[[v*.0254 for v in p] for p in evidence['coralFloor']['verticesInch']]
 rows=[]
 for index,c in enumerate(runtime['cases']):
  if c['season']!=2025:continue
  e=c['embeddedExit'];p=e['positionM'];v=e['velocityMps']
  for yaw in (0,-15,15):
   a=math.radians(yaw);rotated=[v[0]*math.cos(a)-v[1]*math.sin(a),v[0]*math.sin(a)+v[1]*math.cos(a),v[2]]
   # Bounded target-local search: exit x .15..25m, y .08..14m, unchanged height, speed and flight time.
   candidates=[([x/1000,y/1000,p[2]],rotated) for x in range(150,251,10) for y in range(80,141,10)]
   for mu in (0,.1,.3,.5):
    baseline=evaluate(p,v,yaw,mu,polygon)
    scored=[(evaluate(cp,cv,yaw,mu,polygon),cp,cv) for cp,cv in candidates]
    def score(item):
     r=item[0];return r['sweptMarginM'] if r['sweptMarginM'] is not None else r['landingMarginM']
    best,bp,bv=max(scored,key=score)
    rows.append(dict(sourceCaseIndex=index,sourceExit=c['sourceExit'],yawDeg=yaw,muHypothesis=mu,baseline=baseline,improvedRegistration=dict(exitPositionM=bp,exitVelocityMps=bv,translationFromBaselineM=[bp[i]-p[i] for i in range(3)],yawRotationDeg=yaw),improved=best))
 return dict(schema='frc-coral-placement/v1',sourceTargetReportSha256=hashlib.sha256(target.read_text(encoding='utf-8-sig').encode()).hexdigest(),sourceRunId=runtime['runId'],pins={p:hashlib.sha256((ROOT/p).read_text(encoding='utf-8-sig').encode()).hexdigest() for p in PINS},floorSource=evidence['coralFloor'],halfLengthM=HALF,radiusM=RADIUS,cases=rows,assumptions=['Fixed horizontal finite cylinder at yaw0 or +/-15deg; no orientation inferred from runtime','Floor is isolated convex part-local unrounded patch, no holes, corner radii, walls or installed transform','Perfectly inelastic vertical landing; horizontal velocity preserved; no impact impulse coupling','Axial sliding only when velocity aligns tube axis; hypothetical constant Coulomb mu, no rolling, spin or settling','Bounded grid registration is a design hypothesis, not an installed mechanism; best landing used for mu0, not a stop','Whole swept fixed projection containment proven by convex endpoint support; no hole or pressure/contact-area proof'],calibration=None,installedRegistration=None,officialScore=None,engineeringAcceptance='blocked')
if __name__=='__main__':
 import argparse
 a=argparse.ArgumentParser();a.add_argument('--targets');a.add_argument('--receipt');a.add_argument('--output');v=a.parse_args();text=json.dumps(report(v.targets,v.receipt),indent=2,allow_nan=False)+'\n'
 if v.output:
  with pathlib.Path(v.output).open('x') as f:f.write(text)
 else:print(text,end='')
