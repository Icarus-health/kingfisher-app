# Nachrichten lesen und kontrolliert antworten — 2026-09-07

## Ablauf

Nachrichten öffnen sich in der bestehenden Nachrichtenansicht. Angezeigt werden Absender, Reply-To, Postfach und Text. HTML wird zu reinem Text verarbeitet, Bilder und Skripte werden nicht geladen. Sehr lange Einzeltexte werden sichtbar auf 20.000 Zeichen begrenzt. Ein lokaler Browserentwurf bleibt beim Schließen erhalten und wird nach erfolgreicher Übergabe an das Gespräch aus dem Entwurfsspeicher entfernt.

„Als Quelle merken“ übernimmt nur Rohmaterial und erzeugt keine Wissensaussage. Wiederholtes Merken derselben Mail erzeugt kein Duplikat. Antworten werden mit dem Konto der geöffneten Nachricht vorbereitet. Die sichtbare Freigabe im Gespräch zeigt tatsächliches Absenderkonto, Reply-To, Betreff, Text und Verlaufsbezug. Vor Freigabe wird nichts gesendet; das Ergebnis bleibt im Gespräch.

## Korrigierte Unterbaufehler

- IMAP verwendete Sequenznummern statt UIDs. Der Connector nutzt nun UID SEARCH/FETCH und prüft UIDVALIDITY. Alte oder zu einer anderen Postfachgeneration gehörende Kennungen werden abgewiesen, statt eine andere Mail zu öffnen. Lesen bleibt readonly und verwendet BODY.PEEK.
- Bei mehreren Konten ist Versand mit expliziter Konto-ID möglich. Entfernte Konten fallen nie still auf ein anderes Konto zurück. Die Vorschau löst Absender aus dem verbundenen Konto auf.
- Collections verändern gelieferte Message-Objekte nicht mehr, damit wiederholtes Lesen keine mehrfachen Kontopräfixe erzeugt.
- Ein Ausfall einzelner Postfächer wird in der Nachrichtenansicht gemeldet, während verfügbare Nachrichten sichtbar bleiben.

## Nachweise

- 100 unterschiedliche gezielte Backendtests erfolgreich: Mail-/Freigabe-/Mehrkonten-/Connector-/Containerverträge sowie neue UID-, HTML- und Gesprächsablauftests. Bestehende Starlette/httpx-Abkündigungswarnung.
- Neue Nachweise: identische Remote-Kennung in zwei Konten, korrektes Reply-To, falsche Bestätigung blockiert, einmaliger Versand nur im gewählten Testkonto, Kontoentzug ohne Ersatzversand, Quellenaufnahme ohne Fakten und stabile UID trotz Sequenzänderung.
- TypeScript/Vite-Build im Docker-Image erfolgreich; Assetmanifest unverändert (14 Dateien, 17 Icons).
- Echter Browser gegen lokale Testapp und fertiges Docker-Image mit zwei isolierten Testpostfächern: öffnen, lokalen Entwurf wiederfinden, Quelle merken, Vorschau im Gespräch, freigeben und dauerhaftes Ergebnis nach Neuladen. Keine JavaScript-Seitenfehler und keine entfernten Medienabrufe.
- Ausschließlich Fake-Mailbox-Senken: keine echte E-Mail gesendet. Docker-Testcontainer und temporärer Datenspeicher von der Nutzerinstanz getrennt. Browser plugin not available; reguläres Playwright.
- Screenshot: outputs/mail-reader-desktop.png im lokalen Aufgabenordner.

## Verbleibend

Echter IMAP-/SMTP-Anbieterlauf und produktive Mailfreigabe sind damit nicht bewiesen. Automatische Mailaufnahme, KI-Antwortvorschläge, vollständiger Beziehungskontext und Terminvorbereitung bleiben weitere CoS-Arbeit. Die Leseansicht ist eine reduzierte Ableitung vorhandener Gestaltungsformen, keine behauptete vollständige kanonische visuelle Abnahme.
