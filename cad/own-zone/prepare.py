"""Prepare native student authoring inputs with no desktop or robot connection."""
import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def box(name, role, lower, upper):
    return {"name": name, "role": role, "shape": "box", "lower": lower, "upper": upper}


def tube(name, start, end, width, height, wall):
    return {"name": name, "role": "structure", "shape": "tube", "start": start,
            "end": end, "width": width, "height": height, "wall": wall}


def cylinder(name, role, start, end, radius):
    return {"name": name, "role": role, "shape": "cylinder", "start": start, "end": end, "radius": radius}


def layout():
    cfg = json.loads((HERE / "layout.json").read_bytes())
    half = cfg["frameOutsideMm"] / 2
    width, height, thickness = cfg["railWidthMm"], cfg["railHeightMm"], cfg["railWallMm"]
    rail_z = cfg["railBaseMm"] + height / 2
    gap = cfg["intakeOpeningMm"] / 2
    shell = half - width / 2
    inside = half - width
    items, proxies, sites = [], [], []
    for sign, side in [(1, "left"), (-1, "right")]:
        items.append(tube(side + " perimeter tube", [-half, sign*shell, rail_z], [half, sign*shell, rail_z], width, height, thickness))
        items.append(tube(side + " front return", [shell, min(sign*gap,sign*inside), rail_z], [shell,max(sign*gap,sign*inside),rail_z], width,height,thickness))
        items.append(box(side+" blue side bumper","bumper-blue",[-half-76,min(sign*half,sign*(half+76)),48],[half+76,max(sign*half,sign*(half+76)),168]))
        items.append(box(side+" blue front bumper","bumper-blue",[half,min(sign*half,sign*gap),48],[half+76,max(sign*half,sign*gap),168]))
    items.append(tube("rear perimeter tube",[-shell,-inside,rail_z],[-shell,inside,rail_z],width,height,thickness))
    items.append(box("rear blue bumper","bumper-blue",[-half-76,-half,48],[-half,half,168]))
    wheel_x,wheel_y=cfg["wheelAxisFromRobotCenterMm"]
    for sx, end in [(1,"front"),(-1,"rear")]:
        for sy, side in [(1,"left"),(-1,"right")]:
            x,y=sx*wheel_x,sy*wheel_y
            # Both supplier horizontal axes point inboard; the columns preserve handedness.
            first,other=([-sx,0,0],[0,-sy,0]) if sx*sy==-1 else ([0,-sy,0],[-sx,0,0])
            rot=[[first[i],int(i==2),other[i]] for i in range(3)]
            site=end+" "+side
            sites.append({"name":site,"rotation":rot,"translation":[x,y,cfg["wheelRadiusMm"]]})
            # Two original spacer blocks meet the inner perimeter face and receive
            # the paired supplier tab holes. Flush outer faces can be attached
            # to the perimeter after the joint detail is qualified.
            def to_robot(source):
                return [sum(row[col]*source[col] for col in range(3))+offset
                        for row,offset in zip(rot,[x,y,cfg["wheelRadiusMm"]])]
            for index in (0,1):
                def oriented(u,v,h):
                    return to_robot([u,h,v] if index==0 else [v,h,u])
                corners=[oriented(u,v,h) for u in (-(inside-wheel_x),-23.5)
                         for v in (51.5,88.5) for h in (40.22,73.4)]
                block=box(site+" module tab spacer "+str(index+1),"structure",
                          [min(p[j] for p in corners) for j in range(3)],
                          [max(p[j] for p in corners) for j in range(3)])
                block["holes"]=[[ *oriented(-31.75,tab,0)[:2],2.65] for tab in (57.15,82.55)]
                items.append(block)
            proxies.append(cylinder(site+" public wheel","wheel",[x,y-13,38.1],[x,y+13,38.1],38.1))
            proxies.append(box(site+" public drive housing","drive",[x-40,y-40,70],[x+40,y+40,115]))
            proxies.append(cylinder(site+" public motor reserve","drive",[x,y,115],[x,y,171.46],29.9))
    return cfg,items,proxies,sites


def main():
    cli=argparse.ArgumentParser(description=__doc__)
    cli.add_argument("plugin",type=Path)
    cli.add_argument("supplier_step",type=Path)
    cli.add_argument("output",type=Path)
    args=cli.parse_args()
    cfg,items,proxies,sites=layout()
    pin=cfg["swerve"]["sha256"]
    if sha(args.supplier_step)!=pin:
        raise ValueError("Supplier STEP differs from the selected revision")
    import sys
    sys.path.insert(0,str(args.plugin.resolve()/"scripts"))
    from component_palette import resolve_palette
    colors=resolve_palette(ROOT)
    assert all(p["role"] in colors for p in items+proxies)
    for record in sites:
        a,b,c=record["rotation"]
        determinant=a[0]*(b[1]*c[2]-b[2]*c[1])-a[1]*(b[0]*c[2]-b[2]*c[0])+a[2]*(b[0]*c[1]-b[1]*c[0])
        assert determinant==1
    args.output.mkdir(exist_ok=True,parents=True)
    job={"items":items,"proxies":proxies,"sites":sites,"palette":colors,"layout":cfg,
         "supplier":str(args.supplier_step.resolve()),"output":str(args.output.resolve())}
    (args.output/"native-job.json").write_text(json.dumps(job,indent=2)+"\n",encoding="utf-8")
    print(f"{len(items)} original components and {len(sites)} supplier placements")

if __name__=="__main__":
    main()
