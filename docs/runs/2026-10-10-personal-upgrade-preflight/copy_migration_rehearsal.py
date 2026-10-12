from pathlib import Path
import tarfile,sqlite3,hashlib,json,os,subprocess,stat,base64
archive=Path('/backup/volume.tar.gz');data=Path('/work/data');data.mkdir()
proof=json.loads(Path('/backup/backup-verification.json').read_text())
with archive.open('rb') as stream:assert hashlib.file_digest(stream,'sha256').hexdigest()==proof['archive_sha256']
manifest=json.loads(Path('/backup/volume-manifest.json').read_text())
with tarfile.open(archive,'r:gz') as tf:
    members=tf.getmembers();assert len(members)==len(manifest)
    for member in members:
        path=Path(member.name)
        assert not path.is_absolute() and '..' not in path.parts and str(path) in manifest
        assert member.isdir() or member.isfile() or member.islnk()
        if member.islnk():
            link=Path(member.linkname);assert not link.is_absolute() and '..' not in link.parts and str(link) in manifest
subprocess.run(['tar','--acls','--xattrs','--xattrs-include=*','--same-owner','--same-permissions','-xf',str(archive),'-C',str(data)],check=True,capture_output=True)
actual={}
for p in [data,*sorted(data.rglob('*'))]:
    st=p.lstat();assert stat.S_ISDIR(st.st_mode) or stat.S_ISREG(st.st_mode)
    item={'type':'directory' if p.is_dir() else 'file','uid':st.st_uid,'gid':st.st_gid,'mode':stat.S_IMODE(st.st_mode),'mtime_ns':st.st_mtime_ns,'xattrs':{name:base64.b64encode(os.getxattr(p,name)).decode() for name in sorted(os.listxattr(p))}}
    if p.is_file():
        with p.open('rb') as stream:item.update(sha256=hashlib.file_digest(stream,'sha256').hexdigest(),bytes=st.st_size)
    actual[str(p.relative_to(data))]=item
assert actual==manifest,'Restored copy metadata or content mismatch'
# The application runs as UID/GID 1000; exercise restored access as that user.
os.setgroups([]);os.setgid(1000);os.setuid(1000)
db=data/'episodes.sqlite3'
def table_layout(connection,table):
    columns=[tuple(row) for row in connection.execute('PRAGMA table_info("'+table+'")')]
    sql=connection.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name=?",(table,)).fetchone()[0]
    return {'columns':columns,'sql':sql}
def rows_digest(connection,table):
    rows=[tuple(row) for row in connection.execute('SELECT * FROM "'+table+'" ORDER BY 1').fetchall()]
    encoded=json.dumps(rows,ensure_ascii=False,separators=(',',':'),default=lambda v: {'bytes':v.hex()}).encode()
    return {'rows':len(rows),'sha256':hashlib.sha256(encoded).hexdigest()}
connection=sqlite3.connect(str(db))
old_version=connection.execute('PRAGMA user_version').fetchone()[0]
tables=[r[0] for r in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")]
selected=[t for t in tables if t in ['episodes','source_heads','mail_progress','working_memory_items','working_memory_sources','source_categories','category_corrections','memory_categories','memory_source_categories','memory_category_corrections']]
assert 'episodes' in selected and 'source_heads' in selected
before={t:rows_digest(connection,t) for t in selected};layouts={t:table_layout(connection,t) for t in selected};connection.close()
# Only store initialization and schema migration, never app/agent/provider construction.
from icarus_memory.episodes import EpisodeStore
store=EpisodeStore(db)
new_version=store._conn.execute('PRAGMA user_version').fetchone()[0]
assert old_version==20 and new_version==21
assert store._conn.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
after={t:rows_digest(store._conn,t) for t in selected}
assert before==after,'Existing source/store rows changed'
assert {t:table_layout(store._conn,t) for t in selected}==layouts,'Existing selected table layout changed'
store.close()
# Reopen the migrated persistent store independently.
second=EpisodeStore(db);assert {t:rows_digest(second._conn,t) for t in selected}==before
assert {t:table_layout(second._conn,t) for t in selected}==layouts;second.close()
result={'schema_before':old_version,'schema_after':new_version,'existing_selected_table_row_content_preserved':len(selected),'existing_selected_table_columns_and_ddl_preserved':len(selected),'restored_metadata_verified_before_migration':True,'restored_copy_migrated_as_uid':os.getuid(),'original_episode_rows_preserved':before['episodes']['rows'],'source_heads_preserved':before['source_heads']['rows'],'sqlite_integrity':'passed','reopened_migrated_store':'passed','original_backup_readonly':True,'model_or_provider_constructed':False,'network':'none','productive_database_modified':False}
print(json.dumps(result,sort_keys=True))
