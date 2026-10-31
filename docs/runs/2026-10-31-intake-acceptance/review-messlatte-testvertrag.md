# Unabhängiges enges Review: Messlatte-Testframework

31.10.2026, Worktree `/private/tmp/kf-skill-categories-20261031`. Nur die vier beauftragten Testdateien und ihre unmittelbaren Fixtures gelesen. Keine Produktions-/kanonischen Miniweltänderungen durch den Reviewer.

**Abschließendes Urteil nach enger Nachprüfung: Kein verbleibender Befund im geprüften Test-only-Patch. Projektionskorrektur, getrennte Rollenregressionen und Fristerwartung sind sachgerecht; der gemeldete lokale Test-Oracle-Widerspruch ist geschlossen.**

## Offener Testwiderspruch

In `messlatte/tests/test_pruefmodell.py::test_der_pruefmodus_des_skriptmodells_ist_skriptbar` verlangt die Variante `urteil='ja'` ausdrücklich, dass sowohl RICHTIG als auch die neue falsche Rollenvertauschung im Rendertext stehen. Die abschließende Assertion verlangt dennoch `bewerte_antwort(...).klasse == 'richtig'`.

Die dort verwendete unveränderte Standard-Miniwelt enthält die neu eingeführte Falschaussage nicht als Verbot. Der Test besteht daher mit einem tatsächlich falschen Zusatz, den seine Bewertungsassertion fälschlich als richtig bezeichnet. Die separate Hauptkalibrierung über `welt_mit_skript` trägt das neue Verbot korrekt und erkennt dieselbe Falschaussage. Der Befund betrifft ausschließlich die Aussagekraft dieser zusätzlichen Testassertion, nicht einen neuen Produkt- oder Graderfehler.

Enge Empfehlung an Root gesendet: Für diese lokale Bewertung eine kopierte Frage mit dem neuen FALSCH-Verbot verwenden. Dann bei absichtlich falschem Prüfer-Ja `falsch` erwarten, in den abweisenden Varianten `richtig`. Kanonische Miniwelten und Produktionsgrader unverändert lassen.

## Bestätigte Projektionskorrektur

Das Skriptmodell nutzt zuerst den strikten Produktdecoder für gleichnamige Literal-Feldkopien. Danach ersetzt ein alleinstehender eigener Kurzmarker nur den eigenen text-Wert. Der ausführliche FUNDSTELLE-Marker wird auch innerhalb eines langen Kontextauszugs durch text derselben Zeile ersetzt; der restliche Kontext bleibt vorhanden. Das entspricht der bestehenden Modellanweisung und verhindert keine reale Negations-/Kontextprüfung.

Die neuen Tests prüfen originale Reihenfolge und IDs, aktuellen statt referenzierten Zeilentext bei kopiertem Marker, unveränderte Eingangsdaten und strikte Ablehnung ungültiger/fremder/self/forward/chained/wrongfield-Verweise. Ein abweichender Kontext wird nicht durch text ersetzt; Metadaten werden nicht zu zusätzlichen Suchfeldern. Der Kurzmarker innerhalb sonstigen Kontexts löst keine allgemeine Textausweitung aus.

Der lange synthetische Fall verwendet tatsächlich `auszug` und `ergaenzen` auf einem Original oberhalb GANZ_BIS. Er prüft, dass der relevante Originaltext im projizierten Kontext nur über den FUNDSTELLE-Marker erreichbar ist und dass Zusatzbedingung, Kopf, Trennstelle und Kürzungshinweis weiter auswählbar bleiben. Die frühere enge Annahme, auch dieser Marker dürfe text nicht einsetzen, wäre mit dem Produktvertrag unvereinbar; ihre Korrektur ist sachgerecht.

## Rollen- und Fristtests

Die neue nichtmenschliche Rollenvertauschung ist eine passende Kalibrierung des zweiten Tors: Der Test verlangt ausdrücklich null Verwerfungen im ersten Tor und eine Verwerfung im Judge, samt korrekter Zählung im Bericht. Ohne Judge wird die Falschaussage im lokal ergänzten Oracle als falsch erkannt. Die frühere erfundene Lea-Zuständigkeit bleibt als eigener Test erhalten und muss bereits am primären Personenschutz scheitern. Kein Schutz wurde gelockert, um den Judge künstlich zu erreichen.

Der Fristtest akzeptiert den beabsichtigten Originalmodus, verlangt aber weiterhin die vollständige neue Frist, keine alte Frist, keine falsche Aussage und jetzt sogar exakt die alleinige aktuelle Quelle `mainz-003`. Das ist keine inhaltliche Abschwächung zugunsten eines grünen Präfixtests.

## Eigene Prüfung

**28 gezielte Offline-Tests bestanden in 4,84 s**: neues Projektionsmodul sowie `test_pruefmodell.py` und `test_antwort_saetze.py`. Ein bestehender Starlette/HTTPX-Deprecationhinweis. Der oben genannte Testwiderspruch besteht trotz Grün und ist deshalb gesondert gemeldet.

Keine Modelle, privaten Daten, Netzaufrufe, Produktedits, Commits oder gesamte Messlatte durch den Reviewer. Die vollständige neue Messlatte und spätere CI bleiben Roots getrennte Nachweise. Dieser Frameworktest belegt keine fachliche Qualität eines realen Modells.

## Abschließende Nachprüfung des lokalen Oracle-Fixes

Der aktualisierte Test erzeugt mittels `dataclasses.replace` eine lokale Kopie der Frage und ihres Verbotsobjekts; nur dort wird FALSCH zusätzlich aufgenommen. Die kanonische Ausgangsfrage bleibt unverändert, ausdrücklich per Assertion kontrolliert. Eingabe, Modellantwort, beide Prüferanfragen und Verwerfungszähler wurden für die Korrektur nicht verändert.

Der absichtlich falsche Judge-Ja-Fall verlangt jetzt `klasse == 'falsch'` und `falsche_aussage is True`. Nein, unklar und Prüferfehler verlangen weiterhin `richtig` und False, da hier die Falschaussage aus der Antwort entfernt ist. Damit wird der frühere false-green-Oracle-Widerspruch nicht verborgen, sondern direkt zum Gegenbeweis.

**Alle vier Varianten unabhängig grün nachgeprüft.** Nur dieser einzelne parametrisierte Test wurde nach dem Fix erneut ausgeführt. Kein Produktions-/Grader-/kanonischer Miniweltedit und keine Modelle/Privatdaten durch den Reviewer. Der vorherige 28er-Lauf bleibt als Zwischenstand dokumentiert; die vollständige Messlatte nach dem finalen Testpatch ist Roots gesonderter Nachweis.
