"""Status darf weder aus einer anderen Sache noch aus dem Quellenkopf stammen."""
import pytest
from icarus_memory.satzpruefung import Beleg, Satz, satz_pruefen


@pytest.mark.parametrize(('statement', 'sources'), [
    ('Die Lieferung Z-204 wurde bezahlt.',{'1':Beleg('1','Die Rechnung R-719 wurde bezahlt.'),'2':Beleg('2','Die Lieferung Z-204 wurde vorbereitet.')}),
    ('Die Lieferung Z-204 ist offen.',{'1':Beleg('1','Die Rechnung R-719 ist offen.'),'2':Beleg('2','Die Lieferung Z-204 wurde vorbereitet.')}),
    ('Die Rechnung R-719 wurde zugestellt.',{'1':Beleg('1','Die Lieferung Z-204 wurde zugestellt.'),'2':Beleg('2','Die Rechnung R-719 wurde erstellt.')}),
    ('Die Lieferung Z-204 wurde bezahlt.',{'1':Beleg('1','Die Lieferung Z-205 wurde bezahlt.'),'2':Beleg('2','Die Lieferung Z-204 wurde vorbereitet.')}),
    ('Die Rechnung R-720 ist offen.',{'1':Beleg('1','Die Rechnung R-719 ist offen.'),'2':Beleg('2','Die Rechnung R-720 wurde erstellt.')}),
    ('Mira Sander hat bezahlt.',{'1':Beleg('1','Anna Keller hat bezahlt.'),'2':Beleg('2','Mira Sander hat die Unterlagen geprüft.')}),
    ('Nora Weber hat bezahlt.',{'1':Beleg('1','Nola Weber hat bezahlt.'),'2':Beleg('2','Nora Weber hat die Unterlagen geprüft.')}),
    ('Die Lieferung Z-204 wurde bezahlt.',{'1':Beleg('1','Die Lieferung Z-205 wurde bezahlt; die Lieferung Z-204 wurde vorbereitet.')}),
    ('Die Lieferung Z-204 wurde bezahlt.',{'1':Beleg('1','Die Rechnung R-719 wurde bezahlt. Die Lieferung Z-204 wurde vorbereitet.')}),
    ('Die Lieferung Z-204 wurde bezahlt; die Rechnung R-719 wurde vorbereitet.',{'1':Beleg('1','Die Lieferung Z-204 wurde vorbereitet; die Rechnung R-719 wurde bezahlt.')}),
    ('Z-204 wurde bezahlt.',{'1':Beleg('1','Z-205 wurde bezahlt.'),'2':Beleg('2','Z-204 wurde vorbereitet.')}),
    ('Tim hat bezahlt.',{'1':Beleg('1','Jan hat bezahlt.'),'2':Beleg('2','Tim hat die Unterlagen geprüft.')}),
    ('Die Rechnung ist bezahlt.',{'1':Beleg('1','Die Rechnung R-719 wurde bezahlt.'),'2':Beleg('2','Die Rechnung R-720 ist noch offen.')}),
    ('Z-204: Die Zustimmung liegt noch nicht vor.',{'1':Beleg('1','Z-205: Die Zustimmung liegt noch nicht vor.'),'2':Beleg('2','Z-204: Die Zustimmung liegt bereits vor.')}),
    ('Die Lieferung ist bezahlt.',{'1':Beleg('1','Anna Keller: Die Lieferung Z-204 wurde bezahlt.'),'2':Beleg('2','Mira Sander: Die Lieferung Z-205 wurde vorbereitet.')}),
    ('Die Rechnung R-719 wurde bezahlt.',{'1':Beleg('1','Die Rechnung R-719 wurde erstellt.',kopf='Rechnung R-719 wurde bezahlt')}),
    ('Die Rechnung R-719 wurde bezahlt.',{'1':Beleg('1','Die Rechnung R-720 wurde bezahlt.',kopf='Rechnung R-719'),'2':Beleg('2','Die Rechnung R-719 wurde erstellt.')}),
    ('Die Rechnung R-719 ist offen und die Rechnung R-720 ist bezahlt.',{'1':Beleg('1','Die Rechnung R-719 ist bezahlt und die Rechnung R-720 ist offen.')}),
    ('Die Rechnung ist bezahlt.',{'1':Beleg('1','Die Rechnung R-719 wurde bezahlt.'),'2':Beleg('2','Die Rechnung ist noch offen.')}),
    ('R-719 wurde bezahlt.',{'1':Beleg('1','R-719 wurde bezahlt.'),'2':Beleg('2','R-719 ist noch offen.')}),
])
def test_status_cannot_be_donated_by_an_unrelated_subject(statement, sources):
    assert not satz_pruefen(Satz(statement,tuple(sources)),sources).bestanden


@pytest.mark.parametrize(('statement', 'source'), [
    ('Die Lieferung Z-204 wurde bezahlt.','Die Lieferung Z-204 wurde bezahlt.'),
    ('Die Rechnung R-719 ist offen.','Die Rechnung R-719 ist offen.'),
    ('Mira Sander hat bezahlt.','Mira Sander hat bezahlt.'),
    ('Z-204 wurde bezahlt.','Z-204 wurde bezahlt.'),
    ('Tim hat bezahlt.','Tim hat bezahlt.'),
    ('Die Lieferung z-204 wurde bezahlt.','Die Lieferung Z-204 wurde bezahlt.'),
    ('Die Rechnung R-719 ist bezahlt und unterschrieben.','Die Rechnung R-719 ist bezahlt und unterschrieben.'),
    ('Die Lieferung Z-204 wurde bezahlt; die Rechnung R-719 wurde vorbereitet.','Die Lieferung Z-204 wurde bezahlt; die Rechnung R-719 wurde vorbereitet.'),
    ('Die Rechnung R-719 wurde vorbereitet; die Lieferung Z-204 wurde bezahlt.','Die Rechnung R-719 wurde vorbereitet; die Lieferung Z-204 wurde bezahlt.'),
    ('Bei Z-204 darf die Lieferung erst nach schriftlicher Zustimmung versandt werden. Die Zustimmung liegt noch nicht vor.','Bei Z-204 darf die Lieferung erst nach schriftlicher Zustimmung versandt werden. Die Zustimmung liegt noch nicht vor.'),
])
def test_status_keeps_its_own_subject(statement, source):
    sources = {'1':Beleg('1',source)}
    result = satz_pruefen(Satz(statement,('1',)),sources)
    assert result.bestanden, result.gruende

def test_source_title_can_identify_its_own_status_body():
    sources = {'1':Beleg('1','Die Rechnung wurde bezahlt.',kopf='Rechnung R-719')}
    result = satz_pruefen(Satz('Die Rechnung R-719 wurde bezahlt.',('1',)),sources)
    assert result.bestanden, result.gruende
