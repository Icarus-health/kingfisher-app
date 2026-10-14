import {useEffect,useState} from 'react';
import {workspaceViewApi,type ViewOverview} from './workspaceViewApi';
type Snapshot={overview:ViewOverview|null;error:boolean};
let snapshot:Snapshot={overview:null,error:false};
const subscribers=new Set<(value:Snapshot)=>void>();
let requestVersion=0;
let pending:Promise<void>|null=null;
function publish(value:Snapshot) {snapshot=value;subscribers.forEach(subscriber=>subscriber(value));}
async function refresh() {
  if(pending)return pending;
  const version=++requestVersion;
  pending=(async()=>{
    try{const overview=await workspaceViewApi.overview();if(version===requestVersion)publish({overview,error:false});}
    catch{if(version===requestVersion)publish({...snapshot,error:true});}
    finally{if(version===requestVersion)pending=null;}
  })();
  return pending;
}
function changed() {
  // A save during a read must trigger a fresh read after that read completes.
  if(pending)void pending.then(()=>refresh());else void refresh();
}
export function useWorkspaceMemoryView() {
  const [value,setValue]=useState(snapshot);
  useEffect(()=>{
    subscribers.add(setValue);setValue(snapshot);
    if(subscribers.size===1){window.addEventListener('workspace-view-changed',changed);void refresh();}
    return()=>{
      subscribers.delete(setValue);
      if(!subscribers.size){window.removeEventListener('workspace-view-changed',changed);++requestVersion;pending=null;snapshot={overview:null,error:false};}
    };
  },[]);
  return {...value,refresh};
}
