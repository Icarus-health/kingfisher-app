from pathlib import Path
import sqlite3,tempfile
from migration_guard import capture,verify

def setup(root):
 p=root/'episodes.sqlite3'
 c=sqlite3.connect(p);c.execute('CREATE TABLE episodes(id TEXT PRIMARY KEY, body TEXT)');c.execute("INSERT INTO episodes VALUES ('one','untouched')");c.execute('PRAGMA user_version=21');c.commit();c.close()
 c=sqlite3.connect(root/'tasks.sqlite3');c.execute('CREATE TABLE tasks(id TEXT, title TEXT)');c.commit();c.close()
 return p

def add_expected(p):
 c=sqlite3.connect(p);c.execute('CREATE TABLE episode_mail_headers(value TEXT NOT NULL, episode_id TEXT NOT NULL, PRIMARY KEY(value,episode_id))');c.execute('CREATE INDEX idx_mail_headers_episode ON episode_mail_headers(episode_id)')
 for n in ('insert','update','delete'):c.execute('CREATE TRIGGER trg_mail_headers_'+n+' AFTER INSERT ON episodes BEGIN SELECT 1; END')
 c.execute('PRAGMA user_version=22');c.commit();c.close()

for case in ('valid','unexpected-table','missing-trigger','original-mutation','other-schema','wrong-version'):
 with tempfile.TemporaryDirectory() as d:
  root=Path(d);p=setup(root);before=capture(root);add_expected(p)
  if case!='valid':
   c=sqlite3.connect(root/'tasks.sqlite3' if case=='other-schema' else p)
   if case=='unexpected-table' or case=='other-schema':c.execute('CREATE TABLE unexpected(x TEXT)')
   if case=='missing-trigger':c.execute('DROP TRIGGER trg_mail_headers_update')
   if case=='original-mutation':c.execute("UPDATE episodes SET body='changed'")
   if case=='wrong-version':c.execute('PRAGMA user_version=21')
   c.commit();c.close()
  rejected=False
  try:verify(before,capture(root))
  except AssertionError:rejected=True
  assert rejected==(case!='valid'),case
print('6 migration-guard counterexamples passed; no personal data accessed')
