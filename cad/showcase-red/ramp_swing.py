"""Continuous clearance bound for the moving original intake versus the proposed fixed supports."""
import argparse, hashlib, json, math, sys
from pathlib import Path
from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
from OCP.BRepExtrema import BRepExtrema_DistShapeShape
from OCP.gp import gp_Trsf,gp_Ax1,gp_Pnt,gp_Dir
from showcase_contacts import products,bounds,lower_bound,np
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('source_step',type=Path)
parser.add_argument('recipe_dir',type=Path)
parser.add_argument('output',type=Path)
parser.add_argument('--issued',action='store_true')
args=parser.parse_args()
sys.path.insert(0,str(args.recipe_dir.resolve()))
from ramp_support import parts
from offline import shape
source=products(args.source_step)
recipe=parts()
fixed={n:(source[n] if args.issued else shape(dict(kind='profile',points=v['points'],delta=v['delta'],holes=[]))) for n,v in recipe.items()}
fixed_bounds={n:np.array(bounds(s)) for n,s in fixed.items()}
pivot=gp_Ax1(gp_Pnt(275,0,240),gp_Dir(0,1,0))
moving=['ground intake roller']+[side+' intake '+part for side in ('left','right') for part in ('bearing arm','journal')]
def rotate(s,deg):
    t=gp_Trsf()
    t.SetRotation(pivot,math.radians(84-deg))
    return BRepBuilderAPI_Transform(s,t,False).Shape()
result={}
for n in moving:
    s=source[n]
    b=bounds(s)
    R=max(math.hypot(x-275,z-240) for x in [b[0],b[3]] for z in [b[2],b[5]])
    best=math.inf
    for angle in range(-39,85,3):
        obj=rotate(s,angle)
        bb=np.array(bounds(obj))
        for fn,fs in fixed.items():
            if lower_bound(bb,fixed_bounds[fn])>=best:continue
            q=BRepExtrema_DistShapeShape(obj,fs)
            if not q.IsDone():raise ValueError((n,fn,angle))
            if q.Value()<best:
                best=q.Value()
                limiting=dict(angleDeg=angle,fixedPart=fn)
    # Every unsampled position is within 1.5 degrees of an evaluated sample.
    error=2*R*math.sin(math.radians(.75))
    result[n]=dict(minSampledMm=best,continuousLowerBoundMm=max(0.,best-error),maxRadialDistanceMm=R,**limiting)
report=dict(stepSha256=hashlib.sha256(args.source_step.read_bytes()).hexdigest(),
    recipeSha256=hashlib.sha256((args.recipe_dir/'ramp_support.py').read_bytes()).hexdigest(),
    installedSource=args.issued,rotationAxisMm=[275,0,240],parkAngleDeg=84,captureAngleDeg=-39,sampleDegrees=3,
    scope='Legacy roller and both bearing arms and journals vs six stationary repair plates. Continuous rigid rotation bound via farthest bounding-box radius. Does not validate unrelated original moving components against the chassis.',clearance=result)
args.output.write_text(json.dumps(report,indent=2)+'\n')
print({n:round(r['continuousLowerBoundMm'],3) for n,r in result.items()})
