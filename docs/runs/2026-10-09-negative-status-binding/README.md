# Negative Angaben wiederfinden und Status an seine Sache binden

Produktcode: `7295b2e08f39020998a02bdefb7f2b6b49c4298f`. Zwei Gedächtnismodule geändert; Oberfläche, signiertes Mac-Programm und Schema 20 unverändert. Die abschließende Gesamtprüfung ist bestanden. Der geprüfte Stand ist nach kalter Sicherung auf dem Mac installiert.

## Fehler und Änderung

Bei einer Frage nach der bereits eingegangenen Versandfreigabe lag die Originalquelle samt „Freigabe liegt noch nicht vor“ in der Auswahl. Das Modell wählte trotzdem keine Information. Im Originalstellen-Modus erhält nur diese formal gültige leere Auswahl eine zusätzliche, begrenzte Prüfung mit demselben Kontext, denselben Originalkennungen und derselben Frist. Alle ursprünglichen Quellen-, Bedingungs-, Identitäts- und Modellprüfungen bleiben aktiv. Ein gewöhnliches Nichtwissen bekommt keinen weiteren Aufruf.

Daneben konnte ein Status von einer fremden Sache stammen: „Rechnung R-719 bezahlt“ belegte im alten freien Antwortweg fälschlich „Lieferung Z-204 bezahlt“, wenn beide Quellen zitiert wurden. Die Statusprüfung bindet nun Satzteile an ihre eigenen Quellenstellen, Kennungen und Namensfolgen. Ein Quellenkopf darf die Sache benennen, aber keinen Status belegen. Mehrdeutige Kennungen und widersprüchliche passende Stände führen zu Originalzitaten. Regeln oder Pflichten belegen keinen tatsächlich erfüllten Stand.

Gültige Zusage-/Bestätigungsnomen bleiben Sachanker. Ein ausdrücklich mit „Später:“ gekennzeichneter einfacher Statusabschluss kann nur den früheren Stand derselben Sache innerhalb derselben Quelle ablösen. Gleiche Kennungen, Namensfolgen und Sachwortmengen sind erforderlich. Fragen, Bedingungen, Regeln, Unsicherheitsmarker und Zitate verhindern diese Ablösung; das spätere Prädikat muss in den eng begrenzten deklarativen Statusrahmen passen. Die Reihenfolge allein und Zeitstempel anderer Quellen genügen nicht. Dies ist keine allgemeine Grammatik-, Chronologie- oder Bedeutungsprüfung.

## Unabhängige Korrektur und Regressionen

Der erste vollständige Lauf auf 8b37ffe hatte 16 Fehler: gültige Zusagen wurden mangels verbliebener Sachanker abgewiesen, eine ausdrücklich spätere Zahlung als Konflikt behandelt; acht Zweites-Tor-Tests erwarteten noch eine inzwischen schon deterministisch erkannte falsche Zustimmung. Die gültigen Erwartungen wurden erhalten. Das zweite Tor prüft nun eine echte, weiterhin nur semantisch erkennbare Umkehr von Lieferant und Empfänger.

Ein unabhängiges Review fand im Zwischenstand eine neue Modalitätslücke bei „Später: wenn/vermutlich/Frage“. Diese wurde vor Installation geschlossen. Das [Nachreview](kingfisher-spaeter-status-recheck-20261009.md) findet in der begrenzten Änderung keinen Blocker. [Die isolierte Mutation](modality-mutation.log) lässt 7 der 8 Gegenfälle fehlschlagen, wenn die Aussagegrenze entfernt wird. Die echte Produktionsdatei blieb währenddessen unverändert. [365 betroffene Prüfungen](targeted-tests.log) bestehen; [Die vollständige abschließende Prüfung](full-backend-tests.log) besteht mit 5.834 Prüfungen, einer übersprungenen Prüfung und 26 bestandenen Subtests (zwei vorhandene Warnungen).

## Paket und reale künstliche Abläufe

Das Paket basiert auf dem exakt bereits installierten63f7078-Image und ersetzt nur die beiden geprüften Pythonmodule und die Versionsangabe. [266 Python-/112 Oberflächendateien](package-check.json) sind byteweise geprüft. Der [echte Ablauf im fertigen Paket](package-integration.log) benutzt echte Abhängigkeiten und echte Speicher-/Neustart-/Quellenentzugswege, lediglich die externe JSON-Modellantwort ist geskriptet. Keine persönlichen Datenträger oder Netzwerkverbindungen. Die falsche Statusaussage wird in neuer Antwort und alter gespeicherter Antwort zurückgewiesen; die Originale bleiben bei Neustart und Quellenentzug erhalten. Der gleiche Ablauf auf 63f7078 ließ die falsche freie Aussage noch durch; siehe vorherige Nachweise unter `previous-8b37ffe/`.

Die getrennten echten Mac-Modellläufe verwenden dieselben eingefrorenen künstlichen Kataloge, qwen3.5:4b und bge-m3 sowie eigene Modellkopien mit unabhängigen Inodes. Kein Cloudzugriff, kein produktiver Modellendpunkt, keine privaten Quellen. Temporäres Entladen nach vier Quellen ist eine Diagnosehilfe, keine nachgewiesene produktive Speicherpolitik. Die 900 Sekunden/8 GiB-RSS-Notabschaltung ist kein harter GPU-/Speicherdeckel. Originalcache-Hashes und Metadaten werden vor und nach jedem Lauf geprüft.

Die [unabhängige finale CoS-Inhaltsprüfung](cos-content-review.md) bewertet alle 23 Antworten als ausreichend:19 beantwortbare Fälle und 4 korrekte Enthaltungen gemäß unverändertem Katalog, insbesondere RQ06 mit ausdrücklich fehlender Freigabe. Alle 18 Quellenkörper stimmen. Die Personenerkennung übersieht diesmal Noa Jansen:8 der 9 Prüffälle stimmen; im vorherigen Lauf waren es 9/9. Die Einordnungsmodule sind unverändert; diese Laufabweichung bleibt ein echter offener Qualitätsbefund und wurde nicht durch Wiederholung verborgen.

Die [unabhängige finale Regelprüfung](normative-content-review.md) bewertet 14/16 als ausreichend,2 teilweise, 0 falsch. W04 fehlt weiterhin der ausdrückliche Unzulässigkeitsschluss trotz zutreffender Regel-/Ereignisquelle; IA05 liefert einen überflüssigen Satz zu einem anderen Arbeitsschritt. IA05 ist zum alten Lauf bytegleich; bei gleicher strenger Messlatte war deshalb auch die frühere Bewertung 14/16 und nicht 15/16. Alle 19 Quellenkörper stimmen, alle 16 gespeicherten Antworten bleiben nach Neustart bytegleich ohne zusätzliche Modellaufrufe. Quellenentzug macht die Antwort unverfügbar und bewahrt den Originalkörper.

CoS 325,18 Sekunden/5,62 GiB und Regeln 219,65 Sekunden/5,96 GiB sind gemessene Diagnosewerte für Prozess-RSS, keine produktive Akku-/GPU-/Großimportabnahme. Beide Läufe wurden ordentlich beendet; native Quelldateien samt Metadaten unverändert.

[5.834 Backendprüfungen](full-backend-tests.log), eine übersprungene Prüfung und 26 bestandene Subtests bestehen (1010,06 Sekunden; zwei vorhandene Warnungen).365 betroffene Prüfungen und beide isolierten Mutationskontrollen ergänzen diesen Nachweis. Kein neuer Oberflächenbuild war nötig: alle 112 Oberflächendateien und das signierte native Programm stimmen mit dem geprüften Elternpaket überein.

## Gesicherte Mac-Installation

Installiert ist `1.0.6-local.7295b2e`, Image `sha256:002d4626799a33ebc9a7dc292eedcc08da833141d6e61428a67ca67d96c94011`. Die App wurde über ihr Menü beendet. Die wiederholt beobachtete Wartungsruhe und der gestoppte einzige Datenträgerschreiber gingen der vollständigen Rohkopie einschließlich SQLite-Journalen voraus. Rohkopie und WAL-bewusster Datenvergleich stimmen. 344 Originale, 17 SQLite-Dateien, Konten/Einstellungen und explizite Importpause bleiben erhalten, gleicher Datenvolume, Schema 20, keine Migration. Das ursprüngliche signierte native Programm bleibt unverändert. Rückweg liegt lokal im geschützten Sicherungsordner; keine persönlichen Daten oder Zugangsschlüssel wurden ins Repository kopiert.

Die App wurde nach dem Update erneut über das native Fenster gestartet. Heute lädt seine Übersicht, die Ortszeit läuft weiter, Gedächtnisbereiche und die Aufgabenansicht sind erreichbar. Kalender lädt den vorhandenen Zeitraum und den ausgewählten Termin samt Zeit/Quellenlabel. Einstellungen zeigen erhaltenes Postfach und Kalender-Abo. Der Mac-Kalenderhelfer meldet sich auch nach dem Neustart nicht; er ist damit weiterhin ein offener Integrationsfehler. Die Seiten zeigen während des Nachladens Ladezustände; eine verlässliche Navigations-Latenz ist damit noch nicht nachgewiesen. Diese Bedienung ist keine vollständige persönliche Inhalts-, Latenz- oder Akkuabnahme. Die ältere8b37ffe-Messung bleibt als ausdrücklich nicht ausgelieferter Zwischenstand unter `previous-8b37ffe/` erhalten.

## Mac-Bedienung und offene Produktgrenzen

Vor dem Update wurden im echten nativen Fenster Heute, Aufgaben, Kalender, Gedächtnis und die KI-Einstellungen geöffnet. Die Ortszeit läuft mit; verbundene Zugänge und die ausdrückliche Importpause sind sichtbar. Keine Mail-/Kalender-/Aufgabenänderung, keine neue Modellwahl, Cloudfreigabe oder Verarbeitung aktiviert. Der Mac-Kalenderhelfer meldet sich in diesem Stand nicht; das vorhandene Kalender-Abo ist davon getrennt.

Der beobachtete MIME-kodierte Personenname in einer alten Lage bleibt ein offener Qualitätsfehler. Die normale aktuelle Mailaufnahme decodiert Header bereits; ältere Beteiligtenmetadaten und wortgetreue klassifizierte Quelltextspannen müssen vor einer Reparatur auseinandergehalten werden. Keine Personenverschmelzung allein durch gleiche Anzeigenamen und keine Veränderung der Originalzitate.

Alltags-/Akkuabnahme, vollständige persönliche Quellenabdeckung, ressourcenschonende produktive Modellwahl und die offenen Regelanwendungs-/Relevanzfragen sind weiterhin erforderlich. Kein perfektes oder fertiges Gesamtprodukt wird aus diesen begrenzten Tests abgeleitet.
