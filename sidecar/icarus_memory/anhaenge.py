"""Anhänge lesen (M4): PDF-Rechnungen und Verträge werden eine Quelle mit Beleg (Seite).

Eine Rechnung kommt meist als PDF im Anhang, und die Mail selbst sagt nur „anbei die Rechnung“. Ohne den Anhang fehlt
die Frist. Deshalb liest die Aufnahme (`mail_intake.py`) die Anhänge einer Mail mit, **lokal und ohne Netz**:

* **PDF mit Text:** Seite für Seite über den begrenzten Prozess `pdf_text_worker.py` (pypdf, CPU- und Speichergrenze,
  Zeitgrenze `ZEITGRENZE_S`), höchstens `MAX_SEITEN` Seiten und `MAX_ZEICHEN` Zeichen. Nichts aus der Datei wird
  ausgeführt: Gelesen werden Text und eingebettete Bilder, sonst nichts.
* **Gescannt** (keine Textebene) oder ein Foto einer Rechnung: Texterkennung nur, wenn ein lokales OCR-Modell
  eingerichtet ist (`glm-ocr` oder `deepseek-ocr` im lokalen Ollama, `ocr_fuer`); nie über die Cloud. Sonst steht
  ehrlich da: „Gescannte Rechnung „…pdf“, noch nicht gelesen.“
* **Zu groß** (über der Grenze der Aufnahme) oder **nicht lesbar** (verschlüsselt, beschädigt): ein Satz, warum.

Jeder Anhang wird eine eigene Quelle (Art `document`) mit denselben Beteiligten wie die Mail, also in derselben Akte
(Zahnarztpraxis, Versicherung). Ihr Text trägt vor jeder Seite „Seite N“; damit nennt jeder Beleg seine Seite
(`seite_der_stelle`). Die Quelle läuft wie jede andere durch die Einordnung und durch die Fristensuche
(`akten_arten.fristen_vorlegen`); jede Zahl eines Vorschlags steht wörtlich darin (`zahlen_belegt`).
"""
from __future__ import annotations

import base64
import email.message
import hashlib
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import PurePosixPath
from typing import Any, Callable

#: Höchstens so viele Anhänge je Mail, Seiten je Anhang, Zeichen je Anhang.
MAX_ANHAENGE = 5
MAX_SEITEN = 30
MAX_ZEICHEN = 60_000
MAX_BYTES = 5 * 1024 * 1024
#: Wanduhr je PDF (der Prozess hat dazu eine CPU-Grenze); OCR je Seite.
ZEITGRENZE_S = 12.0
OCR_ZEITGRENZE_S = 90.0
#: Bilder (Fotos einer Rechnung) zählen nur mit einem dieser Wörter im Dateinamen: Ein Urlaubsfoto ist keine Quelle.
_DOKUMENT_NAME = re.compile(r'rechnung|beleg|quittung|scan|vertrag|police|bescheid|mahnung|invoice|receipt', re.I)
_BILD = {'image/jpeg', 'image/png'}
OCR_MODELLE = ('glm-ocr', 'deepseek-ocr')
TAG = 'anhang'
BERICHT_TAG = 'mail:attachments:'

GELESEN, OCR, GESCANNT, ZU_GROSS, FEHLER = 'gelesen', 'ocr', 'gescannt', 'zu_gross', 'fehler'


@dataclass(frozen=True)
class Anhang:
    dateiname: str
    art: str
    """`pdf` oder `bild`."""
    status: str
    """`gelesen`, `ocr` (über Texterkennung), `gescannt` (noch nicht gelesen), `zu_gross`, `fehler`."""
    seiten: tuple[str, ...] = ()
    gesamt: int = 0
    """Seiten der Datei; gelesen sind höchstens `MAX_SEITEN`."""
    hinweis: str = ''
    leere_seiten: tuple[int, ...] = field(default=())

    @property
    def gelesen(self) -> bool:
        return self.status in (GELESEN, OCR)

    @property
    def ungelesene_seiten(self) -> list[int]:
        return [n for n, seite in enumerate(self.seiten, 1) if not seite.strip()]

    @property
    def vollstaendig(self) -> bool:
        return (self.gelesen and bool(self.seiten) and not self.ungelesene_seiten
                and self.gesamt <= len(self.seiten) and not _inhalt(self)[1])


Ocr = Callable[[bytes], str]


def _name(part: email.message.Message) -> str:
    from .connectors.mail import _decode
    roh = part.get_filename() or ''
    name = _decode(roh) if roh else ''
    name = PurePosixPath(name.replace('\\', '/')).name.strip()
    return re.sub(r'[\x00-\x1f]', '', name)[:180]


def _ist_pdf(part: email.message.Message, name: str) -> bool:
    return part.get_content_type() == 'application/pdf' or name.lower().endswith('.pdf')


def gescannt_satz(name: str, seiten: int) -> str:
    was = 'Gescannte Rechnung' if 'rechnung' in name.casefold() else 'Gescanntes Dokument'
    umfang = f' ({seiten} {"Seite" if seiten == 1 else "Seiten"})' if seiten else ''
    return (f'{was} „{name}“{umfang}, noch nicht gelesen. Für gescannte Dokumente braucht Kingfisher ein lokales Modell '
            'zur Texterkennung; ohne es bleibt der Inhalt ungelesen.')


def _pdf(name: str, daten: bytes, ocr: Ocr | None) -> Anhang:
    from .document_text import pdf_seiten
    try:
        gelesen = pdf_seiten(daten, max_seiten=MAX_SEITEN, bilder=ocr is not None, zeitgrenze=ZEITGRENZE_S)
    except ValueError as exc:
        return Anhang(name, 'pdf', FEHLER, hinweis=f'Anhang „{name}“ konnte nicht gelesen werden: {exc}')
    seiten = [str(s or '') for s in gelesen.get('seiten', [])]
    gesamt = int(gelesen.get('gesamt') or len(seiten))
    leer = tuple(int(n) for n in gelesen.get('leer', []))
    status = GELESEN
    if ocr is not None:
        for nummer, b64 in sorted((gelesen.get('bilder') or {}).items(), key=lambda p: int(p[0])):
            try:
                text = ocr(base64.b64decode(b64)).strip()
            except Exception:  # noqa: BLE001 - eine Seite ohne Erkennung bleibt leer
                text = ''
            if text:
                seiten[int(nummer) - 1] = text
                status = OCR
    if not any(s.strip() for s in seiten):
        return Anhang(name, 'pdf', GESCANNT, gesamt=gesamt, hinweis=gescannt_satz(name, gesamt), leere_seiten=leer)
    hinweis = ''
    if gesamt > len(seiten):
        hinweis = f'Gelesen sind die ersten {len(seiten)} von {gesamt} Seiten.'
    ungelesen = [str(n) for n, seite in enumerate(seiten, 1) if not seite.strip()]
    if ungelesen:
        hinweis = (hinweis + ' ' if hinweis else '') + ('Seite ' if len(ungelesen) == 1 else 'Seiten ') + ', '.join(ungelesen) + ' ohne lesbaren Text; der Inhalt ist nicht vollständig erfasst.'
    return Anhang(name, 'pdf', status, tuple(seiten), gesamt, hinweis, leer)


def _bild(name: str, daten: bytes, ocr: Ocr | None) -> Anhang:
    if ocr is None:
        return Anhang(name, 'bild', GESCANNT, gesamt=1, hinweis=gescannt_satz(name, 0))
    try:
        text = ocr(daten).strip()
    except Exception:  # noqa: BLE001
        text = ''
    if not text:
        return Anhang(name, 'bild', GESCANNT, gesamt=1, hinweis=gescannt_satz(name, 0))
    return Anhang(name, 'bild', OCR, (text,), 1)


def aus_mail(nachricht: email.message.Message, *, abgeschnitten: bool = False, ocr: Ocr | None = None,
             bericht: dict[str, Any] | None = None) -> tuple[Anhang, ...]:
    """Die Anhänge einer Mail: PDFs immer, Bilder nur mit Dokumentnamen („Rechnung.jpg“). Höchstens `MAX_ANHAENGE`.

    `abgeschnitten`: Die Mail kam über der Größengrenze der Aufnahme; ihre Anhänge sind unvollständig und werden nicht
    gelesen (ein Satz sagt das).
    """
    ergebnis: list[Anhang] = []
    gesehen: set[str] = set()
    gefunden = ausgelassen = nicht_unterstuetzt = doppelt = unbenannt = 0
    zuordnung_vollstaendig = True
    for part in nachricht.walk():
        name = _name(part)
        attachment = part.get_content_disposition() == 'attachment'
        if part.is_multipart():
            if attachment or name:
                gefunden += 1
                nicht_unterstuetzt += 1
                zuordnung_vollstaendig = False
            continue
        if not name:
            if attachment or part.get_content_type() == 'application/pdf':
                gefunden += 1
                unbenannt += 1
                zuordnung_vollstaendig = False
            continue
        gefunden += 1
        pdf = _ist_pdf(part, name)
        bild = part.get_content_type() in _BILD and bool(_DOKUMENT_NAME.search(name))
        if not (pdf or bild):
            nicht_unterstuetzt += 1
            continue
        if len(ergebnis) >= MAX_ANHAENGE:
            ausgelassen += 1
            continue
        if abgeschnitten:
            ergebnis.append(Anhang(name, 'pdf' if pdf else 'bild', ZU_GROSS,
                                   hinweis=f'Anhang „{name}“ ist zu groß für die Aufnahme und wurde nicht gelesen.'))
            continue
        daten = part.get_payload(decode=True) or b''
        fingerabdruck = hashlib.sha256(daten).hexdigest()
        if fingerabdruck in gesehen:
            doppelt += 1
            continue
        if not daten:
            ergebnis.append(Anhang(name, 'pdf' if pdf else 'bild', FEHLER,
                                   hinweis=f'Anhang „{name}“ enthält keine lesbaren Dateidaten.'))
            continue
        gesehen.add(fingerabdruck)
        if len(daten) > MAX_BYTES:
            ergebnis.append(Anhang(name, 'pdf' if pdf else 'bild', ZU_GROSS,
                                   hinweis=f'Anhang „{name}“ ist größer als 5 MiB und wurde nicht gelesen.'))
            continue
        ergebnis.append(_pdf(name, daten, ocr) if pdf else _bild(name, daten, ocr))
    if bericht is not None:
        mime_fehler = sum(len(part.defects) for part in nachricht.walk())
        if mime_fehler:
            zuordnung_vollstaendig = False
        voll = sum(item.vollstaendig for item in ergebnis)
        teilweise = sum(item.gelesen and not item.vollstaendig for item in ergebnis)
        ungelesen = len(ergebnis) - voll - teilweise
        hinweise = []
        if abgeschnitten:
            hinweise.append('Die Mail wurde unvollständig abgerufen; weitere Anlagen können fehlen.')
        if ausgelassen:
            hinweise.append(f'{ausgelassen} weitere Anlagen wurden wegen der Grenze von {MAX_ANHAENGE} je Mail nicht gelesen.')
        if nicht_unterstuetzt:
            hinweise.append(f'{nicht_unterstuetzt} Dateien haben ein nicht unterstütztes Format oder sind Bilder ohne Dokumentnamen.')
        if teilweise or ungelesen:
            hinweise.append(f'{teilweise} Anlagen sind teilweise gelesen, {ungelesen} noch ungelesen.')
        if unbenannt:
            hinweise.append(f'{unbenannt} Anlagen ohne Dateinamen wurden nicht gelesen; ihre Zuordnung ist ungeklärt.')
        if mime_fehler:
            hinweise.append('Die Mailstruktur ist beschädigt; die Anlagen können nicht vollständig zugeordnet werden.')
        komplett = not (abgeschnitten or ausgelassen or nicht_unterstuetzt or teilweise or ungelesen or unbenannt or mime_fehler)
        bericht.update(geprueft=True, abruf_vollstaendig=not abgeschnitten, vollstaendig=komplett, gefunden=gefunden, gelesen=voll,
                       zuordnung_vollstaendig=zuordnung_vollstaendig, unbenannt=unbenannt, mime_fehler=mime_fehler,
                       teilweise=teilweise, ungelesen=ungelesen, ausgelassen=ausgelassen,
                       nicht_unterstuetzt=nicht_unterstuetzt, doppelt=doppelt,
                       dateien=[als_dict(item) for item in ergebnis],
                       hinweis=('Anlagen nicht vollständig erfasst. ' + ' '.join(hinweise)) if not komplett
                       else 'Text der erkannten unterstützten Anlagen erfasst. Texterkennung und eingebettete Bilder können Informationen auslassen.' if gefunden else 'Keine benannten Anlagen gefunden.')
    return tuple(ergebnis)


# -- Die Quelle ---------------------------------------------------------------------------------------------------


def _inhalt(anhang: Anhang) -> tuple[list[str], bool]:
    """One shared, nonnegative character budget including page separators."""
    teile, rest = [], MAX_ZEICHEN
    for nummer, seite in enumerate(anhang.seiten, 1):
        if not seite.strip():
            continue
        stueck = f'Seite {nummer}' + (' (Texterkennung)' if anhang.status == OCR and nummer in anhang.leere_seiten or
                                       anhang.art == 'bild' else '') + f'\n{seite.strip()}'
        rest = max(0, rest - (2 if teile else 0))
        if len(stueck) > rest:
            if rest:
                teile.append(stueck[:rest])
            return teile, True
        teile.append(stueck)
        rest -= len(stueck)
    return teile, False


def text(anhang: Anhang, betreff: str, datum: datetime | None) -> str:
    """Source header, bounded readable pages and explicit missing-content warnings."""
    wann = f' vom {datum:%d.%m.%Y}' if datum else ''
    kopf = f'Anhang „{anhang.dateiname}“ der Mail „{betreff or "(kein Betreff)"}“{wann}.'
    if not anhang.gelesen:
        return f'{kopf}\n\n{anhang.hinweis}'
    teile, gekuerzt = _inhalt(anhang)
    if gekuerzt:
        teile.append('(Gekürzt: Der Anhang ist länger, als Kingfisher je Anhang liest.)')
    if anhang.hinweis:
        teile.append(anhang.hinweis)
    return f'{kopf}\n\n' + '\n\n'.join(teile)


def titel(anhang: Anhang, betreff: str) -> str:
    return f'{anhang.dateiname} (Anhang zu „{(betreff or "(kein Betreff)")[:120]}“)'


_SEITE = re.compile(r'^Seite (\d+)(?: \(Texterkennung\))?$', re.M)


def seite_der_stelle(text_: str, stelle: str) -> int | None:
    """Die Seite, auf der eine wörtliche Stelle steht („Seite N“ davor), sonst None."""
    position = text_.find(stelle)
    if position < 0:
        return None
    seiten = [int(t.group(1)) for t in _SEITE.finditer(text_, 0, position)]
    return seiten[-1] if seiten else None


def ist_anhang(episode: Any) -> bool:
    return TAG in (getattr(episode, 'tags', None) or ())


def aufnehmen(episodes: Any, message: Any, *, schluessel: str, herkunft: str, beteiligte: list, teilnehmer: list,
              parent_id: str, claims: Any = None) -> list[str]:
    """Legt je Anhang einer Mail eine Quelle an (Art `document`, Beteiligte wie die Mail). Gibt die neuen IDs zurück."""
    from .episodes import EpisodeKind
    from .model import Provenance, SourceType
    from .source_versions import track_source
    neu: list[str] = []
    beobachtet: set[str] = set()
    for nummer, anhang in enumerate(getattr(message, 'anhaenge', ()) or (), 1):
        key = f'{schluessel}:anhang:{nummer}'
        episode, erstellt = episodes.record(
            EpisodeKind.DOCUMENT, titel(anhang, message.subject), text(anhang, message.subject, message.date),
            Provenance(source_type=SourceType.EMAIL, source_ref=f'{herkunft}#anhang:{nummer}:{anhang.dateiname}',
                       captured_at=message.date),
            occurred_at=message.date, participants=teilnehmer, contacts=beteiligte,
            tags=[TAG, f'{TAG}:{anhang.status}', f'mail-parent:{parent_id}']
                 + ([] if anhang.vollstaendig else ['source:truncated']), source_key=key)
        track_source(episodes, claims, key, episode)
        beobachtet.add(episode.id)
        if erstellt:
            neu.append(episode.id)
    report = getattr(message, 'anhang_bericht', None)
    # Only a complete MIME fetch without a count limit proves absence. Normal
    # message views and truncated fetches must never withdraw unseen originals.
    if (report and report.get('abruf_vollstaendig') is True and report.get('zuordnung_vollstaendig') is True
            and report.get('ausgelassen') == 0):
        from .source_versions import invalidate_with_corrections
        for child_id in episodes.mail_attachment_children(parent_id):
            if child_id not in beobachtet:
                if claims is None:
                    raise ValueError('Für Anlagenänderungen muss der Wissensspeicher verfügbar sein.')
                invalidate_with_corrections(episodes, claims, child_id)
                episodes.ignore(child_id, grund='mail-anlage-entfallen')
    return neu


# -- Texterkennung über ein lokales Modell (nur wenn eingerichtet) --------------------------------------------------


def ocr_modell(installiert: dict[str, str] | None) -> str:
    """Das erste lokal installierte OCR-Modell (`glm-ocr`, `deepseek-ocr`), sonst leer. Cloud zählt nie."""
    from .ollama_inventar import LOKAL
    for name, art in sorted((installiert or {}).items()):
        grund = name.strip().rsplit('/', 1)[-1].split(':', 1)[0].lower()
        if art == LOKAL and grund in OCR_MODELLE:
            return name
    return ''


def ocr_fuer(app: Any) -> Ocr | None:
    """Eine Texterkennung über das lokale Ollama, wenn dort ein OCR-Modell lokal liegt; sonst None. Fail closed."""
    import httpx
    from .ollama_inventar import inventar_von
    try:
        inventar = inventar_von(app)
        wurzel = inventar._wurzel()  # noqa: SLF001 - dieselbe Adresse, die das Inventar fragt
        modell = ocr_modell(inventar.installiert(wurzel))
    except Exception:  # noqa: BLE001
        return None
    if not modell:
        return None
    transport = getattr(app.state, 'ollama_transport', None)

    def lesen(bild: bytes) -> str:
        with httpx.Client(timeout=OCR_ZEITGRENZE_S, trust_env=False, follow_redirects=False, transport=transport) as client:
            antwort = client.post(wurzel + '/api/generate', json={
                'model': modell, 'stream': False, 'options': {'temperature': 0},
                'prompt': 'Gib den Text auf diesem Bild wörtlich wieder, Zeile für Zeile, ohne Erklärung.',
                'images': [base64.b64encode(bild).decode('ascii')]})
            antwort.raise_for_status()
            daten = antwort.json()
        return str(daten.get('response') or '') if isinstance(daten, dict) else ''

    return lesen


def als_dict(anhang: Anhang) -> dict[str, Any]:
    return {'dateiname': anhang.dateiname, 'art': anhang.art, 'status': anhang.status, 'seiten': len(anhang.seiten),
            'gesamt': anhang.gesamt, 'hinweis': anhang.hinweis, 'vollstaendig': anhang.vollstaendig,
            'ungelesene_seiten': anhang.ungelesene_seiten}


def gespeicherter_bericht(episode: Any) -> dict[str, Any] | None:
    import json
    for tag in reversed(getattr(episode, 'tags', ())):
        if tag.startswith(BERICHT_TAG):
            try:
                report = json.loads(tag[len(BERICHT_TAG):])
            except (ValueError, TypeError):
                return None
            return report if isinstance(report, dict) and report.get('geprueft') is True else None
    return None


__all__ = ['Anhang', 'FEHLER', 'GELESEN', 'GESCANNT', 'MAX_ANHAENGE', 'MAX_SEITEN', 'MAX_ZEICHEN', 'OCR', 'OCR_MODELLE',
           'TAG', 'ZEITGRENZE_S', 'ZU_GROSS', 'als_dict', 'aufnehmen', 'aus_mail', 'gescannt_satz', 'ist_anhang',
           'ocr_fuer', 'ocr_modell', 'seite_der_stelle', 'text', 'titel']
