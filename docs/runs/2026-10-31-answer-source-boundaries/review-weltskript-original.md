# Unabhängiges enges Review: WeltSkript und Original-ID-Vertrag

## Urteil

**Freigabe für den begrenzten Adapterpatch; keine kritischen oder wichtigen Funde.**

Freeze: `4fedcd18abe616e20ff78914c7b431e0a11d7d40`, direkte Basis `7165da562e763aac9533f788d2cf0c1c2f13a29b`, Worktree `/private/tmp/kf-answer-source-boundaries-20261031`. HEAD und sauberer Arbeitsbaum vor/nach den Läufen bestätigt. Keine Repositoryänderung durch diesen Reviewer.

Geprüft: vollständiger Diff, `messlatte/skript.py`, zwölf neue Protokoll-/Produktkontrollen und Ownerbericht. Der Diff ändert keine Kerngates, Welt, Frage, Golden oder alte Qualitätsassertion. Produktänderung ausschließlich 15 Ergänzungen/3 Entfernungen im Skriptanbieter; dazu neue Tests und Bericht.

**15 gezielte Repositorytests plus 6 eigene externe Gegenproben bestanden.** Keine Vollsuite, privaten Daten, echten Modelle oder Netzaufrufe. Dies ist Adapter-/Produktmechanik, keine Bewertung realer Modellqualität.

## Konkreter Vertragscheck

- `skript.py:70-80`: Originalmodus wird über Schema oder angebotene `originalsaetze` erkannt. Unbekannte Frage, Prüferrolle und keine passenden Belege antworten mit dem richtigen leeren Feld: `originalstellen` bzw. `saetze`.
- Die vorhandene `skript.auswahl` bestimmt weiterhin die Belegwahl. Fehlt `text`, werden ausschließlich die angebotenen Originaleinheiten als Auswahltext gelesen; kein Zugriff auf nicht angebotene Rawquelle oder erwartete Antwort als neuen Beleg.
- `81-84`: Nur `sorgfaeltig` im Originalmodus liefert angebotene `(beleg,satz)`-IDs. Vorhandenes `MAX_SAETZE` begrenzt die Ausgabe. Die angebotenen Einheiten werden nicht in Text umgeschrieben oder aufgeteilt. Die Vollständigkeits-/Bindungsprüfung der angebotenen Einheiten bleibt beim unveränderten Produkt.
- `85-89`: `unaufmerksam` behält ausdrücklich den richtigen und falschen freien Legacy-Kandidaten. Der falsche Kandidat wird nicht in ein richtiges Original-ID-Ergebnis verwandelt. Normaler Textmodus und das ideale Skriptprüfmodell bleiben unverändert.

## Eigene unabhängige Kontrollen

Externe Datei: `/private/tmp/kf_weltskript_original_independent_20261101.py`.

Log: `/private/tmp/kf-weltskript-original-independent-20261101.log`.

**6 bestanden in 5,10 s**, eine vorhandene Starlette-Testclient-Abkündigungswarnung.

1. Basiscode mittels rein lesendem `git show` in separatem Inprozess-Modul geladen. Exakter Original-ID-Payload ohne `text` löst auf `7165da5` `KeyError('text')` aus. Derselbe Payload liefert auf dem Freeze ausschließlich die tatsächlich angebotene ID `(17,41)`.
2. Originalmodus ohne explizites Schema: Match nur im angebotenen Originaltext, neutraler Titel, zusätzliche unpassende Quelle und nicht fortlaufende IDs. Ergebnis exakt `(6,93)`, kein erwarteter `richtig`-/`falsch`-Text, keine Inputmutation. Dadurch wird nicht nur der schemagesteuerte Positivfall geprüft.
3. Originalschema mit passendem Text/Titel, aber **keiner angebotenen Originaleinheit**: korrekt `nichts_vorliegend/originalstellen=[]`. Keine erfundene ID und kein freier erwarteter Satz als Ersatz.
4. `unaufmerksam` mit Originalpayload bleibt exakt `saetze=[richtig,falsch]` mit tatsächlicher Belegnummer; kein `originalstellen`-Feld. Die negative Kontrolle wird nicht durch eine Adapterrettung positiv.
5. Echter synthetischer MIME-Intake → Speicher → Konversations-POST → gespeicherter Konversations-GET, `sorgfaeltig`: gespeicherter Status **`saetze`**, **`verworfen=0`**, freigegebene strukturierte Sätze, exakt vollständiges mehrsätziges Original als `roh`, **1 aktiver Prüfaufruf**. POST/GET-Inhalt und Quellenlinks identisch; kein `original_fallback` als Erfolgsersatz.
6. Gleicher realer Produktpfad, `unaufmerksam`: gespeicherter Status **`zitate`**, **`verworfen=1`**, **1 aktiver Prüfaufruf**, keine freigegebene Satzstruktur; falscher Satz weder in POST noch gespeichertem GET sichtbar. Der Originalbody bleibt unverändert. Eine bloße Anbieterexception oder ein unsichtbarer Vollzitat-Rückfall könnte die geforderten Verwerfungs-/Strukturassertions nicht erfüllen.

## Wiederholter gezielter Repositorylauf

Log: `/private/tmp/kf-weltskript-original-selected-20261101.log`.

**15 bestanden in 4,77 s**, eine vorhandene Starlette-Testclient-Abkündigungswarnung:

- sämtliche zwölf neuen Fälle in `messlatte/tests/test_weltskript_original.py`;
- bestehender sorgfältiger Prüffall ohne Verwerfung richtiger Sätze;
- bestehender unaufmerksamer Fall ohne Prüfer: falsche Aussage kommt weiterhin durch und wird als falsch bewertet;
- bestehender unaufmerksamer Fall mit Prüfer: falsche Aussage wird weiterhin verworfen und getrennt gezählt.

Beide Läufe: `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=sidecar:.`, `/private/tmp/kf-person-context-20261030-4cjo275h/env/bin/python -m pytest -q -p no:cacheprovider`.

Die Positivassertions verlangen echte freigegebene Satzstruktur und aktives Tor; die Negativassertions verlangen echte Verwerfung. Erwartete Inhalte oder Qualitätsmaßstäbe wurden nicht zur Anpassung an einen Rückfall abgeschwächt. Keine weitere Suche oder zusätzliche Architektur empfohlen. Gesamtbackendterminal und reale Produkt-/Modellprüfung bleiben Root vorbehalten.
