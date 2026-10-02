from pathlib import Path
from tempfile import TemporaryDirectory
import importlib.util
from icarus_memory.episodes import EpisodeStore, EpisodeKind
from icarus_memory.claims import ClaimStore, KnowledgeService
from icarus_memory.proposals import ProposalStore, Evidence
from icarus_memory.model import Provenance, SourceType
from icarus_memory.knowledge_context import evidence_chain_available
from icarus_memory.recovery_bundle import export_bundle, restore_bundle
from icarus_memory import config
with TemporaryDirectory(prefix='synthetic-restore-') as tmp:
    root=Path(tmp); data=root/'data'
    es=EpisodeStore(data/'episodes.sqlite3'); cs=ClaimStore(data/'knowledge.sqlite3'); ps=ProposalStore(data/'proposals.sqlite3')
    e,_=es.record(EpisodeKind.MESSAGE,'Synthetic','Ada leitet Atlas.',Provenance(source_type=SourceType.CHAT, source_ref='synthetic:restore'))
    svc=KnowledgeService(proposals=ps, claims=cs, episodes=es)
    p,_=svc.propose(subject_ref='person:ada',predicate='note',value=e.body,statement=e.body,rationale='Synthetic',evidence=[Evidence(e.id,e.body,e.digest)])
    c=svc.accept(p.id,supersedes=[])
    settings=config.Settings();settings.schedule.enabled=True;settings.schedule.with_model=True;config.save(data,settings)
    env=root/'synthetic.env';env.write_text('ICARUS_SECRETS_PASSPHRASE=synthetic-only\n')
    bundle=export_bundle(data,env,root/'bundle','synthetic-password-12345')
    es.ignore(e.id);cs.invalidate_source(e.id)
    assert not evidence_chain_available(cs.get(c.id),cs,es)
    target=restore_bundle(bundle,root/'restored','synthetic-password-12345')
    restored_es=EpisodeStore(target/'data/episodes.sqlite3');restored_cs=ClaimStore(target/'data/knowledge.sqlite3')
    assert evidence_chain_available(restored_cs.get(c.id),restored_cs,restored_es)
    assert config.load(target/'data').schedule.enabled and config.load(target/'data').schedule.with_model
    print('Current revoked evidence: blocked; old restored evidence: usable; restored scheduler enabled+with_model: true')
    spec=importlib.util.spec_from_file_location('launcher','/tmp/kingfisher-memory-work/restore-audit-ed39aa0/scripts/open_restored_app.py')
    launcher=importlib.util.module_from_spec(spec);spec.loader.exec_module(launcher)
    calls=[];launcher.run=lambda *args: calls.append(args) or ''
    launcher.urlopen=lambda *a,**k: env.open()
    launcher.start('synthetic-docker',target,'synthetic-image')
    create=next(c for c in calls if c[1]=='create')
    assert '--network' not in create and '--restart' in create and '--env-file' in create
    assert any(c[1]=='start' for c in calls)
    print('Mock Docker launch: writable volume, old env, restart unless-stopped, normal networking; no quarantine gate')
    for store in [es,cs,ps,restored_es,restored_cs]:store.close()
