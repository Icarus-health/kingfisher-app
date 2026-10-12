import assert from 'node:assert/strict';
import {after,test} from 'node:test';
import {fileURLToPath} from 'node:url';
import {createServer} from 'vite';

const server=await createServer({root:fileURLToPath(new URL('..',import.meta.url)),
  plugins:[{name:'original-source-hooks',enforce:'pre',
    resolveId(id){if(id==='virtual:original-hooks')return '\0'+id;},
    load(id){if(id==='\0virtual:original-hooks')return `
      export const useState=(...args)=>globalThis.__originalDriver.state(...args);
      export const useEffect=(...args)=>globalThis.__originalDriver.effect(...args);`;},
    transform(code,id){if(id.endsWith('/src/ProfileSource.tsx'))return code.replace(/from (["'])react\1/,'from "virtual:original-hooks"');}
  }],server:{middlewareMode:true,watch:null,ws:false,hmr:false},appType:'custom'});
after(()=>server.close());
const {ProfileSource}=await server.ssrLoadModule('/src/ProfileSource.tsx');
const {api}=await server.ssrLoadModule('/src/api.ts');
function nodes(node,predicate,out=[]){if(!node||typeof node!=='object')return out;
  if(predicate(node))out.push(node);for(const child of [node.props?.children].flat(10))nodes(child,predicate,out);return out;}
function uniqueSiblingKeys(node){if(!node||typeof node!=='object')return;
  const children=[node.props?.children].flat(10).filter(c=>c&&typeof c==='object');
  const keys=children.filter(c=>c.key!==null&&c.key!==undefined).map(c=>c.key);
  assert.equal(new Set(keys).size,keys.length,'source controls need distinct sibling identities');
  children.forEach(uniqueSiblingKeys);}
async function opened(props,run){
  const oldApi=api.profileSource,oldWindow=globalThis.window;let reads=0;
  const values=[],effects=[],pending=[];let s=0,e=0;
  const d={state(initial){const i=s++;if(!(i in values))values[i]=initial;return [values[i],next=>values[i]=typeof next==='function'?next(values[i]):next];},
    effect(fn,deps){const i=e++;if(!effects[i]||deps.some((v,j)=>v!==effects[i].deps[j])){effects[i]?.cleanup?.();effects[i]={deps};pending.push(()=>effects[i].cleanup=fn());}},
    render(){s=e=0;globalThis.__originalDriver=d;return ProfileSource({kind:'episode',id:'source-one',...props});},
    runEffects(){pending.splice(0).forEach(fn=>fn());}};
  api.profileSource=async()=>{reads++;return {title:'Synthetic',body:'Original text',state:'new',provenance:{source_ref:'synthetic'},attachment_sources:[{id:'child',title:'Attachment'}],correction_id:'correction'};};
  globalThis.window={setInterval:()=>0,clearInterval:()=>{}};
  try{let tree=d.render();assert.equal(reads,0);nodes(tree,n=>n.type==='button')[0].props.onClick();
    d.render();d.runEffects();await new Promise(setImmediate);tree=d.render();assert.equal(reads,1);await run(tree);}
  finally{effects.forEach(item=>item.cleanup?.());api.profileSource=oldApi;globalThis.window=oldWindow;delete globalThis.__originalDriver;}
}
for(const eigeneFrage of [false,true]){
  test(`source controls have distinct sibling identities (own question: ${eigeneFrage})`,()=>opened({eigeneFrage},tree=>uniqueSiblingKeys(tree)));
  test(`original view mounts no classification or relationship readers (own question: ${eigeneFrage})`,()=>opened({eigeneFrage,originalOnly:true,allowDismiss:true},tree=>{
    assert.equal(nodes(tree,n=>['SourceCategories','SourceBezuege','SourceProject','SourceCorrection'].includes(n.type?.name)).length,0);
    const nested=nodes(tree,n=>n.type===ProfileSource);assert.ok(nested.length>0);
    const text=node=>node===null||node===undefined?'':typeof node==='object'?[node.props?.children].flat(10).map(text).join(''):String(node);
    assert.match(text(tree),/Quelldatum: unbekannt · Erfasst: unbekannt/);
    for(const source of nested){assert.equal(source.props.originalOnly,true);assert.equal(source.props.readOnly,true);}
    assert.equal(nodes(tree,n=>n.type==='button'&&[n.props.children].flat(5).join('').match(/ausschließen|verwerfen|zulassen|berichtigen|verwenden/)).length,0);
  }));
}
