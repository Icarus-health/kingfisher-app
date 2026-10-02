# Von der Nachricht zur Aufgabe — 7. September 2026

In einer geöffneten Nachricht lässt sich ausdrücklich eine lokale Aufgabe festhalten. Titel, Projekt, Fälligkeit und optional die Person, auf deren Rückmeldung gewartet wird, sind bearbeitbar. Die Mail wird als Rohmaterial aufgenommen; die Aufgabe trägt einen Verweis auf diese Episode. Keine automatische Wissensaussage und kein Versand. Bei Quellenentzug oder ungültigem Projekt entsteht keine Aufgabe.

Die neue Aufgabe erscheint in der bestehenden Aufgaben-/Warteansicht. In der Terminvorbereitung des gewählten Projekts ist die ursprüngliche Mail als Quelle der offenen Aufgabe lesbar, ohne nebenbei die gesamte Mail einem Projekt zuzuordnen. Erneutes Merken derselben Quelle bleibt dedupliziert.

## Nachweise

- Vollständige Backend-Suite: 801 Tests bestanden in 136 Sekunden; eine bestehende Starlette/httpx-Abkündigungswarnung.
- Neuer Test: Aufgabe und Wartezustand mit Originalmail, Projektkontext, keine Wissensübernahme/kein Versand, leere Eingaben und entfernte Quellen abgewiesen.
- TypeScript/Vite lokal und im Docker-Image grün; Assetmanifest unverändert; git diff --check grün.
- Echter Browser gegen lokale Testapp und Docker: Mail öffnen, Aufgabe mit Projekt und wartender Person speichern, erneutes Speichern im Formular gesperrt, korrekte Warteansicht, Neuladen behält die Aufgabe. Synthetisches Postfach, keine Nutzerdaten angelegt.
- Bestehender Antwort-/Freigabeablauf in frischem Docker-Testpostfach erneut erfolgreich. Lokale Nutzerinstanz auf Port 8891 aktualisiert; bestehendes Volume erhalten und echter Kalender-/Teilnehmerfluss im Browser erneut geprüft.
- Screenshot im lokalen Aufgabenordner: outputs/mail-task-desktop.png.

## Grenzen

Dies erfasst ausdrücklich eingetragene Aufgaben und Wartezustände. Einzelne Mail kann nun auf Knopfdruck lokale Aufgabenvorschläge liefern. Fortlaufende Zusagenerkennung, Antwortzuordnung und gemeinsame CoS-Gesamtabnahme fehlen weiterhin. Die UI folgt bestehenden Gestaltungsformen; keine behauptete vollständige kanonische visuelle Abnahme. Ein erneuter manueller Vorgang kann eine weitere Aufgabe zu derselben Mail anlegen.

## Lokale Vorschläge ergänzt

„Aufgaben vorschlagen“ analysiert nur die geöffnete Mail mit einem als lokal konfigurierten Modell. Cloud-Anbieter erhalten hierbei keine Nachricht. Bis zu drei Vorschläge enthalten jeweils ein im Mailtext nachgewiesenes Zitat; unbelegte Zitate werden verworfen. Der Aufruf hat keine Werkzeuge und schreibt keine Episode, Aufgabe oder Wissensaussage. „In Aufgabe übernehmen“ füllt nur den Titel; Speichern bleibt eine eigene Aktion. Ein Digest bindet übernommene Vorschläge an die aktuelle Mailfassung. Bei Änderung wird Speichern mit HTTP 409 abgewiesen.

Nachweise: 9 gezielte Mail-/Kalenderkontexttests bestanden einschließlich fehlender Zitate, Werkzeugaufrufen, ungültigem JSON, Cloud-Ausschluss und geänderter Quelle. Ein echter Aufruf des lokalen Ollama-Modells qwen3.5:4b erkannte in einer synthetischen Mail die Angebotsprüfung und Rückmeldung mit wörtlichen Belegen. Browserlauf lokal und im Docker-Image: Vorschlag anzeigen, keine implizite Aufgabe, Titel übernehmen, ausdrücklich speichern und Aufgabe öffnen. Screenshot: outputs/mail-suggestions-desktop.png. Die vorherige Gesamtsuite mit 801 Tests gehört zum vorausgehenden Mail-Aufgaben-Stand; sie wurde für diesen kleinen Ergänzungsschritt nicht vollständig wiederholt.

Die Vorschläge sind keine garantierte vollständige Erkennung: Zitatprüfung beweist Wortlaut, nicht Interpretation. Verantwortliche, Projekt und Fälligkeit werden bewusst nicht aus dem Modell übernommen. Lange Mailtexte werden durch den bestehenden Leser begrenzt; die Leseansicht kennzeichnet den Auszug.

## Aufgabenquelle direkt öffnen

Aus Mail erfasste Aufgaben zeigen „Quelle öffnen“ in der Aufgabenansicht. Der gespeicherte Stand ist unabhängig vom Postfach verfügbar, auch bei erledigten Aufgaben. Herkunft, Aufnahmezeit und Quellentext bleiben sichtbar; externe Inhalte werden ausschließlich als Text dargestellt. Bereits beim Maillesen gekürzte Quellen tragen bei neuer Aufnahme eine Auszugsmarkierung, die auch in Aufgaben- und Terminvorbereitung erhalten bleibt.

Nachweise: 12 gezielte Tests bestanden, darunter neue Store-Verbindungen nach Postfachentzug und Erledigung sowie fehlende Quellen und Auszugsmarkierung. TypeScript/Vite und Assetmanifest grün. Browserablauf gegen lokale Testapp und Docker-Image: Mail zur wartenden Projektaufgabe, Neuladen, Quelle öffnen und Text prüfen. Screenshot: outputs/task-source-desktop.png. Für ältere, bereits ohne Markierung gespeicherte Auszüge lässt sich nachträglich nicht sicher feststellen, ob sie gekürzt wurden.


## Textstelle an der übernommenen Aufgabe

Ein übernommener Vorschlag hält sein wörtliches Zitat in `Provenance.verbatim`
fest. Der Server verlangt dafür den passenden Mail-Digest und prüft den
Wortlaut erneut, bevor er Rohmaterial oder Aufgabe speichert. Die API liefert
die Textstelle beim Öffnen der Aufgabenquelle, unabhängig vom Postfach und
nach erneutem Öffnen des Stores. Ausschluss der Quelle wird sichtbar markiert;
das historische Zitat bleibt lesbar, ohne als gültiger Wissensbeleg zu gelten.

15 Mail-/Kalenderkontexttests bestanden. Der geschützte Docker-Browserlauf
prüft Vorschlag ohne implizite Aufgabe, ausdrückliche Übernahme, Speichern,
Navigation, Beleg nach Neuladen und Ausschlusshinweis. Postfach und
Vorschlagsmodell sind dabei kontrollierte Testadapter; ein echter lokaler
Modellaufruf gehört zu den früheren Nachweisen oben. Kein Mailversand.
