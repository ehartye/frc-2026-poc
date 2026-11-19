"""Fresh atomic execution receipt for the separate powered guide model."""
import pathlib,hashlib,json,subprocess,os,uuid,tempfile,xml.etree.ElementTree as ET
ROOT=pathlib.Path(__file__).resolve().parents[1]
CODE=['examples/java-2026-sim/src/main/java/org/agentfrc/lesson/IntegratedPregripPrototype.java','examples/java-2026-sim/src/main/java/org/agentfrc/lesson/PregripSupervisor.java','scripts/run-integrated-prototype.py','examples/java-2026-sim/build.gradle','examples/java-2026-sim/src/main/java/org/agentfrc/lesson/PoweredGuidePlant.java','examples/java-2026-sim/src/main/java/org/agentfrc/lesson/SharedSupply.java','examples/java-2026-sim/src/test/java/org/agentfrc/lesson/IntegratedPregripPrototypeTest.java']
CLASSES=['IntegratedPregripPrototype','IntegratedPregripPrototype$Result','PregripSupervisor','PregripSupervisor$State','PregripSupervisor$Observation','PregripSupervisor$Output','PoweredGuidePlant','PoweredGuidePlant$Config','PoweredGuidePlant$Sample','SharedSupply','SharedSupply$Result','IntegratedPregripPrototypeTest']
TESTS={'zeroAndChangedDemandReachThePlant()','allSeasonRuntimeExitsAndTimestepSensitivity()','missingContactAndGateFeedbackNeverFeed()','lostGripTerminatesWithoutClaimingPhysicalStop()','invalidScenariosRejected()'}
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def pins():return {n:hashlib.sha256((ROOT/n).read_text(encoding='utf-8-sig').encode()).hexdigest() for n in CODE}
def run(out,jdk,cache):
 out=pathlib.Path(out).resolve();java=pathlib.Path(jdk)/'bin/java.exe'
 if out.exists() or not java.is_file() or not pathlib.Path(cache).is_dir():raise ValueError('fresh output and existing toolchain required')
 out.parent.mkdir(parents=True,exist_ok=True);pending=pathlib.Path(tempfile.mkdtemp(prefix=out.name+'-pending-',dir=out.parent));token=str(uuid.uuid4());before=pins();project=ROOT/'examples/java-2026-sim'
 env=os.environ.copy();env.update(JAVA_HOME=jdk,GRADLE_USER_HOME=cache,FRC_PROTOTYPE_RUN_ID=token,FRC_PROTOTYPE_RUNTIME=str(pending/'runtime.properties'));env['PATH']=str(java.parent)+os.pathsep+env['PATH']
 with (pending/'gradle.log').open('w') as log:r=subprocess.run([str(project/'gradlew.bat'),'test','--tests','org.agentfrc.lesson.IntegratedPregripPrototypeTest','--offline','--no-daemon','--rerun-tasks'],cwd=project,env=env,stdout=log,stderr=subprocess.STDOUT)
 if r.returncode:raise RuntimeError('native test failure; diagnostics retained')
 runtime={line.split('=',1)[0]:line.split('=',1)[1] for line in (pending/'runtime.properties').read_text().splitlines() if '=' in line and not line.startswith('#')}
 classes={n:sha(project/f'build/classes/java/{"test" if n=="IntegratedPregripPrototypeTest" else "main"}/org/agentfrc/lesson/{n}.class') for n in CLASSES}
 if before!=pins() or runtime.get('runId')!=token or any(runtime.get(n+'Sha256')!=h for n,h in classes.items()):raise ValueError('stale runtime or changed inputs')
 # Pin the actual vendor motor implementation loaded by this run, not a guessed motor table.
 import zipfile
 jars=list(pathlib.Path(cache).glob('caches/modules-2/files-2.1/edu.wpi.first.wpimath/wpimath-java/2026.2.1/*/*.jar'))
 if len(jars)!=1:raise ValueError('ambiguous WPIMath runtime')
 with zipfile.ZipFile(jars[0]) as z:dc=hashlib.sha256(z.read('edu/wpi/first/math/system/plant/DCMotor.class')).hexdigest()
 if runtime.get('DCMotorSha256')!=dc:raise ValueError('motor implementation mismatch')
 classes['DCMotor']=dc
 xml=(project/'build/test-results/test/TEST-org.agentfrc.lesson.IntegratedPregripPrototypeTest.xml').read_bytes();tree=ET.fromstring(xml)
 if {n.get('name') for n in tree.findall('testcase')}!=TESTS or tree.get('tests')!=str(len(TESTS)) or any(tree.get(k)!='0' for k in ['failures','errors','skipped']):raise ValueError('incomplete tests')
 if sum((node.text or '').splitlines().count('PROTOTYPE_RUN_ID='+token) for node in tree.findall('system-out'))!=1:raise ValueError('XML run binding mismatch')
 (pending/'tests.xml').write_bytes(xml);observations=[l.strip() for node in tree.findall('system-out') for l in (node.text or '').splitlines() if l.strip().startswith('PROTOTYPE_EXIT ')]
 if len(observations)!=32:raise ValueError('exit inventory')
 report=dict(schema='frc-integrated-prototype-run/v1',runId=token,tests=sorted(TESTS),sourceCodeSha256=before,runtimeClassSha256=classes,wpimathJarSha256=sha(jars[0]),javaExecutableSha256=sha(java),artifactsSha256={n:sha(pending/n) for n in ['runtime.properties','tests.xml','gradle.log']},observations=observations,physicalRobotIoExecuted=False,calibration=None,engineeringAcceptance='blocked')
 (pending/'receipt.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n');pending.rename(out);return report
if __name__=='__main__':
 import argparse
 a=argparse.ArgumentParser();a.add_argument('--output',required=True);a.add_argument('--java-home',required=True);a.add_argument('--gradle-home',required=True);v=a.parse_args();print(json.dumps(run(v.output,v.java_home,v.gradle_home),indent=2))
