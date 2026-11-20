"""Try assembly omissions on the intended fixed structural path, independently of Fusion group constraints."""
import argparse, hashlib, itertools, json, sys
from pathlib import Path
from OCP.BRepExtrema import BRepExtrema_DistShapeShape
from showcase_contacts import products,route
from offline import shape
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('source',type=Path)
p.add_argument('recipe_dir',type=Path)
p.add_argument('output',type=Path)
p.add_argument('--issued',action='store_true')
args=p.parse_args()
sys.path.insert(0,str(args.recipe_dir.resolve()))
from ramp_support import parts
shapes=products(args.source)
rows=parts()
if not args.issued:
    for n,v in rows.items():
        shapes[n]=shape(dict(kind='profile',points=v['points'],delta=v['delta'],holes=[]))
checks={}
for side in ['left','right']:
    ramp=side+' intake ramp'
    aft=side+' ramp bridge aft'
    fwd=side+' ramp bridge forward'
    cheek=side+' intake foundation cheek'
    frame='front deck crossmember'
    returnrail=side+' front return'
    names=[ramp,aft,fwd,cheek,frame,returnrail]
    gaps={}
    for a,b in itertools.combinations(names,2):
        q=BRepExtrema_DistShapeShape(shapes[a],shapes[b])
        if not q.IsDone():raise ValueError((a,b))
        gaps[(a,b)]=q.Value()
    trials=[]
    for tag,remove,expect in [('complete',[],True),('aft gusset omitted',[aft],True),
        ('forward gusset omitted',[fwd],True),('both gussets omitted',[fwd,aft],False),
        ('support cheek omitted',[cheek],False),('front crossmember omitted',[frame],True),
        ('front return omitted',[returnrail],True)]:
        nodes={n:set() for n in names if n not in remove}
        for (n,m),gap in gaps.items():
            if gap<=.05 and n in nodes and m in nodes:
                nodes[n].add(m)
                nodes[m].add(n)
        paths={n:route(nodes,ramp,n) for n in (frame,returnrail) if n in nodes}
        assert any(paths.values())==expect,(tag,paths)
        trials.append(dict(control=tag,chassisPaths=paths,hasPath=expect))
    checks[side]=trials
report=dict(stepSha256=hashlib.sha256(args.source.read_bytes()).hexdigest(),installedSource=args.issued,
    scope='Nominal geometric closure through the six named structural members on each side, ignoring all moving parts, bumper and geometry outside each chosen path. Omission trials treat omitted parts as unavailable. They do not establish safe single-gusset strength.',checks=checks)
args.output.write_text(json.dumps(report,indent=2)+'\n')
print('Passed',sum(map(len,checks.values())),'path and omission trials.')
