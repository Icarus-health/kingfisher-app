# Lokales Stilgedächtnis

Mailantworten berücksichtigen ausdrücklich bestätigte Formpräferenzen aus dem
bestehenden Selbstmodell: Anrede, Form der Anrede, relative Antwortlänge,
Emojis, Grußformel wörtlich und Sprache. Eine Regel kann allgemein gelten, für
einen bestätigten Kreis (`docs/49-kreis-und-privat.md`) oder für die konkrete
Antwortadresse innerhalb eines Postfachs. Die Schichtung ist allgemein → Kreis
→ Kontakt; „Standard“ erbt die darunterliegende Vorgabe. Ein ausdrücklicher
Hinweis für die aktuelle Antwort hat Vorrang.

## Stand 21. Oktober 2026 (Paket B5): Ton aus eigenen gesendeten Mails

Seit Paket B1 liest Kingfisher den Gesendet-Ordner. Die eigenen gesendeten Mails
an genau eine Adresse im selben Konto (Absender „ich“, einziger Empfänger; die
eigene Adresse im Cc zählt nicht mit) sind seitdem die erste Quelle für den
eigenen Ton: höchstens die 20 jüngsten, der zitierte Verlauf abgeschnitten, über
eine gezielte Abfrage (`EpisodeStore.gesendete_an`) statt eines Durchlaufs über
den Bestand (10.003 Episoden: 66 ms im Test). Dazu zählen weiter die
ausdrücklich bestätigten eigenen Schreibbelege.

Ab drei verschiedenen Texten entsteht ein deterministischer Vorschlag, als ein
Satz dort, wo die Stilregeln stehen („Dein Ton an anna@…: Du, kurz, ohne Emoji,
Gruß „Viele Grüße“ (aus 7 gesendeten Mails).“) mit „Übernehmen“, „Nicht
übernehmen“ und den Belegen zum Aufklappen; beim Entwurf nur ein Hinweis mit Weg
dorthin, im Briefing nichts. Nur **Einstimmigkeit** zählt: gemischtes Du/Sie
ergibt keine Anrede, verschiedene Grußformeln keinen Gruß; die übrigen Regeln
bleiben. „Übernehmen“ geht über den bestehenden `PUT` mit den Belegen als
`evidence_ids`; ein veralteter Vorschlag wird mit 409 abgewiesen. „Nicht
übernehmen“ (`POST …/style/ablehnen`) wird im Selbstmodell gemerkt und der
Vorschlag erst wieder gezeigt, wenn ein neuer Beleg dazukommt. Fällt eine
gesendete Mail weg (ausgeschlossen oder durch eine neue Fassung überholt), gilt
die daraus bestätigte Regel nicht mehr. Der Ton je bestätigtem Kreis entsteht aus
den gesendeten Mails an alle Personen des Kreises, mit Einstimmigkeit über die
Kontakte (`/api/v1/stil/kreise`, Einstellungen → Kingfisher und du).

Es werden höchstens 20 aktive Schreibbelege je Kontakt verwaltet. Belege liegen
im bestehenden Episodenspeicher, bestätigte Regeln und Ablehnungen im
Selbstmodell; keine zusätzliche Datenbank oder Cloud.

Zurücksetzen widerruft die Regeln; Entfernen eines Schreibbelegs schließt den
Beleg aus und widerruft davon abgeleitete Regeln. Die Historie bleibt erhalten.
Wird ein Beleg über die allgemeine Quellenverwaltung ausgeschlossen, prüft die
Antwortfunktion dessen Zustand ebenfalls vor Verwendung der abgeleiteten Regel.

## Grenzen

Dies ist ein eng begrenzter Lernschritt, kein Finetuning und keine
vollständige Nachbildung von Humor, Wortwahl, Beziehungen oder Situationen.
Gesendete Mails zählen nur, wenn der Gesendet-Ordner eingelesen ist (Paket B1)
und die Aufnahme den Absender als eigene Adresse kennt (`ich`); Mails an mehrere
Empfänger belegen nichts für einen einzelnen Kontakt. Schreibbelege sind vom
Nutzer als eigener Text deklarierte Entwürfe, kein Nachweis für tatsächlich
erfolgten Versand. Bekannte unveränderte KI-Vorschläge werden durch Vergleich
abgewiesen; die Urheberschaft beliebig eingefügter Texte kann das System nicht
beweisen. Die Grußformel wird nur übernommen, wenn eine ganze Schlusszeile einer
bekannten Formel entspricht (Liste in `mail_style._GRUSS`), höchstens 40
Zeichen; freier Text aus einer Mail gelangt so nicht in den Systemhinweis. Die
Spracherkennung zählt Stoppwörter (Deutsch, Englisch), weitere Sprachen und
Dialekt erkennt sie nicht. Die Form der Anrede liest nur die erste Zeile. Der
Kreis einer Person wird über `person:a:<adresse>` gefunden; eine
zusammengeführte Person mit anderer Kennung bekommt keinen Kreis-Ton (fail
closed). „Ausführlich“ bleibt innerhalb der bestehenden begrenzten
Vorschlagslänge. Wie ein lokales Modell die Regeln `gruss`, `anrede_form` und
`sprache` umsetzt, ist in dieser Umgebung nur mit einem Skriptmodell geprüft.

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
