import {request} from './api';
import type {GroupData,ViewRecord} from './workspaceViewApi';
export type OrganisationSuggestion={id:string;name:string;members:string[];reason:string};
export type OrganisationSnapshot={entries:{id:string;name:string}[];total:number;complete:boolean;source_revision:string;groups_revision:string;groups:ViewRecord<GroupData>[];dismissals:(ViewRecord<{dismissed:boolean}>&{name?:string|null})[];suggestions:OrganisationSuggestion[]};
export type OrganisationConfirmation={source_revision:string;groups_revision:string;candidate_id:string|null;group_id:string|null;group_revision:number;name:string;members:string[]};
const base='/api/v1/organisation-group-suggestions';
const changed=()=>window.dispatchEvent(new Event('workspace-view-changed'));
export const organisationSuggestionsApi={
 overview:()=>request<OrganisationSnapshot>(base),
 confirm:async(body:OrganisationConfirmation)=>{const result=await request<ViewRecord<GroupData>>(base+'/confirm',{method:'POST',body:JSON.stringify(body)});changed();return result;},
 dismiss:async(id:string,basis:Pick<OrganisationSnapshot,'source_revision'|'groups_revision'>)=>{const result=await request<ViewRecord<{dismissed:boolean}>>(base+'/'+encodeURIComponent(id)+'/dismiss',{method:'POST',body:JSON.stringify(basis)});changed();return result;},
 undoDismissal:async(id:string,revision:number)=>{const result=await request<ViewRecord>(base+'/'+encodeURIComponent(id)+'/undo-dismissal',{method:'POST',body:JSON.stringify({revision})});changed();return result;},
};
