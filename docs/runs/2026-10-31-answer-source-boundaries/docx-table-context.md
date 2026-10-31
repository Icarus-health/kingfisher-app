# Word-Tabellen: Feldbezug repariert, Anhang-Antwort noch begrenzt

Basis dieses separaten Nachtrags: `b0527fdb64097e13becea3d0b871fba99be9e385`.
Nur synthetische Word-/MIME-Quellen, lokale Teststores und feste Modellantworten;
kein Root-Edit, privates Dokument, Modell, Netzprovider oder App-Zugriff.

## Datenstruktur

Eine Word-Zelle mit zwei `w:p`-Elementen enthielt synthetisch
`Beschäftigungsbeginn:` und `18.11.2026`. Die bisherige Leerzeile nach jedem
Absatz trennte sie in zwei `_blocks`-Einheiten. Die leere Nachbarzelle hatte
das Feldlabel `Rücksendedatum:`. Oberhalb stand ein eigenständiger
Datenschutz-/Regelabsatz.

Der bestehende ElementTree-Leser erhält nun die vorhandenen Container:

- Absätze innerhalb einer Zelle werden mit LF verbunden;
- Zellen derselben Tabellenzeile werden mit Tab getrennt, auch bei inneren
  leeren Zellen;
- jede Tabellenzeile endet mit einer echten Absatzgrenze;
- normale Body-Absätze behalten Leerzeilen; `w:br` und `w:cr` bleiben LF;
- eine verschachtelte Tabelle beginnt eigene Zeilen, statt ihren Inhalt an
  ein vorausgehendes äußeres Feld anzuhängen.

Der Feldbeleg lautet danach wörtlich
`Beschäftigungsbeginn:\n18.11.2026\tRücksendedatum:`. Er bleibt ein gemeinsamer
Quellenblock und erreicht als solcher auch die gespeicherten Indexverweise.
Es werden weder Punkte noch Datumsrollen ergänzt. Gelöschte/verschobene Texte,
XML-/Paket-/UTF-8-Textlimits, Entitätsverbot und Verschachtelungsgrenze bleiben
aktiv. Die Änderung betrifft ausschließlich neue Word-Lesevorgänge. Alte
Originale bleiben unverändert; erneutes Einlesen folgt der normalen
Quellenversionierung.

## Komponentenbeleg und echte Anhang-Komposition

RED auf `b0527fd`: vier von fünf Anfangskontrollen scheiterten, darunter die
Feld-/Wertstruktur und die kurze Antwort aus dem nackten DOCX-Haupttext.
Nach der Tabellenkorrektur besteht dieser Komponentenpfad:
DOCX → `_blocks` → Store/Indexverweise → `prepare` → Formulierung → `render`.
Die positive Datumsantwort bleibt kurz; die synthetische leere Rücksendefrist
bleibt `nichts`. Das prüft den technischen Kontext, keine reale Modellsemantik.

Der zusätzliche **echte MIME-Pfad** benutzt die vorhandene IMAP-Attrappe,
`message_mit_anhaengen`, `remember`, den tatsächlich von `anhaenge.aufnehmen`
erzeugten Anhangbody, Store, `prepare`, Formulierung und `render`.
Dieser Pfad ist noch **kein positiver End-to-end-Nachweis für eine kurze
Beschäftigungsbeginn-Antwort**:

| Synthetischer vollständiger Anhang | Feld/Wert im selben Block | Originaleinheit | Satzaufrufe | Ergebnis |
|---|---|---:|---:|---|
| Kleine anschließende Prosa | ja | 109 Zeichen | 1 | `zitate`, generierter Kopf mit vier deutschen Quotezeichen sperrt die Bindung |
| Lange unpunktierte Nachbarfelder | ja | 539 Zeichen | 0 | `zitate`, bestehendes 400-Zeichen-Limit sperrt die vollständige Einheit |

[Exakte synthetische Zahlen](docx-table-mime-result.json). In beiden Fällen
bleibt der gespeicherte Anhangbody unverändert; der bestehende Render-Rückfall
zeigt weiterhin die gesamte Quelle. Die grünen Regressionstests für diese
beiden Fälle **charakterisieren diese offene Integrationsgrenze**, sie erklären
sie nicht für repariert.

Die Tabellenkorrektur kann diese zwei Grenzen nicht allein lösen: Der generierte
Metadatenkopf ist Teil des Prüfvolltexts, und der vorhandene Originalsplitter
verbindet unpunktierte Feld-/Wertangaben bis zur nächsten abgeschlossenen Prosa.
Eine Header-Sonderausnahme, erfundene Satzpunkte oder eine Lockerung von
Original-/400-Zeichen-Guards wurde nicht eingebaut.

Kleinste gesondert zu prüfende Optionen: eine konservative Unterstützung
eindeutiger nicht verschachtelter deutscher Zitatspans statt einer Header-
Sonderregel; oder ein begrenzter, vollständiger Originalauszug im Zitat-Rückfall,
während die Satzprüfung unverändert sperrt. Eine Ausgabe der 539-Zeichen-Einheit
als Satz würde hingegen einen anderen Originaleinheitenvertrag erfordern.
Diese Optionen sind keine Implementierungs- oder Abnahmebehauptung dieses Commits.

## Prüfungen

`sidecar/tests/test_docx_table_context.py`: 16 Kontrollen für echte Zellen/Zeilen,
leere Nachbarfelder, Body-Absätze, innere Umbrüche, Verschachtelung, verworfene
Texte, vollständige Regeln, Wenn-/Dann-Fortsetzung, UTF-8-/Paket-/XML-Limits,
leere Dokumente und Recursion-Fehler sowie die echte MIME-Komposition.
Eine zusätzlich künstlich vorgeschlagene Zuordnung des Beschäftigungsdatums
zum leeren Rücksendefeld wird durch die echte Satzprüfung verworfen.

Gezielter breiter Lauf: **666 bestanden**, eine vorhandene Starlette/httpx-
Deprecation-Warnung, 46,10 Sekunden. Der anschließende enge Lauf einschließlich
der zusätzlichen falschen Feldzuordnung: **16 bestanden**. Enthalten sind im
breiten Lauf auch die vorhandenen Original-/Mehrsatz-/Zitat-/Frischeprüfungen
und die Pflichtkernprüfungen aus `CONTRIBUTING.md`; keine komplette Suite.

```sh
PYTHONPATH=sidecar:. python -m pytest -q \
  sidecar/tests/test_docx_table_context.py sidecar/tests/test_document_text.py \
  sidecar/tests/test_mail_docx_attachments.py
```

Die bestehenden Anhangtests prüfen weiterhin normale neue Quellenversionen,
unveränderte alte Originale und Widerruf durch die Elternmail. Kein Push, PR,
Release oder persönliche Nachklassifikation in diesem Worktree.
