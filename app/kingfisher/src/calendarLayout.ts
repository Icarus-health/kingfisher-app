import {calendarWindow, eventsInRange} from './calendarRange.ts';
export type WorkspaceCalendarView = 'Tag'|'Woche'|'Monat'|'Liste'|'Jahr';
type Event = {uid:string;start?:string|null;end?:string|null;all_day?:boolean;source_id?:string;source_copies?:Array<{uid:string;source_id:string;source_label:string}>};
export const calendarEventKey=(event:Event)=>JSON.stringify([event.source_id||'',event.uid,event.start||'']);
export function calendarColor(id:string):string {
  const colors=['#075268','#95642f','#486e3a','#795497','#a54854','#326c9e','#786128'];
  let hash=0;for(const char of id) hash=(Math.imul(hash,31)+char.charCodeAt(0))|0;
  return colors[(hash>>>0)%colors.length];
}
export function calendarVisibleEvents<T extends Event>(events:T[], selected:Set<string>|null):T[] {
  return selected===null?events:events.filter(event=>(event.source_copies?.length?event.source_copies.map(copy=>copy.source_id):[event.source_id||'unknown']).some(id=>selected.has(id)));
}
export function calendarWorkspaceWindow(focus:Date, view:WorkspaceCalendarView):{from:Date;until:Date} {
  const from=new Date(focus.getFullYear(),focus.getMonth(),focus.getDate());
  if(view==='Tag'||view==='Liste')return{from,until:new Date(from.getFullYear(),from.getMonth(),from.getDate()+(view==='Tag'?1:7))};
  return calendarWindow(focus,view);
}
export type CalendarPlacement<T>={event:T;startMinute:number;endMinute:number;column:number;columns:number;continuesBefore:boolean;continuesAfter:boolean};
/** Visual wall-clock positions; range membership still uses real instants (DST aware). */
export function calendarDayLayout<T extends Event>(events:T[],day:Date):CalendarPlacement<T>[] {
  const from=new Date(day.getFullYear(),day.getMonth(),day.getDate()),until=new Date(day.getFullYear(),day.getMonth(),day.getDate()+1);
  const minute=(value:Date)=>value.getHours()*60+value.getMinutes()+value.getSeconds()/60;
  const placements=eventsInRange(events,from,until).filter(e=>!e.all_day).map(event=>{
    const start=new Date(event.start!),parsedEnd=event.end?new Date(event.end):null;
    const end=parsedEnd&&Number.isFinite(+parsedEnd)&&parsedEnd>start?parsedEnd:new Date(+start+30*60000);
    const startMinute=start<from?0:minute(start),endMinute=end>=until?1440:Math.min(1440,Math.max(startMinute+15,minute(end)));
    return{event,startMinute,endMinute,column:0,columns:1,continuesBefore:start<from,continuesAfter:end>until};
  }).sort((a,b)=>a.startMinute-b.startMinute||a.endMinute-b.endMinute||calendarEventKey(a.event).localeCompare(calendarEventKey(b.event)));
  let group:CalendarPlacement<T>[]=[],ends:number[]=[],groupEnd=-1;
  const finish=()=>{for(const item of group)item.columns=Math.max(1,ends.length);group=[];ends=[];};
  for(const item of placements){
    if(item.startMinute>=groupEnd){finish();groupEnd=-1;}
    let lane=ends.findIndex(end=>end<=item.startMinute);if(lane<0)lane=ends.length;
    ends[lane]=item.endMinute;item.column=lane;group.push(item);groupEnd=Math.max(groupEnd,item.endMinute);
  }
  finish();return placements;
}
