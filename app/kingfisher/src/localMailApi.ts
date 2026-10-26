import {request, type MailDetail} from './api';
export type LocalMailItem = {episode_id:string;account_id:string;account_label:string;remote_uid:string|null;sender:string;subject:string;preview:string;date:string|null;recorded_at:string;source_ref:string|null;truncated:boolean;state:string;bereich?:string|null};
export type LocalMailPage = {items:LocalMailItem[];accounts:Array<{id:string;label:string;count:number;last_sync:string|null}>;total:number;offset:number;limit:number;has_more:boolean;detail:string};
export type LocalMailDetail = MailDetail & LocalMailItem & {source_current:boolean;source_digest:string};
export const localMailApi = {
 page: ({q='',account_id,offset=0,limit=40}: {q?:string;account_id?:string;offset?:number;limit?:number},signal?:AbortSignal) => request<LocalMailPage>(`/api/v1/local-mail?${new URLSearchParams({q,offset:String(offset),limit:String(limit),...(account_id!==undefined?{account_id}:{})})}`,{signal}),
 detail: (id:string,signal?:AbortSignal) => request<LocalMailDetail>(`/api/v1/local-mail/${encodeURIComponent(id)}`,{signal}),
};
