package org.agentfrc.lesson;
import edu.wpi.first.math.geometry.*;
import edu.wpi.first.math.kinematics.*;
/** Integrated preloaded season slice. Ideal kinematic drive/rigid hold, not drivetrain energy or physical sensing. */
public final class SeasonRobotPrototype {
 public record Dock(double time,double x,double y,double heading,double goalX,double goalY,double goalHeading,double maxWheelSpeed,boolean authorized){}
 public record Run(int year,Dock dock,IntegratedPregripPrototype.Result mechanism,double exitX,double exitY,double exitZ,double worldVx,double worldVy,double worldVz,double absoluteExitTime){}
 public static Dock approach(int year,int fault){return approach(year,fault,true);}
 public static Dock approach(int year,int fault,boolean refined){
  if(year!=2024&&year!=2025&&year!=2026||fault<0||fault>2)throw new IllegalArgumentException("scenario");
  double heading=year==2024?Math.PI:0,angle=year==2024?Math.toRadians(50):year==2026?Math.toRadians(60):0,length=year==2025?.15:.3;
  double desiredExitX=year==2024?1.95:year==2025?(refined?.15:.2):-2,goalX=desiredExitX-Math.cos(heading)*(.25+length*Math.cos(angle)),goalY=year==2025?(refined?.08:.11):0;
  var goal=new Pose2d(goalX,goalY,new Rotation2d(heading));var pose=new Pose2d(goalX-1.5*Math.cos(heading),goalY+.1,new Rotation2d(heading+.1));var drive=new DifferentialDriveKinematics(.6);double held=0,peak=0;
  for(int k=0;k<1000;k++){
   double t=k*.02,sampleTime=fault==1?Math.min(t,.28):t;if(t-sampleTime>.03)return new Dock(t,pose.getX(),pose.getY(),pose.getRotation().getRadians(),goalX,goalY,heading,peak,false);
   double dx=goalX-pose.getX(),dy=goalY-pose.getY(),distance=Math.hypot(dx,dy),bearing=Math.atan2(dy,dx),angleError=new Rotation2d(bearing).minus(pose.getRotation()).getRadians();
   double finalError=goal.getRotation().minus(pose.getRotation()).getRadians();double v=distance>.005?Math.min(.8,1.5*distance)*Math.max(0,Math.cos(angleError)):0;double w=Math.max(-1.2,Math.min(1.2,2.5*(distance>.005?angleError:finalError)));
   if(distance<.005&&Math.abs(finalError)<.005){v=0;w=0;held+=.02;}else held=0;
   var wheels=drive.toWheelSpeeds(new ChassisSpeeds(v,0,w));wheels.desaturate(1);peak=Math.max(peak,Math.max(Math.abs(wheels.leftMetersPerSecond),Math.abs(wheels.rightMetersPerSecond)));var actual=drive.toChassisSpeeds(wheels);
   if(fault!=2)pose=pose.exp(new Twist2d(actual.vxMetersPerSecond*.02,0,actual.omegaRadiansPerSecond*.02));
   if(held>=.2)return new Dock(t+.02,pose.getX(),pose.getY(),pose.getRotation().getRadians(),goalX,goalY,heading,peak,true);
  }
  return new Dock(20,pose.getX(),pose.getY(),pose.getRotation().getRadians(),goalX,goalY,heading,peak,false);
 }
 public static Run run(int year,double mass,double volts,int fault){return run(year,mass,volts,fault,true);}
 public static Run run(int year,double mass,double volts,int fault,boolean refined){
  var dock=approach(year,fault,refined);if(!dock.authorized())return new Run(year,dock,null,Double.NaN,Double.NaN,Double.NaN,Double.NaN,Double.NaN,Double.NaN,Double.NaN);
  var mechanism=IntegratedPregripPrototype.run(year,mass,volts,.00005,0,year==2024?.0003:.0005,year==2025?(refined?.04:.08):.6);
  if(mechanism.state()!=PregripSupervisor.State.DONE)throw new IllegalStateException("No completed mechanism exit");
  double h=dock.heading(),a=mechanism.angle(),travel=.25+mechanism.plant().x()*Math.cos(a),height=year==2025?.05715+.01:.7;
  // Mount height is selected so the known straight-guide endpoint reaches the declared height.
  double mountHeight=height-mechanism.length()*Math.sin(a),z=mountHeight+mechanism.plant().x()*Math.sin(a),v=mechanism.plant().speed();
  return new Run(year,dock,mechanism,dock.x()+Math.cos(h)*travel,dock.y()+Math.sin(h)*travel,z,v*Math.cos(a)*Math.cos(h),v*Math.cos(a)*Math.sin(h),v*Math.sin(a),dock.time()+mechanism.finalTime());
 }
}
