"""Local mail-to-calendar preparations never execute calendar writes."""
import hashlib
import sqlite3
import tempfile
import unittest
from pathlib import Path

from icarus_memory.calendar_actions import ActionError
from icarus_memory.mail_calendar_preparations import MailCalendarPreparations

UID = 'work:message-17'
BINDING = 'a' * 64


def context(text, *, limited=False, truncated=False):
    return {'uid': UID, 'status': 'ready', 'limited': limited, 'items': [
        {'episode_id': 'episode-17', 'current': True, 'title': 'Einladung',
         'text': text, 'truncated': truncated, 'attendees': ['ignored@example.invalid']},
    ]}


class MailCalendarPreparationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'calendar-actions.sqlite3'
        self.store = MailCalendarPreparations(self.path)

    def test_existing_action_table_persistence_restart_and_stale_stand(self):
        original = context('Wir treffen uns am 2026-10-24T10:00+02:00 bis 2026-10-24T11:00+02:00.')
        record = self.store.prepare(UID, BINDING, original, 'Einladung')
        self.assertEqual((record['status'], record['kind'], record['source_id']), ('preparation', 'mail_preparation', ''))
        self.assertFalse(record['reviewed'])
        self.assertEqual(record['fields'], {'title': 'Einladung', 'start': '2026-10-24T10:00+02:00', 'end': '2026-10-24T11:00+02:00'})
        quote = 'Wir treffen uns am 2026-10-24T10:00+02:00 bis 2026-10-24T11:00+02:00.'
        self.assertEqual(record['origins']['start'], {'kind': 'source', 'quote': quote})
        with sqlite3.connect(self.path) as db:
            self.assertEqual(db.execute('SELECT status FROM actions WHERE id=?', (record['id'],)).fetchone(), ('preparation',))
            self.assertEqual(db.execute("SELECT sql FROM sqlite_master WHERE name='actions'").fetchone()[0],
                'CREATE TABLE actions (id TEXT PRIMARY KEY, status TEXT NOT NULL, record TEXT NOT NULL)')
        edited = self.store.update(record['id'], record['stand'],
            {'title': 'Eigener Titel', 'start': record['fields']['start'], 'end': record['fields']['end']}, True)
        reopened = MailCalendarPreparations(self.path)
        repeated = reopened.prepare(UID, BINDING, original, 'Einladung')
        self.assertEqual(repeated, edited)
        self.assertEqual(repeated['origins']['title'], {'kind': 'user', 'quote': ''})
        self.assertTrue(repeated['reviewed'])
        with self.assertRaises(ActionError) as stale:
            reopened.update(record['id'], record['stand'], edited['fields'], True)
        self.assertEqual(stale.exception.status, 409)

    def test_idempotent_prepare_preserves_saved_edits(self):
        first = self.store.prepare(UID, BINDING,
            context('Am 2026-10-24T10:00+02:00 bis 2026-10-24T11:00+02:00.'), 'Alt')
        edited = self.store.update(first['id'], first['stand'], {'title': 'Von mir', 'start': '', 'end': ''}, False)
        second = self.store.prepare(UID, BINDING,
            context('Am 2026-10-25T10:00+02:00 bis 2026-10-25T11:00+02:00.'), 'Neu')
        self.assertEqual(second, edited)
        self.assertEqual(second['fields']['title'], 'Von mir')
        self.assertIn('unbestätigt', second['context']['warnings'][0])

    def test_missing_times_and_strict_user_time_validation(self):
        record = self.store.prepare(UID, BINDING, context('Bitte melde dich wegen des Termins.'), 'Betreff')
        self.assertEqual(record['fields']['start'], record['fields']['end'], '')
        self.assertEqual(record['origins']['start']['kind'], 'missing')
        invalid = (
            {'title': 'T', 'start': '2026-10-24T10:00', 'end': ''},
            {'title': 'T', 'start': '2026-10-24 10:00+02:00', 'end': ''},
            {'title': 'T', 'start': '2026-10-24T10:00+02:99', 'end': ''},
            {'title': 'T', 'start': '2026-10-24T10:00+02:00', 'end': '2026-10-24T10:00+02:00'},
            {'title': 'T' * 501, 'start': '', 'end': ''},
            {'title': 'T', 'start': '', 'end': 'x' * 65},
        )
        for fields in invalid:
            with self.subTest(fields=fields), self.assertRaises(ActionError):
                self.store.update(record['id'], record['stand'], fields, False)
        with self.assertRaises(ActionError) as missing:
            self.store.get('missing')
        self.assertEqual(missing.exception.status, 404)

    def test_alternative_cancellation_limited_and_truncated_text_never_auto_select(self):
        cases = (
            ('Option A 2026-10-24T10:00+02:00 bis 2026-10-24T11:00+02:00 oder Option B 2026-10-25T10:00+02:00 bis 2026-10-25T11:00+02:00.', False, False),
            ('2026-10-24T10:00+02:00 und 2026-10-24T11:00+02:00.', False, False),
            ('2026-10-24T10:00+02:99 bis 2026-10-24T11:00+02:00.', False, False),
            ('Der Termin ist abgesagt: 2026-10-24T10:00+02:00 bis 2026-10-24T11:00+02:00.', False, False),
            ('2026-10-24T10:00+02:00 bis 2026-10-24T11:00+02:00.', True, False),
            ('2026-10-24T10:00+02:00 bis 2026-10-24T11:00+02:00.', False, True),
        )
        for index, (body, limited, truncated) in enumerate(cases):
            with self.subTest(body=body, limited=limited, truncated=truncated):
                uid = f'{UID}:{index}'
                record = self.store.prepare(uid, BINDING, context(body, limited=limited, truncated=truncated) | {'uid': uid}, 'Betreff')
                self.assertEqual(record['fields']['start'], record['fields']['end'], '')
                self.assertEqual(record['origins']['start']['kind'], record['origins']['end']['kind'], 'missing')
                self.assertTrue(record['context']['unverified_limited_history'])
                self.assertTrue(record['context']['warnings'])

    def test_nonunique_current_item_and_guest_data_are_not_used(self):
        data = context('2026-10-24T10:00+02:00 bis 2026-10-24T11:00+02:00.')
        data['items'].append({'episode_id': 'episode-18', 'current': True, 'text': 'andere', 'truncated': False})
        record = self.store.prepare(UID, BINDING, data, 'Betreff')
        self.assertEqual(record['fields']['start'], record['fields']['end'], '')
        self.assertNotIn('attendees', record)
        self.assertFalse({'guests', 'attendees', 'provider_event_id'} & set(record))
        self.assertEqual(record['id'], 'mp' + hashlib.sha256((UID + BINDING).encode()).hexdigest())

    def test_truncated_historical_item_blocks_time_suggestions(self):
        data = context('2026-10-24T10:00+02:00 bis 2026-10-24T11:00+02:00.')
        data['items'].append({'episode_id': 'episode-old', 'current': False,
                              'text': 'älterer Verlauf', 'truncated': True})
        record = self.store.prepare(UID, BINDING, data, 'Betreff')
        self.assertEqual(record['fields']['start'], record['fields']['end'], '')
        self.assertTrue(any('gekürzt' in warning for warning in record['context']['warnings']))

    def test_complete_german_long_date_and_numeric_date_are_normalized_with_source_quote(self):
        cases = (
            ('Besprechung am 12. Oktober 2026 von 10:30 bis 11:15 Uhr (MESZ)',
             '2026-10-12T10:30:00+02:00', '2026-10-12T11:15:00+02:00'),
            ('12.10.2026, 10:30–11:15 Uhr UTC+02:00',
             '2026-10-12T10:30:00+02:00', '2026-10-12T11:15:00+02:00'),
            ('12.10.2026, 10:30 bis 11:15 Uhr (MEZ)',
             '2026-10-12T10:30:00+01:00', '2026-10-12T11:15:00+01:00'),
            ('12.10.2026, 10:30–11:15 Uhr UTC',
             '2026-10-12T10:30:00+00:00', '2026-10-12T11:15:00+00:00'),
            ('12.10.2026, 10:30–11:15 Uhr UTC-04:00',
             '2026-10-12T10:30:00-04:00', '2026-10-12T11:15:00-04:00'),
        )
        for index, (paragraph, start, end) in enumerate(cases):
            with self.subTest(paragraph=paragraph):
                uid = f'{UID}:de:{index}'
                record = self.store.prepare(uid, BINDING, context(paragraph) | {'uid': uid}, 'Termin')
                self.assertEqual((record['fields']['start'], record['fields']['end']), (start, end))
                self.assertEqual(record['origins']['start'], {'kind': 'source', 'quote': paragraph})
                self.assertEqual(record['origins']['end'], {'kind': 'source', 'quote': paragraph})

    def test_incomplete_invalid_and_alternative_german_spans_stay_empty(self):
        cases = (
            'Besprechung am 12. Oktober von 10:30 bis 11:15 Uhr (MESZ)',
            'Besprechung am 12. Oktober 2026 um 10:30 Uhr (MESZ)',
            'Besprechung am 12. Oktober 2026 von 10:30 bis 11:15 Uhr',
            '12.10.2026, 10:30–11:15 Uhr UTC+02:99',
            '31.02.2026, 10:30–11:15 Uhr UTC+02:00',
            '12.10.2026, 10:30–11:15 Uhr UTC+24:00',
            '12.10.2026, 10:30–11:15 Uhr UTC+02:00 oder 13.10.2026, 10:30–11:15 Uhr UTC+02:00',
            'Absage: 12.10.2026, 10:30–11:15 Uhr UTC+02:00',
            '12.10.2026, 10:30–11:15 Uhr (UTC+02:00) und zusätzlich 12.10.2026, 12:00–13:00 Uhr (UTC+02:00)',
        )
        for index, paragraph in enumerate(cases):
            with self.subTest(paragraph=paragraph):
                uid = f'{UID}:de-invalid:{index}'
                record = self.store.prepare(uid, BINDING, context(paragraph) | {'uid': uid}, 'Termin')
                self.assertEqual(record['fields']['start'], record['fields']['end'], '')
                self.assertEqual(record['origins']['start']['kind'], record['origins']['end']['kind'], 'missing')

    def test_cancellation_in_a_known_item_title_blocks_times_from_its_body(self):
        data = context('Treffen: 2026-10-12T10:00+02:00 bis 2026-10-12T11:00+02:00.')
        data['items'][0]['title'] = 'Absage: Treffen'
        record = self.store.prepare(f'{UID}:title-cancel', BINDING, data | {'uid': f'{UID}:title-cancel'}, 'Treffen')
        self.assertEqual(record['fields']['start'], record['fields']['end'], '')
        self.assertTrue(any('Absage' in warning for warning in record['context']['warnings']))

    def test_different_complete_time_range_in_known_reply_blocks_auto_choice(self):
        data = context('Termin: 2026-10-12T10:00+02:00 bis 2026-10-12T11:00+02:00.')
        data['items'].append({'episode_id': 'reply', 'current': False, 'title': 'Re: Termin',
            'text': 'Neuer Termin: 2026-10-12T12:00+02:00 bis 2026-10-12T13:00+02:00.', 'truncated': False})
        uid = f'{UID}:different-reply'
        record = self.store.prepare(uid, BINDING, data | {'uid': uid}, 'Termin')
        self.assertEqual(record['fields']['start'], record['fields']['end'], '')
        self.assertTrue(any('abweichende' in warning for warning in record['context']['warnings']))

    def test_identical_quoted_time_range_in_known_reply_can_survive(self):
        paragraph = 'Termin: 2026-10-12T10:00+02:00 bis 2026-10-12T11:00+02:00.'
        data = context(paragraph)
        data['items'].append({'episode_id': 'reply', 'current': False, 'title': 'Re: Termin',
            'text': 'Zur Erinnerung: ' + paragraph, 'truncated': False})
        uid = f'{UID}:same-reply'
        record = self.store.prepare(uid, BINDING, data | {'uid': uid}, 'Termin')
        self.assertEqual((record['fields']['start'], record['fields']['end']),
            ('2026-10-12T10:00+02:00', '2026-10-12T11:00+02:00'))


if __name__ == '__main__':
    unittest.main()
