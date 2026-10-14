import {request} from './api';

export type ViewRecord<T = Record<string, unknown>> = {kind: string; id: string; revision: number; data: T | null};
export type FolderData = {name: string; parent_id: string | null};
export type GroupData = {name: string; members: string[]};
export type PositionData = {lat: number; lng: number};
export type ViewOverview = {
  folders: ViewRecord<FolderData>[];
  source_folders: ViewRecord<{folder_id: string | null}>[];
  organisation_groups: ViewRecord<GroupData>[];
  places: ViewRecord<PositionData>[];
  avatars: ViewRecord<{available: boolean}>[];
  logos?: ViewRecord<{available:boolean}>[]; truncated?:string[];
  online: {logos: boolean; maps: boolean}; online_revision: number;
};
const path = (kind: string, id: string) => `/api/v1/workspace-view/${encodeURIComponent(kind)}/${encodeURIComponent(id)}`;
const changed = () => window.dispatchEvent(new Event('workspace-view-changed'));
export const workspaceViewApi = {
  overview: () => request<ViewOverview>('/api/v1/workspace-view'),
  get: <T,>(kind: string, id: string) => request<ViewRecord<T>>(path(kind, id)),
  save: async <T extends Record<string, unknown>,>(kind: string, id: string, data: T, revision: number) => {
    const result = await request<ViewRecord<T>>(path(kind, id), {method:'PUT', body:JSON.stringify({data, revision})});
    changed(); return result;
  },
  undo: async (kind: string, id: string, revision: number) => {
    const result = await request<ViewRecord>(path(kind, id) + '/undo', {method:'POST', body:JSON.stringify({revision})});
    changed(); return result;
  },
};
