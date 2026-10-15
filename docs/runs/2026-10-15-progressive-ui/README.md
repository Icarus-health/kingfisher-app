# Wesentliches zuerst · 15. Oktober 2026

Fortsetzung von PR #65 auf `3ab0a8c`. Nutzerziel: schlicht, elegant und situationsabhängig. Die freigegebenen Farben, Bilder und bestehenden Funktionen bleiben erhalten; die erste Ebene zeigt weniger Erklärtext.

## Umsetzung

- **Heute:** kleinerer Tageskopf, Aufgaben und Termine früher sichtbar. Der Quellenstand bleibt als sichtbarer Status; die vollständigen Ausfallhinweise und Aktualisierung sind aufklappbar. Nur eine zentrale Quellenwarnung. Änderungen und neue Hinweise sowie Tageslage/Verlauf liegen hinter eigenen Zusammenfassungen.
- **Aufgaben:** Titel und primäre Aktion bleiben sichtbar. Ungeprüfter Verlauf bleibt ein kurzer Warnhinweis. Begründung, Quellen und weitere Bearbeitung stehen unter „Details & Bearbeiten“. Wird eine laufende Bearbeitung zugeklappt, öffnet „Bearbeitung fortsetzen“ denselben Editor wieder.
- **Situationsabhängige Module:** erfolgreich geladene leere Wiedervorlagen, Wissensklärungen und Gedächtnisfragen nehmen auf Heute keinen Platz ein. Einträge, Ladezustände, Fehler, begrenzte Ergebnisse und Aktionsrückmeldungen bleiben sichtbar. Die eigenen vollständigen Ansichten behalten ihre Leerzustände.
- **Vorschläge:** Aufgabe, Projekt, genaue Frist und zeitliche Warnung bleiben vor der Bestätigung sichtbar. Derselbe Fristwert wird für Darstellung und Übernahme verwendet. Beleg, Aufnahmezeit und Begründung sind aufklappbar. Sammelaktion erst nach Auswahl; keine unnötigen Seitenschaltflächen bei nur einer Seite.
- **Gedächtnis und Projekte:** Erläuterungen in Suche, Akten und Bereichen öffnen sich bei Bedarf. Leere Personen-/Projektblöcke verdrängen keine Originaltreffer. Projektkennzahlen bleiben direkt erreichbar; die zusätzliche Aufgabenvorschau ist aufklappbar.
- **Update-Rückmeldungen:** bleiben außerhalb geschlossener Klappbereiche sichtbar. Es wird kein einmaliger Erfolgs-/Fehlerhinweis unsichtbar verbraucht.

Die Tageslage wird erst beim ausdrücklichen Öffnen gelesen; ihr Marker für den letzten Blick wird vorher nicht verbraucht. Nach dem ersten Öffnen bleibt sie montiert, damit Zuklappen keine Eingaben verwirft.

Keine neuen Modelle, automatischen Entscheidungen oder Hintergrundaufrufe hinzugefügt. Die Anpassung folgt vorhandenen Daten und sichtbaren Zuständen; sie ist keine neue KI-Personalisierung.

## Prüfung

- 722/722 UI-Tests, TypeScript/Produktionsbuild, Assetvertrag und Diffprüfung bestanden. Sieben neue Verhaltensprüfungen: sichtbare Unsicherheit bei geschlossenen Details, kompakter Quellenstand, korrekt ausgeblendete Leerzustände einschließlich Fehler-/Rückmelde-/Trunkierungsfällen, unveränderte genaue Bestätigungsfrist, Wiederaufnahme eines versteckten Editors und sichtbare einmalige Update-Rückmeldungen und erst nach Öffnen gelesene Tageslage.
- Zunächst drei neue Prüfungen rot, anschließend grün. Die zwei vom unabhängigen Review gefundenen Nebenwirkungen waren ebenfalls zunächst mit Regressionen rot und nach Korrektur grün. Nachreview ohne wichtige offene Befunde.
- Echte Browserprobe im getrennten künstlichen Bestand: Heute bei 1.280×900 und 390×844, Details per Tastatur öffnen, Editor zu-/aufklappen ohne Zustandsverlust, Quellenstand öffnen, Vorschlagsbeleg öffnen, Auswahl/Sammelvorschau öffnen und schließen, Suchergebnisse mit aufklappbarer Suchhilfe. Kein horizontaler Seitenüberlauf bei 390 px. Am Ende keine erfassten Konsolenfehler, normale Fenstergröße wiederhergestellt.
- Der Backendkern blieb unverändert; seine große Suite aus der vorangehenden Abnahme wurde nicht ohne Anlass wiederholt. Bestehende Bundlewarnung bleibt offen.

Die Vorschau ist aktualisiert. Kein Merge, kein persönliches Mac-Update, keine Aktivierung eines Providers und keine Fortsetzung des Großimports. Reale Konten und native Berechtigungen behalten die Grenzen der vorangehenden Prüfung.

## Erweiterung: Mail, Kalender und Personenprofile

Der Originaltext steht im Mailleser vor dem Arbeitsformular. Antwort, Aufgaben- und Terminvorbereitung sind klar benannte Klappbereiche. Ein aus dem Überblick übernommener Aufgabenvorschlag öffnet und fokussiert das bereits eingebundene Formular; Antworten bleiben beim Bearbeiten einer Aufgabe erhalten. Die Mailliste zeigt den Namen kompakt, die vollständige Adresse bleibt am Namen und im Lesebereich erreichbar.

Die Rasteransichten des Kalenders haben eine geschlossene zusätzliche Tagesliste; die ausdrücklich gewählte Listenansicht bleibt offen. Datums- und Kalendernavigation klappt auf kleinen Fenstern ein und bei Wechsel auf Desktopbreite auf. Filter, Zeitraster, Termindetail, Teilnehmende und belegte Kalenderkopien bleiben erreichbar. Es wird kein Termin wegen seines Titels zusammengeführt.

Personenprofile wiederholen Namen und Kontaktadresse nicht in mehreren Karten. Belegter Kontakt, Projektverbindungen und ausdrückliche wartende Aufgaben stehen vor ausführlicher Akte und Pflege. Verlauf, Beziehungskreis, zusätzliche Verbindungen und KI-Überblick sind gezielt aufklappbar. Unbekannte Zuordnungen und veraltete KI-Überblicke bleiben erkennbar.

Prüfung der Erweiterung: 725/725 UI-Tests einschließlich Regressionen für Lesereihenfolge, einzelne Identität, sichtbare Unsicherheiten, Entwurfserhalt und Fokusübergang. Die drei anfänglichen Verhaltensregressionen wurden vor der Korrektur rot beobachtet. Produktionsbuild, Assetvertrag und Diffprüfung bestanden; unabhängiges Code- und Nachreview ohne wichtige offene Befunde. Browserprüfung mit ausschließlich künstlichen Daten bei 1280×900, 900×900, 390×844 und 1280×360: Mail lesen/bearbeiten, Quellen öffnen, Details per Tastatur, Profilrückweg mit Suche, Kalenderfilter, Raster und Listenansicht. Keine erfassten Konsolenwarnungen oder -fehler. Echte Mailübertragung und Terminänderungen gehören nicht zu dieser Oberflächenprüfung.
