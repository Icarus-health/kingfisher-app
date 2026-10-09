# Unabhängiges Review: Absatzschutz für normative Originalstellen

Geprüftes isoliertes Archiv: `/private/tmp/kingfisher-rule-paragraph-context-20261009/repo`, Basis `fda6dc213a2c9183e92531940c137afc162b69a5`. Patch SHA256 **`a4214ae4c936de71721327c0ab5f0f60ecad2c4096516572eb923bcea8223334`**. Keine Produktänderungen, tatsächlichen Modellaufrufe, privaten Daten oder Netzwerkzugriffe. Keine Gegenproben laufen mehr auf dieser Fassung.

**Ergebnis: vor Übernahme korrigieren. Zwei bestätigte Schutzlücken lassen eingeschränkte Erlaubnisse allein ausgeben und nach Store-Neustart wiederherstellen. Die zusätzliche Satzmengenprüfung erhält außerdem keine zusammenhängende Originalreihenfolge.**

## P1: Absatzlokale und globale Satzeinheiten passen nach einer Überschrift nicht zusammen

Quelle:

```text
Entwurf

Die Klappe darf geöffnet werden. Dies gilt nur während der Prüfung.
```

`_originalstellen` bietet aus der globalen Satzzerlegung unter ID 2 die Einheit `Entwurf\n\nDie Klappe darf geöffnet werden.` an. Die Auswahl dieser ID ergibt **`status=saetze`, keine Verwerfung**. Das gilt auch mit einem synthetischen zweiten Tor, das einmal Ja liefert.

Ursache: `satzpruefung.py:731–733` zerlegt jeden Absatz lokal. `satzantwort.py:720–729` zerlegt die ausgewählten Einheiten dagegen global und erwartet die lokale Regel als genaues Mengenmitglied. `Die Klappe darf geöffnet werden.` ist nicht gleich `Entwurf\n\nDie Klappe darf geöffnet werden.`; die leere Schnittmenge überspringt den Kontextschutz vollständig.

Die gleichartige Quelle mit `Dies gilt ausschließlich nach schriftlicher Freigabe.` wurde zusätzlich unabhängig über den Legacy-Textpfad und einen gültigen gespeicherten Antwort-Payload geprüft. Nach echtem Schließen und Wiederöffnen von EpisodeStore und ClaimStore liefert `wiederherstellen` die unvollständige Antwort erneut, auch mit gespeichertem Prüfmodell-Ja. Entzug durch `ignore` sperrt sie anschließend korrekt und erhält den Originaltext.

**Korrekturrichtung:** gemeinsame, konsistente Quellabsatz-/Ausgabeeinheiten. Ein Header darf eine Regel nicht so umrahmen, dass deren Absatzpflicht unerkannt bleibt. Keine neue sprachliche Musterliste nötig.

## P1: Normative Einschränkung wird ausdrücklich vom Schutz ausgeschlossen

Quelle, jeweils mit einem der drei Modalverben:

```text
Die Klappe darf geöffnet werden. Dies darf ausschließlich nach schriftlicher Freigabe erfolgen.
Die Klappe darf geöffnet werden. Dies muss ausschließlich nach schriftlicher Freigabe erfolgen.
Die Klappe darf geöffnet werden. Dies soll ausschließlich nach schriftlicher Freigabe erfolgen.
```

In allen drei Fällen genügt Auswahl des ersten Satzes: **`status=saetze`, keine Verwerfung**, sowohl ohne zweites Tor als auch nach dessen synthetischem Ja. Die direkte Satzprüfung besteht ebenfalls; der neue Absatzhelper liefert keine Kontexte.

Ursache: `satzpruefung.py:735–736` verlangt einen Begleitsatz ohne irgendein Regelsignal. Dadurch fällt gerade eine ebenfalls normative Einschränkung aus der strukturellen Bindung. Diese Ausnahme steht zwar im Manifest, erfüllt aber nicht das vom Hauptreview ausdrücklich bestätigte Ziel, einschränkende Begleitsätze zu erhalten.

Der `darf`-Fall ist auch beim Wiederherstellen eines alten Antwort-Payloads nach echtem EpisodeStore-/ClaimStore-Neustart bestätigt: unvollständiger Satz wird angenommen, nach Ignore dagegen korrekt verworfen.

**Korrekturrichtung:** alle mehrsätzigen Absätze mit erkannter Regel binden; keine Ausnahme für ausschließlich normative Begleitsätze. Bewusste Änderungen bisheriger kleinteiliger Satzverträge offen ausweisen.

## P2: Vollständige Satzmenge erhält den Zusammenhang bei Umordnung nicht

Quelle 1:

```text
Die Klappe darf geöffnet werden. Dies gilt ausschließlich nach schriftlicher Freigabe.
```

Quelle 2:

```text
Der Schalter darf umgelegt werden.
```

Akzeptierte Ausgabe:

1. `Die Klappe darf geöffnet werden.` [Quelle 1]
2. `Der Schalter darf umgelegt werden.` [Quelle 2]
3. `Dies gilt ausschließlich nach schriftlicher Freigabe.` [Quelle 1]

Alle Sätze bestehen; Ergebnis **`saetze`**. Der anaphorische Nachsatz steht im Lesefluss hinter der anderen Erlaubnis. Auch reine Umkehrung der beiden Sätze von Quelle 1 wird angenommen. `satzantwort.py:720–731` prüft Mengeninklusion, keine Reihenfolge oder zusammenhängende Ausgabe. Quellnummern bleiben erhalten, ersetzen aber nicht die ursprüngliche sprachliche Zuordnung.

**Korrekturrichtung:** vollständige Regelabsätze als atomare, serverseitig materialisierte Originalausgabe behandeln oder streng in Originalreihenfolge zu einer solchen Einheit zusammenführen. Keine freie Neusortierung. Sind vollständiger Absatz, Sichtbarkeit oder Größenrahmen nicht gesichert, Zitatfallback.

## Bestandene Gegenproben und Kosten des Vertrags

- **98 gezielte Tests unabhängig bestanden:** `test_normative_paragraph_context`, `test_normative_source_binding`, `test_original_sentence_selection`. Dies ist keine Vollsuite und keine Entkräftung der zusätzlichen Gegenbeispiele.
- Vollständiger sichtbarer gemischter Absatz bleibt positiv, auch mit synthetischem zweitem Ja. Eine isolierte Regel aus demselben normalen Absatz wird verworfen.
- Kontext nur mit falscher Quellnummer, Kontext aus anderer Quelle bei unsichtbarem ursprünglichem Absatz sowie ein vom zweiten Tor verworfener Begleitsatz führen korrekt zum Zitatmodus. Ein beliebiges zweites Ja rettet diese drei Gegenproben nicht.
- Nach realem Store-Neustart bleiben vollständiger Absatz, Ein-Satz-Regel und gewöhnlicher Fakt gültig. Ignore sperrt alle sechs geprüften wiederhergestellten Szenarien und bewahrt jeweils den Originaltext.
- Die zentrale Einzelprüfung darf in dieser Architektur einen wörtlichen Regelsatz weiterhin bestehen lassen; die neue strukturelle Pflicht liegt auf der abschließenden Antwort und auf `wiederherstellen`. Beide Ausgabegrenzen müssen dieselben konsistenten Einheiten verwenden. Direkte Einzelprüfungsurteile sind weiterhin kein Beweis vollständigen Kontextes.
- Ein atomarer Absatzvertrag erzeugt längere Antworten und mehr Zitatfallbacks, besonders bei langen Absätzen, Auszügen, irrelevanten Begleitsätzen oder Ablehnung eines Teils durch ein Prüftor. Das ist eine offen zu benennende Verfügbarkeits-/UX-Kostenstelle. Die bestehende Größenbegrenzung darf nicht durch stilles Weglassen des Kontextes umgangen werden.
- Kein allgemeiner Beweis für Dokumentautorität, heutige Gültigkeit oder semantische Wahrheit. Echte Absatzgrenzen und nicht erkannte normative Sprache bleiben getrennte Grenzen. Keine Erweiterung allgemeiner NLP-Grammatik vorgeschlagen.

## Fingerprints und Evidenz

- `satzantwort.py`: `c8049e9df9b4425a32a08d0f8280225ed7e445f806e2e372d605ab90e90c18b9`
- `satzpruefung.py`: `73d9789d3c148e0925687995ab1a2d0a43b2f11a9a08b8e00490e05651c8db1f`
- Unveränderte Goldfixture: `a53217e6a52aa5a6c55728cc5ccc6d12ba21317a53538a391adbda970db4a361`
- Hauptgegenproben und echte Store-Neustarts: `/private/tmp/kingfisher-rule-paragraph-review-probes-20261009.json`
- Reproduzierbarer Runner: `/private/tmp/kingfisher-rule-paragraph-review-probe-20261009.py`
- Unabhängige Helper-/ID-/Ja-Gegenproben: `/private/tmp/kingfisher-rule-paragraph-independent-helpers-20261009.json`

Die Restore-Gegenproben verwenden synthetische gültige Quellverweise und einen über den Produktionspfad erzeugten, für alte Antwortformen angepassten Antwort-Payload; sie prüfen `wiederherstellen` nach Neustart der echten Stores, nicht Browserdarstellung oder den kompletten Gesprächsexport.
