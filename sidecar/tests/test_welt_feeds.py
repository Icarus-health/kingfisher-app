"""Feeds: RSS und Atom sicher lesen. Keine Entitäten, Größenlimits, nur https, fremder Text bleibt Text."""
import socket

import httpx
import pytest

from icarus_memory import security, welt_feeds
from icarus_memory.welt_feeds import FeedFehler, abrufen, lesen

RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel><title>Nachrichten</title>
<item><title>Klinikum Rheingau-Süd baut aus</title><link>https://news.example/a1</link>
<description>&lt;p&gt;Der &lt;b&gt;Neubau&lt;/b&gt; soll 2027 fertig sein.&lt;/p&gt;&lt;script&gt;alert(1)&lt;/script&gt;</description>
<pubDate>Tue, 29 Sep 2026 07:30:00 +0200</pubDate><guid>a1</guid></item>
<item><title>Ohne Link</title><link>javascript:alert(1)</link><description>x</description></item>
<item><title></title><link>https://news.example/leer</link></item>
</channel></rss>""".encode()

ATOM = """<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom"><title>Blog</title>
<entry><title>Neue Regel für Pflegekräfte</title><id>tag:x,2026:1</id>
<link rel="alternate" href="https://blog.example/regel"/><link rel="self" href="https://blog.example/self"/>
<updated>2026-09-29T06:00:00Z</updated><summary>Ab Januar gilt eine neue Regel.</summary></entry></feed>""".encode()


def test_rss_wird_gelesen_html_wird_text_und_unsichere_links_fallen_weg():
    eintraege = lesen(RSS)
    assert [e.titel for e in eintraege] == ['Klinikum Rheingau-Süd baut aus', 'Ohne Link']  # leerer Titel entfällt
    erster, zweiter = eintraege
    assert erster.text.startswith('Der Neubau soll 2027 fertig sein.')
    assert '<' not in erster.text and 'script' not in erster.text.lower()
    assert erster.link == 'https://news.example/a1' and erster.datum.year == 2026 and erster.kennung == 'a1'
    assert zweiter.link == ''  # javascript: ist kein Link


def test_atom_wird_gelesen_und_nimmt_den_alternate_link():
    (eintrag,) = lesen(ATOM)
    assert eintrag.titel == 'Neue Regel für Pflegekräfte' and eintrag.link == 'https://blog.example/regel'
    assert eintrag.text == 'Ab Januar gilt eine neue Regel.' and eintrag.datum.isoformat() == '2026-09-29T06:00:00+00:00'


def test_feed_mit_entitaeten_oder_dokumenttyp_wird_abgelehnt_bevor_ein_parser_ihn_sieht(monkeypatch):
    lachen = b'<?xml version="1.0"?><!DOCTYPE lolz [<!ENTITY a "aaaaaaaaaa"><!ENTITY b "&a;&a;&a;&a;&a;&a;">]>' \
             b'<rss><channel><item><title>&b;</title></item></channel></rss>'
    extern = b'<?xml version="1.0"?><!DOCTYPE x [<!ENTITY e SYSTEM "file:///etc/passwd">]><rss><channel>' \
             b'<item><title>&e;</title></item></channel></rss>'
    klein = b'<!doctype rss><rss><channel><item><title>x</title></item></channel></rss>'
    aufgerufen = []
    monkeypatch.setattr(welt_feeds.ET, 'fromstring', lambda *a, **k: aufgerufen.append(1))
    for boese in (lachen, extern, klein):
        with pytest.raises(FeedFehler, match='Definitionen'):
            lesen(boese)
    assert aufgerufen == []  # der Parser bekam nichts davon zu sehen


def test_utf16_kann_die_entitaetenpruefung_nicht_umgehen():
    boese = '<?xml version="1.0" encoding="utf-16"?><!DOCTYPE x [<!ENTITY a "b">]><rss/>'.encode('utf-16')
    with pytest.raises(FeedFehler):
        lesen(boese)


def test_zu_grosse_feeds_werden_abgelehnt_und_die_zahl_der_eintraege_ist_begrenzt():
    with pytest.raises(FeedFehler, match='zu groß'):
        lesen(b'<rss>' + b'x' * welt_feeds.MAX_FEED_BYTES + b'</rss>')
    viele = '<rss><channel>' + ''.join(f'<item><title>Meldung {i}</title></item>' for i in range(200)) + '</channel></rss>'
    assert len(lesen(viele.encode())) == welt_feeds.MAX_EINTRAEGE


def test_was_kein_feed_ist_wird_abgelehnt():
    for kaputt in (b'<html><body>Hallo</body></html>', b'kein xml', b'<rss><channel><item>'):
        with pytest.raises(FeedFehler):
            lesen(kaputt)


def test_sehr_lange_titel_werden_gekuerzt_und_zeilenumbrueche_zu_leerzeichen():
    lang = '<rss><channel><item><title>' + 'Wort\n\t ' * 200 + 'Ende</title></item></channel></rss>'
    (eintrag,) = lesen(lang.encode())
    assert len(eintrag.titel) <= welt_feeds.MAX_TITEL + 2 and '\n' not in eintrag.titel and '\t' not in eintrag.titel


# -- Abruf ---------------------------------------------------------------------------------------------------------------


@pytest.fixture
def oeffentlich(monkeypatch):
    def aufloesen(host, port, *, proto):
        privat = host in ('intern.example', 'localhost')
        return [(socket.AF_INET, socket.SOCK_STREAM, proto, '', ('10.0.0.5' if privat else '93.184.215.14', port))]
    monkeypatch.setattr(security.socket, 'getaddrinfo', aufloesen)


def client(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_abruf_liefert_die_bytes_eines_oeffentlichen_https_feeds(oeffentlich):
    with client(lambda r: httpx.Response(200, content=RSS)) as c:
        assert abrufen('https://news.example/feed.xml', client=c) == RSS


def test_abruf_lehnt_http_und_interne_ziele_ab_ohne_anzufragen(oeffentlich):
    anfragen = []
    with client(lambda r: anfragen.append(r) or httpx.Response(200, content=RSS)) as c:
        for url in ('http://news.example/feed.xml', 'https://intern.example/feed.xml', 'https://localhost/feed',
                    'https://user:pw@news.example/feed.xml'):
            with pytest.raises(FeedFehler, match='nicht erlaubt'):
                abrufen(url, client=c)
    assert anfragen == []


def test_eine_weiterleitung_auf_ein_internes_ziel_wird_vor_der_anfrage_gestoppt(oeffentlich):
    gesehen = []

    def handler(request):
        gesehen.append(str(request.url))
        return httpx.Response(302, headers={'location': 'https://intern.example/geheim'})
    with client(handler) as c:
        with pytest.raises(FeedFehler, match='nicht erlaubt'):
            abrufen('https://news.example/feed.xml', client=c)
    assert gesehen == ['https://news.example/feed.xml']


def test_zu_grosse_antworten_brechen_ab_auch_ohne_angabe_der_laenge(oeffentlich):
    def stueckweise():
        for _ in range(100):
            yield b'x' * 8192
    with client(lambda r: httpx.Response(200, content=stueckweise())) as c:
        with pytest.raises(FeedFehler, match='zu groß'):
            abrufen('https://news.example/feed.xml', client=c)
    with client(lambda r: httpx.Response(200, headers={'content-length': str(10 ** 8)}, stream=httpx.ByteStream(b'x'))) as c:
        with pytest.raises(FeedFehler, match='zu groß'):
            abrufen('https://news.example/feed.xml', client=c)


def test_netzfehler_und_fehlerstatus_nennen_weder_adresse_noch_inhalt(oeffentlich):
    with client(lambda r: httpx.Response(503, content=b'geheimer Serverfehler')) as c:
        with pytest.raises(FeedFehler) as fehler:
            abrufen('https://news.example/feed.xml?token=abc', client=c)
    assert 'token' not in str(fehler.value) and 'geheim' not in str(fehler.value)
