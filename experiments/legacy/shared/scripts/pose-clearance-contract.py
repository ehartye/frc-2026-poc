"""Conservative gate/guide clearance contract for bounded pose and motion estimates."""
import math,pathlib,json,hashlib
ROOT=pathlib.Path(__file__).resolve().parents[1]
GEOMETRY={2024:(177.8,177.8),2025:(150.8125,57.15),2026:(75.,75.)}
def finite(x):
 if isinstance(x,bool) or not isinstance(x,(float,int)) or not math.isfinite(x):raise ValueError('finite numeric input required')
 return x

def support(year,yaw,pitch):
 if type(year) is not int or year not in GEOMETRY:raise ValueError('season required')
 yaw,pitch=[math.radians(finite(a)) for a in (yaw,pitch)]
 if year==2026:return 75.,75.,75.
 if year==2025:
  ax=math.cos(pitch)*math.cos(yaw);ay=math.cos(pitch)*math.sin(yaw)
  return tuple(150.8125*abs(a)+57.15*math.sqrt(max(0,1-a*a)) for a in (ax,ay))+(math.hypot(150.8125,57.15),)
 nx=math.sin(pitch)*math.cos(yaw);ny=math.sin(pitch)*math.sin(yaw)
 return tuple(152.4*math.sqrt(max(0,1-a*a))+25.4 for a in (nx,ny))+(177.8,)

def certificate(year,q=0,lateral=0,yaw=0,pitch=0,x_error=0,y_error=0,angle_error_deg=0,
                angular_rate_bound_deg_s=0,lateral_speed_bound=0,initial_v_lower=0,accel_bound=0,duration=.02):
 vals=locals().copy()
 for key,v in vals.items():
  if key!='year':finite(v)
 if min(x_error,y_error,angle_error_deg,angular_rate_bound_deg_s,lateral_speed_bound,accel_bound)<0 or not 0<duration<=.5:raise ValueError('nonnegative uncertainty and bounded duration required')
 if abs(q)>200 or abs(lateral)>100 or max(abs(yaw),abs(pitch))>45 or angle_error_deg>20 or angular_rate_bound_deg_s>360 or accel_bound>200000 or abs(initial_v_lower)>3000:raise ValueError('study domain exceeded')
 hx,hy,radius=support(year,yaw,pitch);nomx,nomy=GEOMETRY[year]
 inflation=0 if year==2026 else radius*math.radians(angle_error_deg+angular_rate_bound_deg_s*duration)
 backward=min(0.,initial_v_lower*duration-.5*accel_bound*duration*duration)
 rear=20+q-x_error-(hx+inflation-nomx)+backward
 side=nomy+10-(abs(lateral)+y_error+hy+inflation+lateral_speed_bound*duration)
 return dict(inputs=vals,rotationProjectionInflationMm=inflation,minBackwardDisplacementBoundMm=backward,
  rearGateClearanceLowerBoundMm=rear,sideGuideClearanceLowerBoundMm=side,
  gateAndGuidePermission=rear>=2 and side>=2,requiredClearanceMm=2,
  captureQualified=False,requiresSeparatePadContactLoadAndActuatorEvidence=True)

def report():
 rows=[]
 for y in GEOMETRY:
  for name,kw in [('nominal-exact',{}),('yaw3-near-gate',dict(q=-17.9,yaw=3)),('uncertain-arrival',dict(initial_v_lower=980,accel_bound=104000,x_error=1,y_error=1,angle_error_deg=2)),('uncertain-stationary',dict(accel_bound=104000,x_error=1,y_error=1,angle_error_deg=2)),('rebound-slow-gate',dict(initial_v_lower=-400,duration=.1))]:rows.append(dict(season=y,scenario=name,**certificate(y,**kw)))
 return dict(schema='frc-pose-clearance-contract/v1',status='evaluated-conservative-conditional-clearance-bounds',cases=rows,
  sourceCodeSha256=hashlib.sha256(pathlib.Path(__file__).read_text(encoding='utf-8-sig').encode()).hexdigest(),
  assumptions=['All position/angle/velocity/acceleration/error bounds are hypothetical inputs, not a measured sensor or calibrated mechanism',
   'Angular error parameter bounds total yaw-plus-pitch uncertainty; angular rate bounds total rotation-rate magnitude during closure',
   'Rigid piece support functions and circumsphere angular Lipschitz inflation; known planar floor-resting pose geometry',
   'Gate/guide clearance only; no pad force, swept actuator hardware, moving chassis, capture or release qualification',
   'This is a candidate supervisor contract, not yet wired into the controller; old native counterexamples remain preserved'],calibration=None,engineeringAcceptance='blocked')
if __name__=='__main__':print(json.dumps(report(),indent=2,allow_nan=False))
