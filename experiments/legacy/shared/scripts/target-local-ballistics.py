"""Uncalibrated constant-gravity exit-state/target-plane experiments in local frames."""
import math
G=(0.,0.,-9.80665)
def finite(v):
 if isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v):raise ValueError('finite numeric required')
 return v
def vec(v):
 if not isinstance(v,(list,tuple)) or len(v)!=3:raise ValueError('3-vector required')
 return tuple(finite(x) for x in v)
def dot(a,b):return sum(x*y for x,y in zip(a,b))
def cross(a,b):return (a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0])
def frame(origin,axes):
 origin=vec(origin)
 if len(axes)!=3:raise ValueError('three frame axes required')
 axes=[vec(a) for a in axes]
 if any(abs(dot(a,b)-(1 if i==j else 0))>1e-9 for i,a in enumerate(axes) for j,b in enumerate(axes)) or dot(cross(axes[0],axes[1]),axes[2])<1-1e-9:raise ValueError('right-handed orthonormal axes required')
 return origin,axes
def to_local(point,origin,axes):
 origin,axes=frame(origin,axes);point=vec(point);delta=tuple(a-b for a,b in zip(point,origin));return tuple(dot(delta,a) for a in axes)
def position(p,v,t):
 p,v=vec(p),vec(v);finite(t)
 if t<0:raise ValueError('negative time')
 return tuple(p[i]+v[i]*t+.5*G[i]*t*t for i in range(3))
def crossing(p,v,origin,normal,horizon=3.):
 p,v,origin,normal=map(vec,(p,v,origin,normal));finite(horizon)
 if horizon<=0 or abs(dot(normal,normal)-1)>1e-9:raise ValueError('positive horizon and unit normal required')
 a=.5*dot(G,normal);b=dot(v,normal);c=dot(tuple(x-y for x,y in zip(p,origin)),normal)
 if abs(a)<1e-12:roots=[] if abs(b)<1e-12 else [-c/b]
 else:
  d=b*b-4*a*c;roots=[] if d<0 else [(-b-math.sqrt(d))/(2*a),(-b+math.sqrt(d))/(2*a)]
 return [dict(timeS=t,positionM=list(position(p,v,t)),normalVelocityMps=b+2*a*t) for t in sorted(set(roots)) if 0<t<=horizon]
def torus_support(direction,axis=(0,0,1),major=.1524,minor=.0254):
 direction,axis=vec(direction),vec(axis)
 finite(major);finite(minor)
 if major<=0 or minor<=0:raise ValueError('positive torus dimensions')
 if abs(dot(direction,direction)-1)>1e-9 or abs(dot(axis,axis)-1)>1e-9:raise ValueError('unit vectors required')
 return major*math.sqrt(max(0,1-dot(direction,axis)**2))+minor

def hex_projection_margin(x,y,apothem,radius):
 for v in [x,y,apothem,radius]:finite(v)
 if apothem<=0 or radius<=0:raise ValueError('positive dimensions')
 return min(apothem-radius-x*math.cos(math.pi/6+k*math.pi/3)-y*math.sin(math.pi/6+k*math.pi/3) for k in range(6))
