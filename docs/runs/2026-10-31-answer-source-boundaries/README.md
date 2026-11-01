# Vollständige Originalstellen im Antwortauszug

Basis: `47b3c1754abaa3fc714762f17ab3c402a0e158a1`. Nur synthetische Quellen,
lokale SQLite-Teststores und feste Modellgrenzen. Kein echtes Modell, privates
Postfach, persönlicher Datenbestand, Cloudanbieter oder App wurde aufgerufen.
Die Änderung wurde in einem eigenen Worktree entwickelt; der eingefrorene
Root-Worktree blieb unverändert.

## Fehler und Reparatur

HTML-Layouteinrückung konnte eine kurze zweisätzige Aussage in einen 686 Zeichen
langen Originalabsatz verwandeln. Geteilte Auszugsfenster ließen dessen Rawtext
nicht mehr vollständig sichtbar. Der Antwortweg brach vor dem Modellaufruf ab
und zeigte die gesamte Mail. Der HTML-Leser faltet jetzt normalen ASCII-
Layoutraum; `pre`/`textarea`, NBSP, Inline-Abstände und `<br>` bleiben erhalten.
Dies ist weiterhin ein begrenzter Textleser, kein Browser mit beliebiger CSS-
`white-space`-Semantik.

Word-Absätze `w:p` werden als Leerzeile statt als einfacher Zeilenumbruch
gelesen. `w:br` und `w:cr` bleiben interne Zeilenumbrüche. Damit macht ein
Datenschutzabsatz nicht mehr das gesamte Formular zum atomaren Regelabsatz.
Bereits gespeicherte Word-Texte werden nicht umgeschrieben. Wo deren echte
Absatzstruktur verloren ging, ist eine normale erneute Quellenaufnahme nötig;
Quellenfassung und Frischeprüfung bleiben im bestehenden Versionsweg.

Nur für die Satzantwort wird der gewählte Auszug anschließend an den bereits
vorhandenen Originaleinheiten bzw. atomaren Regelabsätzen vervollständigt.
Rawtext und Offsets stammen aus derselben unveränderten Quelle, vor der
Einschleusungsbereinigung. Ergänzt werden nur überlappende vollständige Spans.
Wörtliche Quellbereiche bleiben in Quellenreihenfolge, fehlender Inhalt behält
`[…]`. Ein neu angenommener Auszug bleibt einschließlich Kopf und Kürzungsvermerk
innerhalb des Erweiterungsbudgets von 2.500 Zeichen. Ein bereits zuvor größerer
Auszug bleibt unverändert; dies ist keine neue harte Grenze auf sämtlichen
bestehenden Rückgabepfaden. Es gibt keine neue Satzgrammatik, Datums-/Absenderliste
oder Änderung der Suchverweise.

Auch bereits gespeicherte HTML-Rohtexte können dadurch ihren vollständigen
Absatz zeigen. Erst **nach** unveränderter Raw-Sichtbarkeitsprüfung wird bei
einer überlangen angebotenen Einheit ausschließlich horizontaler ASCII-
Leerraum (Space/Tab) zeilenweise für die Darstellung vereinheitlicht. Jede
geänderte Zeile muss bereits nach dem bestehenden Originalsplitter eine ganze
einzeilige Originalaussage mit Satzabschluss sein. Änderungen innerhalb einer
mehrzeiligen Originaleinheit bleiben gesperrt. Wörter,
Reihenfolge, Satzzeichen, Negation, Überschriftstatus, LF, Leerzeilen, NBSP und
Formfeed bleiben erhalten. Die vorhandene `originaltext`-Wortlautbindung und
Mehrsatzprüfung prüfen die Ausgabe erneut. Inhaltlich mehr als 400 Zeichen
bleiben abgelehnt; der Originaltext und die Rawbelege des Prüfmodells bleiben
unverändert. Das ist keine Zusage über die Bedeutung beliebiger Codeformatierung;
kurze Originale bleiben wörtlich und die bestehende Zitatgrenze gilt weiterhin.
Der unabhängige Review fand einen 685 Zeichen langen unzitierten Codeblock, bei
dem die erste Darstellungsfassung Einrückung verlor. Sein exakter permanenter
RED-Test bestand erst nach dieser Einschränkung; der Codeblock bleibt nun vor
dem Modellaufruf im Zitatmodus. Die positive 620-Leerzeichen-Prosa bleibt nutzbar.
Der unabhängige Reviewer hat diesen Gegenfall anschließend erneut ausgeführt:
`zitate`, null Provideraufrufe; die positive Rate-Prosa samt vollständigem
Rawbeleg am aktiven synthetischen Prüftor bestand. Keine weiteren wichtigen
Restfunde im eng geprüften Scope. Separater Reviewbericht:
`/private/tmp/kf-answer-boundary-repair-review-20261031.md`.

## Synthetischer Vorher-/Nachher-Nachweis

Der unabhängige Repro läuft mit den echten Parsern, Store, `prepare`,
Belegsammlung, Formulierung und `render`. Die lokale Attrappe darf nur aus den
wirklich angebotenen Original-IDs wählen. Indexeinträge werden synthetisch über
die bestehenden `_blocks`-Offsets geschrieben. Das prüft die technische Grenze,
nicht das Verständnis eines echten Modells.

| Fall | Vorher: Satzaufrufe / Status / Renderzeichen | Nachher |
|---|---|---|
| Neue HTML-Mail, 620 Einrückungsleerzeichen | 0 / `zitate` / 36.709 | 1 / `saetze` / 191 |
| Word-Feld mit Datenschutzvorspann | 0 / `zitate` / 3.076 | 1 / `saetze` / 250 |
| Word-Feld, Regel nur im unsichtbaren Volltext | 0 / `zitate` / 3.076 | 1 / `saetze` / 250 |
| Unbelegte Rücksendefrist, Word mit Regel | 0 / `zitate` | 2 / `nichts` |

Die [kompakte Ergebnistabelle](synthetic-boundary-results.json) enthält alle neun
synthetischen Varianten. Repro-SHA256:
`a687f7909b026b9a93a77c52944068d0696069bac6af1bc129308d1e407fd570`.
Der Repro lag lokal unter `/private/tmp/kf-answer-boundary-probe-20261031.py`;
für den Nachlauf wurde ausschließlich sein JSON-Ausgabepfad geändert.

Permanenter Regressionstest:
`sidecar/tests/test_answer_source_boundaries.py`. Er enthält zusätzlich einen
über 30.000 Zeichen langen alten Rohbody: die vollständige 686-Zeichen-Stelle
bleibt im Rawauszug und im 4.000-Zeichen-Fenster des aktiven synthetischen
Prüfmodells; die angebotene Darstellung hat 66 Zeichen. Der gespeicherte Body
bleibt identisch. Nur normalisiert sichtbare Teilstücke werden weiterhin vor
dem Modellaufruf abgelehnt.

## Prüfungen

RED auf der Basis reproduziert: HTML-620, beide Word-Feldvarianten und Word-
Absatz/Zeilenumbruch scheiterten; ohne Einrückung bestand die Kontrolle.
Nach nur den Parserkorrekturen scheiterten beide Word-Feldvarianten weiter
(`nichts`), bis die bestehende vollständige Originaleinheit sichtbar war.
Der permanente Altbestandstest scheiterte vor der Darstellungsänderung mit
`zitate` und besteht danach einschließlich aktivem synthetischem Prüfmodell.

Gezielter Gesamtlauf auf dem abschließenden Stand: **591 bestanden**, eine vorhandene
Starlette/httpx-Deprecation-Warnung. Enthalten: neue Grenztests,
Originalsatz-Auswahl, normative Absatzkontexte, Absatzauswahl/Satzantwort und
Satzprüfung einschließlich Prüfmodell, DOCX-Leser/-Anhänge/-Upload/-Ablage,
Mail-UID und MIME-Retry sowie die Pflichtkernprüfungen aus `CONTRIBUTING.md`
(`context`, `egress`, `agent`, `kingfisher`, `claims`, `graph`). Der zusätzliche
enge Lauf nach Formfeed-Erhaltungsprobe und Codegegenfall: **72 bestanden**
(18 Grenztests und 54 bestehende Original-/Absatzschutztests).
`git diff --check` ohne Befund.

Enger reproduzierbarer Kernlauf (mit eingerichteter Sidecar-Testumgebung):

```sh
PYTHONPATH=sidecar:. python -m pytest -q \
  sidecar/tests/test_answer_source_boundaries.py \
  sidecar/tests/test_original_sentence_selection.py \
  sidecar/tests/test_normative_paragraph_context.py \
  sidecar/tests/test_absatzauswahl_saetze.py
```

Schutzfälle: abgeschnittene Qualifier, Mehrsatzreihenfolge/Atomarität,
Einschleusungen, verschiedene Personen und Termine, unbelegte Rücksendefrist,
Budget inklusive Kopf/Marker genau an der Grenze und ein Zeichen darunter,
inhaltlich überlange Regel, Quellenfrische/Widerruf und unveränderte Originale.

Keine vollständige Backend-Suite in diesem Worktree, kein Push, PR, Release,
Deployment oder privater Modellabnahmelauf. Diese Abnahmen gehören zum
gesonderten Integrationslauf nach Übernahme des geprüften Commits.
