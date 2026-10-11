"""Derived exact mail header lookup, maintained atomically with original episodes."""
from .migrations import IndexContract

TABLES = {"episode_mail_headers": {"value", "episode_id"}}
KEYS = {"episode_mail_headers": {"value", "episode_id"}}
INDEXES = {"idx_mail_headers_episode": IndexContract("episode_mail_headers", ("episode_id",))}


def _select(document, episode_id, kind):
    return f"""SELECT DISTINCT j.value,{episode_id} FROM json_each({document},'$.tags') j
    WHERE {kind}='message' AND json_extract({document},'$.provenance.source_type')='email'
    AND json_type({document},'$.tags')='array' AND j.type='text'
    AND (j.value GLOB 'mail:message:*' OR j.value GLOB 'mail:reply:*')"""


TRIGGERS = {
    "trg_mail_headers_insert": """CREATE TRIGGER trg_mail_headers_insert AFTER INSERT ON episodes
    BEGIN INSERT OR IGNORE INTO episode_mail_headers(value,episode_id) """
    + _select("NEW.document", "NEW.id", "NEW.kind") + "; END",
    "trg_mail_headers_update": """CREATE TRIGGER trg_mail_headers_update AFTER UPDATE OF document,kind ON episodes
    BEGIN DELETE FROM episode_mail_headers WHERE episode_id=OLD.id;
    INSERT OR IGNORE INTO episode_mail_headers(value,episode_id) """
    + _select("NEW.document", "NEW.id", "NEW.kind") + "; END",
    "trg_mail_headers_delete": """CREATE TRIGGER trg_mail_headers_delete AFTER DELETE ON episodes
    BEGIN DELETE FROM episode_mail_headers WHERE episode_id=OLD.id; END""",
}


def migrate(connection):
    connection.execute("CREATE TABLE episode_mail_headers(value TEXT NOT NULL, episode_id TEXT NOT NULL, PRIMARY KEY(value,episode_id))")
    connection.execute("CREATE INDEX idx_mail_headers_episode ON episode_mail_headers(episode_id)")
    connection.execute("INSERT OR IGNORE INTO episode_mail_headers(value,episode_id) "
                       "SELECT j.value,e.id FROM episodes e,json_each(e.document,'$.tags') j "
                       "WHERE e.kind='message' AND json_extract(e.document,'$.provenance.source_type')='email' "
                       "AND json_type(e.document,'$.tags')='array' AND j.type='text' "
                       "AND (j.value GLOB 'mail:message:*' OR j.value GLOB 'mail:reply:*')")
    for sql in TRIGGERS.values():
        connection.execute(sql)
