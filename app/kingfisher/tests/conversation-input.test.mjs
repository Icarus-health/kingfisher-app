import assert from 'node:assert/strict';
import {after,test} from 'node:test';
import {fileURLToPath} from 'node:url';
import {createServer} from 'vite';
import {testCache} from './testcache.mjs';
const server=await createServer({cacheDir:testCache('conversation-input.test'),root:fileURLToPath(new URL('..',import.meta.url)),
  plugins:[{name:'conversation-input-hooks',enforce:'pre',
    resolveId(id){if(id==='virtual:input-hooks')return '\0'+id;},
    load(id){if(id==='\0virtual:input-hooks')return `export const useState=(...a)=>globalThis.__inputDriver.state(...a);export const useRef=(...a)=>globalThis.__inputDriver.ref(...a);export const useEffect=(...a)=>globalThis.__inputDriver.effect(...a);`;},
    transform(code,id){if(['/src/CommandBar.tsx','/src/DocumentImport.tsx','/src/ConversationCapture.tsx','/src/useSystem.ts'].some(path=>id.endsWith(path)))return code.replace(/from (["'])react\1/,'from "virtual:input-hooks"');}
  }],server:{middlewareMode:true,watch:null,ws:false,hmr:false},appType:'custom'});
after(()=>server.close());
const {api}=await server.ssrLoadModule('/src/api.ts');
const tick=async()=>{for(let n=0;n<3;n++)await new Promise(setImmediate);};
function nodes(node,type,out=[]){if(!node||typeof node!=='object')return out;if(node.type===type)out.push(node);for(const child of [node.props?.children].flat(10))nodes(child,type,out);return out;}
const byName=(tree,name)=>nodes(tree,'button').find(node=>[node.props.children].flat(5).join('')===name);
async function driver(name,props){
  const Component=(await server.ssrLoadModule(`/src/${name}.tsx`))[name];
  const states=[],refs=[],effects=[],pending=[];let s=0,r=0,e=0;
  const d={props,state(v){const i=s++;if(!(i in states))states[i]=typeof v==='function'?v():v;return [states[i],n=>states[i]=typeof n==='function'?n(states[i]):n];},
    ref(v){return refs[r++]??={current:v};},
    effect(fn,deps){const i=e++;if(!effects[i]||deps.some((v,j)=>v!==effects[i].deps[j])){effects[i]?.cleanup?.();effects[i]={deps};pending.push(()=>effects[i].cleanup=fn());}},
    render(){s=r=e=0;globalThis.__inputDriver=d;return Component(d.props);},
    runEffects(){pending.splice(0).forEach(fn=>fn());},close(){effects.forEach(x=>x.cleanup?.());delete globalThis.__inputDriver;}};
  return d;
}
const voice=()=>({state:{phase:'ready',dictationAvailable:true},cancel(){}});

test('conversation preserves multiple lines until explicit submit and retains failed drafts',async()=>{
  let sent=[],fail=true;const d=await driver('CommandBar',{conversation:true,onSubmit:async text=>{sent.push(text);if(fail)throw Error('offline');}});
  try{let tree=d.render();const field=nodes(tree,'textarea')[0];assert.ok(field);
    field.props.onChange({target:{value:' Erste Zeile\nZweite Zeile '}});
    assert.equal(sent.length,0);await nodes(d.render(),'form')[0].props.onSubmit({preventDefault(){}});
    assert.deepEqual(sent,['Erste Zeile\nZweite Zeile']);assert.match(nodes(d.render(),'textarea')[0].props.value,/Zweite Zeile/);
    fail=false;await nodes(d.render(),'form')[0].props.onSubmit({preventDefault(){}});
    assert.equal(nodes(d.render(),'textarea')[0].props.value,'');
  }finally{d.close();}
});
test('Enter sends; Shift and IME preserve the draft; modified Enter still sends',async()=>{
  const d=await driver('CommandBar',{conversation:true,onSubmit:async()=>{throw Error('not requested');}});
  try{let requests=0,prevented=0;const field=nodes(d.render(),'textarea')[0];
    field.props.onKeyDown({key:'Enter',ctrlKey:false,metaKey:false,preventDefault(){prevented++;},currentTarget:{form:{requestSubmit(){requests++;}}}});
    assert.equal(requests,1);assert.equal(prevented,1);
    for(const nativeEvent of [{isComposing:true},{keyCode:229}]) field.props.onKeyDown({key:'Enter',nativeEvent,preventDefault(){throw Error('IME must keep composing');},currentTarget:{form:{requestSubmit(){throw Error('IME must not submit');}}}});
    field.props.onKeyDown({key:'Enter',shiftKey:true,preventDefault(){throw Error('Shift keeps newline');},currentTarget:{form:{requestSubmit(){throw Error('newline must not submit');}}}});
    field.props.onKeyDown({key:'Enter',ctrlKey:true,metaKey:false,preventDefault(){prevented++;},currentTarget:{form:{requestSubmit(){requests++;}}}});
    assert.equal(requests,2);assert.equal(prevented,2);
  }finally{d.close();}
});
test('a dictated addition only changes the editable draft; recording and disabled state block send',async()=>{
  let sends=0;const v=voice();const d=await driver('CommandBar',{conversation:true,voice:v,onSubmit:async()=>sends++});
  try{const tree=d.render();const controls=[nodes(tree,'form')[0].props.children].flat().find(n=>n?.type?.name==='VoiceDraftControls');
    assert.ok(controls);controls.props.onDraft('Diktierter Entwurf\nmit Zeile');assert.equal(sends,0);
    v.state={...v.state,phase:'listening'};await nodes(d.render(),'form')[0].props.onSubmit({preventDefault(){}});assert.equal(sends,0);
    v.state={...v.state,phase:'ready'};d.props={...d.props,disabled:true};await nodes(d.render(),'form')[0].props.onSubmit({preventDefault(){}});assert.equal(sends,0);
  }finally{d.close();}
});
test('home search keeps its existing single-line input',async()=>{
  const d=await driver('CommandBar',{onSubmit:async()=>{}});try{assert.equal(nodes(d.render(),'input').length,1);assert.equal(nodes(d.render(),'textarea').length,0);}finally{d.close();}
});
test('conversation capture stays closed without mounting any file importer',async()=>{
  const d=await driver('ConversationCapture',{});try{
    const tree=d.render();assert.equal([tree.props.children].flat().some(n=>n?.type?.name==='DocumentImport'),false);
    byName(tree,'Datei oder Transkript aufnehmen').props.onClick();
    const importer=[d.render().props.children].flat().find(n=>n?.type?.name==='DocumentImport');
    assert.ok(importer);assert.equal(importer.props.initiallyExpanded,true);assert.equal(importer.props.showLibrary,false);
    importer.props.onClose();assert.equal([d.render().props.children].flat().some(n=>n?.type?.name==='DocumentImport'),false);
  }finally{d.close();}
});
test('conversation file selection previews locally; only explicit save records the source',async()=>{
  const old={projects:api.projects,importDocument:api.importDocument};let writes=[];
  api.projects=async()=>[];api.importDocument=async body=>{writes.push(body);return {id:'e-synthetic',created:true,title:body.filename,project_id:null};};
  const d=await driver('DocumentImport',{initiallyExpanded:true,showLibrary:false,onClose(){}});
  try{let tree=d.render();d.runEffects();await tick();tree=d.render();
    const field=nodes(tree,'input').find(n=>n.props.type==='file');assert.ok(field);
    field.props.onChange({target:{files:[new File(['Besprechung\nNächste Schritte'], 'notizen.txt')],value:'file'}});await tick();
    assert.equal(writes.length,0);assert.ok(byName(d.render(),'Datei als Quelle aufnehmen'));
    byName(d.render(),'Datei als Quelle aufnehmen').props.onClick();await tick();
    assert.deepEqual(writes,[{filename:'notizen.txt',body:'Besprechung\nNächste Schritte',project_id:null}]);
  }finally{d.close();Object.assign(api,old);}
});

test('closing a ready file preview needs an explicit discard; keeping it preserves the unsaved text',async()=>{
  const old=api.projects;api.projects=async()=>[];let closed=0;
  const d=await driver('DocumentImport',{initiallyExpanded:true,showLibrary:false,onClose(){closed++;}});
  try{d.render();d.runEffects();await tick();nodes(d.render(),'input').find(n=>n.props.type==='file').props.onChange({target:{files:[new File(['behalten'], 'notizen.txt')],value:'file'}});await tick();
    byName(d.render(),'Schließen').props.onClick();assert.equal(closed,0);
    byName(d.render(),'Weiter bearbeiten').props.onClick();assert.ok(byName(d.render(),'Datei als Quelle aufnehmen'));
    byName(d.render(),'Schließen').props.onClick();byName(d.render(),'Vorschau verwerfen und schließen').props.onClick();assert.equal(closed,1);
  }finally{d.close();api.projects=old;}
});

// A late send result must never discard a newer edit or a different conversation.
test('conversation drafts survive unmount, isolate chats, and clear only the submitted revision',async()=>{
  let resolve;const pending=new Promise(r=>resolve=r);
  const a=await driver('CommandBar',{conversation:true,conversationId:'draft-a',onSubmit:()=>pending});
  let tree=a.render();nodes(tree,'textarea')[0].props.onChange({target:{value:'erster Entwurf'}});
  const sent=nodes(a.render(),'form')[0].props.onSubmit({preventDefault(){}});
  nodes(a.render(),'textarea')[0].props.onChange({target:{value:'nächster Entwurf'}});a.close();
  const b=await driver('CommandBar',{conversation:true,conversationId:'draft-b',onSubmit:async()=>{}});
  try{assert.equal(nodes(b.render(),'textarea')[0].props.value,'');
    nodes(b.render(),'textarea')[0].props.onChange({target:{value:'anderes Gespräch'}});
    resolve();await sent;assert.equal(nodes(b.render(),'textarea')[0].props.value,'anderes Gespräch');
    const restored=await driver('CommandBar',{conversation:true,conversationId:'draft-a',onSubmit:async()=>{}});
    try{assert.equal(nodes(restored.render(),'textarea')[0].props.value,'nächster Entwurf');
      await nodes(restored.render(),'form')[0].props.onSubmit({preventDefault(){}});
      assert.equal(nodes(restored.render(),'textarea')[0].props.value,'');
    }finally{restored.close();}
  }finally{b.close();}
});
test('recording never requests keyboard submit',async()=>{
  const v=voice();v.state.phase='listening';
  const d=await driver('CommandBar',{conversation:true,voice:v,onSubmit:async()=>{throw Error('voice must not submit');}});
  try{nodes(d.render(),'textarea')[0].props.onKeyDown({key:'Enter',ctrlKey:true,preventDefault(){},currentTarget:{form:{requestSubmit(){throw Error('recording must not request submit');}}}});}finally{d.close();}
});
test('two submit events during the same pending send issue only one request',async()=>{
 let resolve,sends=0;const d=await driver('CommandBar',{conversation:true,onSubmit:()=>{sends++;return new Promise(r=>resolve=r);}});
 try{nodes(d.render(),'textarea')[0].props.onChange({target:{value:'einmal'}});const submit=nodes(d.render(),'form')[0].props.onSubmit;
   const first=submit({preventDefault(){}});const second=submit({preventDefault(){}});assert.equal(sends,1);resolve();await Promise.all([first,second]);
 }finally{d.close();}
});
