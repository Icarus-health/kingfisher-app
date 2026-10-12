from pathlib import Path
import sqlite3,json,hashlib
root=Path('/data')
selection={'episodes.sqlite3':['episodes','source_heads'],'tasks.sqlite3':['tasks'],'workspace.sqlite3':['projects','notes'],'conversations.sqlite3':['conversations','conversation_messages']}
result={}
for name,wanted in selection.items():
    db=sqlite3.connect((root/name).as_uri()+'?mode=ro',uri=True)
    tables={r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    for table in wanted:
        assert table in tables, 'Required preservation table missing'
        rows=db.execute('SELECT * FROM "'+table+'"').fetchall()
        encoded=sorted(json.dumps(row,ensure_ascii=False,separators=(',',':'),default=lambda b:{'bytes':b.hex()}) for row in rows)
        result[name+'/'+table]={'rows':len(rows),'sha256':hashlib.sha256(json.dumps(encoded,separators=(',',':')).encode()).hexdigest()}
    db.close()
assert 'episodes.sqlite3/episodes' in result and 'episodes.sqlite3/source_heads' in result and 'tasks.sqlite3/tasks' in result
print(json.dumps(result,sort_keys=True))
