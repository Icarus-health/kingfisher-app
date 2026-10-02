#!/usr/bin/env python3
"""Prüft die synthetische Entwicklungswelt unter messlatte/welt/ gegen messlatte/FORMAT.md.

Eigenständig (nur Standardbibliothek). Sichert nur die Inhalte ab; das Rahmenwerk hat
eine eigene Validierung. Aufruf:

    python3 messlatte/welt/pruefe_welt.py [PFAD_ZUR_WELT]

Ausgang 0 = sauber, 1 = Fehler gefunden. Hinweise (H) sind Warnungen ohne Einfluss
auf den Ausgang, sie zeigen Stellen, die man noch einmal ansehen sollte.
"""
import collections
import datetime as dt
import glob
import json
import os
import re
import sys

WURZEL = sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(os.path.abspath(__file__))

ARTEN = {"mail", "termin", "transkript", "notiz"}
KATEGORIEN = ["rueckblick", "mehrdeutigkeit", "frist", "vorbereitung", "profil", "identitaet",
              "aktualitaet", "falle", "paraphrase", "zeitraum", "wartet_auf", "fremde_anweisung"]
SCHWEREN = {"kritisch", "normal"}
VERHALTEN = {"antworten", "rueckfrage", "nicht_bekannt"}
ORDNER = {"INBOX", "Sent"}
MONATE = ["januar", "februar", "märz", "april", "mai", "juni", "juli", "august", "september",
          "oktober", "november", "dezember"]

fehler = []
hinweise = []


def F(ort, text):
    fehler.append("%s: %s" % (ort, text))


def H(ort, text):
    hinweise.append("%s: %s" % (ort, text))


def lade(pfad):
    try:
        with open(pfad, encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:  # Syntax- oder Lesefehler
        F(pfad, "nicht ladbar: %s" % e)
        return None


def zeit(wert, ort):
    """ISO 8601 mit Zeitzone; gibt datetime zurück oder None."""
    if not isinstance(wert, str):
        F(ort, "Zeit fehlt oder ist kein Text")
        return None
    try:
        d = dt.datetime.fromisoformat(wert)
    except ValueError:
        F(ort, "Zeit nicht lesbar: %r" % wert)
        return None
    if d.tzinfo is None:
        F(ort, "Zeit ohne Zeitzone: %r" % wert)
        return None
    return d


def adresse_ok(a, ort):
    if not isinstance(a, str) or not re.fullmatch(r"[\w.+-]+@[\w-]+(\.[\w-]+)*\.example", a):
        F(ort, "Adresse keine .example-Adresse: %r" % (a,))


def person(p, ort):
    if not isinstance(p, dict) or not p.get("name") or not p.get("adresse"):
        F(ort, "Person braucht name und adresse: %r" % (p,))
        return
    adresse_ok(p["adresse"], ort)


def text_von(q):
    """Alles, was in einer Quelle als Text steht (für die Belegprüfung)."""
    teile = [q.get("betreff", ""), q.get("titel", ""), q.get("text", ""), q.get("ort", ""), q.get("notiz", "")]
    for k in ("von",):
        if isinstance(q.get(k), dict):
            teile += [q[k].get("name", ""), q[k].get("adresse", "")]
    for k in ("an", "cc", "teilnehmer"):
        for p in q.get(k, []) or []:
            teile += [p.get("name", ""), p.get("adresse", "")] if isinstance(p, dict) else [str(p)]
    return "\n".join(str(t) for t in teile)


def daten_in(text):
    """Alle (Tag, Monat) in einem Text: '12.10.', '12. Oktober', ..."""
    r = set()
    for m in re.finditer(r"(\d{1,2})\.\s?(\d{1,2})\.", text):
        r.add((int(m.group(1)), int(m.group(2))))
    for m in re.finditer(r"(\d{1,2})\.\s?(%s)" % "|".join(MONATE + [x[:3] for x in MONATE]), text.lower()):
        mon = m.group(2)
        idx = [i for i, x in enumerate(MONATE) if x == mon or x[:3] == mon][0]
        r.add((int(m.group(1)), idx + 1))
    return r


def ist_datum(alt):
    return bool(re.fullmatch(r"\s*\d{1,2}\.\s?(\d{1,2}|[A-Za-zä]+)\.?(\s?\d{2,4})?\.?\s*", alt))


# --- welt.json ---------------------------------------------------------------
welt = lade(os.path.join(WURZEL, "welt.json")) or {}
stichtag = zeit(welt.get("stichtag"), "welt.json stichtag")
if welt.get("version") != 1:
    F("welt.json", "version muss 1 sein")
if welt.get("zeitzone") != "Europe/Berlin":
    F("welt.json", "zeitzone muss Europe/Berlin sein")
nutzer = welt.get("nutzer", {})
if not nutzer.get("name") or not nutzer.get("adressen") or not nutzer.get("wohnort"):
    F("welt.json", "nutzer braucht name, adressen, wohnort")
for a in nutzer.get("adressen", []):
    adresse_ok(a, "welt.json nutzer")
wahrheit = welt.get("wahrheit", {})
wids = set()
for kind in ("personen", "projekte"):
    for e in wahrheit.get(kind, []):
        if e.get("id") in wids:
            F("welt.json", "doppelte Wahrheits-ID %s" % e.get("id"))
        wids.add(e.get("id"))
        if not e.get("namen") or not e.get("beschreibung"):
            F("welt.json", "%s braucht namen und beschreibung" % e.get("id"))
        for a in e.get("adressen", []) or []:
            adresse_ok(a, "welt.json %s" % e.get("id"))
wahre_adressen = {a for p in wahrheit.get("personen", []) for a in p.get("adressen", [])}
nutzer_adressen = set(nutzer.get("adressen", []))

# --- Szenarien ---------------------------------------------------------------
dateien = sorted(glob.glob(os.path.join(WURZEL, "szenarien", "*.json")))
if not dateien:
    F(WURZEL, "keine Szenarien gefunden")
alle_quellen = {}          # id -> (Szenario, Quelle)
szenarien = []
for pfad in dateien:
    s = lade(pfad)
    if s is None:
        continue
    sid = s.get("id")
    stamm = os.path.splitext(os.path.basename(pfad))[0]
    if sid != stamm:
        F(pfad, "id %r stimmt nicht mit Dateiname %r überein" % (sid, stamm))
    for k in ("titel", "beschreibung", "quellen", "fragen"):
        if k not in s:
            F(pfad, "Feld %s fehlt" % k)
    szenarien.append(s)
    for q in s.get("quellen", []):
        qid = q.get("id")
        ort = "%s %s" % (sid, qid)
        if qid in alle_quellen:
            F(ort, "Quellen-ID nicht weltweit eindeutig")
        alle_quellen[qid] = (sid, q)
        if not isinstance(qid, str) or not re.fullmatch(re.escape(str(sid)) + r"-\d{3}", qid):
            F(ort, "ID passt nicht zu Präfix <Szenario-ID>-NNN")
        art = q.get("art")
        if art not in ARTEN:
            F(ort, "unbekannte art %r" % art)
            continue
        z = zeit(q.get("zeit"), ort + " zeit")
        if z and stichtag and z >= stichtag:
            F(ort, "zeit liegt nicht vor dem Stichtag: %s" % q["zeit"])
        if art == "mail":
            for k in ("von", "an", "betreff", "text"):
                if not q.get(k):
                    F(ort, "Mail ohne %s" % k)
            person(q.get("von"), ort + " von")
            for p in q.get("an", []):
                person(p, ort + " an")
            for p in q.get("cc", []) or []:
                person(p, ort + " cc")
            eigene = isinstance(q.get("von"), dict) and q["von"].get("adresse") in nutzer_adressen
            ordner = q.get("ordner", "INBOX")
            if ordner not in ORDNER:
                F(ort, "unbekannter ordner %r" % ordner)
            if eigene and ordner != "Sent":
                F(ort, "eigene Mail muss ordner Sent haben")
            if not eigene and ordner == "Sent":
                F(ort, "Sent-Mail muss von der Nutzerin stammen")
        elif art == "termin":
            for k in ("beginn", "ende", "titel"):
                if not q.get(k):
                    F(ort, "Termin ohne %s" % k)
            b = zeit(q.get("beginn"), ort + " beginn")
            e = zeit(q.get("ende"), ort + " ende")
            if b and e and e <= b:
                F(ort, "Termin endet nicht nach dem Beginn")
            if b and z and b < z and False:
                pass
            for p in q.get("teilnehmer", []) or []:
                person(p, ort + " teilnehmer")
        elif art == "transkript":
            if not q.get("titel") or not q.get("text"):
                F(ort, "Transkript braucht titel und text")
            zeilen = [x for x in q.get("text", "").split("\n") if x.strip()]
            if not zeilen or not all(re.match(r"^[^:\n]{2,40}: \S", x) for x in zeilen):
                F(ort, "Transkript: jede Zeile muss 'Name: Gesagtes' sein")
        elif art == "notiz":
            if not q.get("titel") or not q.get("text"):
                F(ort, "Notiz braucht titel und text")
        # Nur .example-Adressen im Volltext (auch in Signaturen und Weiterleitungen)
        for a in re.findall(r"[\w.+-]+@[\w.-]+", text_von(q)):
            if not a.rstrip(".").endswith(".example"):
                F(ort, "Adresse im Text nicht auf .example: %s" % a)
    # Antwortketten
    ids = {q["id"]: q for q in s.get("quellen", []) if "id" in q}
    for q in s.get("quellen", []):
        ref = q.get("antwort_auf")
        if ref:
            if ref not in ids:
                F("%s %s" % (sid, q["id"]), "antwort_auf %s existiert nicht im Szenario" % ref)
            elif ids[ref].get("zeit", "") > q.get("zeit", ""):
                F("%s %s" % (sid, q["id"]), "antwort_auf liegt zeitlich nach der Antwort")

# --- Fragen ------------------------------------------------------------------
frage_ids = set()
for s in szenarien:
    sid = s.get("id")
    lokal = {q["id"] for q in s.get("quellen", []) if "id" in q}
    for fr in s.get("fragen", []):
        fid = fr.get("id")
        ort = "%s %s" % (sid, fid)
        if fid in frage_ids:
            F(ort, "Frage-ID nicht eindeutig")
        frage_ids.add(fid)
        if not isinstance(fid, str) or not re.fullmatch(re.escape(str(sid)) + r"-\d{2}", fid):
            F(ort, "Frage-ID passt nicht zu <Szenario-ID>-NN")
        if not fr.get("frage") or not fr.get("notiz"):
            F(ort, "frage und notiz sind Pflicht")
        if fr.get("kategorie") not in KATEGORIEN:
            F(ort, "unbekannte kategorie %r" % fr.get("kategorie"))
        if fr.get("schwere") not in SCHWEREN:
            F(ort, "unbekannte schwere %r" % fr.get("schwere"))
        e = fr.get("erwartet", {})
        v = fr.get("verboten", {})
        verh = e.get("verhalten")
        if verh not in VERHALTEN:
            F(ort, "unbekanntes verhalten %r" % verh)
        aussagen = e.get("aussagen")
        if not isinstance(aussagen, list) or not all(isinstance(g, list) and g and all(isinstance(x, str) and x for x in g) for g in aussagen):
            F(ort, "aussagen muss eine Liste nichtleerer Alternativgruppen sein")
            aussagen = []
        if verh == "antworten" and not aussagen:
            F(ort, "verhalten antworten braucht aussagen")
        if verh == "nicht_bekannt" and aussagen:
            F(ort, "nicht_bekannt darf keine erwarteten aussagen haben")
        if verh == "rueckfrage":
            b = e.get("bedeutungen")
            if not b or len(b) < 2 or not all(isinstance(g, list) and g for g in b):
                F(ort, "rueckfrage braucht mindestens zwei bedeutungen (Gruppen)")
        elif "bedeutungen" in e:
            F(ort, "bedeutungen nur bei rueckfrage")
        belege = e.get("belege", [])
        if verh != "nicht_bekannt" and not belege:
            F(ort, "erwartet.belege darf nicht leer sein")
        vbel = v.get("belege", [])
        for b in belege + vbel:
            if b not in alle_quellen:
                F(ort, "Beleg %s existiert nicht" % b)
            elif b not in lokal:
                H(ort, "Beleg %s liegt in einem anderen Szenario" % b)
        if set(belege) & set(vbel):
            F(ort, "Beleg zugleich erwartet und verboten")
        if not isinstance(v.get("aussagen", []), list) or not all(isinstance(x, str) and x for x in v.get("aussagen", [])):
            F(ort, "verboten.aussagen muss eine Liste von Texten sein")
        verboten = [x.lower() for x in v.get("aussagen", [])]
        # Gruppe unerfüllbar, wenn jede Alternative eine verbotene Aussage enthält
        for g in aussagen:
            if all(any(vv in a.lower() for vv in verboten) for a in g):
                F(ort, "erwartete Gruppe %r enthält verbotene Aussage: richtige Antwort wäre falsch" % (g,))
        # Belegtext prüfen: steht die erwartete Aussage in den Belegen?
        beleg_text = "\n".join(text_von(alle_quellen[b][1]) for b in belege if b in alle_quellen)
        beleg_low = beleg_text.lower()
        beleg_daten = daten_in(beleg_text)
        for g in aussagen:
            gefunden = False
            for a in g:
                if a.lower().strip() in beleg_low:
                    gefunden = True
                elif ist_datum(a) and daten_in(a) & beleg_daten:
                    gefunden = True
            if not gefunden:
                H(ort, "erwartete Gruppe %r steht nicht wörtlich in den Belegen" % (g,))
        # Verbotene Aussagen dürfen nicht in den erwarteten Belegen stehen (wären dann Zitat)
        for vv in verboten:
            if vv in beleg_low and verh != "nicht_bekannt":
                H(ort, "verbotene Aussage %r steht in den erwarteten Belegen" % vv)
        # Überschneidungsgefahr: Alternative ist Teilzeichenkette einer anderen Gruppe/verbotenen
        for g in aussagen:
            for a in g:
                for vv in verboten:
                    if a.lower() in vv and a.lower() != vv:
                        H(ort, "Alternative %r steckt in verbotener Aussage %r" % (a, vv))

# --- Statistik und Mengengerüst ----------------------------------------------
quellen_art = collections.Counter(q["art"] for _, q in alle_quellen.values() if "art" in q)
fragen = [fr for s in szenarien for fr in s.get("fragen", [])]
kat = collections.Counter(fr.get("kategorie") for fr in fragen)
verh = collections.Counter(fr.get("erwartet", {}).get("verhalten") for fr in fragen)
schw = collections.Counter(fr.get("schwere") for fr in fragen)

for s in szenarien:
    n, m = len(s.get("quellen", [])), len(s.get("fragen", []))
    if not 10 <= n <= 30:
        H(s["id"], "%d Quellen (Ziel 10 bis 30)" % n)
    if not 3 <= m <= 6:
        H(s["id"], "%d Fragen (Ziel 3 bis 6)" % m)
if not 55 <= len(fragen) <= 70:
    H("gesamt", "%d Fragen (Ziel 55 bis 70)" % len(fragen))
for k in KATEGORIEN:
    if kat[k] < 2:
        F("gesamt", "Kategorie %s weniger als zweimal benutzt" % k)
if not any(fr["erwartet"].get("verhalten") == "rueckfrage" for fr in fragen):
    F("gesamt", "keine rueckfrage-Frage")

print("Welt: %s" % WURZEL)
print("Szenarien: %d, Quellen: %d, Fragen: %d" % (len(szenarien), len(alle_quellen), len(fragen)))
print("\nQuellen je Art:")
for k, n in sorted(quellen_art.items()):
    print("  %-11s %3d" % (k, n))
print("\nFragen je Kategorie:")
for k in KATEGORIEN:
    print("  %-17s %3d" % (k, kat[k]))
print("\nFragen je Verhalten:")
for k, n in sorted(verh.items()):
    print("  %-14s %3d" % (k, n))
print("\nFragen je Schwere:")
for k, n in sorted(schw.items()):
    print("  %-8s %3d" % (k, n))
print("\nJe Szenario (Quellen / Fragen):")
for s in szenarien:
    print("  %-20s %3d / %d" % (s["id"], len(s.get("quellen", [])), len(s.get("fragen", []))))

if hinweise:
    print("\nHinweise (%d):" % len(hinweise))
    for h in hinweise:
        print("  H", h)
if fehler:
    print("\nFEHLER (%d):" % len(fehler))
    for f in fehler:
        print("  F", f)
    sys.exit(1)
print("\nSauber.")
