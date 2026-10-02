"""Derived provenance lookup and durable local authorization schema contracts."""
EPISODE_TABLES = {'episode_produced_assertions': {'assertion_id','episode_id'}}
EPISODE_TRIGGERS = {
 'trg_episode_projection_insert': """CREATE TRIGGER trg_episode_projection_insert BEFORE INSERT ON episode_produced_assertions
 WHEN NOT EXISTS(SELECT 1 FROM episodes e,json_each(e.document,'$.produced') j WHERE e.id=NEW.episode_id AND j.type='text' AND j.value=NEW.assertion_id)
 BEGIN SELECT RAISE(ABORT,'invalid episode projection'); END""",
 'trg_episode_projection_delete': """CREATE TRIGGER trg_episode_projection_delete BEFORE DELETE ON episode_produced_assertions
 WHEN EXISTS(SELECT 1 FROM episodes e,json_each(e.document,'$.produced') j WHERE e.id=OLD.episode_id AND j.type='text' AND j.value=OLD.assertion_id)
 BEGIN SELECT RAISE(ABORT,'cannot hide episode projection'); END""",
 'trg_episode_projection_update': """CREATE TRIGGER trg_episode_projection_update BEFORE UPDATE ON episode_produced_assertions
 BEGIN SELECT RAISE(ABORT,'episode projection update forbidden'); END""",
 'trg_episode_support_generation': """CREATE TRIGGER trg_episode_support_generation AFTER UPDATE OF state ON episodes
 WHEN NEW.state='ignored' AND OLD.state!='ignored'
 BEGIN UPDATE episodes SET support_generation=OLD.support_generation+1 WHERE id=NEW.id; END""",
 'trg_episode_support_monotonic': """CREATE TRIGGER trg_episode_support_monotonic BEFORE UPDATE OF support_generation ON episodes
 WHEN NEW.support_generation < OLD.support_generation BEGIN SELECT RAISE(ABORT,'support generation cannot decrease'); END""",
 'trg_episode_support_insert': """CREATE TRIGGER trg_episode_support_insert AFTER INSERT ON episodes BEGIN
 INSERT OR IGNORE INTO episode_produced_assertions SELECT value,NEW.id FROM json_each(NEW.document,'$.produced') WHERE type='text'; END""",
 'trg_episode_support_update': """CREATE TRIGGER trg_episode_support_update AFTER UPDATE OF document ON episodes BEGIN
 DELETE FROM episode_produced_assertions WHERE episode_id=OLD.id AND assertion_id NOT IN (SELECT value FROM json_each(NEW.document,'$.produced') WHERE type='text');
 INSERT OR IGNORE INTO episode_produced_assertions SELECT value,NEW.id FROM json_each(NEW.document,'$.produced') WHERE type='text'; END""",
 'trg_episode_support_delete': """CREATE TRIGGER trg_episode_support_delete AFTER DELETE ON episodes BEGIN
 DELETE FROM episode_produced_assertions WHERE episode_id=OLD.id; END""",
 'trg_episode_no_replace': """CREATE TRIGGER trg_episode_no_replace BEFORE INSERT ON episodes
 WHEN EXISTS(SELECT 1 FROM episodes WHERE id=NEW.id OR (digest=NEW.digest AND source_key=NEW.source_key AND metadata_digest=NEW.metadata_digest))
 BEGIN SELECT RAISE(ABORT,'episode replacement forbidden'); END""",
 'trg_episode_id_immutable': """CREATE TRIGGER trg_episode_id_immutable BEFORE UPDATE OF id ON episodes WHEN NEW.id!=OLD.id
 BEGIN SELECT RAISE(ABORT,'episode id immutable'); END""",
}
PROPOSAL_TRIGGERS = {
 'trg_proposal_support_insert': """CREATE TRIGGER trg_proposal_support_insert BEFORE INSERT ON proposals
 WHEN NEW.id IS NOT json_extract(NEW.document,'$.id') OR NEW.kind IS NOT json_extract(NEW.document,'$.kind') OR NEW.state IS NOT json_extract(NEW.document,'$.state') OR NEW.produced_assertion_id IS NOT CASE WHEN json_type(NEW.document,'$.produced')='text' THEN json_extract(NEW.document,'$.produced') ELSE NULL END
 BEGIN SELECT RAISE(ABORT,'producer projection mismatch'); END""",
 'trg_proposal_support_update': """CREATE TRIGGER trg_proposal_support_update BEFORE UPDATE OF document,produced_assertion_id,id,kind,state ON proposals
 WHEN NEW.id IS NOT json_extract(NEW.document,'$.id') OR NEW.kind IS NOT json_extract(NEW.document,'$.kind') OR NEW.state IS NOT json_extract(NEW.document,'$.state') OR NEW.produced_assertion_id IS NOT CASE WHEN json_type(NEW.document,'$.produced')='text' THEN json_extract(NEW.document,'$.produced') ELSE NULL END
 BEGIN SELECT RAISE(ABORT,'producer projection mismatch'); END""",
 'trg_proposal_no_replace': """CREATE TRIGGER trg_proposal_no_replace BEFORE INSERT ON proposals WHEN EXISTS(SELECT 1 FROM proposals WHERE id=NEW.id)
 BEGIN SELECT RAISE(ABORT,'proposal replacement forbidden'); END""",
 'trg_proposal_id_immutable': """CREATE TRIGGER trg_proposal_id_immutable BEFORE UPDATE OF id ON proposals WHEN NEW.id!=OLD.id
 BEGIN SELECT RAISE(ABORT,'proposal id immutable'); END""",
}


def migrate_episodes(connection):
    connection.execute('CREATE INDEX idx_source_heads_episode ON source_heads(episode_id)')
    connection.execute('ALTER TABLE episodes ADD COLUMN support_generation INTEGER NOT NULL DEFAULT 0 CHECK(support_generation>=0)')
    connection.execute('CREATE TABLE episode_produced_assertions(assertion_id TEXT NOT NULL, episode_id TEXT NOT NULL, PRIMARY KEY(assertion_id,episode_id))')
    connection.execute('CREATE INDEX idx_episode_produced_episode ON episode_produced_assertions(episode_id)')
    connection.execute("INSERT OR IGNORE INTO episode_produced_assertions SELECT j.value,e.id FROM episodes e,json_each(e.document,'$.produced') j WHERE j.type='text'")
    for sql in EPISODE_TRIGGERS.values(): connection.execute(sql)


def migrate_proposals(connection):
    connection.execute('ALTER TABLE proposals ADD COLUMN produced_assertion_id TEXT')
    connection.execute('ALTER TABLE proposals ADD COLUMN support_authorization TEXT')
    connection.execute("UPDATE proposals SET produced_assertion_id=json_extract(document,'$.produced') WHERE json_type(document,'$.produced')='text'")
    connection.execute('CREATE INDEX idx_proposals_produced ON proposals(produced_assertion_id)')
    for sql in PROPOSAL_TRIGGERS.values(): connection.execute(sql)
