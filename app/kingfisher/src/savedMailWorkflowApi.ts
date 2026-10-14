import {request, type Task, type TaskCandidate} from './api';
export type SavedMailWorkflowView = {
 episode_id:string;source_digest:string;fingerprint:string;status:'unprepared'|'unavailable'|'ready'|'incomplete';
 quotes:string[];items:Array<TaskCandidate & {review_required:boolean}>;projects:Array<{id:string;name:string}>;
 project_preparation_status?:'unprepared'|'unavailable'|'ready'|'not_needed';project_preparation_detail?:string;
 temporal_status:string;temporal_reason:string;detail:string;
};
export type SavedTaskInput = {fingerprint:string;source_digest:string;title:string;project_id:string|null;new_project_name:string|null;due:null;waiting_for:null};
const base = (id:string) => `/api/v1/local-mail/${encodeURIComponent(id)}/workflow`;
export const savedMailWorkflowApi = {
 read:(id:string,signal?:AbortSignal)=>request<SavedMailWorkflowView>(base(id),{signal}),
 prepare:(id:string,signal?:AbortSignal)=>request<SavedMailWorkflowView>(base(id)+'/prepare',{method:'POST',body:'{}',signal}),
 accept:(id:string,proposalId:string,input:SavedTaskInput)=>request<Task>(base(id)+`/tasks/${encodeURIComponent(proposalId)}/accept`,{method:'POST',body:JSON.stringify(input)}),
};
