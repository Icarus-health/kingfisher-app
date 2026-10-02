# Lokales Stilgedächtnis

Mailantworten berücksichtigen ausdrücklich bestätigte Formpräferenzen aus dem
bestehenden Selbstmodell: Anrede, relative Antwortlänge und Emojis. Eine Regel
kann allgemein gelten oder für die konkrete Antwortadresse innerhalb eines
Postfachs. Kontaktregeln überschreiben allgemeine Werte; „Standard“ erbt sie.
Ein ausdrücklicher Hinweis für die aktuelle Antwort hat Vorrang.

Eigene Entwürfe werden nur nach ausdrücklicher Bestätigung als Schreibbeleg
übernommen. Ab drei unterschiedlichen Texten entstehen deterministische,
prüfbare Vorschläge. Sie werden vor Übernahme gezeigt und können für den
Kontakt oder ausdrücklich allgemein bestätigt werden. Gemischte Du-/Sie-Texte
begründen keine eindeutige Anrede. Es werden höchstens 20 aktive Beispiele je
Kontakt verwaltet. Die Beispiele liegen im bestehenden Episodenspeicher, die
bestätigten Regeln im Selbstmodell; keine zusätzliche Datenbank oder Cloud.

Zurücksetzen widerruft die Regeln; Entfernen eines Schreibbelegs schließt den
Beleg aus und widerruft davon abgeleitete Regeln. Die Historie bleibt erhalten.
Wird ein Beleg über die allgemeine Quellenverwaltung ausgeschlossen, prüft die
Antwortfunktion dessen Zustand ebenfalls vor Verwendung der abgeleiteten Regel.

## Grenzen

Dies ist ein erster, eng begrenzter Lernschritt, kein Finetuning und keine
vollständige Nachbildung von Humor, Wortwahl, Beziehungen oder Situationen.
Gesendete Ordner werden nicht automatisch eingelesen. Beispiele sind vom Nutzer
als eigener Text deklarierte Entwürfe, kein Nachweis für tatsächlich erfolgten
Versand. Bekannte unveränderte KI-Vorschläge werden durch Vergleich abgewiesen;
die Urheberschaft beliebig eingefügter Texte kann das System nicht beweisen.
„Ausführlich“ bleibt innerhalb der bestehenden begrenzten Vorschlagslänge.

Der Roadmap-Stand bleibt 15/20 = 75 %; kein weiterer gesamter Abnahmepunkt ist
allein durch diese Ergänzung erfüllt.

## Nachweise

- 33 gezielte Tests für Stil, Antwortvorschläge, lokale JSON-Ausgabe und
  Mailfreigabe bestanden. Darunter: Kontakt-/Kontotrennung, bewusste globale
  Übernahme, Du-/Sie-Mehrdeutigkeit, Dubletten, ausgeschlossene KI-Ausgangstexte,
  unveränderte Speicher nach Quellenwechsel, Rücknahme und Wiederöffnen der
  SQLite-Speicher sowie Stiländerung während einer Modellantwort.
- UI-Build, Assetmanifest und unabhängiger Review bestanden.
- Docker-Browser mit ausschließlich synthetischen Mails: drei selbst eingegebene
  Texte bewusst markieren, Regelvorschlag prüfen, Kontaktregel bestätigen.
  Tatsächlicher lokaler Ollama-Aufruf mit qwen3.5:4b verwendet danach kurze
  Du-Ansprache ohne Emojis. Der Text bleibt ein prüfpflichtiger Vorschlag; im
  Test wich die inhaltliche Formulierung teilweise vom eigenen Hinweis ab.
- Keine echten Nachrichten versendet, keine produktiven Stilbeispiele angelegt.
