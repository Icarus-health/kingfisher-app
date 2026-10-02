# Einrichtung und natives Mac-Fenster — 28.09.2026

## Ausgelieferter Stand

Implementierung f4c1cb9, letzte UI-Korrekturen cd89eb1; Docker-Abbild `kingfisher:pilot-onboarding-20260928` trägt Revision cd89eb1. Die folgenden Dokumentationsänderungen ändern das Abbild nicht.

- Einstellungen beginnen mit einer Übersicht und direkten nächsten Schritten. Mail, Kalender, lokale KI, Dokumente, Automatik, Arbeitsvorlieben und Sicherungen sind getrennte Bereiche. Technische Felder bleiben unter Erweitert erreichbar.
- Native AppKit/WKWebView-Hülle verwendet denselben lokalen Dienst und dauerhaften Datenbestand. Kein Safari-/Chrome-Fenster nötig. Externe HTTPS-Anmeldung geht an den Systembrowser. Dateiauswahl, Downloads, Fehleranzeige und erneutes Öffnen sind implementiert.
- Host-Bericht erkennt den tatsächlichen Mac statt des Docker-Speichers. Kapazitätsschätzung und vorhandene Modelle sind Hinweise, kein Nachweis der Gedächtnisqualität. Es werden keine Modelle automatisch installiert oder gewechselt.
- Google OAuth mit PKCE, einmaligem zeitlich begrenztem State, verschlüsselten lokalen Refresh-Tokens und ausdrücklicher Konten-/Kalenderauswahl. Kalender nur lesend; Gmail nutzt vorhandenes IMAP/SMTP und benötigt dessen vollständigen Mail-Scope. Bestehende Freigaben für Versand bleiben bestehen.

## Kurz starten

1. `~/Applications/Kingfisher.app` öffnen; unter Einstellungen → Einrichtung beginnen.
2. Lokale KI: Gerätehinweis ansehen und Verbindung prüfen. Angezeigte Dauer ist eine Verbindungsmessung, keine Gedächtnisbewertung.
3. Mail/Kalender: vorhandene manuelle Anbindung verwenden oder Google einmalig vorbereiten. Automatischen Mailabruf separat aktivieren; reine Anmeldung aktiviert ihn nicht.
4. Dokumente zunächst mit wenigen bekannten Dateien testen und Quellen/Antworten gegenprüfen. Sicherungen bleiben unter Sicherung erreichbar.

### Google einmalig vorbereiten

Im eigenen Google-Cloud-Projekt einen OAuth-Client vom Typ **Desktop-App** anlegen, Consent-Konfiguration und eigene Testnutzer einrichten; für Kalender die Calendar API aktivieren. Das heruntergeladene Desktop-Client-JSON ausschließlich im lokalen Kingfisher-Bereich „Google-Anmeldung einmalig vorbereiten“ einfügen. Keine Zugangsdaten in Chat oder Repository ablegen.

Dann „Mit Google anmelden“, den Browser-Link öffnen, nach Rückkehr „Anmeldung prüfen“ und das angezeigte Konto beziehungsweise die gewünschten Kalender ausdrücklich verbinden. Beide Gmail-Konten werden einzeln angemeldet. Entfernen in Kingfisher entfernt den lokalen Zugang; Google-Freigaben können zusätzlich im Google-Konto widerrufen werden.

Primärdokumentation: [Desktop OAuth](https://developers.google.com/identity/protocols/oauth2/native-app), [Gmail XOAUTH2 und Scope](https://developers.google.com/workspace/gmail/imap/xoauth2-protocol), [Calendar-Autorisierung](https://developers.google.com/workspace/calendar/api/auth).

## Tatsächlich geprüft

- Vollständige Backend-Suite: **2541 bestanden**, 2 bestehende Deprecation-Warnungen, 251 Sekunden. Backend seit diesem Lauf unverändert.
- Zusätzlich fokussierte Integrations-/Native-/Geräte-/OAuth-Prüfungen; enthalten in der Gesamtsuite. Native Regeln werden auch als kompiliertes Swift-Programm geprüft.
- UI-Build (TypeScript/Vite) und finale Docker-Erstellung erfolgreich; freigegebener Asset-Vertrag geprüft.
- Unabhängiger Review: behobene Keychain-/Lock-/State-/Duplikatfälle sowie Aktualisierung der Google-Konfiguration beim Tabwechsel und ehrliche legacy_active-Anzeige. Abschließende begrenzte Codeprüfung ohne weitere Befunde.
- Finales Docker-Abbild auf getrenntem synthetischem Bestand gestartet: vorhandene Quelle und Aufgabe sowie pausierte Automatik unverändert erhalten. Hardware-Bericht M2 Max / 32 GiB; Google noch nicht konfiguriert, geschützter Speicher verfügbar.
- Pilot vor Aktualisierung gesichert; bestehendes Volume `kingfisher-pilot-data` weiterverwendet. Quellen-/Aufgaben-IDs, Integrationseinstellungen und aktive Automatik vor/nach Aktualisierung gleich. Keine Rücksetzung.
- Native App kompiliert, installiert, ausführbares Dateirecht und Ad-hoc-Signatur verifiziert. Vorherige Browser-App als `Kingfisher-Browser-vor-Fenster-20260928.app` erhalten. Alter Container bleibt gestoppt als Rückfalloption erhalten; er darf nicht gleichzeitig auf dasselbe Volume zugreifen.

## Offen und ausdrücklich nicht nachgewiesen

- Computersteuerung verweigerte weiterhin Zugriff auf Kingfisher trotz zweimaliger Nutzerfreigabe. Kein Umgehen über andere Werkzeuge. Einrichtung, Import und Sicherungsdownload **im nativen Fenster nicht praktisch abgenommen**; Kompilierung und Regeltests ersetzen dies nicht.
- Kein Google-Desktop-Client hinterlegt, deshalb keine echte Google-Anmeldung, kein echter Token-Refresh und kein Abruf persönlicher Mail-/Kalenderdaten. OAuth-Tests verwenden simulierte Google-Antworten.
- Kein zusätzlicher Nachweis mehrtägiger Gedächtnisqualität; die Tests oben belegen diese begrenzte Lieferung, kein fehlerfreies Gedächtnis.
