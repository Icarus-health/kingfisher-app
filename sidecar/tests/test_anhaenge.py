"""Anhänge lesen (M4): PDF-Rechnungen werden eine Quelle mit Seite, Fristen daraus mit wörtlichem Beleg.

Zusicherungen (jede mit Sabotageprobe, docs/49-kreis-und-privat.md):

1. Ein PDF-Anhang mit Text wird Seite für Seite gelesen; Bilder ohne Dokumentnamen (Urlaubsfotos) nicht.
2. Grenzen: höchstens `MAX_SEITEN` Seiten, Zeitgrenze, zu große oder beschädigte Anhänge sagen in einem Satz, warum.
3. Gescannt ohne Texterkennung: ehrlich „noch nicht gelesen“; mit einem lokalen OCR-Modell gelesen; ein OCR-Modell nur
   in der Cloud zählt nie.
4. Der Anhang wird eine eigene Quelle mit den Beteiligten der Mail (gleiche Akte) und „Seite N“ im Text.
5. Fristen aus dem Anhang: Aufgabenvorschlag mit wörtlichem Satz, Seite in der Begründung, jede Zahl belegt; dieselbe
   Frist in Mail und Anhang ist ein Vorschlag, nicht zwei.
"""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from email.message import EmailMessage
from io import BytesIO

import httpx
import pytest
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject, NumberObject

from icarus_memory import akten_arten, anhaenge
from icarus_memory.akten_arten import zahlen_belegt
from icarus_memory.connectors.mail import Message
from icarus_memory.mail_ingestion import remember
from tests.test_context_identity import core  # noqa: F401 - Fixture
from tests.test_kreis import ICH, api  # noqa: F401 - Fixture

PRAXIS = 'rechnung@zahnarzt-sommer.example'
JPEG = bytes.fromhex('ffd8ffe000104a46494600010101004800480000ffdb004300') + b'\xff' * 64 + bytes.fromhex(
    'ffc0000b080001000101011100ffc40014100100000000000000000000000000000000ffda0008010100013f10ffd9')


def kuenftig(tage: int) -> date:
    return date.today() + timedelta(days=tage)


def pdf(seiten: list[list[str]] | None = None, *, scan: int = 0, verschluesselt: bool = False) -> bytes:
    """Eine PDF wie aus einem Rechnungsprogramm (Helvetica, WinAnsi) oder, mit `scan`, nur Bilder ohne Textebene."""
    writer = PdfWriter()
    font = writer._add_object(DictionaryObject({  # noqa: SLF001
        NameObject('/Type'): NameObject('/Font'), NameObject('/Subtype'): NameObject('/Type1'),
        NameObject('/BaseFont'): NameObject('/Helvetica'), NameObject('/Encoding'): NameObject('/WinAnsiEncoding')}))
    for zeilen in seiten or []:
        page = writer.add_blank_page(width=595, height=842)
        page[NameObject('/Resources')] = DictionaryObject({NameObject('/Font'): DictionaryObject({NameObject('/F1'): font})})
        inhalt = b'BT /F1 11 Tf 14 TL 50 790 Td\n' + b''.join(
            b'(' + z.encode('cp1252').replace(b'(', b'\\(').replace(b')', b'\\)') + b') Tj T*\n' for z in zeilen) + b'ET'
        strom = DecodedStreamObject()
        strom.set_data(inhalt)
        page[NameObject('/Contents')] = writer._add_object(strom)  # noqa: SLF001
    for _ in range(scan):
        page = writer.add_blank_page(width=595, height=842)
        bild = DecodedStreamObject()
        bild.set_data(JPEG)
        bild.update({NameObject('/Type'): NameObject('/XObject'), NameObject('/Subtype'): NameObject('/Image'),
                     NameObject('/Width'): NumberObject(1), NameObject('/Height'): NumberObject(1),
                     NameObject('/ColorSpace'): NameObject('/DeviceGray'), NameObject('/BitsPerComponent'): NumberObject(8),
                     NameObject('/Filter'): NameObject('/DCTDecode')})
        page[NameObject('/Resources')] = DictionaryObject({NameObject('/XObject'): DictionaryObject(
            {NameObject('/Im1'): writer._add_object(bild)})})  # noqa: SLF001
        strom = DecodedStreamObject()
        strom.set_data(b'q 595 0 0 842 0 0 cm /Im1 Do Q')
        page[NameObject('/Contents')] = writer._add_object(strom)  # noqa: SLF001
    if verschluesselt:
        writer.encrypt('geheim')
    ausgabe = BytesIO()
    writer.write(ausgabe)
    return ausgabe.getvalue()


def rechnung(tage_bis: int = 18) -> list[list[str]]:
    return [['Zahnarztpraxis Dr. Sommer', 'Rechnung Nr. S-2026-311', 'Rechnungsbetrag: 112,80 €',
             f'Bitte überweisen Sie den Rechnungsbetrag bis zum {kuenftig(tage_bis):%d.%m.%Y}.'],
            ['Vielen Dank für Ihr Vertrauen.']]


def mail_mit(*dateien: tuple[str, bytes, str], text: str = 'Sehr geehrte Frau Hartmann,\n\nanbei Ihre Rechnung.') -> EmailMessage:
    nachricht = EmailMessage()
    nachricht['From'] = f'Zahnarztpraxis Dr. Sommer <{PRAXIS}>'
    nachricht['To'] = ICH
    nachricht['Subject'] = 'Ihre Rechnung'
    nachricht.set_content(text)
    for name, daten, art in dateien:
        haupt, _, unter = art.partition('/')
        nachricht.add_attachment(daten, maintype=haupt, subtype=unter, filename=name)
    return nachricht


# -- 1. bis 3.: Lesen -------------------------------------------------------------------------------------------------


def test_pdf_wird_seite_fuer_seite_gelesen_urlaubsfotos_nicht():
    (anhang,) = anhaenge.aus_mail(mail_mit(('Rechnung-S-2026-311.pdf', pdf(rechnung()), 'application/pdf'),
                                           ('Strand.jpg', JPEG, 'image/jpeg')))
    assert (anhang.dateiname, anhang.status, anhang.gesamt) == ('Rechnung-S-2026-311.pdf', anhaenge.GELESEN, 2)
    assert 'Rechnungsbetrag: 112,80 €' in anhang.seiten[0] and anhang.seiten[1] == 'Vielen Dank für Ihr Vertrauen.'
    text = anhaenge.text(anhang, 'Ihre Rechnung', datetime(2026, 9, 20))
    assert text.startswith('Anhang „Rechnung-S-2026-311.pdf“ der Mail „Ihre Rechnung“ vom 20.09.2026.')
    assert '\n\nSeite 1\nZahnarztpraxis Dr. Sommer' in text and '\n\nSeite 2\nVielen Dank' in text
    assert anhaenge.seite_der_stelle(text, 'Vielen Dank für Ihr Vertrauen.') == 2
    assert anhaenge.seite_der_stelle(text, 'Rechnungsbetrag: 112,80 €') == 1


def test_grenzen_seiten_zeit_groesse_und_beschaedigt(monkeypatch):
    monkeypatch.setattr(anhaenge, 'MAX_SEITEN', 1)
    (anhang,) = anhaenge.aus_mail(mail_mit(('Rechnung.pdf', pdf(rechnung()), 'application/pdf')))
    assert len(anhang.seiten) == 1 and anhang.hinweis == 'Gelesen sind die ersten 1 von 2 Seiten.'
    monkeypatch.setattr(anhaenge, 'ZEITGRENZE_S', 0.001)
    (zu_lang,) = anhaenge.aus_mail(mail_mit(('Rechnung.pdf', pdf(rechnung()), 'application/pdf')))
    assert zu_lang.status == anhaenge.FEHLER and 'zu lange' in zu_lang.hinweis
    monkeypatch.undo()
    (kaputt,) = anhaenge.aus_mail(mail_mit(('Vertrag.pdf', b'%PDF-1.4 kaputt', 'application/pdf')))
    assert kaputt.status == anhaenge.FEHLER and kaputt.hinweis.startswith('Anhang „Vertrag.pdf“ konnte nicht gelesen werden:')
    (geheim,) = anhaenge.aus_mail(mail_mit(('Police.pdf', pdf(rechnung(), verschluesselt=True), 'application/pdf')))
    assert geheim.status == anhaenge.FEHLER and 'unverschlüsselte' in geheim.hinweis
    (gross,) = anhaenge.aus_mail(mail_mit(('Rechnung.pdf', pdf(rechnung()), 'application/pdf')), abgeschnitten=True)
    assert gross.status == anhaenge.ZU_GROSS and 'zu groß' in gross.hinweis
    viele = [(f'Rechnung-{n}.pdf', pdf([[f'Seite {n}']]), 'application/pdf') for n in range(7)]
    assert len(anhaenge.aus_mail(mail_mit(*viele))) == anhaenge.MAX_ANHAENGE


def test_gescannt_ohne_texterkennung_ehrlich_mit_lokaler_texterkennung_gelesen():
    (scan,) = anhaenge.aus_mail(mail_mit(('Rechnung-Scan.pdf', pdf(scan=1), 'application/pdf')))
    assert scan.status == anhaenge.GESCANNT and not scan.gelesen
    assert scan.hinweis.startswith('Gescannte Rechnung „Rechnung-Scan.pdf“ (1 Seite), noch nicht gelesen.')
    gesehen = []
    (gelesen,) = anhaenge.aus_mail(mail_mit(('Rechnung-Scan.pdf', pdf(scan=1), 'application/pdf')),
                                   ocr=lambda bild: gesehen.append(bild) or 'Rechnungsbetrag: 64,00 €')
    assert gelesen.status == anhaenge.OCR and gelesen.seiten == ('Rechnungsbetrag: 64,00 €',) and gesehen == [JPEG]
    assert 'Seite 1 (Texterkennung)\nRechnungsbetrag: 64,00 €' in anhaenge.text(gelesen, 'Rechnung', None)
    (foto,) = anhaenge.aus_mail(mail_mit(('Quittung.jpg', JPEG, 'image/jpeg')))
    assert foto.status == anhaenge.GESCANNT and 'noch nicht gelesen' in foto.hinweis


class _Ollama:
    def __init__(self, tags):
        self.tags, self.anfragen = tags, []
        self.transport = httpx.MockTransport(self._antwort)

    def _antwort(self, anfrage: httpx.Request) -> httpx.Response:
        koerper = json.loads(anfrage.content) if anfrage.content else None
        self.anfragen.append((anfrage.url.path, koerper))
        if anfrage.url.path == '/api/tags':
            return httpx.Response(200, json={'models': self.tags})
        if anfrage.url.path == '/api/generate':
            return httpx.Response(200, json={'response': 'Zahlbar bis 30.11.2026'})
        return httpx.Response(404)


def test_texterkennung_nur_mit_lokalem_ocr_modell(api):
    app, _ = api
    lokal = {'name': 'glm-ocr:latest', 'digest': '0' * 64, 'details': {'format': 'gguf'}}
    cloud = {'name': 'deepseek-ocr:cloud', 'remote_host': 'https://ollama.com:443', 'digest': '', 'details': {}}
    andere = {'name': 'qwen3:8b', 'digest': '1' * 64, 'details': {'format': 'gguf'}}
    for tags, erwartet in (([andere], False), ([cloud, andere], False), ([lokal, andere], True)):
        app.state.ollama_inventar = None
        ollama = _Ollama(tags)
        app.state.ollama_transport = ollama.transport
        lesen = anhaenge.ocr_fuer(app)
        assert (lesen is not None) == erwartet, tags
    assert lesen(JPEG) == 'Zahlbar bis 30.11.2026'
    pfad, koerper = ollama.anfragen[-1]
    assert pfad == '/api/generate' and koerper['model'] == 'glm-ocr:latest' and koerper['images']


# -- 4. und 5.: Quelle, Akte, Frist ------------------------------------------------------------------------------------


def _aufnehmen(app, nachricht: EmailMessage, uid: str = '1'):
    from icarus_memory.anhaenge import aus_mail
    message = Message(uid=f'konto:{uid}', subject=str(nachricht['Subject']), sender=str(nachricht['From']),
                      date=datetime.now(timezone.utc) - timedelta(days=1), preview='', unread=False,
                      body=nachricht.get_body(('plain',)).get_content(), account_id='konto',
                      message_id=f'<anhang-{uid}@example.invalid>',
                      recipients=({'rolle': 'an', 'name': 'Lea Hartmann', 'adresse': ICH},), own_addresses=(ICH,),
                      anhaenge=aus_mail(nachricht))
    return remember(app.state.episodes, message, claims=app.state.claims)


def test_anhang_wird_quelle_in_derselben_akte_und_frist_mit_seite(api):
    app, client = api
    ergebnis = _aufnehmen(app, mail_mit(('Rechnung-S-2026-311.pdf', pdf(rechnung()), 'application/pdf')))
    (anhang_id,) = ergebnis['anhaenge']
    episode = app.state.episodes.get(anhang_id)
    assert episode.kind.value == 'document' and anhaenge.ist_anhang(episode) and 'anhang:gelesen' in episode.tags
    assert episode.title == 'Rechnung-S-2026-311.pdf (Anhang zu „Ihre Rechnung“)'
    assert episode.provenance.source_ref.endswith('#anhang:1:Rechnung-S-2026-311.pdf')
    assert [c['adresse'] for c in episode.contacts if c['rolle'] == 'von'] == [PRAXIS]
    lauf = client.post('/api/v1/akten/arten/fristen').json()
    assert lauf['vorgeschlagen'] == 1, lauf
    (vorschlag,) = [v for v in client.get('/api/v1/task-candidates').json()
                    if v['proposed_by'].startswith(akten_arten.VORGESCHLAGEN_VON)]
    assert vorschlag['statement'] == f'Zahlung bis {kuenftig(18):%d.%m.%Y}: 112,80 € (Zahnarztpraxis Dr. Sommer)'
    assert vorschlag['evidence'][0]['episode_id'] == anhang_id
    assert vorschlag['evidence'][0]['quote'] == f'Bitte überweisen Sie den Rechnungsbetrag bis zum {kuenftig(18):%d.%m.%Y}.'
    assert 'Aus dem Anhang „Rechnung-S-2026-311.pdf“, Seite 1, einer Mail der Akte' in vorschlag['rationale']
    assert zahlen_belegt(vorschlag['statement'], episode.body) == []
    # Die Akte der Praxis kennt den Anhang als Quelle.
    quellen = client.get('/api/v1/akten/akte', params={'sache': 'organisation:zahnarztsommer'}).json()
    assert quellen['quellen']['gesamt'] == 2


def test_gescannter_anhang_steht_ehrlich_da_und_ergibt_keine_frist(api):
    app, client = api
    ergebnis = _aufnehmen(app, mail_mit(('Rechnung-Scan.pdf', pdf(scan=1), 'application/pdf')))
    (anhang_id,) = ergebnis['anhaenge']
    body = app.state.episodes.get(anhang_id).body
    assert 'Gescannte Rechnung „Rechnung-Scan.pdf“ (1 Seite), noch nicht gelesen.' in body
    assert client.post('/api/v1/akten/arten/fristen').json()['vorgeschlagen'] == 0


def test_dieselbe_frist_in_mail_und_anhang_ist_ein_vorschlag(api):
    app, client = api
    from icarus_memory.datumstext import MONATE
    tag = kuenftig(18)
    # Anders geschrieben als im PDF („19. Oktober 2026“ statt „19.10.2026“): derselbe Tag, derselbe Betrag, eine Frist.
    satz = f'Bitte überweisen Sie den Rechnungsbetrag bis zum {tag.day}. {MONATE[tag.month - 1]} {tag.year}.'
    _aufnehmen(app, mail_mit(('Rechnung.pdf', pdf(rechnung()), 'application/pdf'),
                             text=f'Sehr geehrte Frau Hartmann,\n\nRechnungsbetrag: 112,80 €\n\n{satz}'))
    assert client.post('/api/v1/akten/arten/fristen').json()['vorgeschlagen'] == 1


@pytest.mark.parametrize('name', ['Urlaub.jpg'])
def test_ohne_dokumentnamen_kein_bild(name):
    assert anhaenge.aus_mail(mail_mit((name, JPEG, 'image/jpeg'))) == ()
