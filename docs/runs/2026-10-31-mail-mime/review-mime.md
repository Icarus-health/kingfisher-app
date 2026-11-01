# Unabhängiges Review: begrenzter vollständiger MIME-Abruf

31.10.2026. Worktree `/private/tmp/kf-skill-categories-20261031`, Branch `fix/mail-attachment-wire-20261031`, Basis `ef8e02c` (offizielle 1.0.36). Geprüft: MIME-Abrufdelta in `connectors/mail.py`, neue Wiretests, zwei angepasste Inventorytests und zugehöriger Bericht. Die parallelen Änderungen an Anhangsextraktion und eigenen Adressen/Kontakten sind außerhalb dieses Reviews.

**Abschließendes Urteil nach enger Nachprüfung: Alle drei eingefrorenen P2-Befunde geschlossen. Kein verbleibender Befund in diesem geprüften MIME-Scope. Die ursprünglichen Reproduktionen und Grenzen bleiben unten dokumentiert; die abschließende Nachprüfung steht am Ende.**

## P2-1: UID und Größe können aus einem anderen FETCH-Datensatz stammen

Ort: `sidecar/icarus_memory/connectors/mail.py:479–492`, `_message_literal`.

Der Helfer verlangt genau ein Literal, verbindet aber sämtliche weiteren Bytefragmente zu einer Metadatenzeichenkette, ohne die zugehörige FETCH-Datensatzgrenze zu prüfen. Ein bereits geschlossener Literal-Datensatz kann dadurch UID/Größe aus einer separaten Antwort übernehmen.

Unabhängiger synthetischer Gegenfall bei Anfrage UID `7.103`:

```python
[(b'2 (BODY[]<0> {n}', foreign_raw), b')',
 b'1 (UID 103 RFC822.SIZE n)']
```

`foreign_raw` ist eine kleine synthetische vollständige Mail mit Body `FOREIGN SOURCE`. Der tatsächliche Connector liefert sie als UID `7.103` und **truncated=False**. UID/Größe wurden jedoch nicht im Datensatz des Literals belegt. Das kann eine fremde/unzuordenbare Antwort als vollständige Quelle erscheinen lassen. Der Gegenfall erfordert eine widersprüchliche bzw. unerwartete Serverantwort; es wurde kein reales Anbieterfehlverhalten behauptet.

Enge Korrektur: Identitäts-/Größenfelder nur innerhalb desselben zusammenhängenden FETCH-Datensatzes wie das Literal berücksichtigen. Legale Metadaten nach dem Literal weiterhin zulassen; unabhängige FETCH-Datensätze nicht als dessen Identitätsbeleg zusammensetzen.

## P2-2: Widersprüchliche UIDVALIDITY-Angaben werden ignoriert

Ort: `mail.py:357–365` und neuer FETCH-Nachcheck `:1008–1011`.

`_mailbox_response_number` liest ausschließlich `response[0]`. Der neue Nachcheck akzeptiert daher `imap.response('UIDVALIDITY') == (..., [b'7', b'8'])` als Generation 7. Eine zweite ausdrücklich widersprechende Generation wird nicht ausgewertet.

Unabhängiger tatsächlicher Connector-Gegenfall: Während FETCH werden beide Werte bereitgestellt. Die kleine Mail wird trotzdem **truncated=False** unter `7.103` zurückgegeben. Das Lesen nur des ersten Werts war Teil des bisherigen Zahlenhelpers; durch seine neue Verwendung für FETCH-Generationsänderungen und mehrteilige Verkettung bleibt hier gerade die behauptete zusätzliche Identitätsgrenze offen.

Enge Korrektur: Widersprüchliche/mehrdeutige Generationenantworten ablehnen, statt nur die erste Zahl als Nachweis zu verwenden. Die normale konsumierte/nicht vorhandene Antwort muss von einer explizit widersprüchlichen Antwort unterscheidbar bleiben.

## P2-3: Explizit malformed BODY-Abschnitt gilt als fehlende Angabe

Ort: `mail.py:1018–1023`.

Die Regex erkennt nur geschlossene `BODY[...]`-Angaben. Eine erste Antwort mit `BODY[HEADER` ohne schließende Klammer ergibt gar keinen Treffer. Danach greift die Kompatibilitätsregel für eine kleine vollständige Antwort ohne Origin.

Unabhängiger tatsächlicher Connector-Gegenfall: Korrekte UID und Größe, Literalheader mit `BODY[HEADER` statt `BODY[]<0>`. Ergebnis: **truncated=False** statt Ablehnung. Damit unterscheidet die Logik eine fehlende Bereichsangabe nicht zuverlässig von einer explizit fehlerhaften Abschnittsangabe. Ein falscher/unklarer Abschnitt darf nicht als vollständige MIME bestätigt werden.

Enge Korrektur: Vorhandene, aber syntaktisch ungültige BODY-Abschnittsangaben ablehnen; die ausdrücklich vorgesehene kleine Antwort ohne Origin nicht pauschal verbieten.

## Bestätigte Eigenschaften außerhalb dieser Befunde

- Sequenzielle Anfragen bleiben bei maximal 2 MiB; die akzeptierte Parsergesamtmenge bei 40 MiB und maximal 20 FETCHs je Versuch. Kurze, leere, überlieferte und längenwidersprüchliche Antworten stoppen ohne unbegrenzte Fortsetzungsversuche und bleiben unvollständig.
- Fortsetzungen benötigen passende UID, stabile gemeldete Größe, exakten Origin und stabile Provider-ID. Zusätzlich unabhängig geprüft: stabile Gmail-ID 123 wird akzeptiert; auf dem zweiten Teil geänderte oder fehlende Gmail-ID wird abgewiesen.
- Normale kleine Antworten bleiben ein schreibgeschützter Aufruf. Ohne gemeldete Größe bleibt eine Antwort bewusst unvollständig; eine kurze bekannte Größe kann Vollständigkeit ohne expliziten Origin begründen.
- Vor Fortsetzungen wird readonly neu gewählt. Einzelne erkannte neue UIDVALIDITY sowie falsche UID/Origins werden abgewiesen. Wiederverbindung startet den vollständigen Versuch neu, ohne alte Chunks zu übernehmen. Die vorhandene Sitzung erlaubt höchstens einen solchen Neustart, also gegebenenfalls bis zu 40 FETCHs über zwei Versuche, nicht 20 insgesamt.
- Der 2,6-MB-Fall erreicht den Parser als vollständige Original-MIME und die PDF-Extraktion mit identischen Attachmentbytes. Die 5-MiB-Anlagengrenze und die Ablehnung bei einem zusätzlichen Byte bleiben erhalten. Mailtextbegrenzung ist weiterhin getrennt von MIME-Vollständigkeit.
- Die beiden Inventoryteständerungen bilden den neuen begrenzten Mehrfachabruf ab; sie erlauben keinen unbeschränkten Ganzabruf und behalten die Textgrenze bei.

## Eigene Verifikation und Grenzen

**117 gezielte Tests bestanden in 4,42 s**: `test_mail_bounded_mime.py`, `test_mail_inventory.py`, `test_mail_uid.py`, `test_mail_inbox_preview_budget.py`, `test_mail_session.py`. Ein bestehender Starlette/HTTPX-Deprecationhinweis. Die neuen Wiretests enthalten den Attachment-Durchlauf; die parallel bearbeiteten Anhangs-/DOCX-Module wurden nicht zusätzlich auditiert oder verändert.

Dazu sechs unabhängige In-Memory-Gegenproben: die drei oben beschriebenen Fehlannahmen sowie stabile/geänderte/fehlende spätere Gmail-Provider-ID. Die Findings bestehen trotz grüner vorhandener Suite. Keine privaten Dateien, Credentials, realen Provider, Netzwerk-/Modellaufrufe, Docker, Produktedits, Commits, Resets oder Stashes. Keine persönlichen Probe-Artefakte gelesen.

Bekannte, korrekt dokumentierte Grenze: imaplib puffert die vom Server deklarierte Literale vor der Connectorprüfung. Die neue Logik begrenzt akzeptierte Bytes/Parserinput und Anzahl der angeforderten Bereiche, liefert aber keine absolute Transport-/Speichergrenze gegen einen regelwidrigen Server. Auch eine feste gesamte Wallclock-Frist folgt nicht allein aus 20 Anfragen. Keine reale Anbieter-/Performance-/Postfachabnahme und keine breite Architekturempfehlung aus diesem Review.

## Abschließende Nachprüfung der drei eingefrorenen Befunde

Keine Erweiterung des Audits; nur die drei Korrekturen, das aktualisierte MIME-Testmodul und die bereits definierten Gegenkontrollen geprüft.

- **P2-1 geschlossen:** `_message_literal` verlangt den Literal-Datensatz am Anfang und genau eine geschlossene äußere FETCH-Klammer. Nach deren Ende ist ausschließlich Whitespace zulässig; quoted/escaped Zeichen werden beim Klammerzählen berücksichtigt. Legaler UID-/Größennachlauf innerhalb derselben Klammer bleibt erlaubt. Die exakte separate-FETCH-Reproduktion wird jetzt mit „Die gelieferte Mail enthält mehrere FETCH-Datensätze“ vor dem MIME-Parser abgewiesen.
- **P2-2 geschlossen:** Alle expliziten Generationselemente werden validiert; sie müssen dieselbe gültige Zahl liefern. Widersprüche und malformed Elemente werden abgewiesen, identische Wiederholungen bleiben zulässig. Der FETCH-Nachcheck unterscheidet die normale alleinige None-Antwort von einer mehrteiligen fehlerhaften Liste. `[b'7', b'8']` wird jetzt vor dem MIME-Parser abgewiesen; der neue Test deckt auch `[None, b'7']` ab.
- **P2-3 geschlossen:** Die Zahl expliziter BODY-Abschnittsanfänge muss der Zahl syntaktisch vollständig erfasster Abschnitte entsprechen. Der exakte Header `BODY[HEADER` wird damit vor dem MIME-Parser abgewiesen. Die bekannte vollständige kleine Antwort ohne Origin bleibt kompatibel.

Die drei ursprünglichen Gegenproben wurden unabhängig mit denselben `RangeIMAP`-/`reader`-/`small_mail`-Hilfen wiederholt. Ein zusätzlich eingesetzter Parser-Tripwire hätte bei jeglichem MIME-Parsing einen AssertionError ausgelöst; alle drei Fälle scheiterten zuvor mit MailError. Die drei bereits definierten Gmail-Kontrollen wurden ebenfalls wiederholt: stabile ID123 akzeptiert, geänderte ID124 im zweiten Teil und später fehlende ID beide abgewiesen.

Exakter unabhängig ausgeführter Testbefehl aus dem Worktree:

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=sidecar:. /private/tmp/kf-person-context-20261030-4cjo275h/env/bin/python -m pytest -q -p no:cacheprovider sidecar/tests/test_mail_bounded_mime.py
```

Ergebnis: **56 passed in 3.32s**. Darin bleiben legaler Literal-Nachlauf, kleine Mail ohne Origin, Gesamt-/Requestgrenzen, unvollständige Teilantworten, Wiederverbindung und Attachmentbyte-/Größenkontrollen grün. Der vorherige eigene 117er-Lauf bleibt als Vor-Korrektur-Zwischenstand dokumentiert; die gemeldeten 155 Worker-Prüfungen wurden nicht als eigene Ausführung gezählt.

Keine weiteren Produktsuchen, Runtime-/Provider-/Modellaufrufe, privaten Daten oder Edits. Anhangs-/DOCX- und eigene-Adressänderungen bleiben außerhalb dieses Reviews. Die bereits dokumentierten imaplib-Pufferungs- und fehlenden realen Anbieterabnahmegrenzen gelten unverändert. Finding Count bleibt drei historische Befunde, jetzt drei geschlossen und null offen.
