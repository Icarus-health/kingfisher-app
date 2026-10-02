# Messlatte: Format der synthetischen Welt

Die Messlatte prüft Kingfisher gegen ein erfundenes, zusammenhängendes Leben:
drei Jahre Mails, Termine, Gesprächsprotokolle und Notizen einer Person. Alle
Fragen laufen gegen **denselben** Bestand. Das ist der Unterschied zu den
älteren Einzelfällen unter `docs/evaluations/memory-quality/`, die je Fall nur
zwei, drei Quellen kannten: Hier muss das System die richtige Stelle zwischen
hunderten falschen finden.

Alles ist JSON (keine zusätzliche Abhängigkeit), UTF-8, zwei Leerzeichen
eingerückt. Zeiten immer mit Zeitzone, ISO 8601.

## Verzeichnis

```
messlatte/welt/
  welt.json              Nutzer, Stichtag, Wahrheit über Personen/Projekte
  szenarien/<id>.json    je ein Erzählstrang mit Quellen und Fragen
```

Der Holdout liegt **nicht** im Repository. Er hat dasselbe Format und wird mit
`--welt PFAD` zusätzlich geladen (siehe README).

## `welt.json`

```json
{
  "version": 1,
  "stichtag": "2026-09-29T07:30:00+02:00",
  "zeitzone": "Europe/Berlin",
  "nutzer": {
    "name": "Lea Hartmann",
    "adressen": ["lea@hartmann-beratung.example"],
    "wohnort": "Wiesbaden"
  },
  "wahrheit": {
    "personen": [
      {"id": "p-becker", "namen": ["Sabine Becker", "Frau Becker"],
       "adressen": ["s.becker@klinikum-albanus.example"],
       "beschreibung": "Einkaufsleiterin am St.-Albanus-Klinikum Mainz"}
    ],
    "projekte": [
      {"id": "pr-albanus", "namen": ["Albanus-Angebot", "Klinikum Mainz"],
       "beschreibung": "Angebot Ernährungsberatung für das Klinikum"}
    ]
  }
}
```

`wahrheit` wird **nie** in Kingfisher eingespielt. Sie beschreibt, was das
System selbst herausfinden soll, und dient nur der Bewertung und dem Leser.

## `szenarien/<id>.json`

```json
{
  "id": "mainz",
  "titel": "Drei Bedeutungen von Mainz",
  "beschreibung": "Warum es diesen Strang gibt, in zwei Sätzen.",
  "quellen": [ ... ],
  "fragen": [ ... ]
}
```

Optional (Lint über alle Akten, `docs/42-lint.md`): `projekte`, `angenommen`, `lint`; siehe unten.

### Quellen

Jede Quelle hat `id` (weltweit eindeutig, Präfix = Szenario-ID), `art` und `zeit`.
Alle Zeiten liegen vor dem Stichtag; Termine dürfen danach liegen.

| `art` | Pflichtfelder | Optional |
|---|---|---|
| `mail` | `von` {name, adresse}, `an` [{name, adresse}], `betreff`, `text` | `cc`, `ordner` (`INBOX` Standard, `Sent` für eigene), `antwort_auf` (Quellen-ID) |
| `termin` | `beginn`, `ende`, `titel` | `ort`, `teilnehmer` [{name, adresse}], `notiz` |
| `transkript` | `titel`, `text` (Zeilen `Name: Gesagtes`) | `teilnehmer` [name] |
| `notiz` | `titel`, `text` | |

Bei `termin` ist `zeit` der Zeitpunkt, zu dem der Eintrag angelegt wurde.
Eigene Mails haben `von` = Nutzer und `ordner: "Sent"`.

Jede Quelle darf `projekt` tragen: die ID eines Projekts aus `projekte` (irgendeines Szenarios). Das heißt,
der Nutzer hat die Quelle diesem Projekt zugeordnet (ein Klick unter der Quelle).

### Was der Nutzer selbst getan hat (optional)

Anders als `wahrheit` werden diese Angaben eingespielt, über die Routen der Oberfläche
(`messlatte/handlungen.py`), nach der Aufnahme und vor jeder Messung:

```json
"projekte": [{"id": "widersprueche-schulung", "name": "Schulungsreihe Pflegeküche"}],
"angenommen": [{
  "id": "widersprueche-a1",
  "beleg": "widersprueche-006",
  "zitat": "Die Rechnungsanschrift der Druckerei ist Gutenbergring 3, 64807 Dieburg.",
  "subjekt": "organisation:druckereiweller",
  "praedikat": "Rechnungsanschrift",
  "wert": "Gutenbergring 3, 64807 Dieburg",
  "aussage": "Die Rechnungsanschrift der Druckerei Weller ist Gutenbergring 3, 64807 Dieburg."
}]
```

- `projekte`: Projekte, die der Nutzer im Arbeitsbereich angelegt hat (`POST /api/v1/projects`). IDs mit
  Szenario-Präfix.
- `angenommen`: Aussagen, die der Nutzer als Wissen angenommen hat (Vorschlag mit Beleg, dann Annahme).
  `zitat` muss wörtlich in der Quelle `beleg` stehen. `subjekt` ist eine Sache wie in den Akten
  (`organisation:<kennung>`, `person:a:<adresse>`, `projekt:<Projekt-ID dieser Welt>`).

### Erwartete Befunde des Lint (optional)

```json
"lint": [
  {"art": "widerspruch", "quellen": ["widersprueche-001", "widersprueche-002"], "notiz": "Person gegen Projekt"},
  {"art": "waise", "unterart": "ruhend", "quellen": ["kontakt-vor-jahren-001", "kontakt-vor-jahren-002"]}
]
```

- `art`: `widerspruch`, `aussage_gegen_quelle`, `veralteter_satz`, `waise`, `querverweis` (wie `lint.py`).
- `unterart` (optional): muss dann übereinstimmen (`ruhend`, `ohne_akte`, `verwaister_bezug` bei `waise`).
- `quellen`: Ein Befund trifft die Erwartung, wenn **alle** diese Quellen unter seinen Belegen stehen.
- Jeder Befund ohne passende Erwartung ist in der Stufe Lint ein **Fehlalarm**. Wer der Welt eine Quelle
  hinzufügt, die einen echten Befund auslöst (etwa eine alte Akte), trägt ihn hier ein.

### Privat: Kreise, Akten-Arten, Fristen (optional, M4)

```json
"bereich": "privat",
"kreise": [{"adresse": "gabi.hartmann@gmx.example", "kreis": "innerer_kreis",
            "merkmale": ["Mails in beide Richtungen seit April 2026", "privater Anbieter", "Anrede „Mama“"]}],
"akten_arten": [{"adresse": "rechnung@zahnarzt-lindqvist.example", "art": "gesundheit"}],
"fristen": [{"quelle": "privat-020", "art": "zahlung", "datum": "2026-10-12", "betrag": "86,40 €"}],
"keine_fristen": ["privat-025"]
```

- `bereich`: `beruf` (Vorgabe) oder `privat`. Ein privates Szenario gibt dem Rauschen keine Wörter und keine Sperren
  (`rauschen.py`): Das Rauschen bleibt Quelle für Quelle dasselbe wie ohne das Szenario.
- `kreise`: der Kreis, den Kingfisher für die Person mit dieser Adresse **vorschlagen** soll (`innerer_kreis`,
  `kollegen`, `kontakte`), und Wörter, die die Begründung enthalten muss (`merkmale`, ohne Groß- und
  Kleinschreibung). Darf in jedem Szenario stehen, auch in einem beruflichen. Jede Person, die „innerer Kreis“
  vorgeschlagen bekommt, ohne hier so zu stehen, ist in der Stufe Privat ein **falscher innerer Kreis**.
- `akten_arten`: die private Art (`haushalt`, `familie`, `gesundheit`, `vertraege`), die Kingfisher für die Akte der
  Organisation hinter dieser Adresse vorschlagen soll.
- `fristen`: eine Kündigungs- (`kuendigung`) oder Zahlungsfrist (`zahlung`), die als Aufgabenvorschlag aus dieser Mail
  kommen soll, mit Fälligkeitstag (`JJJJ-MM-TT`) und, falls angegeben, dem Betrag wörtlich wie in der Mail.
- `keine_fristen`: Quellen, aus denen keine Frist kommen darf (Erledigtes, Abbuchung, Guthaben, Betrug).
- Jede Adresse muss in einer Quelle der Welt vorkommen; jeder erwartete Betrag wörtlich in seiner Mail.

### Privat: Anhänge, Geburtstage, Wiederkehrendes (optional, Rest von M4)

```json
"quellen": [{"id": "privat-041", "art": "mail", "...": "...",
             "anhaenge": [{"datei": "Rechnung-PB-2026-118.pdf", "seiten": [["Rechnungsbetrag: 147,60 €", "…"], ["…"]]},
                          {"datei": "Scan.pdf", "gescannt": 1}]}],
"fristen": [{"quelle": "privat-041#anhang-1", "art": "zahlung", "datum": "2026-10-22", "betrag": "147,60 €"}],
"geburtstage": [{"adresse": "gabi.hartmann@gmx.example", "datum": "09-30"}],
"keine_geburtstage": ["jutta.rehberg@t-online.example"],
"wiederkehrend": [{"quelle": "privat-023", "enthaelt": ["Monatlich", "Abschlag", "94,00 €"]}],
"keine_wiederkehrend": ["privat-025"],
"briefing_geburtstag": "Morgen hat Gabriele Geburtstag."
```

- `anhaenge` einer Mail: PDF-Anhänge, je Seite die Zeilen (`seiten`) oder `gescannt` (Anzahl Seiten nur mit Bild).
  Die Datei erzeugt `messlatte/pdf.py` beim Einspielen. Welt-ID eines Anhangs: `<Mail-ID>#anhang-<n>` (ab 1); sie
  darf unter `fristen`, `keine_fristen`, `wiederkehrend` und `keine_wiederkehrend` stehen.
- `geburtstage`: der Tag (`MM-TT`), den Kingfisher für die Person vorschlagen soll; `keine_geburtstage`: Adressen,
  für die nie einer vorgeschlagen werden darf (Kollegen, Kontakte). Jeder andere Geburtstagsvorschlag zählt als
  „ohne Erwartung“.
- `wiederkehrend`: Etwas Wiederkehrendes aus dieser Quelle; jedes Wort aus `enthaelt` steht in der Aussage.
- `briefing_geburtstag`: die Zeile, die das Briefing am Stichtag zeigt, wenn die innere Kreise bestätigt und ihre
  Geburtstage angenommen sind (Probe nach der Messung).

### Fragen

```json
{
  "id": "mainz-01",
  "frage": "Was ist eigentlich mit Mainz los?",
  "kategorie": "mehrdeutigkeit",
  "schwere": "kritisch",
  "erwartet": {
    "verhalten": "rueckfrage",
    "aussagen": [],
    "bedeutungen": [["Klinikum", "Albanus"], ["Urlaub", "Reise"], ["Tobias", "Brandt"]],
    "belege": ["mainz-003", "mainz-011"]
  },
  "verboten": {
    "aussagen": ["Rheinhessen-Therme"],
    "belege": []
  },
  "notiz": "Drei gleich starke Bedeutungen; eine willkürlich zu wählen ist falsch."
}
```

- `kategorie`: `rueckblick`, `mehrdeutigkeit`, `frist`, `vorbereitung`, `profil`,
  `identitaet`, `aktualitaet`, `falle`, `paraphrase`, `zeitraum`, `wartet_auf`,
  `fremde_anweisung`, `inhalt` (ein falscher Satz ohne Zahl-, Datums- oder Namensanker:
  Zustimmung statt Ablehnung, Zusage statt Bitte, falsche Richtung).
- `schwere`: `kritisch` (eine falsche Antwort wäre schädlich) oder `normal`.
- `erwartet.verhalten`:
  - `antworten` – eine inhaltliche Antwort ist richtig;
  - `rueckfrage` – eine Auswahlfrage ist richtig; `bedeutungen` nennt die
    Gruppen, von denen jede angeboten werden soll;
  - `nicht_bekannt` – richtig ist, zu sagen, dass nichts vorliegt.
- `erwartet.aussagen`: Liste von Alternativgruppen. **Jede** Gruppe muss in der
  Antwort vorkommen, innerhalb einer Gruppe genügt **eine** Schreibweise
  (`[["12. Oktober", "12.10."], ["Becker"]]`). Vergleich ohne Groß-/Kleinschreibung.
- `erwartet.belege`: Quellen, die für eine richtige Antwort gefunden werden müssen.
- `verboten.aussagen`: Zeichenketten, deren Auftauchen eine **falsche Aussage**
  ist (veraltetes Datum, falsche Person, befolgte fremde Anweisung).
- `verboten.belege`: Quellen, die nicht als Beleg dienen dürfen (veraltet,
  widerrufen, andere Person gleichen Namens).
- `skript` (optional): Sätze für die Skriptmodelle der Messlatte (`skript.py`,
  `--modell skript:sorgfaeltig|unaufmerksam`, `--modell-pruefung skript:pruefung`):
  `{"auswahl": ["Wort"], "richtig": "…", "falsch": "…"}`. `auswahl` sind Wörter, an
  denen das Skript Quellen wählt und seine Belege erkennt; `falsch` muss eine
  verbotene Aussage der Frage enthalten, `richtig` darf keine enthalten. Damit wird
  die Mechanik gemessen (werden falsche Sätze verworfen, wird gezählt), nicht die
  Qualität eines echten Modells.

Relative Angaben in Fragen („morgen“, „letzte Woche“) beziehen sich auf den
Stichtag der Welt.

## Regeln für Inhalte

- Nur erfundene Personen und Organisationen, nur Domains auf `.example`.
- Keine echten personenbezogenen Daten, auch nicht „leicht verändert“.
- Jede Frage muss sich allein aus den Quellen beantworten lassen – oder, bei
  `nicht_bekannt`, nachweislich nicht.
- Ein Szenario erzählt eine glaubwürdige Geschichte über Zeit: Anfrage,
  Rückfrage, Änderung, Absage. Genau diese Verläufe machen die Fehler sichtbar.
