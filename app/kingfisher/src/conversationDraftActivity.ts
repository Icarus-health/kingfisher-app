// Browser-local editing boundaries only; no transcript or user text is retained.
const recordings=new Set<symbol>();
const leaving=new Set<symbol>();
export function setDraftRecording(owner:symbol,active:boolean){if(active)recordings.add(owner);else recordings.delete(owner);}
export const hasDraftRecording=()=>recordings.size>0;
export function setDraftLeaveLock(owner:symbol,active:boolean){if(active)leaving.add(owner);else leaving.delete(owner);}
export const draftLeaveLocked=()=>leaving.size>0;
