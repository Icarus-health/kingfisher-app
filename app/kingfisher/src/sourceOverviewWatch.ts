import type {SourceOverviewData, SourceOverviewState} from './sourceOverviewRows';
type Key=keyof SourceOverviewData;
type Result={key:Key; data?:SourceOverviewData[Key]; failed:boolean; checkedAt:number};
type Readers=Partial<{[K in Key]:(signal:AbortSignal)=>Promise<SourceOverviewData[K]>}>;

// A failed read is not an empty snapshot. Keep the previous data and its read time.
export function adoptSourceResult(state:SourceOverviewState,result:Result):SourceOverviewState {
  return {...state,[result.key]:result.failed ? {...state[result.key],failed:true}
    : {data:result.data,failed:false,checkedAt:result.checkedAt}};
}

/** Visible-only metadata reads. No overlap, no late publication, no retry of actions. */
export function watchSourceOverview({readers,onPart,onBusy=()=>{},visible=true,intervalMs=15000,timeoutMs=15000}: {
  readers:Readers;onPart:(result:Result)=>void;onBusy?:(busy:boolean)=>void;visible?:boolean;intervalMs?:number;timeoutMs?:number;
}) {
  let stopped=false,shown=visible,generation=0;
  let request:{controller:AbortController;done:Promise<void>}|undefined;
  let timer:ReturnType<typeof setTimeout>|undefined;
  const publishable=(version:number)=>!stopped && shown && version===generation;
  function refresh():Promise<void> {
    if(stopped || !shown)return Promise.resolve();
    if(request)return request.done;
    clearTimeout(timer);
    const version=generation,controller=new AbortController();
    const current={controller,done:Promise.resolve()};request=current;onBusy(true);
    const timeout=setTimeout(()=>controller.abort(),timeoutMs);
    current.done=Promise.all(Object.entries(readers).map(async([name,read])=>{
      const key=name as Key;
      try {
        const data=await read(controller.signal);
        if(controller.signal.aborted)throw Error('metadata request aborted');
        if(publishable(version))onPart({key,data,failed:false,checkedAt:Date.now()});
      }catch{
        if(publishable(version))onPart({key,failed:true,checkedAt:Date.now()});
      }
    })).then(()=>{}).finally(()=>{
      clearTimeout(timeout);
      if(request===current)request=undefined;
      if(stopped)return;
      onBusy(false);
      if(!shown)return;
      // A visibility transition may have superseded this read while it was aborting.
      if(version!==generation)void refresh();
      else timer=setTimeout(()=>void refresh(),intervalMs);
    });
    return current.done;
  }
  function setVisible(value:boolean) {
    if(stopped || shown===value)return;
    shown=value;generation++;clearTimeout(timer);
    if(!shown){request?.controller.abort();onBusy(false);}
    else void refresh();
  }
  function stop(){stopped=true;generation++;clearTimeout(timer);request?.controller.abort();}
  void refresh();
  return {refresh,setVisible,stop};
}
