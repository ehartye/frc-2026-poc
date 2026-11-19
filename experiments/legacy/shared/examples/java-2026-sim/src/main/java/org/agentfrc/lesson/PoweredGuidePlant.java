package org.agentfrc.lesson;
import edu.wpi.first.math.system.plant.DCMotor;
/** Separate hypothetical equal opposed rollers and straight frictionless guide.
 * No normal-force actuator, geometry compliance, piece rotation or hardware acceptance. */
public final class PoweredGuidePlant {
 public record Config(double mass,double radius,double inertiaEach,double length,double angle,double normalEach,double mu,double duty,double supplyVolts) {
  public Config {if(!valid(mass,.2,.82)||!valid(radius,.025,.051)||!valid(inertiaEach,.0001,.006)||!valid(length,.05,.6)||!valid(angle,0,Math.PI/2)||!valid(normalEach,0,50)||!valid(mu,0,1)||!valid(duty,0,.8)||!valid(supplyVolts,9,12))throw new IllegalArgumentException("Hypothesis domain");}
 }
 public record Sample(double time,double x,double speed,double omega,double motorWork,double frictionLoss,double feedEnergy,double energyResidual,boolean exited){}
 private static final DCMotor MOTOR=DCMotor.getNEO(1);
 private final Config c;private double[] q=new double[5];private double time,feedEnergy;private boolean feeding,exited;
 public PoweredGuidePlant(Config c){this.c=java.util.Objects.requireNonNull(c);}
 static boolean valid(double x,double lo,double hi){return Double.isFinite(x)&&x>=lo&&x<=hi;}
 public void feed(double speed){if(feeding||exited||!valid(speed,0,.4))throw new IllegalArgumentException("Single bounded feed");feeding=true;q[1]=speed;feedEnergy=.5*c.mass*speed*speed;}
 /** Separate transfer API. Preserves wheel state and the already-running clock.
  * Only horizontal guides and matching body mass are supported; no implicit velocity turn. */
 public void acceptHorizontalHandoff(double mass,double speed,double inheritedTime){
  if(feeding||exited||!valid(speed,0,.5)||!valid(inheritedTime,0,10)||Math.abs(time-inheritedTime)>1e-8||!Double.isFinite(mass)||mass!=c.mass||c.angle!=0)throw new IllegalArgumentException("Incompatible continuous handoff");
  feeding=true;q[1]=speed;feedEnergy=.5*mass*speed*speed;
 }
 private double[] derivative(double[] a){
  var s=SharedSupply.solve(c.supplyVolts,.02,new double[]{c.duty,c.duty},new double[]{a[2]/MOTOR.KvRadPerSecPerVolt,a[2]/MOTOR.KvRadPerSecPerVolt},new double[]{MOTOR.rOhms,MOTOR.rOhms});
  double torque=2*MOTOR.KtNMPerAmp*s.armatureAmps()[0],slip=c.radius*a[2]-a[1];
  double force=feeding?2*c.mu*c.normalEach*Math.tanh(slip/.05):0;
  return new double[]{feeding?a[1]:0,feeding?force/c.mass-9.80665*Math.sin(c.angle):0,(torque-force*c.radius)/(2*c.inertiaEach),torque*a[2],force*slip};
 }
 private static double[] stage(double[] a,double[] d,double h){double[] r=a.clone();for(int i=0;i<r.length;i++)r[i]+=h*d[i];return r;}
 private double[] integrate(double[] a,double h){var k1=derivative(a);var k2=derivative(stage(a,k1,h/2));var k3=derivative(stage(a,k2,h/2));var k4=derivative(stage(a,k3,h));double[] r=a.clone();for(int i=0;i<r.length;i++)r[i]+=h*(k1[i]+2*k2[i]+2*k3[i]+k4[i])/6;return r;}
 public Sample step(double dt){
  if(exited||!valid(dt,.00001,.0002))throw new IllegalArgumentException("Integration domain or already exited");
  var next=integrate(q,dt);double h=dt;
  if(feeding&&q[0]<c.length&&next[0]>=c.length){double lo=0,hi=dt;for(int k=0;k<45;k++){double mid=(lo+hi)/2;if(integrate(q,mid)[0]>=c.length)hi=mid;else lo=mid;}h=hi;next=integrate(q,h);exited=true;}
  for(double x:next)if(!Double.isFinite(x))throw new IllegalStateException("Nonfinite state");
  if(Math.abs(next[1])>30||Math.abs(next[2])>1000||next[0]<-.2)throw new IllegalStateException("Fixture state outside bounded domain");
  q=next;time+=h;return sample();
 }
 public Sample sample(){double energy=.5*c.mass*q[1]*q[1]+c.inertiaEach*q[2]*q[2]+c.mass*9.80665*q[0]*Math.sin(c.angle);return new Sample(time,q[0],q[1],q[2],q[3],q[4],feedEnergy,energy+q[4]-q[3]-feedEnergy,exited);}
}
