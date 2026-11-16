"""Explicit hypothesis-only 1D mechanism state embedding; no installed-frame inference."""
import pathlib, importlib.util, math, json, hashlib
ROOT=pathlib.Path(__file__).resolve().parents[1]
s=importlib.util.spec_from_file_location('ballistics',ROOT/'scripts/target-local-ballistics.py');b=importlib.util.module_from_spec(s);s.loader.exec_module(b)
PINS=['scripts/mechanism-exit-registration.py','scripts/target-local-ballistics.py','case-studies/target-frame-evidence.json','case-studies/mechanism-exit-world-replay.json']

def season(y):
 if type(y) is not int or y not in (2024,2025,2026):raise ValueError('integer season required')
 return y

def embed(y,x,v,registration):
 season(y);b.finite(x);b.finite(v)
 if not isinstance(registration,dict):raise ValueError('explicit registration required')
 if registration.get('basis')!='hypothetical-rigid-registration' or season(registration.get('season'))!=y:raise ValueError('no installed registration supported')
 if registration.get('units')!='m' or registration.get('from')!='MECHANISM_1D' or registration.get('to')!=f'TARGET_LOCAL_{y}':raise ValueError('frame/units mismatch')
 origin,axes=b.frame(registration['originM'],registration['axes'])
 # axes are mechanism basis vectors expressed in the target-local frame.
 return dict(positionM=[origin[i]+x*axes[0][i] for i in range(3)],velocityMps=[v*axes[0][i] for i in range(3)],basis=registration['basis'],installedRegistration=None,orientation=None,scoring=None)

def parse_exit(line):
 if not isinstance(line,str) or not line.startswith('MECHANISM_EXIT '):raise ValueError('exit record required')
 pairs=[x.split('=') for x in line.split()[1:]]
 expected={'year','initialSpeed','fault','timeS','xM','vxMps','externalReleaseImpulseNs','planeXM','dtS'}
 if any(len(p)!=2 for p in pairs) or len(pairs)!=len(expected) or {p[0] for p in pairs}!=expected:raise ValueError('exit fields mismatch')
 d={k:float(v) for k,v in pairs}
 for v in d.values():b.finite(v)
 if not d['year'].is_integer():raise ValueError('season')
 d['year']=season(int(d['year']))
 if d['fault']!=0 or d['initialSpeed'] not in (.1,.2,.4) or d['timeS']<=0 or d['vxMps']>=0 or d['xM']>=.35 or d['planeXM']!=.35 or d['dtS']!=.002 or d['externalReleaseImpulseNs']!=.2:raise ValueError('outside bounded release inventory')
 return d

def report():
 r=json.loads((ROOT/PINS[-1]).read_text());e=json.loads((ROOT/PINS[2]).read_text());exits=[parse_exit(x) for x in r['mechanismExitObservations']]
 if {(x['year'],x['initialSpeed']) for x in exits}!={(y,v) for y in (2024,2025,2026) for v in (.1,.2,.4)} or len(exits)!=9:raise ValueError('incomplete or duplicate releases')
 spec=importlib.util.spec_from_file_location('world_runner',ROOT/'scripts/run-diagnostic-world.py');runner=importlib.util.module_from_spec(spec);spec.loader.exec_module(runner)
 if set(r['sourceCodeSha256'])!=set(runner.CODE):raise ValueError('replay dependency set mismatch')
 # Verify that the receipt refers to this code/input revision, not relabel stale output.
 for p,h in r['sourceCodeSha256'].items():
  if hashlib.sha256((ROOT/p).read_text(encoding='utf-8-sig').encode()).hexdigest()!=h:raise ValueError('stale world replay input: '+p)
 cases=[]
 for x in exits:
  y=x['year'];speed=abs(x['vxMps']);rise=speed*speed/(2*9.80665)
  target_floor={2024:e['speaker']['lowEdgeAboveAssemblyBottomInch']*.0254,2025:None,2026:(e['hub']['controlledHeightInch']-e['hub']['controlledHeightToleranceInch'])*.0254}[y]
  hypothesis={'season':y,'basis':'hypothetical-rigid-registration','units':'m','from':'MECHANISM_1D','to':f'TARGET_LOCAL_{y}','originM':[0,0,.7],'axes':[[1,0,0],[0,1,0],[0,0,1]]}
  cases.append(dict(**x,exitKind='reverse-release-end-of-step-with-external-impulse',nominalEmbedding=embed(y,x['xM'],x['vxMps'],hypothesis),embeddingHypothesis=hypothesis,maximumRiseAnyRotationM=rise,assumedExitHeightM=.7,requiredCenterHeightForSelectedTargetM=target_floor,centerHeightReachableWithoutAddedEnergy=None if target_floor is None else .7+rise>=target_floor,targetFrameRegistration=None,mechanismGeneratedLaunch=False,nominalComponentPoints=None))
 return dict(schema='frc-mechanism-exit-continuity/v1',worldRunId=r['runId'],cases=cases,sourceCodeSha256={p:hashlib.sha256((ROOT/p).read_text(encoding='utf-8-sig').encode()).hexdigest() for p in PINS},limitations=['Fresh HAL toy-plant state extraction, not hardware or a new launcher','Release requires externally prescribed 0.2 Ns reverse impulse, not motor-generated propulsion','End-of-step samples; no asserted exact crossing time, full-body clearance, orientation or spin','0.7 m height and rigid embedding are explicit hypotheses, not installed or field-registered transforms','Energy ceiling neglects drag and allows every launch direction; only excludes selected elevated goals under these assumptions','CORAL installed trough transform, robot release and other-level exclusions remain unknown','No sensor passage or score emitted'],engineeringAcceptance='blocked')

if __name__=='__main__':
 import argparse
 a=argparse.ArgumentParser();a.add_argument('--output',required=True);p=pathlib.Path(a.parse_args().output)
 with p.open('x',encoding='utf-8') as f:json.dump(report(),f,indent=2,allow_nan=False);f.write('\n')
