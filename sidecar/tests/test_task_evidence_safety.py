"""Even an overconfident reviewer cannot add hard facts absent from the task quote."""
import pytest

from icarus_memory.task_review import review_tasks
from tests.test_task_review import Reviewer, verdict


@pytest.mark.parametrize('title,quote', [
    ('Anna Kranz anrufen', 'Bitte ruf Ben Kruse an.'),
    ('Ben Kruse anrufen', 'Bitte ruf Anna Kranz an.'),
    ('Bericht an anna@example.invalid senden', 'Bitte sende den Bericht an ben@example.invalid.'),
    ('Belege bis 20.10.2026 prüfen', 'Bitte prüfe die Belege.'),
    ('Belege bis 20.10.2027 prüfen', 'Bitte prüfe die Belege bis 20. Oktober 2026.'),
    ('Belege bis morgen prüfen', 'Bitte prüfe die Belege.'),
    ('50,00 EUR überweisen', 'Bitte überweise 49,00 EUR.'),
    ('Anna Kranz anrufen', 'Bitte ruf Anna Kranzmann an.'),
    ('Bericht an anna@example.invalid senden', 'Bitte sende den Bericht an joanna@example.invalid.'),
])
def test_positive_model_verdict_cannot_invent_names_addresses_dates_or_amounts(title, quote):
    item = {'title': title, 'quote': quote}
    # The wrong name/date also occurs elsewhere; it still cannot support this quote.
    body = quote + '\n\nAndere Sache: Anna Kranz, Ben Kruse, anna@example.invalid; 20.10.2027; 50,00 EUR.'
    assert review_tasks(Reviewer([verdict()]), 'Aufgabe', body, [item]) == []


@pytest.mark.parametrize('title,quote', [
    ('Anna Kranz anrufen', 'Bitte ruf Anna Kranz an.'),
    ('Belegprüfung', 'Kannst du die Belege prüfen?'),
    ('Entwurf prüfen', 'Bitte prüfe den Entwurf.'),
    ('Belege bis 20.10.2026 prüfen', 'Bitte prüfe die Belege bis 20. Oktober 2026.'),
    ('Belege bis morgen prüfen', 'Bitte prüfe die Belege bis morgen.'),
    ('49 EUR überweisen', 'Bitte überweise 49,00 EUR.'),
    ('Bericht Anna Kranz senden', 'Bitte sende den Bericht an Anna Kranz.'),
    ('Rechnung April bezahlen', 'Bitte bezahle die Rechnung für April.'),
])
def test_supported_names_and_normalized_dates_or_amounts_keep_real_tasks(title, quote):
    item = {'title': title, 'quote': quote}
    assert review_tasks(Reviewer([verdict()]), 'Aufgabe', quote, [item]) == [item]
