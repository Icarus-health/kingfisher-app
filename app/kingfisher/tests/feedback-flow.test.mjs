import assert from 'node:assert/strict';
import {after,test} from 'node:test';
import {createServer} from 'vite';
import {testCache} from './testcache.mjs';

const server=await createServer({cacheDir:testCache('feedback-flow'),plugins:[{
 name:'feedback-hooks',enforce:'pre',resolveId(id){if(id==='virtual:feedback-hooks')return '\0'+id;},
 load(id){if(id==='\0virtual:feedback-hooks')return `export const useState=(...a)=>globalThis.__feedbackDriver.state(...a);export const useRef=(...a)=>globalThis.__feedbackDriver.ref(...a);export const useEffect=(...a)=>globalThis.__feedbackDriver.effect(...a);`;},
 transform(code,id){if(id.endsWith('/src/RueckmeldungAnsicht.tsx'))return code.replace(/from (["'])react\1/,'from "virtual:feedback-hooks"');}
}],server:{middlewareMode:true,watch:null,ws:false,hmr:false},appType:'custom'});
after(()=>server.close());
const {StimmtNicht}=await server.ssrLoadModule('/src/RueckmeldungAnsicht.tsx');
const text=n=>n==null?'':typeof n==='object'?[n.props?.children].flat(30).map(text).join(''):String(n);
function nodes(n,p,out=[]){if(!n||typeof n!=='object')return out;if(p(n))out.push(n);for(const c of [n.props?.children].flat(30))nodes(c,p,out);return out;}
const button=(tree,label)=>nodes(tree,n=>n.type==='button'&&text(n)===label)[0];
const tick=async()=>{for(let i=0;i<4;i++)await new Promise(setImmediate);};
async function fixture(run){const states=[],refs=[],effects=[],pending=[];let s=0,r=0,e=0;
 const old={fetch:globalThis.fetch,raf:globalThis.requestAnimationFrame,caf:globalThis.cancelAnimationFrame};const frames=new Map();let nextFrame=0;
 globalThis.requestAnimationFrame=fn=>{frames.set(++nextFrame,fn);return nextFrame;};globalThis.cancelAnimationFrame=id=>frames.delete(id);
 const calls=[];let fail=false,release;
 globalThis.fetch=async(path,init)=>{calls.push({path,body:JSON.parse(init.body)});if(release)await release.promise;return new Response(JSON.stringify(fail?{detail:'Speichern nicht möglich'}:{meldung:{id:'feedback-a'}}),{status:fail?503:201});};
 const d={state(v){const i=s++;if(!(i in states))states[i]=typeof v==='function'?v():v;return[states[i],n=>states[i]=typeof n==='function'?n(states[i]):n];},ref(v){return refs[r++]??={current:v};},effect(fn,deps){const i=e++;if(!effects[i]||deps.some((v,j)=>v!==effects[i].deps[j])){effects[i]?.cleanup?.();effects[i]={deps};pending.push(()=>effects[i].cleanup=fn());}},render(){s=r=e=0;globalThis.__feedbackDriver=d;return StimmtNicht({conversationId:'chat-a',messageId:'message-a'});},run(){pending.splice(0).forEach(fn=>fn());const callbacks=[...frames.values()];frames.clear();callbacks.forEach(fn=>fn());}};
 try{d.render();d.run();await run({d,calls,fail(v){fail=v;},hold(){let resolve;const promise=new Promise(r=>resolve=r);release={promise};return resolve;}});}
 finally{effects.forEach(x=>x.cleanup?.());delete globalThis.__feedbackDriver;globalThis.fetch=old.fetch;globalThis.requestAnimationFrame=old.raf;globalThis.cancelAnimationFrame=old.caf;}
}

test('escape closes feedback without sending and returns keyboard focus; reopening retains draft',()=>fixture(async({d,calls})=>{
 let tree=d.render();button(tree,'Stimmt nicht?').props.onClick();tree=d.render();d.run();
 button(tree,'Falsch').props.onClick();nodes(tree,n=>n.type==='input')[0].props.onChange({target:{value:'Nur ein Korrekturentwurf'}});
 tree=d.render();let prevented=false;tree.props.onKeyDown?.({key:'Escape',preventDefault(){prevented=true;},stopPropagation(){}});
 assert.ok(prevented,'Escape muss das Formular schließen');tree=d.render();const trigger=button(tree,'Stimmt nicht?');assert.ok(trigger);
 let focused=false;trigger.props.ref.current={focus(){focused=true;}};d.run();assert.ok(focused,'Rückweg führt zur ursprünglichen Aktion');
 trigger.props.onClick();tree=d.render();d.run();assert.equal(nodes(tree,n=>n.type==='input')[0].props.value,'Nur ein Korrekturentwurf');
 assert.equal(button(tree,'Falsch').props['aria-pressed'],true);assert.deepEqual(calls,[]);
}));

test('failed save retains selected issue and correction; retry writes feedback only',()=>fixture(async({d,calls,fail})=>{
 button(d.render(),'Stimmt nicht?').props.onClick();let tree=d.render();d.run();button(tree,'Falsch').props.onClick();
 nodes(tree,n=>n.type==='input')[0].props.onChange({target:{value:'Die Frist ist nicht bekannt.'}});
 fail(true);d.render().props.onSubmit({preventDefault(){}});await tick();tree=d.render();
 assert.match(text(tree),/Speichern nicht möglich/);assert.equal(nodes(tree,n=>n.type==='input')[0].props.value,'Die Frist ist nicht bekannt.');
 assert.equal(button(tree,'Falsch').props['aria-pressed'],true);
 fail(false);tree.props.onSubmit({preventDefault(){}});await tick();tree=d.render();
 assert.equal(tree.props.role,'status');assert.match(text(tree),/Meldung gespeichert/);assert.match(text(tree),/Fakten und Abläufe bleiben unverändert/);
 assert.equal(calls.length,2);assert.ok(calls.every(c=>c.path==='/api/v1/rueckmeldungen'));
 assert.deepEqual(calls[1].body,{conversation_id:'chat-a',message_id:'message-a',art:'falsch',richtig:'Die Frist ist nicht bekannt.'});
}));

test('a save in flight cannot be dismissed as though it had been cancelled',()=>fixture(async({d,hold,calls})=>{
 button(d.render(),'Stimmt nicht?').props.onClick();let tree=d.render();d.run();button(tree,'Falsch').props.onClick();
 const release=hold();tree=d.render();tree.props.onSubmit({preventDefault(){}});tree=d.render();
 tree.props.onKeyDown?.({key:'Escape',preventDefault(){},stopPropagation(){}});
 assert.equal(d.render().type,'form');assert.equal(button(d.render(),'Abbrechen').props.disabled,true);
 release();await tick();assert.equal(calls.length,1);assert.equal(d.render().props.role,'status');
}));
