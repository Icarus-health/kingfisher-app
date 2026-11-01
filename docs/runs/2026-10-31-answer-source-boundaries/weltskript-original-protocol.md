# WeltSkript: Original-ID-Eingang ohne `text` lesen

Basis: `7165da562e763aac9533f788d2cf0c1c2f13a29b`, eigener isolierter Worktree.
Nur `messlatte/skript.py`, neue gezielte Protokolltests und dieser Bericht.
Keine Kerngates, Welten, Fragen, Goldens, alten Qualitätsassertions oder
required_text-Kriterien geändert; keine realen Modelle oder Netzaufrufe.

RED: Der tatsächliche Original-ID-Eingang enthält `originalsaetze` und entfernt
`text`. WeltSkript griff trotzdem auf `b['text']` zu und erzeugte `KeyError`.
Die direkte Protokollkontrolle scheiterte. Auch die neue echte API-Positivprobe
erzeugte keine akzeptierte Satzstruktur; die negative erreichte wegen des
Anbieterfehlers keine tatsächliche Gateverwerfung.

Der Adapter liest jetzt entweder `text` oder die angebotenen Originaleinheiten
für seine unveränderte `skript.auswahl`-Belegwahl. Im sorgfältigen Originalmodus
antwortet er ausschließlich mit tatsächlich angebotenen ganzen IDs der so
gewählten Belege, begrenzt auf das vorhandene Schema-Maximum. Er erzeugt dabei
keinen neuen Antworttext und übernimmt keine erwarteten Fakten als neue Belege.
Leer-/Unklarantworten verwenden das jeweils angebotene Format. Der normale
Textmodus bleibt unverändert. Unaufmerksame freie Legacy-Fehlkandidaten bleiben
ausdrücklich negative Gateproben; sie werden nicht in richtige IDs verwandelt.

Die positive Probe läuft über synthetische MIME-Aufnahme, echte Speicher und
Konversations-API mit aktivem Skriptprüfer. Sie verlangt **gespeicherten Status
saetze, null Verwerfungen, tatsächlich freigegebene strukturierte Sätze und
genau einen aktiven Prüfaufruf**. Ein Vollzitat-Rückfall könnte diese Probe
nicht bestehen. Die negative verlangt Zitatstatus mit tatsächlicher
Gateverwerfung und ohne freigegebene Satzstruktur; der falsche Satz erscheint
nicht. Der vollständige mehrsätzige Originalabsatz bleibt unverändert.

**15 gezielte Tests bestanden in 4,45 Sekunden**, eine vorhandene
Starlette/httpx-Deprecation-Warnung; Diffcheck sauber. Zwölf neue Kontrollen
umfassen beide Antwortformate, leere/unklare Antworten, angebotene echte IDs,
Schema-Maximum, Legacy-Fehlkandidaten und die positive/negative Produktkette.
Drei bestehende Kalibrierfälle bestätigen sorgfältiges Verhalten sowie die
weiterhin sichtbare falsche Aussage ohne bzw. deren Verwerfung mit Prüfmodell.

```sh
PYTHONPATH=sidecar:. python -m pytest -q \
  messlatte/tests/test_weltskript_original.py \
  messlatte/tests/test_pruefmodell.py::test_sorgfaeltig_mit_pruefmodell_verwirft_keinen_richtigen_satz \
  messlatte/tests/test_pruefmodell.py::test_unaufmerksam_ohne_pruefmodell_kommt_der_falsche_satz_durch_und_wird_als_falsch_erkannt \
  messlatte/tests/test_pruefmodell.py::test_unaufmerksam_mit_pruefmodell_wird_der_falsche_satz_verworfen_und_getrennt_gezaehlt
```

Vorhandenes Python-3.12-Testvenv, keine Installation oder komplette Suite.
Die Prüfung misst die Mechanik des Skriptanbieters, keine reale Modellqualität.
Keine Rootänderung, kein Push oder Release; unabhängiger Review folgt separat.
