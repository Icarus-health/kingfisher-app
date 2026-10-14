// Only user-authored, unsent text. This tab's session never stores source payloads.
const drafts = new Map<string, {text: string; revision: number}>();
const prefix = 'kingfisher-chat-draft:';
const listeners = new Map<string,Set<() => void>>();
const sending = new Set<string>();
export const conversationSending = (id:string)=>sending.has(id);
export function beginConversationSend(id:string) {
  if(sending.has(id)) return false;
  sending.add(id);listeners.get(id)?.forEach(listener=>listener());return true;
}
export function endConversationSend(id:string) {sending.delete(id);listeners.get(id)?.forEach(listener=>listener());}
export function subscribeConversationDraft(id:string, listener:()=>void) {
  const entries = listeners.get(id) ?? new Set<() => void>();
  entries.add(listener);listeners.set(id,entries);
  return ()=>{entries.delete(listener);if(!entries.size) listeners.delete(id);};
}
export function conversationDraft(id: string) {
  let draft = drafts.get(id);
  if (!draft) {
    let text = '';
    try { text = sessionStorage.getItem(prefix + id) ?? ''; } catch { /* memory-only fallback */ }
    draft = {text, revision: 0};
    drafts.set(id, draft);
  }
  return draft;
}
export function writeConversationDraft(id: string, text: string) {
  const previous = conversationDraft(id);
  const draft = {text, revision: previous.revision + 1};
  drafts.set(id, draft);
  listeners.get(id)?.forEach(listener=>listener());
  try {
    if (text) sessionStorage.setItem(prefix + id, text);
    else sessionStorage.removeItem(prefix + id);
  } catch { /* memory-only fallback */ }
  return draft;
}
export function clearSubmittedDraft(id: string, revision: number) {
  if (conversationDraft(id).revision !== revision) return false;
  writeConversationDraft(id, '');
  return true;
}
