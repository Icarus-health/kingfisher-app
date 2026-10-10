# Persönliche Sicherung und Upgradevorprüfung – 10.10.2026

Prüfkandidat `1.0.6-preview.6979131`, unveränderter Laufzeitcode `69791314c69c0092cd81e69952c2d0a1fdb21985`. Das gekoppelte Paket ist in [der Paketprüfung](../2026-10-10-daily-ux-package/README.md) gebunden.

## Vollständige Backend-Prüfung

Der vollständige Lauf auf dem Code-Archiv ergab 6.062 bestandene Tests, 18 Fehlschläge, 86 Setupfehler, einen Linux-spezifisch ausgelassenen Fall und 26 bestandene Subtests. Die Sandbox blockierte lokale Testserver/Verbindungen; ein Prüfprogramm benötigte echte Git-Metadaten; Swift durfte seinen Standardcache nicht schreiben. Auch der Test seiner Netzsperre musste außerhalb der vorgeschalteten Sandbox laufen, damit er den eigenen abgefangenen Netzversuch sehen konnte.

Die 104 betroffenen Fälle wurden auf unverändertem Code wiederholt: lokale Testserver zugelassen, getrennte schreibbare Swift-/Clang-Caches, Git-Metadaten des exakt gleichen Commits ergänzt. **104/104 bestanden**, keine Codeänderung. Zusammen sind 6.166 unterschiedliche Tests und 26 Subtests bestanden, ein Fall bleibt plattformbedingt ausgelassen. Das ist eine vollständige Abdeckung in zwei Läufen, kein behaupteter einzelner grüner Gesamtlauf. Rohlogs beider Läufe bleiben erhalten. Keine GitHub-CI-Wiederholung.

## Tatsächliche persönliche Sicherung

Die vorhandene Installation wurde kurz angehalten, das vollständige Datenvolume nur lesend eingehängt und anschließend derselbe alte Stand wieder gestartet. Alle 129 Dateien (229.239.354 Bytes) und acht Verzeichnisse einschließlich Steuerungszuständen und vorhandener Sicherungen wurden archiviert. Das Archiv wurde separat ausgepackt; Dateiinhalte, Verzeichniseinträge, Besitzer und Gruppen, Zugriffsrechte, Nanosekunden-Änderungszeiten und erweiterte Dateiattribute stimmen überein. Im persönlichen Volume sind keine xattrs vorhanden; ihre Erhaltung wurde zusätzlich an einer künstlichen Linux-Dateistruktur mit fünf xattrs und einem leeren Verzeichnis geprüft. Dies ist eine geprüfte Datei-/Verzeichniswiederherstellung, kein Blockgeräteabbild; Inodes und ctime sind nicht Teil des Nachweises. Alle 17 SQLite-Datenbanken im wiederhergestellten Wurzelbestand bestehen die Integritätsprüfung. Die lokale Konfiguration wurde mit der laufenden Instanz abgeglichen und separat mit 0600 gesichert; der private Sicherungsordner ist 0700.

**Persönliche Dateien, Originaltexte, Konfiguration, Passwörter und das private Archiv liegen ausschließlich lokal unter dem Kingfisher-Anwendungssupport. Nichts davon wurde ins Repository kopiert.** Die Skripte hier enthalten nur den Mechanismus, keine Werte oder Quellen. Diese technische Sicherung ist kein verschlüsseltes, portables Recovery-Paket für die Weitergabe und benötigt keine Cloud.

Der unabhängige Review beanstandete die erste, reine Datei-Inhaltsprüfung als unzureichend für eine vollständige Volume-Wiederherstellungsbehauptung. Der korrigierte Nachweis umfasst nun auch die genannten Metadaten und leere Verzeichnisse; die erste Sicherung bleibt zusätzlich erhalten. Der alte Container wird im `finally` anhand seines ursprünglichen Laufzustands gestartet, auch wenn der Stop-Aufruf einen Fehler meldet. Keine Änderung am Produktcode oder am gebauten Paket.

## Upgrade zuerst auf einer Kopie

Eine weitere flüchtige Kopie dieser tatsächlichen Sicherung wurde mit dem neuen lokalen Image unter `--network none` und ohne App-/Anbieter-/Modellkonstruktion geöffnet. `EpisodeStore` migrierte v20→v21. Zeileninhalt sowie Spalten und Tabellen-DDL der sechs ausgewählten vorhandenen Tabellen bleiben identisch, darunter **344 Originalepisoden und 333 Quellenverweise**. Die Wiederherstellung erfolgt mit Besitzern und Rechten; anschließend werden Migration und erneutes Öffnen als regulärer Anwendungsbenutzer UID/GID 1000 geprüft. Integrität und erneutes Öffnen bestehen. Originalvolume und Sicherung blieben unverändert. Dies beweist Erhalt beim Schemawechsel, keine bessere KI-Einordnung der persönlichen Inhalte.

## Noch nicht umgestellt

Das vorhandene Kingfisher-Fenster war erreichbar. Vor dem App-Wechsel hat sich der Mac erneut gesperrt; die Computersteuerung kann nicht entsperren. Daher bleibt die persönliche Installation auf `1.0.6-local.3403623`. Der neue Prüfkandidat ist nicht installiert, der große Mailimport wurde nicht fortgesetzt, keine Cloud-/Modellkosten und keine Systemfreigaben verändert.

Nächster tatsächlicher Schritt nach Entsperren: aktuellen Bestand unmittelbar vor Umschaltung sichern, bestehende App sauber schließen, zusammengehöriges Mac-/Backend-Paket übernehmen, Original-/Aufgaben-/Gesprächserhalt und Oberfläche prüfen. Die zugelassenen drei lokalen Kalender und die tatsächliche Datei-/Diktatbedienung bleiben Teil dieser Abnahme. Kein neuer Umbau der Gedächtnisarchitektur ist dafür vorgesehen.
