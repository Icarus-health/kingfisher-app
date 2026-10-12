from pathlib import Path
import sqlite3,tempfile
from preservation_guard import capture,verify

def setup(root):
 for name,version,ddl in (
 ('episodes.sqlite3',22,"CREATE TABLE episodes(id TEXT PRIMARY KEY, body TEXT); INSERT INTO episodes VALUES ('one','unchanged'); CREATE TABLE episode_mail_headers(value TEXT, episode_id TEXT); CREATE INDEX header_idx ON episode_mail_headers(episode_id);"),
 ('tasks.sqlite3',3,"CREATE TABLE tasks(id TEXT, title TEXT); INSERT INTO tasks VALUES ('t','unchanged'); CREATE TABLE task_requests(id TEXT);"),
 ('self-model.sqlite3',1,"CREATE TABLE assertions(id TEXT, statement TEXT); INSERT INTO assertions VALUES ('a','unchanged');"),
 ('workspace.sqlite3',1,"CREATE TABLE projects(id TEXT);")):
  c=sqlite3.connect(root/name);c.executescript(ddl);c.execute('PRAGMA user_version='+str(version));c.commit();c.close()

for case in ('valid','unexpected-table','missing-index','original-mutation','task-binding-mutation','selfmodel-mutation','other-schema','wrong-version','missing-db'):
 with tempfile.TemporaryDirectory(prefix='kingfisher-unchanged-store-') as d:
  root=Path(d);setup(root);before=capture(root)
  if case=='missing-db': (root/'workspace.sqlite3').unlink()
  elif case!='valid':
   filename='tasks.sqlite3' if case=='task-binding-mutation' else 'self-model.sqlite3' if case=='selfmodel-mutation' else 'workspace.sqlite3' if case=='other-schema' else 'episodes.sqlite3'
   sql={'unexpected-table':'CREATE TABLE unexpected(x TEXT)','missing-index':'DROP INDEX header_idx','original-mutation':"UPDATE episodes SET body='changed'",'task-binding-mutation':"INSERT INTO task_requests VALUES ('new')",'selfmodel-mutation':"UPDATE assertions SET statement='changed'",'other-schema':'ALTER TABLE projects ADD COLUMN unexpected TEXT','wrong-version':'PRAGMA user_version=21'}[case]
   c=sqlite3.connect(root/filename);c.execute(sql);c.commit();c.close()
  rejected=False
  try:verify(before,capture(root))
  except AssertionError:rejected=True
  assert rejected==(case!='valid'),case
print('9 actual SQLite preservation controls passed; no personal data accessed')
