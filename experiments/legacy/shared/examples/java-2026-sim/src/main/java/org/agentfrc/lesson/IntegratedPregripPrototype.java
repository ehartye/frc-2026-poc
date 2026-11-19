package org.agentfrc.lesson;
/** Runnable virtual retained-body -> closure -> gate -> powered exit prototype.
 * Ideal rigid supports, prescribed nip travel/normal force and virtual sensors.
 * Assembly mounting and guide constraint are simulation hypotheses, not installed CAD. */
public final class IntegratedPregripPrototype {
 public record Result(int year,double mass,double volts,double angle,double length,double radius,double inertia,double commandedDuty,double releaseTime,double finalTime,PregripSupervisor.State state,PoweredGuidePlant.Sample plant){}
 public static Result run(int year,double mass,double volts,double dt,int fault){return run(year,mass,volts,dt,fault,.004);}
 public static Result run(int year,double mass,double volts,double dt,int fault,double inertia){return run(year,mass,volts,dt,fault,inertia,year==2025?.08:.6);}
 public static Result run(int year,double mass,double volts,double dt,int fault,double inertia,double requestedDuty){
  if(year!=2024&&year!=2025&&year!=2026)throw new IllegalArgumentException("season");
  if(fault<0||fault>4||!Double.isFinite(dt)||dt<.00001||dt>.0002)throw new IllegalArgumentException("scenario");
  double angle=year==2024?Math.toRadians(50):year==2026?Math.toRadians(60):0;
  double radius=year==2024?.0508:year==2025?.0254:.0381,length=year==2025?.15:.3;
  var plant=new PoweredGuidePlant(new PoweredGuidePlant.Config(mass,radius,inertia,length,angle,15,.8,requestedDuty,volts));
  var controller=new PregripSupervisor(requestedDuty);long seq=0;double now=0,gateRequest=-1,release=-1,commandedDuty=0;boolean gateCommand=false;var sample=plant.sample();
  for(int k=0;k<1000;k++){
   double retraction=Math.max(0,60*(1-now/(fault==4?.41:.35)));double load=retraction<=.2&&fault!=1?15:0;
   boolean gateClosed=gateRequest<0||now-gateRequest<.06||fault==2;
   var observation=new PregripSupervisor.Observation(seq++,now,true,true,gateClosed,retraction,retraction,load,load,0,0,false);
   var output=controller.update(now,observation);
   if(output.openGate()&&!gateCommand){gateRequest=now;gateCommand=true;}
   if(output.state()==PregripSupervisor.State.FAULT)return new Result(year,mass,volts,angle,length,radius,inertia,0,-1,now,output.state(),sample);
   if(output.state()==PregripSupervisor.State.FEED){if(!output.motionEnabled()||!output.openGate())throw new IllegalStateException("Unauthorized drive");if(output.feedDuty()==0)return new Result(year,mass,volts,angle,length,radius,inertia,0,-1,now,output.state(),sample);release=now;commandedDuty=output.feedDuty();plant=new PoweredGuidePlant(new PoweredGuidePlant.Config(mass,radius,inertia,length,angle,15,.8,output.feedDuty(),volts));plant.feed(0);break;}
   now+=.01;
  }
  if(release<0)throw new IllegalStateException("No protocol terminal outcome");
  double nextObservation=.01;
  for(int k=0;k<100000;k++){
   sample=plant.step(dt);
   if(sample.time()+1e-10>=nextObservation||sample.exited()){
    now=release+sample.time();double load=fault==3&&sample.time()>.02?0:15;
    var o=new PregripSupervisor.Observation(seq++,now,true,true,false,0,0,load,load,sample.omega()*60/(2*Math.PI),sample.omega()*60/(2*Math.PI),sample.exited());
    var output=controller.update(now,o);nextObservation+=.01;
    if(output.state()==PregripSupervisor.State.FAULT||output.state()==PregripSupervisor.State.DONE)return new Result(year,mass,volts,angle,length,radius,inertia,commandedDuty,release,now,output.state(),sample);
   }
   if(sample.speed()<-.2)return new Result(year,mass,volts,angle,length,radius,inertia,commandedDuty,release,release+sample.time(),PregripSupervisor.State.FAULT,sample);
  }
  throw new IllegalStateException("Prototype timeout");
 }
}
