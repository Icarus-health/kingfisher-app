import {memoryReturnPath} from './profileReturn';
import type {MemoryAreaNavigation,MemoryAreaView} from './MemoryAreaModel';

type ScrollPosition={x:number;y:number;page:number;directory:number;anchor?:{id:string;offset:number}};
type AreaPosition={view:MemoryAreaView;navigation:MemoryAreaNavigation;selected:string[]};
type Presentation={folders:{selected:string|null;project:string;area:string;sourceArea?:string;sourceListOpen?:boolean;q?:string;offset?:number;limit?:number;documentId?:string|null;documentOpen?:boolean;listScroll?:number};organisations:{members:string[];name:string;editing:string|null};place:{selected:string|null}};
export type MemoryViewPosition={path:string;area?:AreaPosition;scroll?:ScrollPosition}&Partial<Presentation>;
const STATE_KEY='kingfisherMemoryView';
const profileRoute=/^\/memory\/(?:akte|people|projects|registry)\/([^/?#]+)(?:\?[^#]*)?$/;
const safeText=(value:unknown,max:number):value is string=>typeof value==='string'&&value.length<=max&&!/[\\\u0000-\u001f\u007f]/.test(value);
function profilePath(path:string) {
  const match=profileRoute.exec(path);if(!match||!safeText(path,10000))return false;
  try {const id=decodeURIComponent(match[1]);return id!=='.'&&id!=='..'&&safeText(id,2048);}
  catch{return false;}
}
export function memoryListPath(path:string):string|null {
  if(!/^\/memory(?:\?|$)/.test(path)||!safeText(path,4000)||path.includes('#'))return null;
  const query=new URLSearchParams(path.slice('/memory'.length));
  if(!query.has('tab')&&!query.has('area'))query.set('tab','search');
  return memoryReturnPath(new URLSearchParams({return_to:`/memory?${query}`}).toString());
}
function currentListPath() {return typeof window !== 'undefined' && window.location?.pathname==='/memory'?memoryListPath(`/memory${window.location.search}`):null;}
function position(value:unknown):MemoryViewPosition|null {
  if(!value||typeof value!=='object')return null;
  const data=value as MemoryViewPosition;
  if(!safeText(data.path,4000)||memoryListPath(data.path)!==data.path)return null;
  if(data.scroll&&(![data.scroll.x,data.scroll.y,data.scroll.page,data.scroll.directory].every(n=>typeof n==='number'&&Number.isFinite(n)&&n>=0&&n<=1e8)||(data.scroll.anchor&&(!safeText(data.scroll.anchor.id,2048)||!Number.isFinite(data.scroll.anchor.offset)||Math.abs(data.scroll.anchor.offset)>1e8))))return null;
  if(data.folders&&((data.folders.q!==undefined&&!safeText(data.folders.q,200))||(data.folders.offset!==undefined&&(!Number.isSafeInteger(data.folders.offset)||data.folders.offset<0||data.folders.offset>1e8))||(data.folders.limit!==undefined&&(!Number.isInteger(data.folders.limit)||data.folders.limit<1||data.folders.limit>100))||(data.folders.sourceListOpen!==undefined&&typeof data.folders.sourceListOpen!=='boolean')||![data.folders.project,data.folders.area,data.folders.sourceArea??''].every(value=>safeText(value,1000))||(data.folders.selected!==null&&!safeText(data.folders.selected,1000))))return null;
  if(data.folders&&((data.folders.documentId!=null&&!safeText(data.folders.documentId,2048))||(data.folders.documentOpen!==undefined&&typeof data.folders.documentOpen!=='boolean')||(data.folders.listScroll!==undefined&&(!Number.isFinite(data.folders.listScroll)||data.folders.listScroll<0||data.folders.listScroll>1e8))))return null;
  if(data.place&&data.place.selected!==null&&!safeText(data.place.selected,1000))return null;
  if(data.organisations&&(!Array.isArray(data.organisations.members)||data.organisations.members.length>200||!data.organisations.members.every(id=>safeText(id,1000))||!safeText(data.organisations.name,200)||(data.organisations.editing!==null&&!safeText(data.organisations.editing,1000))))return null;
  if(data.area){const a=data.area,n=a.navigation;
    const query=new URLSearchParams(data.path.slice('/memory'.length));
    if((query.get('area')??'work')!==a.view)return null;
    if(!['work','personal','health','finance','other'].includes(a.view)||!n||!Array.isArray(n.history)||!n.history.length||n.history.length>1000||!Number.isInteger(n.index)||n.index<0||n.index>=n.history.length||n.history.some(c=>c!==undefined&&(!Number.isSafeInteger(c)||c<0))||n.cursor!==n.history[n.index]||!Array.isArray(a.selected)||a.selected.length>50||!a.selected.every(id=>safeText(id,1000)))return null;
  }
  return {path:data.path,
    ...(data.area?{area:{view:data.area.view,navigation:{cursor:data.area.navigation.cursor,index:data.area.navigation.index,history:[...data.area.navigation.history]},selected:[...data.area.selected]}}:{}),
    ...(data.folders?{folders:{selected:data.folders.selected,project:data.folders.project,area:data.folders.area,sourceArea:data.folders.sourceArea??'',sourceListOpen:data.folders.sourceListOpen??false,q:data.folders.q??'',offset:data.folders.offset??0,limit:data.folders.limit??25,documentId:data.folders.documentId??null,documentOpen:data.folders.documentOpen??false,listScroll:data.folders.listScroll??0}}:{}),
    ...(data.organisations?{organisations:{members:[...data.organisations.members],name:data.organisations.name,editing:data.organisations.editing}}:{}),
    ...(data.place?{place:{selected:data.place.selected}}:{}),
    ...(data.scroll?{scroll:{x:data.scroll.x,y:data.scroll.y,page:data.scroll.page,directory:data.scroll.directory,...(data.scroll.anchor?{anchor:{id:data.scroll.anchor.id,offset:data.scroll.anchor.offset}}:{})}}:{})};
}
function carriedPosition() {return typeof window==='undefined'?null:position(window.history?.state?.[STATE_KEY]);}
export function readMemoryViewPosition():MemoryViewPosition|null {
  const path=currentListPath(),saved=carriedPosition();return path&&saved?.path===path?saved:null;
}
function write(patch:Partial<MemoryViewPosition>) {
  const path=currentListPath();if(!path||!window.history?.replaceState)return;
  const next={...(readMemoryViewPosition()??{path}),...patch,path};
  window.history.replaceState({...window.history.state,[STATE_KEY]:next},'');
}
export function rememberMemoryArea(view:MemoryAreaView,navigation:MemoryAreaNavigation,selected:string[]) {
  write({area:{view,navigation:{...navigation,history:[...navigation.history]},selected:[...selected]}});
}
export function rememberMemoryPresentation<K extends keyof Presentation>(kind:K,value:Presentation[K]) {write({[kind]:value});}
function captureScroll():ScrollPosition {
  const element=(selector:string)=>typeof document==='undefined'?null:document.querySelector<HTMLElement>(selector);
  const root=element('.memory-page'),directory=element('.memory-directory');
  const bounds=root?.getBoundingClientRect();
  const row=root&&bounds&&Array.from(root.querySelectorAll<HTMLElement>('[data-memory-row]')).find(row=>{
    if(row.getClientRects&&row.getClientRects().length===0)return false;
    const clip=directory?.contains(row)?directory.getBoundingClientRect():bounds;
    const top=Math.max(0,bounds.top,clip.top),bottom=Math.min(window.innerHeight,bounds.bottom,clip.bottom);
    const rect=row.getBoundingClientRect();
    return top<bottom&&rect.bottom>top&&rect.top<bottom;
  });
  return {x:window.scrollX??0,y:window.scrollY??0,page:root?.scrollTop??0,directory:directory?.scrollTop??0,...(row?{anchor:{id:row.dataset.memoryRow!,offset:row.getBoundingClientRect().top}}:{})};
}
/** Carry only presentation state inside this tab's History API. No source bodies, storage or API cache. */
export function memoryNavigationState(target:string):Record<string,unknown> {
  let saved=carriedPosition();const root=currentListPath();
  const targetIsProfile=profilePath(target);
  if(root&&targetIsProfile){saved={...(readMemoryViewPosition()??{path:root}),scroll:captureScroll()};write(saved);}
  if(!saved)return {};
  if(targetIsProfile){const query=target.slice(target.indexOf('?'));return target.includes('?')&&memoryReturnPath(query)===saved.path?{[STATE_KEY]:saved}:{};}
  return memoryListPath(target)===saved.path?{[STATE_KEY]:saved}:{};
}
/** Profile chains retain the original safe memory view rather than replacing it with an entity route. */
export function memoryProfileHref(path:string,kind:'person'|'project'='person'):string {
  if(!profilePath(path)||!safeText(path,8000))return '/memory?tab=people';
  const root=typeof window==='undefined'?null:currentListPath();
  const inProfile=typeof window!=='undefined'&&profilePath(`${window.location.pathname??''}${window.location.search??''}`);
  const profileKind=inProfile?window.location.pathname.startsWith('/memory/projects/')?'project':'person':kind;
  const origin=root??memoryReturnPath(inProfile?window.location.search:'',profileKind);
  const [route,search='']=path.split('?');const query=new URLSearchParams(search);
  query.delete('return_to');query.set('return_to',origin);
  return `${route}?${query}`;
}

/** Restore after current list/source reads settle, and stop immediately if the user starts scrolling. */
export function restoreMemoryScroll(root:HTMLElement|null):()=>void {
  const saved=readMemoryViewPosition();if(!root||!saved?.scroll)return ()=>{};
  const element=root;const wanted=saved.scroll;let stopped=false,frame:number|undefined;
  const observer=typeof MutationObserver==='undefined'?null:new MutationObserver(schedule);
  const resize=typeof ResizeObserver==='undefined'?null:new ResizeObserver(schedule);
  function stop(){if(stopped)return;stopped=true;observer?.disconnect();resize?.disconnect();if(frame!==undefined)window.cancelAnimationFrame(frame);window.clearTimeout(timeout);window.removeEventListener('wheel',stop);window.removeEventListener('touchstart',stop);window.removeEventListener('keydown',stopOnKey);}
  function stopOnKey(event:KeyboardEvent){if(['ArrowUp','ArrowDown','PageUp','PageDown','Home','End',' '].includes(event.key))stop();}
  function attempt(){frame=undefined;if(stopped)return;if(currentListPath()!==saved!.path){stop();return;}
    if(element.matches('[data-memory-loading="true"]')||element.querySelector('[data-memory-loading="true"]'))return;
    const directory=element.querySelector<HTMLElement>('.memory-directory');
    element.scrollTop=Math.min(wanted.page,Math.max(0,element.scrollHeight-element.clientHeight));
    if(directory)directory.scrollTop=Math.min(wanted.directory,Math.max(0,directory.scrollHeight-directory.clientHeight));
    window.scrollTo(wanted.x,wanted.y);
    const anchor=wanted.anchor&&Array.from(element.querySelectorAll<HTMLElement>('[data-memory-row]')).find(row=>row.dataset.memoryRow===wanted.anchor!.id&&(!row.getClientRects||row.getClientRects().length>0));
    if(anchor){const delta=anchor.getBoundingClientRect().top-wanted.anchor!.offset;
      if(wanted.directory>0&&directory)directory.scrollTop+=delta;else if(wanted.page>0)element.scrollTop+=delta;else window.scrollTo(wanted.x,window.scrollY+delta);
    }
    stop();
  }
  function schedule(){if(!stopped&&frame===undefined)frame=window.requestAnimationFrame(attempt);}
  const timeout=window.setTimeout(stop,10000);
  observer?.observe(root,{subtree:true,childList:true,attributes:true});resize?.observe(root);
  window.addEventListener('wheel',stop,{passive:true});window.addEventListener('touchstart',stop,{passive:true});window.addEventListener('keydown',stopOnKey);
  schedule();return stop;
}
