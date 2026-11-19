"""Bind each independent STEP solid to its design dimensions and palette role."""
import json
import math
from pathlib import Path
from OCP.Bnd import Bnd_Box
from OCP.BRepBndLib import BRepBndLib
from OCP.IFSelect import IFSelect_RetDone
from OCP.STEPControl import STEPControl_Reader
from OCP.TopAbs import TopAbs_SOLID
from OCP.TopExp import TopExp_Explorer
from prepare import HERE, layout, sha


def expected(part):
    if part["shape"]=="box":
        return part["lower"]+part["upper"]
    a,b=part["start"],part["end"]
    if part["shape"]=="cylinder":
        length=math.dist(a,b)
        offset=[part["radius"]*math.sqrt(max(0,1-((x-y)/length)**2)) for x,y in zip(a,b)]
    else:
        offset=[part["width"]/2 if a[i]==b[i] else 0 for i in range(2)]+[part["height"]/2]
    return [min(x,y)-r for x,y,r in zip(a,b,offset)]+[max(x,y)+r for x,y,r in zip(a,b,offset)]


def main():
    cfg, parts, proxies, sites=layout()
    source=HERE/"own-zone-public.step"
    reader=STEPControl_Reader()
    if reader.ReadFile(str(source))!=IFSelect_RetDone or not reader.TransferRoots():
        raise ValueError("Fusion STEP did not independently reopen")
    explorer=TopExp_Explorer(reader.OneShape(),TopAbs_SOLID)
    remaining=parts+proxies
    solids=[]
    while explorer.More():
        bbox=Bnd_Box()
        BRepBndLib.AddOptimal_s(explorer.Current(),bbox,False,False)
        actual=[*bbox.CornerMin().Coord(),*bbox.CornerMax().Coord()]
        candidates=[p for p in remaining if max(abs(a-b) for a,b in zip(expected(p),actual))<0.001]
        if len(candidates)!=1:
            raise ValueError(f"Expected one matching CAD part for {actual}, found {len(candidates)}")
        part=candidates[0]
        remaining.remove(part)
        solids.append({"id":part["name"],"role":part["role"],"boundsMm":[round(v,4) for v in actual]})
        explorer.Next()
    assert not remaining
    result={"schema":"agent-frc/assembly-appearances@1","sourceSha256":sha(source),"solids":solids}
    (HERE/"appearances.json").write_text(json.dumps(result,indent=2)+"\n")
    native=json.loads((HERE/"fusion-progress.json").read_bytes())
    assert native["stage"]=="complete" and not native["errors"]
    for site in sites:
        evidence=native["supplierSites"][site["name"]]
        assert evidence["descendants"]==74 and abs(evidence["boundsMm"][2])<.001
        assert abs(evidence["boundsMm"][5]-171.46)<.001
    assert len(native["projectParts"])==len(parts)
    print(f"{len(solids)} independent public-solid bounds, {len(parts)} native editable stock parts and {len(sites)} supplier placements")

if __name__=="__main__":
    main()
