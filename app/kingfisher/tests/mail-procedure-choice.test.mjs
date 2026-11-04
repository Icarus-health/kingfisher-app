import assert from 'node:assert/strict';
import {after,test} from 'node:test';
import {createServer} from 'vite';
import {testCache} from './testcache.mjs';
const server=await createServer({cacheDir:testCache('mail-procedure-choice'),plugins:[{
 name:'choice-hooks',enforce:'pre',resolveId(id){if(id==='virtual:choice-hooks')return '\0'+id;},
 load(id){if(id==='\0virtual:choice-hooks')return `export const useState=(...a)=>globalThis.__choiceDriver.state(...a);export const useRef=(...a)=>globalThis.__choiceDriver.ref(...a);export const useEffect=(...a)=>globalThis.__choiceDriver.effect(...a);`;},
 transform(code,id){if(id.endsWith('/src/MailReplySuggestion.tsx'))return code.replace(/from (["'])react\1/,'from "virtual:choice-hooks"');}
}],server:{middlewareMode:true,watch:null,ws:false,hmr:false},appType:'custom'});
after(()=>server.close());
const {MailReplySuggestion}=await server.ssrLoadModule('/src/MailReplySuggestion.tsx');
const text=n=>n==null?'':typeof n==='object'?[n.props?.children].flat(30).map(text).join(''):String(n);
function nodes(n,p,out=[]){if(!n||typeof n!=='object')return out;if(p(n))out.push(n);for(const c of [n.props?.children].flat(30))nodes(c,p,out);return out;}
function driver(props){const states=[],refs=[],effects=[],pending=[];let s=0,r=0,e=0;
 const d={props,state(v){const i=s++;if(!(i in states))states[i]=typeof v==='function'?v():v;return[states[i],n=>states[i]=typeof n==='function'?n(states[i]):n];},ref(v){return refs[r++]??={current:v};},effect(fn,deps){const i=e++;if(!effects[i]||deps.some((v,j)=>v!==effects[i].deps[j])){effects[i]?.cleanup?.();effects[i]={deps};pending.push(()=>effects[i].cleanup=fn());}},render(){s=r=e=0;globalThis.__choiceDriver=d;return MailReplySuggestion(d.props);},run(){pending.splice(0).forEach(fn=>fn());},close(){effects.forEach(x=>x.cleanup?.());delete globalThis.__choiceDriver;}};return d;}
const tick=async()=>{for(let i=0;i<5;i++)await new Promise(setImmediate);};
const choice={token:'opaque-mail-choice',options:[{id:'a',label:'Zunftmail',version:1},{id:'core',label:'Diesmal ohne persönlichen Ablauf'}]};
const button=(tree,label)=>nodes(tree,n=>n.type==='button'&&text(n)===label)[0];
async function fixture(run){const oldWindow=globalThis.window,oldFetch=globalThis.fetch;const requests=[],applied=[];
 globalThis.window={setTimeout,clearTimeout,addEventListener(){},removeEventListener(){}};
 globalThis.fetch=async(_path,init)=>{const body=JSON.parse(init.body);requests.push(body);return new Response(JSON.stringify(body.procedure_choice?{body:'Geprüfter Entwurf',basis:'message_and_instruction',context_token:null,source_status:'unknown',sources:[]}:{procedure_choice:choice}));};
 const d=driver({uid:'mail-a',hasDraft:true,onApply:s=>applied.push(s)});
 try{d.render();d.run();nodes(d.render(),n=>n.type==='input')[0].props.onChange({target:{value:'Schreibe eine Zunftmail.'}});
  button(d.render(),'Antwort vorschlagen').props.onClick();await tick();
  assert.doesNotThrow(()=>d.render(),'Rückfrage ist kein fertiger Entwurf');await run({d,requests,applied});
 }finally{d.close();globalThis.window=oldWindow;globalThis.fetch=oldFetch;}
}
test('mail choice preserves instruction, invokes exact choice and never overwrites draft automatically',()=>fixture(async({d,requests,applied})=>{
 const picker=nodes(d.render(),n=>n.type?.name==='ProcedureChoice')[0];assert.ok(picker);
 assert.equal(button(d.render(),'Antwortentwurf ersetzen'),undefined);
 await picker.props.onChoose(choice.options[0]);await tick();
 assert.deepEqual(requests,[{instruction:'Schreibe eine Zunftmail.'},{instruction:'Schreibe eine Zunftmail.',procedure_choice:{token:choice.token,id:'a'}}]);
 assert.deepEqual(applied,[]);button(d.render(),'Antwortentwurf ersetzen').props.onClick();assert.equal(applied[0].body,'Geprüfter Entwurf');
}));
test('changing instruction or cancelling removes pending choice but retains input',()=>fixture(async({d,requests})=>{
 const picker=nodes(d.render(),n=>n.type?.name==='ProcedureChoice')[0];assert.ok(picker);picker.props.onCancel();
 assert.equal(nodes(d.render(),n=>n.type?.name==='ProcedureChoice').length,0);
 assert.equal(nodes(d.render(),n=>n.type==='input')[0].props.value,'Schreibe eine Zunftmail.');
 button(d.render(),'Antwort vorschlagen').props.onClick();await tick();
 nodes(d.render(),n=>n.type==='input')[0].props.onChange({target:{value:'Anderer Auftrag'}});
 assert.equal(nodes(d.render(),n=>n.type?.name==='ProcedureChoice').length,0);assert.equal(requests.length,2);
}));
test('switching mail clears the old pending choice before it can be submitted',()=>fixture(async({d,requests})=>{
 d.props={...d.props,uid:'mail-b'};d.render();d.run();
 assert.equal(nodes(d.render(),n=>n.type?.name==='ProcedureChoice').length,0);assert.equal(requests.length,1);
}));
