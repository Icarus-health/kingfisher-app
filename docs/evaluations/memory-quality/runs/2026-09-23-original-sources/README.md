# Originalquellen ohne vorbereitete Wissensaussagen finden

23. September 2026. Ausgangsbasis `463879d`, geprüfter Produktcode `cc7fd99`.

Eine erfolgreich aufgenommene TXT-Quelle war im beleggebundenen Antwortweg bisher unsichtbar, solange keine passende bestätigte Wissensaussage existierte. Der neue begrenzte Rückfall findet gespeicherte Originaltexte anhand eines ausdrücklich genannten Suchbegriffs. Er zeigt einen überprüften Ausschnitt als **„Quelle berichtet · nicht bestätigt“**. Es entsteht weder eine bestätigte Frist noch eine neue Identitätszuordnung.

Beispiel: `Suche in meinen Quellen nach "PAKET-583".` Der geprüfte Text „Prüfung am 14. Oktober nur nach Freigabe. Keine feste Zusage.“ wird unverändert angezeigt. Das Datum wird nicht aus seiner Bedingung herausgelöst. Der Ablauf benötigt keinen Modellaufruf.

Der Nutzer hat die Umsetzung und die Auswahl des nächsten sinnvollen Schritts ausdrücklich an den verantwortlichen Agenten delegiert. Abgegrenzte Such- und HTTP-Testarbeit wurde mit günstigeren Agenten durchgeführt; Antwortvertrag, Integration und abschließende Prüfung blieben beim verantwortlichen Agenten. Keine behauptete Credit-Ersparnis ohne Abrechnungsdaten.

## Vertrag und Grenzen

- Nur ausdrücklich zitierter Suchbegriff (3–120 Zeichen) mit Quellenabsicht, zunächst wenn der bisherige Claim-Abruf keine Kandidaten liefert. Unterstützte Leseformen sind unter anderem „Was steht …“, „Suche in meinen Quellen …“ und „Zeig mir den Originaltext …“. Das ist keine allgemeine Lösung für natürliche Faktenfragen.
- Unverändert lokaler Konfigurationsschutz. Ein konfiguriertes lokales Modell ist noch Voraussetzung, obwohl dieser Rückfall es nicht aufruft. Der Zugriff ist der authentifizierte lokale Eigentümer-Leseweg auf zugelassene Quellen; Provider-Lokalität allein ist keine neue Sensitivitätsfreigabe und erlaubt keinen Versand an ein Modell.
- Nur aktuelle, nicht ausgeschlossene MESSAGE-/DOCUMENT-Originale. Namen bleiben Text in getrennten Quellen. SUMMARY, überholte Quellfassungen und inkonsistente Snapshots sind ausgeschlossen.
- Quellen mit bereits bestehenden Claims beliebigen Status oder erzeugten SelfModel-Aussagen werden konservativ zurückgestellt. Sonst könnte ein widerrufener oder abgelaufener Wissenseintrag über seinen Rohtext wieder erscheinen. Die Zusammenführung dieser Bereiche mit sichtbarem Korrektur-/Konfliktstatus ist weiter offen.
- Literal-Casefold-Suche, keine SQL-Wildcards, keine Synonym- oder Bedeutungsinterpretation. Höchstens 20 Kandidaten, drei Ausschnitte zu jeweils 800 Zeichen. Quellenbody höchstens 512 KiB, Dokumentrepräsentation höchstens 768 KiB. Kooperatives Suchbudget: 1.000.000 SQLite-Schritte bzw. 0,5 Sekunden; Überschreitung verwirft die Kandidaten und wird als unvollständige Suche ausgewiesen. Kein harter Echtzeitnachweis unter beliebiger Systemlast.
- Der Suchraum ist nicht auf die neuesten 500 Quellen begrenzt. Nach 20 Kandidaten kann trotzdem ein passender Treffer fehlen. Gegenbeispiel aus dem Review: 20 zurückgestellte Treffer verdecken einen verwendbaren 21. Treffer. Dieser Fall wird als `source_search_incomplete` gemeldet; er ist nicht als vollständiger Nullbefund bestanden.
- Quellenzeit unbekannt bleibt unbekannt; Erfassungszeit ist separat. Bekannte Kürzung bei der Aufnahme und Kürzung nur für die Anzeige werden getrennt genannt. Fehlende Anlagen und nicht angebundene Kanäle werden nicht als geprüft ausgegeben.

## Verlauf und Quellenentzug

Persistiert werden nur neutraler Antworttext, Quellenkennungen, Inhaltsbindungen und Ausschnittgrenzen. Originaltext, Titel und Herkunft werden für jede betreffende Nachricht erneut aufgelöst. Dadurch enthalten gespeicherter Assistententext und Gesprächsvorschau keine kopierten Originalausschnitte. Vollbackups enthalten weiterhin die gespeicherten Originalquellen; Quellenentzug ist kein Löschauftrag.

Die Bindung umfasst Inhalt, sichtbare Metadaten, Quellkopf und Entzugsgeneration. Der bestehende `support_fingerprint` allein reicht dafür nicht. Änderungen ohne Claim-Revision, Quellenentzug, Ersatz oder Beschädigung führen zu einem neutralen Nichtverfügbarkeitsvermerk. Entzug und spätere Wiederzulassung machen eine alte Antwort nicht wieder gültig; eine neue Suche kann die neu zugelassene Quelle verwenden.

Die letzten 20 Quellenantworten einer Unterhaltung werden beim Öffnen erneut aufgelöst; ältere bleiben neutral und nennen die Anzeigegrenze. Die Nachrichten werden nicht gelöscht. Quellenantworten sind unabhängig von ihrer Gültigkeit aus späterem Modellverlauf ausgeschlossen. Beliebige Folgefragen sind damit noch nicht automatisch Quellenfragen.

Normale Quellenentzug-/Wiederzulassungs- und Gesprächs-API-Wege teilen den Gesprächslock. Die Prüfung bindet die Ausgabe an den dabei gelesenen Stand. Das ist keine Zusage, beliebige direkte Datenbankänderungen nach dem letzten Snapshot rückwirkend aus einer bereits ausgelieferten Antwort zu entfernen.

## Nachweis

- **2.138 Tests und vier Subtests bestanden** in einem abschließenden Lauf von `sidecar/tests scripts` auf `cc7fd99` (174,25 s). Zwei bestehende Bibliothekswarnungen. Lokale Testserver waren erlaubt; keine GitHub-CI-Wiederholung. Ein vorheriger unnötiger breiter Agentenlauf wurde bei 940 bestandenen Tests gestoppt und zählt nicht als zusätzliche Abnahme.
- 41 zusätzliche Regressionen gegenüber der Ausgangsbasis, darunter echte HTTP-Aufnahme ohne vorbereitete Claims, unveränderte Bedingungen, Unicode-Ausschnittgrenzen, Metadatenwechsel, Entzug während Sammlung, übergroße Quellen, erneutes Öffnen, Neustart, fehlende Authentifizierung und Ausschluss aus späterem Modellverlauf.
- Unabhängiges Review fand eine automatische Routinglücke: „Suche …“ konnte den normalen Chat erreichen. Vorher vier rote Formulierungsfälle, nach Korrektur grün; zusätzlich echter HTTP-Nachweis für „Suche …“ ohne Modellaufruf. Die beschriebene Grenze bei 20 Kandidaten bleibt offen und sichtbar.
- TypeScript/Vite-Build und unveränderter Asset-Vertrag bestanden. Docker-Paket `kingfisher:raw-cc7fd99` gebaut.
- Paketprüfung durch echte HTTP-Routen mit synthetischen Quellen: Upload → Frage → exakter Ausschnitt → Containerneustart → weiterhin gültig → Entzug → zweiter Neustart → alter Ausschnitt fehlt → Wiederzulassung → alte Antwort bleibt ungültig, neue Suche findet die Quelle.
- Browser: Originalausschnitt und Bedingung sichtbar, vorhandene Originalansicht geöffnet, Quelle ausgeschlossen, Antwort nach Reload entwertet, Vorschau neutral. Im Docker-Browser alte ungültige und neue gültige Antwort nebeneinander nachgewiesen. Keine Konsolenfehler im geprüften nativen Ablauf. Die automatische Browser-Dateiübergabe verlor ihre Sitzung; die Textdatei wurde deshalb über den echten Upload-Endpunkt aufgenommen. Der Datei-Auswahldialog ist damit kein bestandener neuer UI-Abnahmenachweis.

`package-verification.json` enthält den synthetischen Paketnachweis; `implementation-review.md` den unabhängigen Reviewstand. Der dort zunächst beobachtete Status `no_match_in_searched_text` bei zurückgestellten Kandidaten wurde anschließend auf `source_search_incomplete` präzisiert. Keine produktiven Daten, echten LLM-Aufrufe, neuen Modelle oder Abonnements.

## Nächster fachlicher Schritt

Dieser Lauf belegt Aufnahme bis Quellenfund für eine enge explizite Suche. Er belegt weder vollständige Interpretation eingehender Nachrichten noch verlässliche natürliche Frist-/Personenantworten. Als Nächstes denselben Ablauf um Arbeitsinterpretationen, bekannte Korrekturen und offene Konflikte erweitern; natürliche Fragen müssen ihren belegten Antwortvertrag durchgehend benutzen. Die übrigen Hindernisse aus dem [CoS-Audit](../../audits/2026-09-21/README.md) bleiben offen. Kein perfektes oder bereits allgemein freigegebenes CoS-Gedächtnis.
