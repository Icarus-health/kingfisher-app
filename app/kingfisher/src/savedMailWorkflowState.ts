import type {SavedMailWorkflowView, SavedTaskInput} from './savedMailWorkflowApi';
import type {TaskCandidate} from './api';
import {candidateDay,candidateDeadline} from './taskWorkflow.ts';
export type SavedTaskDraft = {title:string;project:string;newProject:string;due:string;waiting:string;sourceDeadline:string|null;reviewFingerprint:string};
export function initialSavedTask(item:TaskCandidate & {review_required:boolean},projects:Array<{id:string;name:string}>,reviewFingerprint=''):SavedTaskDraft {
 const hint=item.project_suggestion;
 const sourceDeadline=item.review_required ? null : item.frist_vorschlag || null;
 return {title:item.review_required ? `Aktualität der Bitte prüfen: ${item.statement.slice(0,4000)}` : item.statement,
  project:hint?.project_id && projects.some(p=>p.id===hint.project_id) ? hint.project_id : hint?.new_project_name ? 'new' : '',
  newProject:hint?.new_project_name || '',sourceDeadline,due:candidateDay({frist_vorschlag:sourceDeadline}),waiting:'',reviewFingerprint};
}
export function savedTaskPayload(view:Pick<SavedMailWorkflowView,'source_digest'|'fingerprint'>,draft:SavedTaskDraft):SavedTaskInput {
 if(draft.reviewFingerprint && draft.reviewFingerprint!==view.fingerprint)throw new Error('Die Grundlage hat sich verändert. Bitte Eingaben erneut prüfen.');
 return {fingerprint:view.fingerprint,source_digest:view.source_digest,title:draft.title.trim(),
  project_id:draft.project && draft.project!=='new' ? draft.project : null,
  new_project_name:draft.project==='new' ? draft.newProject.trim() : null,
  due:candidateDeadline({frist_vorschlag:draft.sourceDeadline},draft.due),waiting_for:draft.waiting.trim() || null};
}
export function savedDeadlineText(draft:SavedTaskDraft):string {
 try {
  const due=candidateDeadline({frist_vorschlag:draft.sourceDeadline},draft.due);
  return due ? `Frist ${new Date(due).toLocaleString('de-DE',{dateStyle:'medium',timeStyle:'short'})}` : 'Ohne Frist';
 } catch {return 'Frist prüfen';}
}
