package org.agentfrc.lesson;
/** Ideal averaged bridges; no regeneration, inductance, current limit or thermal state. */
public final class SharedSupply {
 public record Result(double volts,double batteryAmps,double[] armatureAmps,double maxElectricalResidualWatts){}
 public static Result solve(double voc,double rb,double[] duty,double[] emf,double[] resistance){
  boolean[] closed=new boolean[duty.length];java.util.Arrays.fill(closed,true);return solve(voc,rb,duty,emf,resistance,closed);
 }
 public static Result solve(double voc,double rb,double[] duty,double[] emf,double[] resistance,boolean[] closed){
  if(closed.length!=duty.length)throw new IllegalArgumentException("Branch mask domain");
  if(!Double.isFinite(voc)||voc<=0||voc>14||!Double.isFinite(rb)||rb<0||rb>.1||duty.length<1||duty.length>8||emf.length!=duty.length||resistance.length!=duty.length)throw new IllegalArgumentException("Supply domain");
  double a=0,b=0;for(int i=0;i<duty.length;i++){
   if(!Double.isFinite(duty[i])||Math.abs(duty[i])>1||!Double.isFinite(emf[i])||Math.abs(emf[i])>100||!Double.isFinite(resistance[i])||resistance[i]<=0||resistance[i]>10)throw new IllegalArgumentException("Branch domain");
   if(!closed[i]){if(duty[i]!=0)throw new IllegalArgumentException("Open branch requires zero duty");continue;}
   a+=duty[i]*emf[i]/resistance[i];b+=duty[i]*duty[i]/resistance[i];
  }
  double v=(voc+rb*a)/(1+rb*b),ib=0,p=0,residual=0;double[] current=new double[duty.length];
  for(int i=0;i<duty.length;i++){
   if(!closed[i]){current[i]=0;continue;}
   current[i]=(duty[i]*v-emf[i])/resistance[i];double load=duty[i]*current[i];
   if(load < -1e-8)throw new IllegalArgumentException("Unsupported regeneration");
   ib+=load;p+=duty[i]*v*current[i];
   residual=Math.max(residual,Math.abs(duty[i]*v*current[i]-(current[i]*current[i]*resistance[i]+emf[i]*current[i])));
  }
  if(v<0||v>voc+1e-8||!Double.isFinite(ib))throw new IllegalArgumentException("Unsupported supply state");
  residual=Math.max(residual,Math.abs(voc*ib-rb*ib*ib-p));
  if(Math.abs(v-(voc-rb*ib))>1e-8||residual>1e-7)throw new IllegalStateException("Electrical identity failed");
  return new Result(v,ib,current,residual);
 }
}
