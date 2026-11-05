# P1 · Review der Aufnahmekorrekturen, Runde 1

- **Spezifikation · bestanden für den begrenzten Aufnahmeadapter.** Alle vier Important-Befunde aus der ersten Runde sind adressiert.
- **Codequalität · bestanden für den geprüften Fix-Diff.** Keine neuen Critical-, Important- oder Minor-Befunde.
- **Produktqualität · NOT EVALUATED.** `bulk_import_authorized = false`.

Geprüft wurde `heldout-intake-fix01.diff` mit SHA-256 `af77be0d9098fc24cf2c91232c58fbcde23599cad5fe63bdd5e8a943210f3b0d` zusammen mit dem Nachtrag im Autorenbericht. Der Diff betrifft die beiden Aufnahmeskripte. Das separate Kalenderpaket lag außerhalb des Reviews.

| Befund aus Runde 0 | Urteil | Beleg |
| --- | --- | --- |
| Verschachtelte Metadaten bleiben nach der SHA-Prüfung veränderbar | **ADDRESSED** | `_freeze_json` macht Maps und Listen bis zu den Blattwerten unveränderlich. Der Loader wendet dies auf beide Eingabelisten an. Der Regressionstest versucht Änderungen an Absender, Empfänger und Anlage. `scripts/memory_acceptance_intake.py:79`, `:129`, `scripts/test_memory_acceptance_intake.py:59`. |
| Laufzeit- und Quellenschlüssel fehlen in den Aufnahmebelegen | **ADDRESSED** | Der Adapter liest das tatsächlich gespeicherte Konto-/Ordner-/UID-/UIDVALIDITY-Tupel und den Produktschlüssel aus dem Support-Snapshot. Der PDF-Beleg führt den Elterntransport, der DOCX-Beleg weist den unversionierten Pfad aus. Der Test gleicht die Belege mit den Produktstores ab und prüft die Stabilität beim Replay. `scripts/memory_acceptance_intake.py:175`, `:238`, `:263`, `scripts/test_memory_acceptance_intake.py:129`, `:156`, `:185`. |
| CLI-Ziel kann in den Freeze-Baum schreiben | **ADDRESSED** | Das aufgelöste Ziel wird vor dem Instanzstart gegen den aufgelösten Fixture-Baum geprüft, sowohl am CLI-Einstieg als auch beim Aufbau der wiederverwendbaren Instanz. Die Ablehnung wird für den direkten Pfad und für einen Symlink-Alias geprüft. `scripts/memory_acceptance_intake.py:134`, `:144`, `:402`, `scripts/test_memory_acceptance_intake.py:246`. |
| Direkter Einstieg setzt keine Modell- und Netzgrenze durch | **ADDRESSED** | Der Instanzaufbau injiziert den Modellwächter für Hauptanbieter, Frage und Satzprüfung. `prepare_baseline` akzeptiert nur die zugehörige aktive Instanz und denselben Quellenbestand, prüft die Konfiguration und setzt die Python-Netzsperre für den Aufruf. Ein Test lehnt eine fremde Instanz ab. Zwei weitere Tests injizieren Modell- und Socketversuche im direkten Aufruf und erwarten den Abbruch vor der ersten Episode. `scripts/memory_acceptance_intake.py:144`, `:344`, `scripts/test_memory_acceptance_intake.py:261`, `:277`. |

Die zwei Minor-Punkte bleiben wie vereinbart separat. Das Adapter-Replay belegt unveränderte Episoden und Transportidentitäten bei bestehenden Intake-Cursorn. Ein erneuter Voll-MIME-Abruf gehört zur späteren S08-Prüfung. Die separate Reply-Probe belegt Connector-Metadaten. Der Nachweis der gespeicherten Reply-Beziehung bleibt offen.

Der gelesene CLI-Bericht unter `/private/tmp/kf-heldout-v2-offline-round1.6CuxvC/baseline.json` stimmt mit dem angegebenen SHA-256 `a899e4c3a95846008989609fe921bfc88d2f8ec760b2c28cac629d6f21b9a25c` überein. Er enthält 110 Belege und 109 Episoden mit 105 `admitted`, vier `partial` und N06 als `withheld` ohne Episode. Die Belege enthalten 102 Mail-Transporttupel und 108 persistierte Produktschlüssel. E09-01 trägt UID 76, N01 und der Elternbeleg von N02 UID 93. N10 ist `unversioned`.

Die Testzahlen aus dem Autorenbericht wurden nicht erneut ausgeführt. Dokumentiert sind 7 fehlgeschlagene und 11 bestandene Tests vor der Korrektur sowie 18 bestandene Tests danach. Die Einzeldatei-Hashes und der leere Fixture-Diff wurden nicht erneut aus dem Arbeitsbaum bestimmt. Der CLI-Bericht der Runde entstand laut Autorenbericht mit dem separat bearbeiteten Kalenderparser. Der Review prüft weder diesen Parser noch Modell-, Abruf- oder Gesamtproduktqualität.
