# K2a: Belege und Widerruf im Gespräch bedienen

Das Gedächtnis bleibt der Kern des vollständigen Icarus-Umfangs in Kingfisher.
Dieses Teilpaket baut auf PR #2 auf und schließt einen konkreten Alltagsablauf:
Merkbitte → Quelle prüfen → bestätigen → falsches Wissen widerrufen → erneut
fragen. K2 insgesamt ist damit noch nicht abgeschlossen.

## Verhalten

- `Quelle anzeigen` führt zur originalen Nutzerzeile in diesem Gespräch und
  setzt den Tastaturfokus dorthin. Das Quellenzitat bleibt in der Karte sichtbar.
- Eine bestätigte Gesprächskarte liest zusätzlich den zugehörigen Claim und
  dessen aktuelle Verwendbarkeit. Die historische Vorschlagsentscheidung wird
  nicht mit dem heutigen Wissensstatus verwechselt.
- `Als falsch widerrufen` widerruft ausdrücklich diese Aussage. Abhängige
  Aussagen verlieren über den vorhandenen Gedächtniskern ihre Gültigkeit.
  Der Widerruf löscht weder die Quelle noch die Entscheidungshistorie.
- Widerrufene, ersetzte und wegen geänderter Grundlagen strittige Aussagen
  erscheinen nicht mehr als aktuell bestätigt. Zeitlich oder anderweitig
  nicht verwendbare Aussagen erhalten ebenfalls keinen Bestätigt-Status.
- Die Änderung wird erst nach erfolgreicher Serverantwort angezeigt. Ein
  Fehler meldet die fehlende Bestätigung der Änderung und lässt einen erneuten
  Versuch zu. Die Route prüft die Zugehörigkeit zum Gespräch und die API-
  Berechtigung; offene Vorschläge können nicht als Wissen widerrufen werden.

## Designvertrag

Referenz: `design-source/06_Screens/Approved/system-overview-canonical-source-v1.png` (vor der Veröffentlichung entfernt),
Abschnitt 04. Die dokumentierte Freigabe
`docs/screen-deviations/SDR-005-approved-conversation-memory-candidate.md`
erlaubt zustandsabhängige Aktionen in der vorhandenen neutralen Gesprächskarte.
Dieses Paket verwendet genau diese Karte und ihre vorhandenen Schaltflächen.
Die Aktionszeile darf bei schmaler Breite umbrechen. Kein neues Modal,
kein neuer Screen und keine neuen Assets. Die Graph-Detailgestaltung wird
dadurch nicht vorweggenommen.

## Reproduzierbare Abnahme

`sidecar/tests/test_conversation_retraction.py` prüft die neuen Serververträge.
Zusätzlich gelten die Pflichtregressionen aus CONTRIBUTING.md, der React-Build
und die Asset-Prüfung.

Im Container-Workflow bleibt der K0-Ablauf erhalten. Danach prüft
`scripts/verify_browser.py --phase memory-controls` an einem eigenen Gespräch:

1. Neues Gespräch über die Oberfläche anlegen und eine synthetische Merkbitte senden.
2. Über `Quelle anzeigen` die ursprüngliche Nutzerzeile fokussieren.
3. Über `Bestätigen` Wissen erzeugen und in einer weiteren Antwort verwenden.
4. Über `Als falsch widerrufen` den Claim entwerten und sofort den neuen Status sehen.
5. Erneut fragen: Der Claim fehlt im Kontext. Nach Browser-Reload bleibt er widerrufen.
6. Desktop-Nachweise samt Konsole, Assets und Schriften erfassen (1440×1000).
7. Den Container erneut starten. `verify_container.py --phase verify-ui`
   prüft den erhaltenen Widerruf, die historische Bestätigung und den Ausschluss
   aus einer weiteren Antwort.

Die beiden Browserphasen erhalten getrennte `summary.json`-Dateien und
Screenshots im Workflow-Artefakt. Die kanonische Übersicht wird zum Vergleich
mit abgelegt. Ausschließlich synthetische Daten und das vorhandene lokale
Testmodell; keine Aussage über Antwortqualität eines echten Modells.

## Stand und verbleibende Arbeit

92 gezielte Backendtests einschließlich der sechs Pflichtsuiten und der neuen
Widerrufsregression sind bestanden. Der lokale React-Build, zwei
Prüfer-/Testmodelltests und die Prüfersyntax sind ebenfalls geprüft. Die lokale Textkopie
enthält weiterhin nicht alle Binärassets. Der integrierte Browser meldet für
die Testadresse `net::ERR_BLOCKED_BY_CLIENT`; daher stammt der vollständige
Container-/Browsernachweis aus GitHub Actions. Ergebnisse werden im PR am
geprüften Commit verlinkt; ein ausstehender Lauf gilt nicht als bestanden.

Noch offen in K2: direktes Bearbeiten einer Aussage mit neuer belegter Fassung,
Personen-/Projektprofile, Identitätsklärung, Graphdetails und die vollständige
visuelle Abnahme. Das Paket liefert Widerruf als bereits definierten
Korrekturweg, keinen vollständigen Beziehungseditor. Kein Merge vor Abgleich
mit dem noch lokalen PC-Stand.

Keine Migration und kein neuer Datenspeicher: Bestehende Claims, Quellen,
Vorschläge und das Änderungsprotokoll bleiben die einzige Wissensgrundlage.

## Beobachteter Lauf und visuelle Befunde

[PR #3](https://github.com/Icarus-health/Kingfisher/pull/3), erster Code-Commit
`c7bd6f63e0c1645b4998d55940f61e8b5580ce19`:
[Containerlauf](https://github.com/Icarus-health/Kingfisher/actions/runs/34030400391)
mit erfolgreich absolviertem Desktop-Browserablauf und zwei tatsächlichen
Containerneustarts. [Artefakt mit Referenz und Screenshots](https://github.com/Icarus-health/Kingfisher/actions/runs/34030400391/artifacts/9988427267).
Auch der lokale HTTP-Vertrag bestand über einen echten Prozessneustart.

Die Asset-CI erkannte zunächst `disputed` fälschlich als Icon, weil ihr
bestehender Scanner auch Zweierlisten von Zeichenketten als Iconliste deutet.
Die Statusprüfung verwendet nun ausdrückliche Vergleiche; die Asset-Allowlist
und die Datei-Prüfung bleiben unverändert. Eine weitere Kopiekorrektur nennt
im Kontextbereich den *aktuell verwendbaren* Stand, um nach einem Widerruf
keine falsche Aussage über die damalige Nutzung zu machen.

Die Desktop-Screenshots zeigen Quelle, Status und Widerruf ohne Überlagerung.
Der Originalscreen enthält diese konkrete Gedächtniskarte nicht; maßgeblich
für ihre Zusatzaktionen bleibt SDR-005, keine Behauptung einer pixelgleichen
Gesamtabnahme.

## Plattformentscheidung: Mac zuerst

Der Nutzer hat Mobile ausdrücklich aus der aktuellen Lieferung genommen.
Die früher aufgezeichnete Überbreite bei 390 px bleibt als historische
Beobachtung nachvollziehbar, ist aber **kein Blocker der Mac-Version**.
Die laufenden Browserprüfungen enthalten deshalb nur noch Desktop-Abläufe.
Docker-Installation auf einem echten Mac und die vollständige Desktop-Designabnahme
bleiben separate Produktnachweise. Das aktuelle Container-/Chromium-Ergebnis
wird nicht als macOS-Laufzeitabnahme ausgegeben.

Klarstellung zum Lieferweg: Docker mit Browser genügt gemäß Produktentscheidung
vom 6. September. Native Paketierung ist kein Freigabekriterium; siehe
[Produktplan](PRODUCT-PLAN.md).
