"""Runtime NOTE exits with conservative whole-torus thin-plane clearance and explicit aim hypotheses."""
import pathlib,json,math,hashlib,importlib.util
ROOT=pathlib.Path(__file__).resolve().parents[1]
s=importlib.util.spec_from_file_location('integrated',ROOT/'scripts/integrated-prototype-targets.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m);b=m.link.b
PINS=sorted(set(m.PINS+['scripts/note-prototype-body.py','case-studies/2024/note-fixture-nominal.json']))
def evaluate(row,distance,pitch,lateral=0,world_state=None,note_axis=None):
 if type(row.get('year')) is not int or row['year']!=2024:raise ValueError('NOTE season required')
 for value in (distance,pitch,lateral):b.finite(value)
 e=json.loads((ROOT/'case-studies/target-frame-evidence.json').read_text())['speaker'];low=e['lowEdgeAboveAssemblyBottomInch']*.0254;rise=(e['highEdgeAboveAssemblyBottomInch']-e['lowEdgeAboveAssemblyBottomInch'])*.0254;reach=e['horizontalReachInch']*.0254;length=math.hypot(reach,rise);width=e['widthInch']*.0254;a=math.atan2(rise,reach);u=(math.cos(a),0,math.sin(a));vaxis=(0,1,0);normal=b.cross(u,vaxis);origin=(0,0,low)
 if world_state is None:state,transform=m.link.embed_exit(row,distance)
 else:
  state=dict(positionM=list(b.vec(world_state['positionM'])),velocityMps=list(b.vec(world_state['velocityMps'])));transform=dict(basis='virtual-chassis-with-declared-mount',units='m',chassisPose=row.get('chassisPose'))
  if abs(b.dot(state['velocityMps'],state['velocityMps'])-row['speed']**2)>1e-8:raise ValueError('velocity reset forbidden')
 p=list(state['positionM']);p[1]+=lateral
 if 'originM' in transform:transform['originM'][1]+=lateral
 velocity=state['velocityMps'];axis=b.vec(note_axis) if note_axis is not None else (-math.sin(pitch),0,math.cos(pitch))
 if abs(b.dot(axis,axis)-1)>1e-9:raise ValueError('unit note axis required')
 geom=json.loads((ROOT/'case-studies/2024/note-fixture-nominal.json').read_text())['pieceSource']['geometryMm'];minor=geom['thickness']/2000;major=geom['outerDiameter']/2000-minor;supports=[b.torus_support(d,axis,major,minor) for d in [u,vaxis,normal]]
 def crossing(offset):
  c=next((c for c in b.crossing(p,velocity,tuple(origin[i]+normal[i]*offset for i in range(3)),normal) if c['normalVelocityMps']>0),None)
  if c:c['absolutePlantTimeS']=row['time']+c['timeS']
  return c
 first,center,last=[crossing(offset) for offset in [-supports[2],0,supports[2]]];margin=None;times=[]
 if first and last and first['timeS']<=last['timeS']:
  times=[first['timeS'],last['timeS']]
  for direction in [u,vaxis]:
   if abs(b.dot(b.G,direction))>1e-12:
    t=-b.dot(velocity,direction)/b.dot(b.G,direction)
    if times[0]<t<times[1]:times.append(t)
  coords=[b.to_local(b.position(p,velocity,t),origin,[u,vaxis,normal]) for t in times];margin=min(min(c[0]-supports[0],length-c[0]-supports[0],width/2-abs(c[1])-supports[1]) for c in coords)
 return dict(sourceExit=row,aimDistanceM=distance,lateralOffsetM=lateral,fixedNotePitchDeg=math.degrees(pitch),fixedNoteAxisM=axis,exitPositionM=p,exitVelocityMps=velocity,registrationHypothesis=transform,planeLengthM=length,planeWidthM=width,planeOriginM=origin,planeAxes=[u,vaxis,normal],torusSupportsM=supports,normalSupportCrossings=[first,center,last],extremumTimesS=times,conservativeWholeTorusProjectionMarginM=margin,conditionalWholeTorusThinPlaneClearance=margin is not None and margin>0,installedRoofWallClearance=None,sensorPassage=None,matchScore=None)
def report(target_file=None,receipt_file=None):
 target=pathlib.Path(target_file) if target_file else ROOT/'case-studies/integrated-prototype-targets.json'
 expected=m.report(receipt_file);stored=json.loads(target.read_text())
 if stored!=expected:raise ValueError('stale integrated target evidence')
 rows={}
 for case in stored['cases']:
  row=case['sourceExit']
  if row['year']==2024:rows[row['volts'],row['inertiaEach']]=row
 e=json.loads((ROOT/'case-studies/target-frame-evidence.json').read_text())['speaker'];angle=math.atan2(e['highEdgeAboveAssemblyBottomInch']-e['lowEdgeAboveAssemblyBottomInch'],e['horizontalReachInch']);pitches=[0,angle,math.radians(50)];baseline=[];best=[]
 for row in rows.values():
  for pitch in pitches:
   baseline.extend(evaluate(row,d,pitch) for d in [1.5,2,2.5]);scan=[evaluate(row,1+k*.025,pitch) for k in range(101)];valid=[c for c in scan if c['conservativeWholeTorusProjectionMarginM'] is not None]
   best.append(dict(volts=row['volts'],inertiaEach=row['inertiaEach'],fixedNotePitchDeg=math.degrees(pitch),evaluatedAimCount=len(scan),best=max(valid,key=lambda c:c['conservativeWholeTorusProjectionMarginM']) if valid else None))
 return dict(schema='frc-note-runtime-body-target/v1',sourceTargetReportSha256=hashlib.sha256(target.read_text(encoding='utf-8-sig').encode()).hexdigest(),baselineCases=baseline,boundedAimStudy=best,aimRangeM=[1,3.5],aimStepM=.025,sourceCodeSha256={p:hashlib.sha256((ROOT/p).read_text(encoding='utf-8-sig').encode()).hexdigest() for p in PINS},sourceExecutionReceiptSha256=stored['sourceExecutionReceiptSha256'],limitations=['Actual motor-generated exit state and global clock; no exit-speed reset or prescribed launch impulse','Fixed torus orientation hypotheses0deg,side-profile-angle,50deg; not measured attitude, spin, deformation or aerodynamics','Projection contains whole torus for entire normal-support crossing interval, sufficient but not necessary for a thin rectangular plane','Bounded aim scan changes hypothetical target-relative registration, not installed chassis pose or physical automatic aim','Nominal side-profile geometry;14deg manual discrepancy and drawing tolerances remain','No roof/wall/sensor model or official scoring'],matchScore=None)
if __name__=='__main__':
 import argparse
 a=argparse.ArgumentParser();a.add_argument('--output',required=True);a.add_argument('--targets');a.add_argument('--receipt');v=a.parse_args()
 with pathlib.Path(v.output).open('x') as f:json.dump(report(v.targets,v.receipt),f,indent=2,allow_nan=False);f.write('\n')
