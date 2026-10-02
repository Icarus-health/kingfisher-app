import json,sys
from datetime import datetime,timezone
from pathlib import Path
p=Path(sys.argv[1]); data=json.loads(p.read_text())
results=[]
def utc(v):return datetime.fromisoformat(v.replace('Z','+00:00')).astimezone(timezone.utc).isoformat() if v else None
for a in data['attempts']:
 if a['status']!='completed':continue
 turn=a['turn']; contract=turn['context']['answer_contract']; rows=[]; current=None
 for line in turn['reply'].splitlines():
  if '. [E' in line:
   current={};rows.append(current)
  elif current is not None and ': ' in line:
   key,value=line.split(': ',1)
   try:current[key]=json.loads(value)
   except ValueError:pass
 errors=[]
 if [r.get('assertion_id') for r in rows]!=contract['selected_assertion_ids']:errors.append('selected ID mismatch')
 for r in rows:
  identifier=r['assertion_id'].removeprefix('claim:')
  claim=a['canonical_manifest']['claims'][identifier];source=a['canonical_manifest']['sources'][r['episode_id']]
  expected={key:claim.get(key) for key in ('statement','value','subject_ref','target_ref','scope_ref','predicate')}
  expected.update(source_type=source['provenance']['source_type'],source_ref=source['provenance'].get('source_ref'),digest=source['digest'],
                  occurred_at=utc(source['occurred_at']),recorded_at=utc(source['recorded_at']),claim_created_at=utc(claim['created_at']),
                  valid_from=utc(claim['valid_from']),valid_until=utc(claim['valid_until']))
  errors.extend([identifier+':'+key for key,value in expected.items() if r.get(key)!=value])
 if turn['used_tools'] or turn['approvals'] or turn['memory_candidate_drafts']:errors.append('unexpected action')
 results.append({'case_id':a['case_id'],'status':contract['status'],'rendered_rows':len(rows),'field_mismatches':errors})
print(json.dumps({'run_status':data['status'],'completed_cases':len(results),'integrity_only':True,'results':results},ensure_ascii=False,indent=2))
