# Personenbezüge, Fristrollen und Sonnet 5.5

Korrekturstand: `6918da1`, auf Basis von `419ff23`; bezahlter Transportlauf auf `363d99e`, lokale Datumsableitungen anschließend ohne Modellaufruf auf `6918da1` nachgeprüft. Zielversion: 1.0.24.

Kurze Namensformen werden ausschließlich innerhalb der aktuellen Mail mit ihren Kontakten abgeglichen. Eindeutige aktuelle Anrede oder abschließende Absendersignatur darf einen Kontaktanker verwenden; zitierte/prosaische Kurznamen bleiben offene Kandidaten. Exakte kurze Kontaktnamen nehmen an der Mehrdeutigkeitsprüfung teil. Äußere ASCII-Namensquotes werden nur für diesen lokalen Vergleich entfernt; innere Apostrophe bleiben bedeutend. Keine globalen Teilnamen-Aliasse, kein automatisches Zusammenführen bestätigter Personen.

Die breite Datumssuche bleibt unverändert verfügbar. Personenakten verlangen für Fristen einen positiven lokalen Frist-/Handlungsbezug. Veranstaltungen, Abwesenheiten und Zeiträume werden nicht allein wegen eines benachbarten Bitte-Absatzes zu Fristen. Ungefähre Angaben behalten ihre Originalposition, auch bei mehrfach gleichem Wortlaut. Eine ausdrücklich verschobene bekannte Aufgabenfrist kann ohne wiederholtes Fristwort fortgeführt werden; ein bloß gemeinsam erwähntes Veranstaltungsobjekt genügt dafür nicht. Abgeleitete Regeln sind versioniert, Originale und Nutzerentscheidungen bleiben unverändert.

Sonnet 5.5 nutzt die vom Anbieter unterstützte strukturierte JSON-Ausgabe; andere Anthropic-Modelle behalten ihren bestehenden Transport. Anfrage- und Ausgabegrenzen werden nicht erhöht. Unvollständige Antworten und geänderte Freigaben werden verworfen. Beide Transporte sind bis zur gespeicherten Personenstelle mit synthetischen Quellen getestet.

## Prüfungen

- 70 neue Datumsrollen-Szenarien und 25 Quellalias-Szenarien; Fehler zunächst reproduziert, anschließend korrigiert. Bestehende Messlatte-Erwartungen bleiben unverändert.
- Unabhängiges finales Review: keine verbleibenden Befunde innerhalb des geprüften Umfangs; 246 gezielte Tests und beide Transportintegrationen bestanden; das letzte kleine Fristgegenstands-Delta wurde zusätzlich unabhängig mit 72 Tests geprüft.
- Gedächtnisdiagnosen unter `scripts/`: 235 bestanden.
- Messlatte und Mac-App einschließlich Swift-Logik: 330 bestanden, 1 übersprungen. Der Swift-Modulcache lag im beschreibbaren temporären Verzeichnis.
- Oberflächenbau, Asset-Vertrag sowie Profil-Schema und Beispiel bestanden. Bestehender Hinweis auf große JavaScript-Pakete bleibt.
- Vollständige Backend-Prüfung: Ergebnis wird vor Veröffentlichung ergänzt.

Der erste vollständige Lauf fand zwei bestehende Fristgegenstands-Regressionsfälle (7.197 andere Tests bestanden); beide wurden vor Veröffentlichung korrigiert und unabhängig geprüft. Die bestehende Testsuite wurde dafür nicht abgeschwächt. Der abschließende vollständige Lauf verwendet zwei getrennte, niedrig priorisierte pytest-Prozesse.

Frühe Läufe ohne Loopbackrechte konnten lokale HTTP-Testserver nicht binden; der vollständige Freigabelauf wird deshalb mit lokalen Testserverrechten ausgeführt. Das ist kein ausgeschalteter Produktschutz. Automatische CI-Doppelläufe sind mit `[skip ci]` wegen des bekannten Minutenlimits ausgelassen; keine CI-Neustarts.

## Begrenzte private Stichprobe

Die zehn unveränderten Originale wurden exakt mit der vorherigen Auswahl abgeglichen. Derselbe Vorfilter hielt eine Werbemail vor einem Modellaufruf zurück. Die übrigen neun Quellen liefen mit dem neuen Cloudtransport in einer getrennten Datenbankkopie und dem vorbereiteten Anthropic-Zugang.

Ergebnis: acht vollständig neue Einordnungen, eine abgewiesene Kategorien-/Personenauswertung; 26 Anfragen, 0,249026 USD aus gemeldeten Tokens zum [Anthropic-Standardtarif](https://platform.claude.com/docs/en/about-claude/pricing), 236,24 Sekunden. Grenze vor Versand: 0,60 USD. Keine Wiederholung, kein Ausweichmodell, keine produktiven Ergebnisübernahmen. 148 frische wörtliche Belege und 13 getrennt gezählte Belege aus einem erhaltenen älteren Kategorienstand wurden gegen Originalstellen geprüft. Wörtliche Übereinstimmung ist kein Vollständigkeits- oder Bedeutungsnachweis.

Die gezielten Kurznamensdubletten sind in dieser Probe beseitigt; Veranstaltungsdatum und Anmeldefrist sind getrennt. Die zurückgewiesene Quelle zählt trotz vollständiger einzelner Aussageauswertung nicht als frischer Gesamterfolg. Eine als unsicher eingeordnete Passage mit einer ausdrücklich genannten redaktionellen Frist zeigt weiterhin eine Erfassungslücke. Erwähnte Fußzeilenpersonen können weiterhin reine Erwähnungsprofile haben; keine fremde Aufgabe oder Frist wurde ihnen in den geprüften Schlüsselfällen zugeteilt.

Ein unabhängiger zweiter Prüfer hat die neun Quellen fachlich gegengeprüft. Ergebnis: kein Nachweis für die Freigabe eines großen Pakets. Der Auftrag meldet `complete_with_gaps`, `quality_verified=false`; der produktive Großimport bleibt pausiert. Die getrennte lokale automatische Aufgabenerkennung wird durch diesen Cloud-Gedächtnisversuch nicht ersetzt.

Produktive Originale, Aufgaben, Projekte, Notizen, bestätigte Wissensaussagen und Nutzerentscheidungen blieben vor und nach der Probe zeilenweise gleich. Während der Probe war kein lokales Ollama-Modell geladen; lokale Leseanfragen antworteten in 5,6–278,5 ms, der App-Container lag bei einer Momentaufnahme bei rund 216 MiB. Das ist keine allgemeine Leistungsgarantie für andere Mac-Programme.

Private Originale, Modellantworten und Belege bleiben außerhalb des öffentlichen Repositorys. Die Mac-Installation wird vor Abschluss mit Sicherung, Datenprüfung und Modulprüfsummen gegen den hier getesteten Code bestätigt.

## Grenzen

Die lokale Fristregel unterstützt ein begrenztes deutsches Vokabular und einfache grammatische Beziehungen. Komplexe oder unbekannte Formulierungen können als Originalquelle ohne abgeleitete Frist erhalten bleiben. Aus Quellen entstehen keine bestätigte Zuständigkeit, Teilnahme oder Aufgabe. Diese Fassung ist kein Versprechen fehlerfreier oder vollständiger Gedächtnisleistung und keine Freigabe für unbeaufsichtigte Massenverarbeitung.
