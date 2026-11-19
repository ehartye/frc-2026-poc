package org.agentfrc.lesson;
import static org.junit.jupiter.api.Assertions.*;
import org.junit.jupiter.api.*;
class SeasonRobotPrototypeTest {
 @Test void approachDockMechanismAndWorldExit(){for(int y:new int[]{2024,2025,2026})for(double m:(y==2025?new double[]{.498951607,.816466266}:new double[]{y==2024?.235:.215}))for(double volts:new double[]{9,12})for(int plan:(y==2025?new int[]{0,1}:new int[]{1})){
  var r=SeasonRobotPrototype.run(y,m,volts,0,plan==1);assertTrue(r.dock().authorized());assertNotNull(r.mechanism());assertTrue(r.mechanism().plant().exited());assertTrue(r.dock().maxWheelSpeed()<=1.000001);assertTrue(Math.hypot(r.dock().x()-r.dock().goalX(),r.dock().y()-r.dock().goalY())<.005);assertEquals(r.mechanism().plant().speed()*r.mechanism().plant().speed(),r.worldVx()*r.worldVx()+r.worldVy()*r.worldVy()+r.worldVz()*r.worldVz(),1e-10);assertEquals(r.dock().time()+r.mechanism().finalTime(),r.absoluteExitTime());assertEquals(0,r.mechanism().plant().feedEnergy());
  System.out.println("ROBOT_EXIT year="+y+" plan="+plan+" mass="+m+" volts="+volts+" dockTime="+r.dock().time()+" chassisX="+r.dock().x()+" chassisY="+r.dock().y()+" heading="+r.dock().heading()+" exitX="+r.exitX()+" exitY="+r.exitY()+" exitZ="+r.exitZ()+" vx="+r.worldVx()+" vy="+r.worldVy()+" vz="+r.worldVz()+" time="+r.absoluteExitTime()+" speed="+r.mechanism().plant().speed()+" residual="+r.mechanism().plant().energyResidual()+" angle="+r.mechanism().angle()+" length="+r.mechanism().length()+" radius="+r.mechanism().radius()+" inertia="+r.mechanism().inertia()+" duty="+r.mechanism().commandedDuty());
 }}
 @Test void stalePoseAndImmobilizedDriveCannotLaunch(){for(int y:new int[]{2024,2025,2026})for(int fault:new int[]{1,2}){var r=SeasonRobotPrototype.run(y,.5,12,fault);assertFalse(r.dock().authorized());assertNull(r.mechanism());assertTrue(Double.isNaN(r.absoluteExitTime()));}}
 @Test void invalidSeasonRejected(){assertThrows(IllegalArgumentException.class,()->SeasonRobotPrototype.approach(2023,0));}
 @AfterAll static void binding()throws Exception{
  String token=System.getenv("FRC_ROBOT_RUN_ID"),output=System.getenv("FRC_ROBOT_RUNTIME");if(token==null&&output==null)return;assertNotNull(token);assertNotNull(output);var p=new java.util.Properties();p.setProperty("runId",token);
  for(String n:new String[]{"SeasonRobotPrototype","SeasonRobotPrototype$Dock","SeasonRobotPrototype$Run","SeasonRobotPrototypeTest","IntegratedPregripPrototype","IntegratedPregripPrototype$Result","PregripSupervisor","PregripSupervisor$State","PregripSupervisor$Observation","PregripSupervisor$Output","PoweredGuidePlant","PoweredGuidePlant$Config","PoweredGuidePlant$Sample","SharedSupply","SharedSupply$Result"}){Class<?> c=Class.forName("org.agentfrc.lesson."+n);p.setProperty(n+"Sha256",java.util.HexFormat.of().formatHex(java.security.MessageDigest.getInstance("SHA-256").digest(c.getResourceAsStream(n+".class").readAllBytes())));}
  var c=edu.wpi.first.math.system.plant.DCMotor.class;p.setProperty("DCMotorSha256",java.util.HexFormat.of().formatHex(java.security.MessageDigest.getInstance("SHA-256").digest(c.getResourceAsStream("DCMotor.class").readAllBytes())));
  try(var out=java.nio.file.Files.newOutputStream(java.nio.file.Path.of(output),java.nio.file.StandardOpenOption.CREATE_NEW)){p.store(out,"Fresh ideal-drive season robot slice");}System.out.println("ROBOT_RUN_ID="+token);
 }
}
