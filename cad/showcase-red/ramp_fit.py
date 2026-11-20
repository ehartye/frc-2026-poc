"""Check each drawing-defined connection and clearance against the named whole-robot STEP solids."""

import argparse
import hashlib
import json
from pathlib import Path
import sys

from OCP.BRepAlgoAPI import BRepAlgoAPI_Common
from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
from OCP.gp import gp_Trsf, gp_Vec

CAD=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(CAD/"assembly-release"))
from drivetrain_fit import broad,vol
from offline import shape
from ramp_support import parts
from supplier import bounds
from verify_products import products


def inspect(path, issued):
    scene=products(path)
    rows=parts()
    for n,r in rows.items():
        planned=shape({"kind":"profile","points":r["points"],"delta":r["delta"],"holes":[]})
        if issued:
            a=abs(vol(scene[n]));b=abs(vol(planned))
            common=abs(vol(BRepAlgoAPI_Common(scene[n],planned).Shape()))
            if max(a-common,b-common) > 0.025:
                raise ValueError((n,a,b,common))
        else:
            scene[n]=planned
    boxes={n:bounds(s) for n,s in scene.items()}
    hits={}
    for n in rows:
        for m in scene:
            if n==m or not broad(boxes[n],boxes[m]):continue
            v=abs(vol(BRepAlgoAPI_Common(scene[n],scene[m]).Shape()))
            if v>0.025:hits[n+" / "+m]=v
    def seat(a,b,axis):
        readings=[]
        for d in (0,0.01,-0.01):
            t=gp_Trsf();t.SetTranslation(gp_Vec(*(d*i for i in axis)))
            shifted=BRepBuilderAPI_Transform(scene[a],t,False).Shape()
            readings.append(abs(vol(BRepAlgoAPI_Common(shifted,scene[b]).Shape())))
        return {"a":a,"b":b,"direction":axis,"overlapMm3":readings[0],"pressedAreaMm2":readings[1]/0.01,
                "reverseMm3":readings[2]}
    receipts=[]
    for side,s in (("left",1),("right",-1)):
        cheek=side+" intake foundation cheek"
        for rank in ("aft","forward"):
            gusset=side+" ramp bridge "+rank
            receipts.extend([seat(side+" intake ramp",gusset,[0,s,0]),seat(gusset,cheek,[0,s,0])])
        receipts.extend([seat(cheek,"front deck crossmember",[-1,0,0]),
                         seat(cheek,side+" front return",[0,s,0])])
    return {"stepSha256":hashlib.sha256(path.read_bytes()).hexdigest(),"issued":issued,
            "productCount":len(scene),"looseBodyCollisionsMm3":hits,"seats":receipts,
            "passed":not hits and all(r["overlapMm3"]<.001 and r["pressedAreaMm2"]>10
                                      and r["reverseMm3"]<.001 for r in receipts)}


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("source",type=Path);p.add_argument("out",type=Path)
    p.add_argument("--issued",action="store_true");a=p.parse_args()
    result=inspect(a.source,a.issued)
    a.out.write_text(json.dumps(result,indent=2)+"\n",encoding="utf8",newline="\n")
    print(result["passed"],result["looseBodyCollisionsMm3"],[(r["a"],r["b"],round(r["pressedAreaMm2"],2)) for r in result["seats"]])
    raise SystemExit(not result["passed"])
