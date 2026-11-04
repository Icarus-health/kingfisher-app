import type {CalendarOverview} from './api';
import {calendarSourceVersions} from './calendarRange.ts';

export function calendarPreview(previous:CalendarOverview|null,next:CalendarOverview,sameRange:boolean):CalendarOverview {
 if(!sameRange || !previous?.read_context || previous.read_context!==next.read_context || !previous.read_at || !next.failed_sources?.length)return next;
 const failed=new Set(next.failed_sources);
 const freshKeys=new Set(next.items.flatMap(item=>calendarSourceVersions(item).map(copy=>`${copy.uid}|${item.start}`)));
 const retained=previous.items.flatMap(item=>{
  const copies=calendarSourceVersions(item);
  // A successfully read copy supersedes the same proven occurrence.
  if(copies.some(copy=>freshKeys.has(`${copy.uid}|${item.start}`)))return [];
  const remaining=copies.filter(copy=>copy.source_id && failed.has(copy.source_id));
  if(!remaining.length)return [];
  const first=remaining[0];
  return [{...item,...first,source_copies:remaining.map(copy=>({uid:copy.uid,source_id:copy.source_id!,source_label:copy.source_label||'',view_source_id:copy.view_source_id})),
   stale_since:item.stale_since||previous.read_at}];
 });
 return {...next,items:[...next.items,...retained].sort((a,b)=>(a.start||'').localeCompare(b.start||''))};
}

export function calendarPreviewLabel(item:CalendarOverview['items'][number]):string {
 return item.stale_since ? `Stand ${new Date(item.stale_since).toLocaleString('de-DE',{dateStyle:'medium',timeStyle:'short'})} · ungeprüft` : '';
}
