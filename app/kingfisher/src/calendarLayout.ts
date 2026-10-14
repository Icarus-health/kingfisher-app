import {calendarWindow, eventsInRange} from './calendarRange.ts';
export type WorkspaceCalendarView = 'Tag'|'Woche'|'Monat'|'Liste'|'Jahr';
type DisplaySource = {source_id?:string;view_source_id?:string};
type Event = DisplaySource & {uid:string;start?:string|null;end?:string|null;all_day?:boolean;source_copies?:Array<{uid:string;source_id:string;source_label:string;view_source_id?:string}>};
export const calendarDisplaySource=(source:DisplaySource)=>source.view_source_id??source.source_id??'unknown';
export const calendarEventKey=(event:Event)=>JSON.stringify([event.source_id||'',event.uid,event.start||'']);
export function calendarColor(id:string):string {
  const colors=['#075268','#95642f','#486e3a','#795497','#a54854','#326c9e','#786128'];
  let hash=0;for(const char of id) hash=(Math.imul(hash,31)+char.charCodeAt(0))|0;
  return colors[(hash>>>0)%colors.length];
}
export function calendarVisibleEvents<T extends Event>(events:T[], selected:Set<string>|null):T[] {
  return selected===null?events:events.filter(event=>(event.source_copies?.length?event.source_copies.map(calendarDisplaySource):[calendarDisplaySource(event)]).some(id=>selected.has(id)));
}
export function calendarWorkspaceWindow(focus:Date, view:WorkspaceCalendarView):{from:Date;until:Date} {
  const from=new Date(focus.getFullYear(),focus.getMonth(),focus.getDate());
  if(view==='Tag'||view==='Liste')return{from,until:new Date(from.getFullYear(),from.getMonth(),from.getDate()+(view==='Tag'?1:7))};
  return calendarWindow(focus,view);
}
export type CalendarPlacement<T>={event:T;startMinute:number;endMinute:number;segmentStart:string;segmentEnd:string;timeLabel:string;column:number;columns:number;continuesBefore:boolean;continuesAfter:boolean};
export const calendarPlacementKey=<T extends Event>(placement:CalendarPlacement<T>)=>JSON.stringify([calendarEventKey(placement.event),placement.segmentStart]);
/** Find constant-offset intervals so skipped/repeated hours never become invented duration. */
function clockIntervals(from:Date,until:Date):Array<[number,number]> {
  const first=+from,last=+until,offset=(stamp:number)=>new Date(stamp).getTimezoneOffset();
  if(offset(first)===offset(last-1))return[[first,last]];
  const cuts=[first];let cursor=first;
  while(cursor<last){
    const probe=Math.min(cursor+3600000,last-1);
    if(offset(cursor)!==offset(probe)){
      let low=cursor,high=probe;
      while(high-low>1){const middle=Math.floor((low+high)/2);if(offset(middle)===offset(low))low=middle;else high=middle;}
      cuts.push(high);cursor=high;
    }else if(probe===last-1)break;else cursor=probe;
  }
  cuts.push(last);return cuts.slice(0,-1).map((cut,index)=>[cut,cuts[index+1]]);
}
const wallTime=(minute:number)=>`${String(Math.floor(minute/60)).padStart(2,'0')}:${String(Math.floor(minute%60)).padStart(2,'0')}`;
/** Visual wall-clock positions; range membership still uses real instants (DST aware). */
export function calendarDayLayout<T extends Event>(events:T[],day:Date):CalendarPlacement<T>[] {
  const from=new Date(day.getFullYear(),day.getMonth(),day.getDate()),until=new Date(day.getFullYear(),day.getMonth(),day.getDate()+1);
  const minute=(value:Date)=>value.getHours()*60+value.getMinutes()+value.getSeconds()/60+value.getMilliseconds()/60000;
  const intervals=clockIntervals(from,until);
  const placements:CalendarPlacement<T>[]=eventsInRange(events,from,until).filter(e=>!e.all_day).flatMap(event=>{
    const start=new Date(event.start!),parsedEnd=event.end?new Date(event.end):null;
    const end=parsedEnd&&Number.isFinite(+parsedEnd)&&parsedEnd>start?parsedEnd:new Date(+start+30*60000);
    return intervals.flatMap(([lower,upper])=>{
      const begin=Math.max(+start,lower),finish=Math.min(+end,upper);if(finish<=begin)return[];
      const startMinute=begin===+from?0:minute(new Date(begin)),endMinute=Math.min(1440,startMinute+(finish-begin)/60000);
      const offset=-new Date(begin).getTimezoneOffset(),absolute=Math.abs(offset);
      const zone=`UTC${offset>=0?'+':'-'}${String(Math.floor(absolute/60)).padStart(2,'0')}:${String(absolute%60).padStart(2,'0')}`;
      return[{event,startMinute,endMinute,segmentStart:new Date(begin).toISOString(),segmentEnd:new Date(finish).toISOString(),timeLabel:`${wallTime(startMinute)}–${wallTime(endMinute)}${intervals.length>1?` ${zone}`:''}`,column:0,columns:1,continuesBefore:begin>+start,continuesAfter:finish<+end}];
    });
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
