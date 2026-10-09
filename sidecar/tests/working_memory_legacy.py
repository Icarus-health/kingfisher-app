"""Hilfsmittel für Migrationstests: Suchindex auf den Stand vor Migration 10 zurückbauen.

Die Ganzzahl-Schlüssel lassen sich nicht in die ursprünglichen Hashes
zurückverwandeln. Migration 10 liest aber nur die ersten 8 Byte, deshalb
genügt ein Hex-Wert mit denselben 8 Byte; der Rest wird mit Nullen aufgefüllt.
"""


def legacy_hex(key):
    return format(key % 2 ** 64, '016x') + '0' * 48


def drop_task_rechecks(connection):
    from icarus_memory.task_rechecks import TABLES, TRIGGERS
    for trigger in TRIGGERS:
        connection.execute('DROP TRIGGER IF EXISTS ' + trigger)
    for table in TABLES:
        connection.execute('DROP TABLE IF EXISTS ' + table)


def drop_intake_extensions(connection):
    drop_task_rechecks(connection)
    from icarus_memory import akten_arten, bezuege, kreis, lage, mail_intake, memory_categories, source_index
    # Der Suchindex zuerst: Beim Löschen der virtuellen Tabelle verschwinden ihre Schattentabellen.
    for table in {**source_index.TABLES, **source_index.WOERTER_TABLES, **mail_intake.TABLES, **memory_categories.TABLES,
                  **bezuege.TABLES, **lage.TABLES, **kreis.TABLES, **akten_arten.TABLES}:
        connection.execute('DROP TABLE IF EXISTS ' + table)


def downgrade_terms(connection, version):
    if 'analysis_version' in {row[1] for row in connection.execute('PRAGMA table_info(working_memory_sources)')}:
        connection.execute('ALTER TABLE working_memory_sources DROP COLUMN analysis_version')
    drop_intake_extensions(connection)
    connection.execute("""CREATE TABLE working_memory_tokens (
        item_id TEXT NOT NULL, token_hash TEXT NOT NULL,
        PRIMARY KEY(item_id, token_hash))""")
    connection.execute("CREATE INDEX idx_working_memory_tokens_hash ON working_memory_tokens(token_hash, item_id)")
    connection.executemany(
        'INSERT INTO working_memory_tokens(item_id,token_hash) VALUES(?,?)',
        [(item_id, legacy_hex(term)) for item_id, term in connection.execute(
            'SELECT i.id, t.term FROM working_memory_terms t JOIN working_memory_items i ON i.key=t.item')])
    connection.execute('DROP TABLE working_memory_terms')
    connection.execute('DROP INDEX idx_working_memory_items_key')
    connection.execute('ALTER TABLE working_memory_items DROP COLUMN key')
    connection.execute(f'PRAGMA user_version={int(version)}')
    connection.commit()
