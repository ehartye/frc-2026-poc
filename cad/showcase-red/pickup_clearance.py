"""Move the finite ball along the recorded ground-pickup polyline against the six new plates."""
import argparse,hashlib,json,sys
from pathlib import Path
import numpy as np
from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeEdge
from OCP.BRepExtrema import BRepExtrema_DistShapeShape
from OCP.gp import gp_Pnt
from showcase_contacts import products, bounds, lower_bound
from offline import shape
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('replay',type=Path)
p.add_argument('recipe_dir',type=Path)
p.add_argument('out',type=Path)
p.add_argument('--issued',type=Path)
args=p.parse_args()
sys.path.insert(0,str(args.recipe_dir.resolve()))
from ramp_support import parts
rows=parts()
fixed=products(args.issued) if args.issued else {n:shape(dict(kind='profile',points=r['points'],delta=r['delta'],holes=[])) for n,r in rows.items()}
boxes={n:np.array(bounds(fixed[n])) for n in rows}
rec=json.loads(args.replay.read_bytes())
seq=np.array(rec['mechanismRows'])
cutoff=rec['atPickup']
i=np.searchsorted(seq[:,0],cutoff)
end=seq[i-1]+(seq[i]-seq[i-1])*(cutoff-seq[i-1,0])/(seq[i,0]-seq[i-1,0])
seq=np.vstack([seq[:i],end])
radius=75.057
summary=[]
for offset in (0,-10,10,-25,25,-50,50):
    best=float('inf')
    for a,b in zip(seq,seq[1:]):
        v=a[1:]+[0,offset,0]
        w=b[1:]+[0,offset,0]
        seg=BRepBuilderAPI_MakeEdge(gp_Pnt(*v),gp_Pnt(*w)).Edge()
        bb=np.r_[np.minimum(v,w),np.maximum(v,w)]
        for name in rows:
            if lower_bound(bb,boxes[name])>best:continue
            q=BRepExtrema_DistShapeShape(seg,fixed[name])
            if not q.IsDone():raise ValueError(name)
            if q.Value()<best:
                best=q.Value()
                witness={'part':name,'timeIntervalS':[a[0],b[0]],'centerMm':list(q.PointOnShape1(1).Coord())}
    summary.append(dict(lateralOffsetMm=offset,minSignedSurfaceClearanceMm=round(best-radius,5),**witness))
print([(r['lateralOffsetMm'],r['minSignedSurfaceClearanceMm']) for r in summary])
args.out.write_text(json.dumps(dict(sourceReplaySha256=hashlib.sha256(args.replay.read_bytes()).hexdigest(),recipeSha256=hashlib.sha256((args.recipe_dir/'ramp_support.py').read_bytes()).hexdigest(),issuedStepSha256=hashlib.sha256(args.issued.read_bytes()).hexdigest() if args.issued else None,mode='Exact swept sphere along piecewise-linear pre-pickup centerline through acquisition timestamp, plus prescribed lateral offsets of the same trace. Offset paths have no recomputed contacts or dynamics. Negative means geometric intrusion into the sphere on that path.',radiusMm=radius,cutoffS=cutoff,segments=len(seq)-1,cases=summary),indent=2)+'\n')
