"""Check the contact graph of the selected showcase STEP and explicit ramp-to-frame interfaces."""
import argparse
import hashlib
import json
import sys
from collections import deque
from pathlib import Path

import numpy as np
from OCP.BRepExtrema import BRepExtrema_DistShapeShape

HERE = Path(__file__).resolve().parent
repo = next(p for p in (HERE, *HERE.parents) if (p / "cad/assembly-release/contact_audit.py").is_file())
sys.path.insert(0,str(repo / "cad/assembly-release"))
from verify_products import products
from supplier import bounds
from contact_audit import audit

def route(graph, start, target):
    todo = deque([(start,[start])])
    seen = {start}
    while todo:
        n, path = todo.popleft()
        if n == target:
            return path
        for neighbor in sorted(graph[n] - seen):
            seen.add(neighbor)
            todo.append((neighbor,path+[neighbor]))
    return []

def lower_bound(a,b):
    return np.linalg.norm(np.maximum.reduce([a[:3]-b[3:],b[:3]-a[3:],np.zeros(3)]))

def nearest(name, shapes, boxes):
    best = float("inf")
    witnesses = []
    for lb, other in sorted((lower_bound(boxes[name],value), key) for key,value in boxes.items() if key != name):
        if lb > best+1e-5:
            break
        q = BRepExtrema_DistShapeShape(shapes[name], shapes[other])
        if not q.IsDone():
            raise ValueError((name, other))
        gap = q.Value()
        if gap < best-1e-5:
            witnesses = []
            best = gap
        if gap <= best+1e-5:
            witnesses.append(dict(product=other, gapMm=round(gap,5)))
    return witnesses

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("step",type=Path)
    p.add_argument("output",type=Path)
    p.add_argument("--require",action="append",default=[],metavar="PRODUCT")
    p.add_argument("--anchor",required=True)
    p.add_argument("--intake-supports",action="store_true",
                   help="Require each named ramp to retain an independent structural path through each gusset.")
    a=p.parse_args()
    shapes=products(a.step)
    for name in [a.anchor,*a.require]:
        if name not in shapes:
            p.error(f"Missing {name!r}")
    boxes={name:np.array(bounds(s)) for name,s in shapes.items()}
    result=audit([(s,{"id":name,"boundsMm":boxes[name].tolist()}) for name,s in shapes.items()])
    graph={name:set() for name in shapes}
    for pair in result["pairs"]:
        i,j=pair["parts"]
        graph[i].add(j)
        graph[j].add(i)
    detached=[g for g in result["groups"] if a.anchor not in g]
    ramps={name:route(graph,name,a.anchor) for name in a.require}
    structural = []
    if a.intake_supports:
        for side in ("left","right"):
            for rank in ("forward","aft"):
                for frame in ("front deck crossmember",side+" front return"):
                    path=[side+" intake ramp",side+" ramp bridge "+rank,
                          side+" intake foundation cheek",frame]
                    observed=all(b in graph.get(x,()) for x,b in zip(path,path[1:]))
                    structural.append({"path":path,"allEdgesPresent":observed})
    result.update(stepSha256=hashlib.sha256(a.step.read_bytes()).hexdigest(),productCount=len(shapes),
                  anchor=a.anchor,detachedGroups=detached,requiredGeometricPaths=ramps,
                  structuralPathsWithAllOtherProductsExcluded=structural,
                  nearestForIsolated={g[0]:nearest(g[0],shapes,boxes) for g in detached if len(g)==1})
    a.output.write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
    print("Detached groups:",detached,"Required paths:",ramps,flush=True)
    return int(any(not path for path in ramps.values()) or any(not s["allEdgesPresent"] for s in structural))
if __name__=="__main__":
    sys.exit(main())
