# Voll-MIME-Wiederholung derselben Quelle

Stand: 05.11.2026. Geprüfter Code: `9e17e2b33922526869c0ec3ea1341b6f9492121c`.

Eine unveränderte Exportkopie dieses Commits wurde in einem getrennten temporären
Verzeichnis ausgeführt. N01 aus dem eingefrorenen Satz wurde zweimal über den
echten `MailConnector.message_mit_anhaengen` gelesen und über `mail_ingestion.remember`
einschließlich Anhangaufnahme gespeichert. Ersetzt wurde ausschließlich der
IMAP-Transport durch die bestehende künstliche Mailbox. Python-Sockets und DNS
waren gesperrt; alle Modellrollen hatten den abbrechenden NoModel-Anbieter.

Ergebnis: Zwei tatsächliche MIME-Abrufe, weiterhin genau zwei Episoden. Eltern-
und Anhang-ID, Originaldokument, Quellenkopf, Inhaltshash und Belegfingerabdruck
sind nach beiden Durchgängen gleich. Der zweite Aufruf meldet weder neue noch
geänderte Quelle. Das eingebettete PDF stimmt bytegenau mit N02 überein; es wurde
nicht separat importiert. Der eingefrorene Bestand blieb unverändert.

[Beobachtete Ergebnisse](result.json) und [ausgeführte Probe](probe.py).

## Grenzen

Dies schließt den bisher fehlenden Nachweis der erneuten Voll-MIME-Übergabe für
dieselbe Konto-/Ordner-/UIDVALIDITY-/UID-Identität. Ein bloßer erneuter
Intake-Aufruf mit schon fortgeschrittenem Cursor hätte das nicht bewiesen.
Anbieteranmeldung, TLS und Dubletten über unterschiedliche Transportidentitäten
werden hier nicht geprüft. Es wurden keine Aufgaben oder Behauptungen erzeugt.
Die semantische Lizenzverpflichtung und SQ10 bleiben **nicht ausgewertet**;
S08 ist damit nicht vollständig als Qualitätsfall bestanden. Keine persönlichen
Daten, Modellaufrufe, API-Kosten oder Mac-Änderungen.

## Reproduktion

In ein frisches temporäres Verzeichnis `source/` die Pfade `sidecar`, `messlatte`,
`scripts` und `docs/fixtures/memory-acceptance-20261104` aus dem genannten Commit
mit `git archive` exportieren. Die Probe daneben als `probe.py` kopieren und den
vollen Commit in `base.txt` speichern. Mit der vorhandenen Sidecar-Testumgebung
(Python 3.12, `PYTHONDONTWRITEBYTECODE=1`) die Probe ausführen. Sie erzeugt einen
neuen synthetischen Instanzordner und `result.json`; kein bestehendes Datenziel
verwenden. Die einzige Laufwarnung war die bestehende Starlette/httpx-
DeprecationWarning. Der erste Exportversuch benutzte irrtümlich das ältere
System-Python, dessen `tarfile.extractall` den Parameter `filter` nicht kennt;
der Export wurde anschließend mit Python 3.12 abgeschlossen. Kein Produktfehler.

## Ergänzung: gespeicherte Antwortverknüpfung je Konto

Eine zweite, eigens erzeugte künstliche Mailfolge wurde vollständig über den
Connector und `remember` aufgenommen. Dieselben Message-ID-Kopfzeilen in zwei
Konten verbinden sich nur innerhalb des jeweiligen Kontos. Die Antwort im
zweiten Konto fehlte zunächst: Die erste Kontoantwort wurde dort nicht als
Treffer ausgegeben. Nach der zweiten Antwort und erneutem Öffnen der Datenbank
zeigt jedes Konto weiterhin genau auf seine eigene gespeicherte Antwort.
Der persistierte Headerindex und der tatsächliche `ReplyIndex` wurden gelesen;
die Probe beschränkt sich damit nicht auf den MIME-Parser.

[Antwortbeobachtung](reply-result.json), [ausgeführte Probe](reply_probe.py).
Vier tatsächliche MIME-Abrufe, vier Quellen, keine Modelle oder Netzverbindung.
Dies ist ein technischer Verknüpfungsnachweis, keine semantische Bewertung von
Personen, Aufgaben oder Zusagen. Ein erster Harness-Versuch suchte vergeblich
nach einer expliziten `reply_to`-Verknüpfung im eingefrorenen Satz; die finale
Probe erzeugt deshalb eine separat gekennzeichnete Mailfolge. Der Holdout wurde
nicht geändert. Reproduktion wie oben, mit `reply_probe.py` und einem neuen
`reply-instance`-Ziel.
