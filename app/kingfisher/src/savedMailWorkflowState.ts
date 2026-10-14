import type {SavedMailWorkflowView, SavedTaskInput} from './savedMailWorkflowApi';
import type {TaskCandidate} from './api';
export type SavedTaskDraft = {title:string;project:string;newProject:string};
export function initialSavedTask(item:TaskCandidate & {review_required:boolean},projects:Array<{id:string;name:string}>):SavedTaskDraft {
 const hint=item.project_suggestion;
 return {title:item.review_required ? `Aktualität der Bitte prüfen: ${item.statement.slice(0,4000)}` : item.statement,
  project:hint?.project_id && projects.some(p=>p.id===hint.project_id) ? hint.project_id : hint?.new_project_name ? 'new' : '',
  newProject:hint?.new_project_name || ''};
}
export function savedTaskPayload(view:Pick<SavedMailWorkflowView,'source_digest'|'fingerprint'>,draft:SavedTaskDraft):SavedTaskInput {
 return {fingerprint:view.fingerprint,source_digest:view.source_digest,title:draft.title.trim(),
  project_id:draft.project && draft.project!=='new' ? draft.project : null,
  new_project_name:draft.project==='new' ? draft.newProject.trim() : null,due:null,waiting_for:null};
}
