# Echter Aufnahmeweg und lokale Personenbelege

Produktcode: `ddc10fa1bd508e5cb7868e6dd8c605237ea60d71`, auf `0143e0e`.

Erstmals gehen die eingefrorenen künstlichen Originale tatsächlich durch Dokument-HTTP-Aufnahme, den Modellworker, den gespeicherten Bedeutungssuchindex und Gesprächs-HTTP-Antworten. Die früheren Antwortmessungen bereiteten die Einordnung deterministisch vor. Hier werden die Datenbanken und der Suchdienst vor Fragen neu geöffnet; eine gespeicherte Antwort wird nach einem weiteren Neustart und Quellenentzug gesperrt. Originaltexte bleiben erhalten. Kein Fenster-/Alltagsnachweis, keine Prüfung automatischer Gesprächsrouten oder sämtlicher Mail-/Kalenderadapter.

## Befund und gezielte Änderung

Der erste vollständige Lauf mit 14 Quellen beantwortet alle 23 Kontrollfragen korrekt; ein unabhängiger Reviewer prüft jede sichtbare Antwort gegen die Originale. Neun Antworten sind freie Sätze, zehn Originalzitate, vier Nichtwissen. Die zusätzliche echte Themen-/Entitätenerkennung liefert jedoch bei allen 14 erfolgreichen Jobs **leere Entitätenlisten**, obwohl fünf Personennennungen ausdrücklich im Text stehen. Technischer Erfolg ist keine Erkennungsquote.

Kontrollversuche trennen die Ursachen: Zitatanker allein helfen nicht; ein deutlicherer Extraktionsprompt allein ebenfalls nicht. Wird im JSON-Schema die Entitätenerkennung vor den Themen dekodiert, erscheinen die Namen. Absolute Modell-Zeichenpositionen sind dann aber häufig falsch. Exakte Zitate lösen dies; die zusätzlich verlangte Vorkommensnummer scheitert wiederum bei einem Zweipersonen-Holdout. Diese erfolglosen Kontrollen sind unverändert mit abgelegt.

Lokale OpenAI-kompatible Anbieter nutzen deshalb jetzt Block-ID und exakten, innerhalb dieses Blocks **eindeutigen** Namen. Der Code bestimmt die Zeichenposition. Das Schema erzeugt Entitäten zuerst, verlangt weder Zeichen- noch Vorkommenszählung. Mehrdeutige Namen, falsche Blöcke, erfundene Namen, zusätzliche Vorkommensfelder und Modell-Absenderrollen bleiben ungültig. Quelle und Fingerabdruck werden vor dem Commit erneut geprüft; keine Originaländerung, Identitätsverschmelzung oder automatische Bestätigung. Die bisherigen lokalen Aufnahmegrenzen von 64.000 Dokumentbytes, 12.000 Textzeichen, 24 Blöcken und 4.000 Zeichen je Block bleiben erhalten. Der explizit freigegebene entfernte Zitatweg behält sein Vorkommensschema und seine bisherigen Grenzen.

## Ergebnis des vollständigen Produktlaufs

Der finale Lauf nutzt `VerifiedLocalProvider` und 18 echte künstliche HTTP-Originale: den unveränderten 14er-Katalog plus vier vorher festgelegte Holdouts. Alle 18 werden eingeordnet, mit Themen/Entitäten bearbeitet und eingebettet; kein offener Indexrest. Die ursprünglichen fünf sowie vier zusätzliche Personennennungen werden korrekt an ihre Originalstellen gebunden (**9/9, keine zusätzliche Person**). Ähnliche Namen bleiben getrennte Erwähnungen; das Servicepostfach wird nicht zur Person. Quellenentzug nach Neustart sperrt die gespeicherte Antwort ohne weiteren Modellaufruf und erhält den Originaltext.

Die Antworten erreichen trotzdem nur **21/23 Quellen-/Statuspunkte**:

- **RQ02:** korrekter Beleg, aber unnötige Rückfrage nach der gemeinten Person.
- **RQ04:** zur Frage nach einer prüfenden Person im Auftrag KL-24 wird die fremde Holdout-Notiz H02 ausgewählt. Der erfundene Satz „Veit Noll prüft die Ware im Auftrag KL-24“ wird korrekt verworfen, weil KL-24 im Beleg fehlt. Der Rückfall zeigt aber das unpassende Originalzitat. Das ist weiterhin ein Auswahl-/Relevanzfehler, kein korrekter Nichtwissensfall.

Der größere Kontrollbestand unterscheidet sich vom ersten 14er-Lauf; 23→21 ist deshalb **kein isolierter Wirkungsvergleich des Codefixes**. Er zeigt eine reale bisher übersehene Störquelle. Ein korrektes Zitat und eine gültige Quellen-ID beweisen nicht, dass die Quelle den erfragten Auftrag betrifft. Nächste Kernarbeit ist die Bindung der ausgewählten Belege an ausdrücklich erfragte Vorgänge, einschließlich gespeicherter Antworten. Keine zugeschnittene Liste der Testkennungen und keine gelockerte Faktenprüfung.

Auch Entitätentypen sind keine bestätigte Wahrheit: derselbe Ortsname „Werkhalle Epsilon“ wird in einer Quelle als Ort, in einer anderen als Organisation vorgeschlagen; das Servicepostfach erscheint teilweise als Organisation. Diese Vorschläge brauchen weitere Qualitätssicherung. Der Nachweis ist weder eine vollständige Personen-/Projektidentität noch eine allgemeine Ablage- oder Fehlerfreiheitsabnahme. Bereits vollständig eingeordnete persönliche Quellen werden durch diese Änderung nicht still erneut verarbeitet; dafür ist der vorhandene gezielte Nachprüfweg nach Modellfreigabe nötig.

## Prüfung, Ressourcen und Grenzen

Zehn neue deterministische Prüfungen: fünf gewünschte Verhaltensfälle zuerst rot, fünf Sicherheitsfälle schon grün; nach Änderung alle grün. Insgesamt **230 betroffene Backend-/Diagnostikprüfungen bestanden**, unabhängiges Codereview ohne blockierenden Befund. Der isolierte netzlose Paket-Smoke unter 1 CPU/512 MiB prüft 263 Pythonquellen, 112 unveränderte UI-Dateien, Originalentzug und den lokalen Unicode-Namensanker. Er ist kein Modellbenchmark.

Ollama 0.35.1, vorhandenes qwen3.5:4b und bge-m3, separater Loopback-Testserver. Keine Modelldownloads, persönlichen Quellen, Cloudaufrufe oder produktiven Modellwechsel. Ein erster finaler Versuch wird bei ungefähr 8,17 GiB gemessenem eigenem Prozess-RSS beendet; er zählt nicht als bestanden. Der vollständige Wiederholungslauf entlädt das Modell ausdrücklich nach jeweils vier Testpaketen, endet nach rund 250 Sekunden bei ungefähr 7,14 GiB maximalem gemessenem eigenem RSS und beendet seinen Testserver. Dieser Stichprobenwächter ist **keine harte RAM-/GPU-Grenze**, und die diagnostischen Entladepausen beweisen keine produktive Akku-/Speicherqualität. Die unveränderten Originalberichte stehen in `aborted-after-*` und `after-*`.

Die vorhandene installierte Oberfläche bleibt unverändert. Produktiver Import und Ollama bleiben pausiert bzw. aus; kein großer persönlicher Importstart und keine neue Cloudfreigabe. Native Fensterbedienung, persönlicher Bestand, ausreichender Speicher für große Importe und Tages-/Akkuabnahme sind weiterhin offen. Der gesamte CoS ist nicht fertig abgenommen.
