# Host-Auswahl des Docker-Images bei der Sicherung

## Konkreter Fehler

Die private Host-Konfiguration enthält `KINGFISHER_IMAGE`. Compose verwendet diesen Wert für die Bildauswahl; die Container-Umgebung enthält ihn üblicherweise nicht. Der Host-Helfer `create_recovery_bundle.py` verglich jedoch alle Host-Werte mit `Config.Env` und lehnte dadurch eine passende native Installation ab. Lesend am laufenden persönlichen Bestand reproduziert: alter Validator lehnt ab, korrigierter Validator akzeptiert. Keine Geheimnisse oder Konfigurationswerte ausgegeben, kein Container angehalten.

## Änderung

Nur `KINGFISHER_IMAGE` wird mit dem ausdrücklich inspizierten `Config.Image` verglichen; die unveränderliche `Image`-ID bleibt das im Archiv gebundene und für den Sicherungsworker verwendete Bild. Alle anderen Werte einschließlich beider erforderlichen Geheimnisse werden weiterhin exakt geprüft. Ein fehlender, leerer oder abweichender Bildnachweis wird vor Stoppen oder Archivierung zurückgewiesen. Ein gefälschter gleichnamiger Container-Env-Wert ersetzt diesen Nachweis nicht.

## Prüfungen und Grenze

Sechs neue Regressionfälle: passende Host-Auswahl bei laufender/gestoppter Instanz, fehlendes/leeres/falsches Bild trotz gleichnamigem Env-Wert und falsches Geheimnis bei richtigem Bild. Vor Änderung scheitern fünf Fälle, zwölf bestehen. Danach bestehen alle **31 betroffenen Tests** für Starter, verschlüsseltes Archiv, vollständigen Datenbestand und Recovery-Jobs; vorhandener Starlette/httpx-Hinweis. Unabhängiger Diff-Review ohne konkreten Blocker.

Der separate Host-Helfer ist weder im nativen DMG noch im gekoppelten Backend-Image enthalten. Das bereits geprüfte Paket `1.0.6-preview.6979131` bleibt unverändert; dessen vollständige Backend-Prüfung wird nicht auf einen neuen Image-Build umgedeutet. Der Fix ist im Repository verfügbar und prüft die reale Konfiguration lesend. Erstellung eines neuen persönlichen verschlüsselten Recovery-Archivs über die App-Oberfläche ist damit noch nicht live bewiesen. Persönliche Installation und echte Bedienprüfung warten weiterhin auf den entsperrten Mac. Kein Import gestartet, kein Modell oder Cloudanbieter aktiviert.
