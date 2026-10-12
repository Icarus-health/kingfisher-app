# Aufgaben-Verlauf: geprüftes Paket und persönliche Installation

Laufzeitcode `a5787c88914400151769dae714dfd74c9ea8a0c3`, Version `1.0.6-preview.a5787c8`, 11.10.2026. [Funktions-, Bedien- und Testbelege](../2026-10-11-confirmed-task-followup/README.md) bleiben getrennt von den folgenden Artefakt-/Installationsbelegen.

## Paket

- Festes Git-Archiv SHA `929612b22b951baccdeda89ad9990337f6df600f3f86cf65f3c2ed21c93dc23e`; alle 271 Backend- und 112 UI-Dateien werden im echten Paket byteweise gegen das Host-Manifest geprüft. Nur die Preview-Artefaktversion ersetzt das allgemeine `VERSION=1.0.6` aus dem Archiv. `staging-overrides.json` dokumentiert beide Inhalte/Hashes und den erzeugten Dockerfile; das Originalarchiv bleibt unverändert.
- Lokales Image basiert auf dem tatsächlich zuvor installierten Digest `e2caaa4f…`, ohne Downloads, Netz oder Abhängigkeitsänderung. Neues Image `sha256:24a5528456eff9474d1aa7b6f9f7e710491e6a6a0323829c2cd00e177387d3cf`. Gesamte Python-/UI-Verzeichnisse ersetzt, keine alten Restdateien.
- Reale Paketprobe läuft in einem netzlosen Wegwerfcontainer mit leerem tmpfs. Bestehende Original-/Rücknahme-/Aufgaben-/Projekt-/Health-/Kalender-/Speicher-/Modellrollenprotokolle sowie der neue echte Aufgaben-Übernahmeweg mit transitiver Mail, Neustart und Quellenrücknahme bestanden. Keine produktiven Mounts oder echte Modellinferenz. Der erste Start mit Host-Bindpfad scheiterte vor Laufzeitstart, weil die Docker-VM `/private/tmp` nicht sieht; Rohfehler erhalten. Tatsächlich erfolgreicher stdin-Lauf mit exakten Skript-/Loghashes im Runtime-Proof.
- ARM64-App gebaut, sechs Bundle-Dateien, strenge tiefe Ad-hoc-Signatur geprüft; nicht notarisiert. DMG schreibgeschützt eingehängt, Bundle identisch, wieder ausgehängt. Kanonisch außerhalb Git: `/Users/sorenkube/Documents/Codex/Kingfisher-Pruefpakete/2026-10-11-confirmed-task-a5787c8/Kingfisher.dmg`, SHA `b5716a692ad9f77249a0ab481d876c74072c213c2cb43a7d322b2a193d47ec55`.
- Enger unabhängiger Artefakt-/Installer-Diffreview ohne Installationsblocker. Das Versionsdetail im Archiv wurde dabei benannt und anschließend im separaten Override-Nachweis präzisiert. Reviewer führte keine Tests oder Installation aus. Installationsprüfungen binden alten bfe-Bestand, neue Image-/Manifest-/Runtime-Prüfsummen und separat die 156/13/557 betroffenen Testbelege; der früher dokumentierte breite Basislauf wird nicht als neuer Gesamtlauf ausgegeben.
- Vier Staging- und drei Recovery-Gegenfälle führen die tatsächlichen Installer-AST-Pfade mit künstlichen Dateien aus: exklusives Staging, Fehlerbereinigung, bestätigt fehlender Container, unbekannter Docker-Zustand und Erhalt neuer Daten. Alle bestanden; kein persönlicher App-/Volumezugriff.

## Tatsächliche Installation

App-Dateien und laufendes Backend wurden auf `1.0.6-preview.a5787c8` gewechselt. Zuvor frische kalte Sicherung: 148 Dateien, neun Verzeichnisse, 281322188 Bytes; 17 SQLite-Datenbanken auf Integrität und komplette Wiederherstellung einschließlich Eigentümer/Modus/Zeit/Xattr geprüft. Alte native Contents und ursprüngliche Konfiguration bleiben im geschützten Sicherungsordner. Keine Datenwiederherstellung in den persönlichen Bestand durchgeführt.

Sieben Kerntabellenfingerprints und die Schemas/user_versions aller 17 Datenbanken sind vor/nach dem Wechsel identisch. Persönliches Volume unverändert; ausschließlich Imageauswahl in der Konfiguration angepasst. Signatur und native Dateien entsprechen dem kanonischen DMG. Drei ausgewählte Kalender und `memory_allowed=false` bleiben erhalten; Dienst gesund, große Aufnahme pausiert und Speicher nicht blockiert. Keine Modellrolle geändert, kein Modellstart oder Cloudaufruf.

Der laufende native Prozess wurde nicht neu gestartet, und das persönliche Fenster wurde hier nicht abgenommen. Diese Installation beweist weder persönliche Gedächtnisqualität noch den vollständigen Arbeitstag. `main` und die öffentliche Updatequelle wurden nicht verändert. Der neue UI-/Aufgabenablauf ist synthetisch tatsächlich bedient und bleibt persönlich noch zu prüfen.

Nach erfolgreicher Installation wurde nur ein übernommenes nachgestelltes Leerzeichen im Installer entfernt. `artifact-normalization.json` hält beide Skript-Hashes und die unveränderte ausführbare AST fest; kein weiterer persönlicher Installationslauf.
