import assert from 'node:assert/strict';
import {test} from 'node:test';
import {createServer} from 'vite';
import {fileURLToPath} from 'node:url';
const root=fileURLToPath(new URL('..',import.meta.url));
function nodes(n,p,out=[]){if(!n||typeof n!=='object')return out;if(p(n))out.push(n);for(const c of [n.props?.children].flat(10))nodes(c,p,out);return out;}
function text(n){return n==null?'':typeof n==='object'?[n.props?.children].flat(10).map(text).join(''):String(n);}
test('source-only cutoffs keep their uncertainty, history and original separate from actionable deadlines',async()=>{
 const server=await createServer({root,configFile:false,server:{middlewareMode:true,watch:null,ws:false,hmr:false},plugins:[{name:'source-cutoff-hooks',enforce:'pre',resolveId(id){if(id==='virtual:cutoff-hooks')return '\0'+id;},load(id){if(id==='\0virtual:cutoff-hooks')return 'export const useState=(v)=>globalThis.__cutoffState(v);export const useEffect=()=>{};export const useCallback=f=>f;export const useRef=v=>({current:v});';},transform(code,id){if(id.endsWith('/AkteAbschnitte.tsx'))return code.replace('from "react"','from "virtual:cutoff-hooks"');}}],appType:'custom'});
 const previous=globalThis.__cutoffState;
 try {
  const {AkteAnsicht}=await server.ssrLoadModule('/src/AkteAbschnitte.tsx');
  const source={episode_id:'synthetic-original',titel:'Redaktionsplanung',occurred_at:'2021-07-01T08:00:00Z',recorded_at:'2021-07-01T08:00:00Z',participants:[],text:'Der Stand ist unklar. 18.8. ist Redaktionsschluss. Bitte erst rückfragen.',art:'Unklare Einordnung',datum:'2021-08-18',ausdruck:'18.8.',art_der_angabe:'datum',ersetzt_durch:null,zeitbezug:'vergangen',einordnung:'uncertain',zustaendigkeit:'ungeklaert',nur_quellenangabe:true};
  const data={name:'Nora Beispiel',art:'person',sache:'person:nora',quellen:{gesamt:1,begrenzt:false},berechnung:{offen:0},offen:{eintraege:[],erledigt:{gesamt:0,eintraege:[]}},fristen:{kommend:[],verstrichen:[],ersetzt:[],gesamt:{kommend:0,verstrichen:0,ersetzt:0},ohne_datum:{gesamt:0,eintraege:[]},quellenangaben:{gesamt:1,eintraege:[source]}},stand_der_dinge:{aktuell:null},termine:{kommend:[],vergangen:[]},aufgaben:{eintraege:[]},beteiligte:{gesamt:0,eintraege:[]},verlauf:{gesamt:0,eintraege:[]},einordnung:{offen:0}};
  const render=()=>{let i=0;globalThis.__cutoffState=v=>[i++===0?data:typeof v==='function'?v():v,()=>{}];return AkteAnsicht({sache:data.sache,compact:true});};
  const tree=render();const panel=nodes(tree,n=>n.type==='details'&&n.props.className==='quiet-details akte-quellenfristen')[0];
  assert.ok(panel);assert.equal(Boolean(panel.props.open),false);
  assert.match(text(panel),/Zuständigkeit ungeklärt/);assert.match(text(panel),/keine bestätigten eigenen Aufgaben/);assert.match(text(panel),/Historie/);assert.match(text(panel),/Unklare Einordnung/);
  assert.equal(nodes(panel,n=>n.type==='blockquote')[0].props.children,source.text);
  assert.equal(nodes(panel,n=>n.type?.name==='Quelle')[0].props.zeile.episode_id,'synthetic-original');
  assert.equal(nodes(panel,n=>n.type==='button').length,0,'Source evidence has no accept-task shortcut');
  assert.equal(nodes(tree,n=>n.type?.name==='Teil'&&n.props.titel==='Fristen').length,0);
  delete data.fristen.quellenangaben;
  assert.equal(nodes(render(),n=>n.type==='details'&&n.props.className==='quiet-details akte-quellenfristen').length,0,'Old cached API responses still render');
 }finally{globalThis.__cutoffState=previous;await server.close();}
});
