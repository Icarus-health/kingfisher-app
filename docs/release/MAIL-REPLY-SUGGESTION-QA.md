# Lokale Antwortvorschläge — 9. September 2026

In einer geöffneten Mail erstellt „Antwort vorschlagen“ einen lokalen Entwurf aus
dem Nachrichtentext und optionalen eigenen Hinweisen. Die Vorschau ersetzt einen
bestehenden Entwurf ausschließlich nach bewusster Übernahme. Der Text bleibt
bearbeitbar. Empfänger, Konto, Betreff und Versand laufen anschließend über die
bestehende separate Aktionsfreigabe. Auch ohne SMTP bleibt ein lokaler Entwurf
bearbeitbar und kopierbar; Versandvorbereitung ist dann gesperrt.

## Nachweise

- 24 gezielte Tests für Vorschläge, lokale JSON-Vervollständigung und den
  Mail-/Freigabeablauf bestanden. Geprüft: Authentifizierung, Cloud-Ausschluss,
  Eingabelimits, Toolcall-/JSON-Fehler, falsche UID, Konto-/Modellwechsel und
  geändertes Reply-To während der Generierung. Kein Schreib- oder Versandaufruf
  beim Vorschlag.
- TypeScript/Vite-Build und Assetmanifest bestanden. Unabhängiger Code-Review
  ohne blockierende Befunde; anschließend zusätzliche UID-/Entzugstests ergänzt.
- Docker-Image `kingfisher:mail-replies` mit echtem lokalen Ollama `qwen3.5:4b`
  im Browser geprüft: synthetische Terminanfrage und eigener Hinweis erzeugen
  eine getrennte Vorschau, während der selbst geschriebene Entwurf unverändert
  bleibt. Bewusstes Ersetzen, Vorbereitung mit korrektem Konto und Reply-To,
  Bestätigung und erfolgreiche Ausführung ausschließlich an eine Fake-Mailbox
  bestanden. Keine echte E-Mail gesendet.
- Zweites Testkonto ohne SMTP: Entwurf editierbar, Versand gesperrt. Visuelle
  Prüfung im Browser und keine Warnungen/Fehler in der Browserkonsole.
- Beim Live-Nachtest gefunden: ein Maildatum ohne Zeitzone ließ den gemeinsamen
  Posteingang beim Sortieren ausfallen. Der Regressionstest reproduzierte exakt
  den TypeError. Der IMAP-Datumsparser liefert jetzt für `-0000` und fehlende
  Zeitzonen UTC; vorhandene Offsets bleiben erhalten. Damit sind 32 gezielte
  Tests einschließlich Mehrkontenablauf grün.

## Grenzen

Der Entwurf nutzt diese Mail und eigene Hinweise, noch keinen umfassenden
Personen-/Projektkontext. Das kleine lokale Modell formulierte im Test teilweise
holprig; der Vorschlag ist kein verifizierter Sachverhalt und muss geprüft werden.
Sehr lange oder gekürzte Mails werden abgewiesen. Abbrechen verwirft die Antwort
in der Oberfläche, beendet jedoch nicht garantiert die laufende Modellrechnung.
Es gibt keinen automatischen Cloud-Fallback und keinen automatischen Versand.
Der vollständige visuelle Referenzvergleich bleibt offen.

Gesamtstand unverändert **15/20 = 75 %**; diese Ergänzung vervollständigt keinen
weiteren gesamten Abnahmepunkt.
