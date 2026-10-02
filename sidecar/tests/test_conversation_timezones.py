"""Mac- und Container-Nachrichten werden nach Zeitpunkten statt ISO-Text sortiert."""
from datetime import datetime
import sqlite3
from icarus_memory.conversations import ConversationStore


def test_mixed_offsets_order_messages_previews_and_latest_after_reopen(tmp_path):
    path=tmp_path/'conversations.sqlite3'
    store=ConversationStore(path)
    older=store.create('Mac-Gespräch',at=datetime.fromisoformat('2026-09-08T09:00:00+02:00'))
    store.add_message(older.id,'user','Vor dem Update',at=datetime.fromisoformat('2026-09-08T09:00:00+02:00'))
    store.add_message(older.id,'assistant','Nach dem Update',at=datetime.fromisoformat('2026-09-08T07:30:00+00:00'))
    newer=store.create('Neueres Gespräch',at=datetime.fromisoformat('2026-09-08T08:00:00+00:00'))
    store.close()
    # Persistierte Werte aus zwei Laufzeiten: Mac +02:00, Container UTC.
    with sqlite3.connect(path) as connection:
        connection.execute("UPDATE conversation_messages SET created_at='2026-09-08T09:00:00+02:00' WHERE content='Vor dem Update'")
        connection.execute("UPDATE conversation_messages SET created_at='2026-09-08T07:30:00+00:00' WHERE content='Nach dem Update'")
        connection.execute("UPDATE conversations SET updated_at='2026-09-08T09:00:00+02:00' WHERE id=?", (older.id,))
        connection.execute("UPDATE conversations SET updated_at='2026-09-08T08:00:00+00:00' WHERE id=?", (newer.id,))
    store=ConversationStore(path)
    assert [m.content for m in store.messages(older.id)]==['Vor dem Update','Nach dem Update']
    assert store.latest().id==newer.id
    rows=store.list()
    assert [item.id for item in rows]==[newer.id,older.id]
    assert rows[1].preview=='Nach dem Update'
    store.close()


def test_submillisecond_order_is_not_replaced_by_random_message_ids(tmp_path):
    path=tmp_path/'conversations.sqlite3'
    store=ConversationStore(path)
    conversation=store.create('Kurze Folge')
    store.add_message(conversation.id,'user','Erste',at=datetime.fromisoformat('2026-09-08T07:00:00.000100+00:00'))
    store.add_message(conversation.id,'assistant','Zweite',at=datetime.fromisoformat('2026-09-08T07:00:00.000200+00:00'))
    store.close()
    with sqlite3.connect(path) as connection:
        connection.execute("UPDATE conversation_messages SET id='z-first' WHERE content='Erste'")
        connection.execute("UPDATE conversation_messages SET id='a-second' WHERE content='Zweite'")
    store=ConversationStore(path)
    assert [m.content for m in store.messages(conversation.id)]==['Erste','Zweite']
    assert store.list()[0].preview=='Zweite'
    store.close()
