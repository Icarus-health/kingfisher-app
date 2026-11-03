// Trusted stdin-only child; HTTP callers cannot supply this configuration.
import {runHarness} from './harness_run.mjs';
try {
 let raw='';
 for await(const chunk of process.stdin){raw+=chunk;if(raw.length>16000)throw new Error('input bound');}
 const result=await runHarness(JSON.parse(raw));
 process.stdout.write(JSON.stringify(result));
 if(result.status!=='complete')process.exitCode=1;
} catch(_error){process.stdout.write(JSON.stringify({status:'failed',error:'HarnessWorkerFailed',syntheticOnly:true}));process.exitCode=1;}
