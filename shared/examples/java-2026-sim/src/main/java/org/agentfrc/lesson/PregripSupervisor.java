package org.agentfrc.lesson;
/** Virtual pregrip protocol only. Input validity, force limits and timing are uncalibrated hypotheses.
 * No old side-pad state, physical actuator, watchdog or safe-stop guarantee is reused. */
public final class PregripSupervisor {
 public enum State {WAIT_HELD,CLOSING,GRIPPED,OPENING_GATE,FEED,DONE,FAULT}
 public record Observation(long sequence,double time,boolean nominalPoseValid,boolean bodySupported,boolean gateClosed,double leftRetractionMm,double rightRetractionMm,double leftLoadN,double rightLoadN,double leftRpm,double rightRpm,boolean downstreamExitClear){}
 public record Output(State state,boolean motionEnabled,boolean closeNip,boolean openGate,double feedDuty){}
 private final double requestedFeedDuty;
 public PregripSupervisor(){this(.08);}
 public PregripSupervisor(double duty){if(!Double.isFinite(duty)||duty<0||duty>.8)throw new IllegalArgumentException("feed duty");requestedFeedDuty=duty;}
 private State state=State.WAIT_HELD;private long sequence=-1;private double previous=-1,started,contactSince=-1;private boolean gateCommand;
 private static boolean finite(double v){return Double.isFinite(v);}
 private static boolean valid(Observation o){return o!=null&&o.sequence>=0&&finite(o.time)&&o.time>=0&&finite(o.leftRetractionMm)&&finite(o.rightRetractionMm)&&o.leftRetractionMm>=0&&o.rightRetractionMm>=0&&o.leftRetractionMm<=61&&o.rightRetractionMm<=61&&finite(o.leftLoadN)&&finite(o.rightLoadN)&&o.leftLoadN>=0&&o.rightLoadN>=0&&o.leftLoadN<=100&&o.rightLoadN<=100&&finite(o.leftRpm)&&finite(o.rightRpm)&&Math.abs(o.leftRpm)<=6000&&Math.abs(o.rightRpm)<=6000;}
 private static boolean stopped(Observation o){return Math.abs(o.leftRpm)<=5&&Math.abs(o.rightRpm)<=5;}
 private static boolean grip(Observation o){return o.leftRetractionMm<=.2&&o.rightRetractionMm<=.2&&o.leftLoadN>=1&&o.leftLoadN<=30&&o.rightLoadN>=1&&o.rightLoadN<=30;}
 private Output output(){return new Output(state,state!=State.FAULT,state==State.CLOSING||state==State.GRIPPED||state==State.OPENING_GATE||state==State.FEED,gateCommand,state==State.FEED?requestedFeedDuty:0);}
 private Output fault(){state=State.FAULT;return output();}
 public Output update(double now,Observation o){
  if(state==State.FAULT)return output();
  if(!finite(now)||!valid(o)||o.sequence<=sequence||Math.abs(now-o.time)>1e-6||previous>=0&&(now<=previous||now-previous>.030000001))return fault();
  sequence=o.sequence;previous=now;
  if(state==State.DONE)return output();
  if(state!=State.FEED&&(!o.nominalPoseValid||!o.bodySupported||!stopped(o)))return fault();
  switch(state){
   case WAIT_HELD -> {if(!o.gateClosed||o.leftRetractionMm<59||o.rightRetractionMm<59||o.leftLoadN>.1||o.rightLoadN>.1||o.downstreamExitClear)return fault();state=State.CLOSING;started=now;}
   case CLOSING -> {if(!o.gateClosed||o.downstreamExitClear||now-started>.5)return fault();if(grip(o)){if(contactSince<0)contactSince=now;if(now-contactSince>=.099999999)state=State.GRIPPED;}else contactSince=-1;}
   case GRIPPED -> {if(!o.gateClosed||!grip(o)||o.downstreamExitClear)return fault();gateCommand=true;state=State.OPENING_GATE;started=now;}
   case OPENING_GATE -> {if(!grip(o)||o.downstreamExitClear||now-started>.2)return fault();if(!o.gateClosed)state=State.FEED;}
   case FEED -> {if(o.gateClosed)return fault();if(o.downstreamExitClear){state=State.DONE;}else if(!grip(o)||!o.bodySupported)return fault();}
   default -> {return fault();}
  }
  return output();
 }
}
