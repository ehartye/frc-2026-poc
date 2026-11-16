"""Original nominal fixture CAD. OCP 8.0.1; mm. No vendor geometry.
Not complete robots, manufacturing drawings or contact/load validation.
Parameters derive from agent-frc21d7853 native-catcher-envelopes and retained-pregrip studies.
"""
import pathlib,argparse,json
from OCP.gp import gp_Pnt,gp_Dir,gp_Ax2
from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox,BRepPrimAPI_MakeCylinder,BRepPrimAPI_MakeTorus,BRepPrimAPI_MakeSphere
from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut
from OCP.STEPControl import STEPControl_Writer,STEPControl_AsIs
from OCP.IFSelect import IFSelect_RetDone
PARAMS={2024:(177.8,177.8,50.8,50.8,24.0125),2025:(150.8125,57.15,114.3,25.4,12.7),2026:(75,75,150,38.1,25.4)}
def box(x,y,z,a,b,c):return BRepPrimAPI_MakeBox(gp_Pnt(x,y,z),a,b,c).Shape()
def build(year,out):
 hx,hy,h,r,w=PARAMS[year];start=400-hx-36;length=2*hx+92
 parts={'floor':box(start,-hy-16,-6,length,2*hy+32,6),'gate':box(400-hx-26,-hy-10,0,6,2*hy+20,h+10),'bumper':box(400+hx,-hy-10,0,6,2*hy+20,h+10)}
 for sign in (-1,1):
  low=-hy-16 if sign<0 else hy+10;cutlow=-hy-17 if sign<0 else hy+9
  parts[f'guide{sign}']=BRepAlgoAPI_Cut(box(start,low,0,length,6,h+10),box(329,cutlow,h/2-20,142,8,40)).Shape()
  parts[f'rollerEnvelope{sign}']=BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(400,sign*(hy+r-1),h/2-w/2),gp_Dir(0,0,1)),r,w).Shape()
 if year==2024:parts['piece']=BRepPrimAPI_MakeTorus(gp_Ax2(gp_Pnt(400,0,h/2),gp_Dir(0,0,1)),152.4,25.4).Shape()
 elif year==2025:
  axis=gp_Ax2(gp_Pnt(400-hx,0,h/2),gp_Dir(1,0,0));parts['piece']=BRepAlgoAPI_Cut(BRepPrimAPI_MakeCylinder(axis,57.15,2*hx).Shape(),BRepPrimAPI_MakeCylinder(axis,50.8,2*hx).Shape()).Shape()
 else:parts['piece']=BRepPrimAPI_MakeSphere(gp_Pnt(400,0,h/2),75).Shape()
 writer=STEPControl_Writer()
 for shape in parts.values():
  if writer.Transfer(shape,STEPControl_AsIs)!=IFSelect_RetDone:raise ValueError('transfer failed')
 out.mkdir(parents=True,exist_ok=True)
 if writer.Write(str(out/f'{year}-original-fixture.step'))!=IFSelect_RetDone:raise ValueError('export failed')
 (out/f'{year}-original-fixture.json').write_text(json.dumps({'season':year,'units':'mm','partsInOrder':list(parts),'parameters':dict(zip(['halfX','halfY','height','rollerRadius','rollerEnvelopeWidth'],PARAMS[year])),'limitations':['Original guide fixture, not complete robot','Rollers are simplified cylindrical envelopes, not vendor CAD','FUEL roller width25.4mm is provisional','Guide slots do not establish support structure or strength','Nominal1mm radial piece interference is not contact calibration','No chassis, motors, rails, opposite supports, fasteners or transmission']} ,indent=2)+'\n')
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--season',type=int,choices=list(PARAMS),required=True);p.add_argument('--output',type=pathlib.Path,required=True);a=p.parse_args();build(a.season,a.output)
