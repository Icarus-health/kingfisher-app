"""Frage vor Antwort, auch bei gleichem Zeitstempel.

Mit fester Uhr (Probe mit Stichtag), nach einem Uhrsprung oder mit gesetztem `at` haben Frage und Antwort
denselben Zeitstempel. Früher entschied dann die zufällige Kennung der Nachricht, und die Antwort stand
mal über der Frage; „Mit aktuellem Stand neu beantworten“ fehlte, weil die Frage die letzte Nachricht war.
"""
from datetime import datetime, timezone

from icarus_memory.conversations import ConversationStore

ZEIT = datetime(2026, 10, 1, 9, 0, tzinfo=timezone.utc)


def test_gleicher_zeitstempel_behaelt_die_einfuegereihenfolge(tmp_path):
    store = ConversationStore(tmp_path / 'conversations.sqlite3')
    gespraech = store.create('Reihenfolge', at=ZEIT)
    for runde in range(30):
        store.add_message(gespraech.id, 'user', f'Frage {runde}', at=ZEIT)
        store.add_message(gespraech.id, 'assistant', f'Antwort {runde}', at=ZEIT)
    inhalte = [m.content for m in store.messages(gespraech.id)]
    erwartet = [text for runde in range(30) for text in (f'Frage {runde}', f'Antwort {runde}')]
    assert inhalte == erwartet


def test_vorschau_zeigt_die_zuletzt_eingefuegte_nachricht(tmp_path):
    store = ConversationStore(tmp_path / 'conversations.sqlite3')
    for runde in range(20):
        gespraech = store.create(f'Vorschau {runde}', at=ZEIT)
        store.add_message(gespraech.id, 'user', 'Wie ist der Stand?', at=ZEIT)
        store.add_message(gespraech.id, 'assistant', 'Der Stand ist gut.', at=ZEIT)
    vorschauen = {zeile.preview for zeile in store.list(limit=50)}
    assert vorschauen == {'Der Stand ist gut.'}, vorschauen
