"""Synthetic-only sqlite-vec fitness probe; no model or personal source access."""
import hashlib,json,math,os,resource,sqlite3,struct,sys,time
from pathlib import Path
import sqlite_vec

N=int(sys.argv[1]);ROOT=Path(sys.argv[2]);D=1024;K=12
assert N in {20000,100000}
ROOT.mkdir(exist_ok=False)
DB=ROOT/'vectors.sqlite3'
resource.setrlimit(resource.RLIMIT_CPU,(180,180))
resource.setrlimit(resource.RLIMIT_FSIZE,(700*2**20,700*2**20))

def vector(i):
    values=[(v-127.5)/127.5 for v in hashlib.shake_256(str(i).encode()).digest(D)]
    norm=math.sqrt(sum(v*v for v in values))
    return struct.pack('<1024f',*(v/norm for v in values))

def connect():
    c=sqlite3.connect(DB)
    c.execute('pragma cache_size=-8192');c.execute('pragma journal_mode=wal')
    c.enable_load_extension(True)
    try: sqlite_vec.load(c)
    finally:c.enable_load_extension(False)
    assert c.execute('select vec_version()').fetchone()[0]=='v0.1.9'
    return c

def knn(c,table,query,partition,k=K):
    return c.execute(f'select rowid,distance from {table} where embedding match ? and model=? and k=? order by distance',(query,partition,k)).fetchall()

c=connect()
c.execute('create virtual table small using vec0(model text partition key, embedding float[1024] distance_metric=cosine)')
small={i:vector(i) for i in range(256)}
c.executemany('insert into small(rowid,model,embedding) values (?,?,?)',((i,'current',v) for i,v in small.items()))
c.execute('insert into small(rowid,model,embedding) values (?,?,?)',(999,'old',vector(100001)))
reference=[]
for seed in (3,173,100001,100003):
    q=vector(seed);qf=struct.unpack('<1024f',q)
    distances=[]
    for i,v in small.items():
        vf=struct.unpack('<1024f',v)
        score=sum(a*b for a,b in zip(qf,vf))/math.sqrt(sum(a*a for a in qf)*sum(b*b for b in vf))
        distances.append((i,1-score))
    exact=sorted(distances,key=lambda r:r[1])[:K]
    actual=knn(c,'small',q,'current')
    assert [r[0] for r in exact]==[r[0] for r in actual],(seed,exact,actual)
    error=max(abs(a[1]-b[1]) for a,b in zip(exact,actual));assert error<2e-6,error
    reference.append({'query_seed':seed,'max_distance_error':error,'exact_top_k':True})
c.execute('create virtual table large using vec0(model text partition key, embedding float[1024] distance_metric=cosine)')
start=time.monotonic()
for offset in range(0,N,256):
    c.executemany('insert into large(rowid,model,embedding) values (?,?,?)',((i,'current',vector(i)) for i in range(offset,min(N,offset+256))))
    c.commit()
    if offset%10000<256:print(json.dumps({'inserted':min(N,offset+256),'seconds':round(time.monotonic()-start,2)}),file=sys.stderr,flush=True)
insert_s=time.monotonic()-start
c.execute('insert into large(rowid,model,embedding) values (?,?,?)',(N+1,'old',vector(173)))
c.commit();c.execute('pragma wal_checkpoint(truncate)');c.close()
# New connection after durable close; OS cache is not evicted, so this is not cold-I/O evidence.
c=connect()
assert c.execute('select count(*) from large').fetchone()[0]==N+1
measurements=[]
for seed in (0,173,N-1,N//2,173,N-1):
    start=time.monotonic();rows=knn(c,'large',vector(seed),'current');elapsed=time.monotonic()-start
    assert len(rows)==K and rows[0][0]==seed and abs(rows[0][1])<2e-6
    assert N+1 not in [r[0] for r in rows]
    assert elapsed<2.0,('query latency budget exceeded',elapsed)
    measurements.append({'query_seed':seed,'seconds':elapsed,'self_match_first':True})
# Deletion is durable and immediate; no need to wait for a model job.
c.execute('delete from large where rowid=?',(173,));c.commit()
assert all(r[0]!=173 for r in knn(c,'large',vector(173),'current'))
assert c.execute('pragma quick_check').fetchall()==[('ok',)]
# Original store must not depend on the extension: this cache is a separate database.
try:c.load_extension(sqlite_vec.loadable_path())
except sqlite3.OperationalError:load_disabled=True
else:raise AssertionError('extension loading still enabled')
c.close()
usage=resource.getrusage(resource.RUSAGE_SELF)
rss=int(usage.ru_maxrss if sys.platform=='darwin' else usage.ru_maxrss*1024)
assert rss<1024*2**20,('RSS budget exceeded',rss)
result={'synthetic_only':True,'version':sqlite_vec.__version__,'sqlite_version':sqlite3.sqlite_version,'platform':sys.platform,
        'vectors':N,'dimension':D,'k':K,'reference_checks':reference,'insert_seconds':insert_s,'queries':measurements,
        'max_query_seconds':max(m['seconds'] for m in measurements),'peak_rss_bytes':rss,
        'database_bytes':DB.stat().st_size,'durable_reopen':True,'model_partition_isolation':True,
        'durable_delete':True,'quick_check':True,'extension_loading_disabled':load_disabled,'os_cache_evicted':False}
(ROOT/'result.json').write_text(json.dumps(result,indent=2));print(json.dumps(result))
