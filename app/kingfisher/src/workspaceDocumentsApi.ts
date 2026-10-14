import {request} from './api';
import type {FolderData,ViewRecord} from './workspaceViewApi';

export type WorkspaceDocumentQuery={q:string;folder_id:string;project_id:string;source_area:string;project_area:string;offset:number;limit:number};
export type WorkspaceDocument={id:string;kind:'episode'|'note';title:string;preview:string;project_id:string|null;project_name:string|null;project_area:string|null;source_areas:string[];folder_id:string|null;source_folder_revision:number;revision:number|null;recorded_at:string};
export type WorkspaceDocumentOptions={folders:ViewRecord<FolderData>[];projects:{id:string;name:string;status:string}[];source_areas:{id:string;label:string}[];project_areas:string[]};
export type WorkspaceDocumentPage={items:WorkspaceDocument[];total:number;has_more:boolean;limit:number;offset:number;options:WorkspaceDocumentOptions};
export const workspaceDocumentsApi={
  page:(query:WorkspaceDocumentQuery)=>request<WorkspaceDocumentPage>(`/api/v1/workspace-documents?${new URLSearchParams(Object.entries(query).map(([key,value])=>[key,String(value)]))}`),
  folders:()=>request<{folders:ViewRecord<FolderData>[]}>('/api/v1/workspace-document-folders'),
};
/** Freie Projektbereiche bleiben erhalten; bekannte Lebensbereiche lesbar anzeigen. */
export function documentAreaLabel(area:string):string {
  return ({work:'Arbeit & Projekte',health:'Gesundheit',finance:'Finanzen',personal:'Persönliches',other:'Sonstiges'} as Record<string,string>)[area]??area;
}
