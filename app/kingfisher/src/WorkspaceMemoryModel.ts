import type {SourceCategoriesResult} from './api';
import type {FolderData, ViewRecord} from './workspaceViewApi';
export const IMAGE_MAX_BYTES = 1_000_000;
export function initials(label: string): string {
  const name = label.replace(/<[^>]*>/g, '').trim() || label;
  return name.split(/\s+/).filter(Boolean).slice(0, 2).map(word => Array.from(word)[0]).join('').toLocaleUpperCase('de');
}
export function validateImageFile(file: {type: string; size: number}): string | null {
  if (!['image/png','image/jpeg','image/webp'].includes(file.type)) return 'Bitte ein PNG-, JPEG- oder WebP-Bild wählen.';
  if (file.size > IMAGE_MAX_BYTES || file.size <= 0) return 'Das Bild darf höchstens 1 MB groß sein und muss Inhalt haben.';
  return null;
}
export function coordinatePair(lat: string, lng: string): {lat: number; lng: number} | null {
  if (!lat.trim() || !lng.trim()) return null;
  const pair = {lat: Number(lat.trim().replace(',','.')), lng: Number(lng.trim().replace(',','.'))};
  return Number.isFinite(pair.lat) && Number.isFinite(pair.lng) && Math.abs(pair.lat) <= 90 && Math.abs(pair.lng) <= 180 ? pair : null;
}
export function canonicalSourceId(id: string, kind: 'episode' | 'note' = 'episode'): string {
  return /^(episode|note):/.test(id) ? id : `${kind}:${id}`;
}
export function folderDescendants(folders: Array<Pick<ViewRecord<FolderData>, 'id' | 'data'>>, id: string): Set<string> {
  const found = new Set([id]);
  for (let changed = true; changed;) {
    changed = false;
    for (const record of folders) if (record.data?.parent_id && found.has(record.data.parent_id) && !found.has(record.id)) {found.add(record.id); changed = true;}
  }
  return found;
}
export type BatchResult = {id: string; ok: boolean; message: string};
export async function batchCategorySave(previews: SourceCategoriesResult[], area: string,
  save: (id: string, categories: string[], revision: string) => Promise<unknown>): Promise<BatchResult[]> {
  const results: BatchResult[] = [];
  for (const source of previews) {
    if (!source.revision || source.status === 'excluded') {results.push({id:source.episode_id,ok:false,message:'Quelle nicht sicher verfügbar. Bitte aktuellen Stand prüfen.'});continue;}
    try {
      await save(source.episode_id, [...new Set([...source.categories.map(c => c.id),area])], source.revision);
      results.push({id:source.episode_id,ok:true,message:'Bereich ergänzt'});
    } catch (error) {
      results.push({id:source.episode_id,ok:false,message:(error as {status?: number})?.status === 409 ? 'Quelle oder Zuordnung geändert. Vorschau neu laden.' : 'Nicht gespeichert. Erneut prüfen.'});
    }
  }
  return results;
}

import type {MemoryGraph} from './api';
import type {FolderSource} from './MemoryFolders';
export function contactDateFromGraph(graph: MemoryGraph, id: string): string {
  // Being mentioned in a source does not establish actual contact.
  const sources = new Set(graph.edges.filter(edge=>edge.source===id&&edge.relation==='participated_in').map(edge=>edge.target));
  const dates = graph.nodes.filter(node=>sources.has(node.id)).map(node=>node.attributes.occurred_at)
    .filter((value):value is string=>typeof value==='string'&&Number.isFinite(Date.parse(value)));
  if(!dates.length)return 'unbekannt';
  return new Date(Math.max(...dates.map(Date.parse))).toLocaleDateString('de-DE');
}
export function folderSourcesFromGraph(graph: MemoryGraph): FolderSource[] {
  return graph.nodes.filter(node=>(node.kind==='document'||node.attributes.episode_kind==='document')
    && /^(episode|note):/.test(node.id)&&node.attributes.source_current!==false&&node.attributes.state!=='ignored'&&node.attributes.state!=='archived')
    .map(node=>{
      const edge=graph.edges.find(edge=>edge.source===node.id&&edge.relation==='belongs_to');
      const project=graph.nodes.find(item=>item.id===edge?.target&&item.kind==='project');
      return {id:node.id,title:node.label,kind:node.id.startsWith('note:')?'note':'episode',project:project?.id??null,projectName:project?.label,
        areas:typeof project?.attributes.area==='string'?[project.attributes.area]:[]};
    });
}

export function workspaceProfileHref(id:string,tab:'organizations'|'places',search=''): string {
  return `/memory/akte/${encodeURIComponent(id)}?${new URLSearchParams({return_to:search?`/memory${search}`:`/memory?tab=${tab}`})}`;
}
