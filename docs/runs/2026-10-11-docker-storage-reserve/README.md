# Docker-Speicherreserve nach persönlichem Update

11. Oktober 2026. Installierter Code/Backend unverändert `1.0.6-preview.bc21155`; nur lokale Betriebsbereinigung, kein neues App-Paket, keine Modell-/Cloudaktivierung und keine CI-Wiederholung.

## Tatsächlicher Befund und Abbau

Die vorherige [Installation](../2026-10-11-local-connection-package/README.md) hatte den alten Dienst aus einem vollen Docker-Dateisystem wiederhergestellt, danach aber nur etwa 90 MiB Reserve. Erste gezielte Archivierung von sechs unbenutzten eigenen Test-Builds mit zwölf Alias-Tags bestand. OCI-Manifeste, alle Blob-Prüfsummen und komprimierte Lesbarkeit bestätigt; dann ausschließlich diese Tags entfernt. Freie Bytes vorher/nachher identisch: 96.178.176. Das war ein geprüftes Archiv, **keine erfolgreiche Kapazitätsfreigabe**. Die Dateischichten blieben über andere Images/Zwischenstände gebunden.

Die anschließende lesende Graphinventur erfasste 2491 Image-Einträge einschließlich der Legacy-Build-Zwischenstände. Aus elf exakt bekannten eigenen früheren Kingfisher-Builds wurden 178 exklusiv unbenutzte Knoten abgeleitet: zehn getaggte Builds und 168 Zwischenstände. Der elfte Ausgangsbuild wurde durch die Schutzmenge ausgeschlossen. Vorfahren sämtlicher anderer getaggter Images und aller Container sowie externer Cache-Kinder bleiben geschützt, einschließlich aktuellem Image und unmittelbarem Rückweg.

Alle 178 OCI-Manifest-IDs und alle bekannten Tags wurden vor dem ersten Entfernen außerhalb Docker exportiert. Archiv geprüft: vollständige Manifest-/Blob-Digests, Tagmenge, Pfade, Membertypen sowie gesamte gzip-Lesbarkeit/CRC. Archivlimit 6 GiB bei mindestens 7 GiB freier Host-Kapazität; tatsächliches Archiv 570.781.309 Bytes, SHA-256 `2e38d8d0d7453fe0d00d9c110f23b4b4600b9f0117beda0fa7089556f0699072`. Lokaler Pfad: `Kingfisher-Pruefpakete/2026-10-11-exclusive-build-cache/exclusive-kingfisher-build-cache.tar.gz`. Rückladung über `docker image load -i exclusive-kingfisher-build-cache.tar.gz`; keine tatsächliche Rückladung in den knappen laufenden Docker-Speicher durchgeführt, daher kein ausgeführter Restore behauptet.

Der Abbau erfolgte Blatt vor Eltern, ohne `--force` und ohne globale Prune-Befehle. Vor jedem Knoten wurden Containeridentitäten/Mounts und Volume-Namen abgeglichen; neue/unbekannte Aliase oder Containerreferenzen stoppen. Nur der konkrete `No such image:`-Fehler gilt als fehlender Knoten. Ein von Docker bereits mit entfernter unbenutzter Parent wurde anschließend als fehlend bestätigt, nicht blind erneut gelöscht. `exclusive-cache-verification.json` bindet alle 178 abschließend fehlenden IDs und die tatsächlich ausgeführten Remove-Referenzen.

**Ergebnis:** freie Docker-Bytes 96.112.640→1.568.862.208 (rund 1,46 GiB). Gleiche Containeridentitäten/Mounts, gleiche Volume-Namen, aktuelles und Rückweg-Image weiter vorhanden, Backend gesund. Vor-/Nach-Abgleich sämtlicher Zeilen der sieben geprüften persönlichen Kerntabellen identisch. Keine Datenvolumes, persönlichen Sicherungen, Modellcache-Dateien oder anderen Container entfernt; keine Sichtung privater Mail-/Termintexte oder neue Inferenz. Das schafft Docker-Reserve, behauptet keine entsprechende Freigabe physischer Mac-SSD-Blöcke.

## Eingebauter Prüfweg und Grenzen

Die tatsächlich installierte Datei `Contents/Resources/update-storage-probe.py` stimmt bytegleich mit dem Repository-Modul überein und wurde im tatsächlichen laufenden Container ausgeführt. Vor- und Nach-Sicherungsregel beide bestanden, einschließlich Byte-/Inode-Reserve. Aktuelle Top-Level-Sicherungsmenge 52.045.993 Bytes/27 Dateien; diese Kapazitätsprobe zählt ausdrücklich nur den bestehenden Top-Level-Updaterweg, nicht alle Dateien der vorherigen vollständigen privaten Sicherung. Sie ersetzt weder vollständiges Backup noch Abnahme eines großvolumigen Imports.

Frisch authentifiziert nach Abbau: Fassung bc21155, große Verarbeitung pausiert, Kalender granted/aktiviert/online, drei ausgewählt, kein Fehler, `memory_allowed:false`. Kein neuer nativer Fensternachweis oder Neustart; Mac war zuletzt gesperrt. Rund 1,5 GB sind keine Freigabe für 122.399 Mails, größere Modellnachladungen oder einen ganzen Arbeitstag. Vor umfangreicher Aufnahme weiter Datenumfang und Kapazität prüfen; Pause beibehalten.

## Enge Validierung

Zwölf künstliche Gegenfälle für Archiv-/Entfernungsschutz bestanden. Weitere Prüfung kombiniert diese Guards mit Graph-/Taglos-Archivfällen: 18 bestandene Fälle, einschließlich gemeinsam genutzter Basis, externem Cache-Kind, verwendetem Branch, falschen IDs, fehlender/veränderter Blobdatei, Traversal, gzip-CRC, unbekanntem Alias und Credential-Environment. Beide Prüfdateien arbeiten ausschließlich mit künstlichen lokalen Archiven und simulierten Image-Metadaten. Kein erneuter Backend-Gesamtlauf ohne Laufzeitcodeänderung.

Unabhängige statische Reviews des Alias- und Graph-/Archivierungs-/Entfernungsablaufs ohne verbleibenden konkreten Blocker. Der anfängliche Reviewer-Einwand zum üblichen Docker-Archivformat wurde anhand des tatsächlich vorhandenen containerd/OCI-Archivs dieses Macs zurückgenommen. Keine universelle Docker-Formatkompatibilität behauptet: bei anderer Layout-/Digestbindung stoppt der Verifier vor Entfernung.

Die beigefügten Skripte dokumentieren exakt diesen festen Plan und sind nicht blind wiederholbare Produkt-Updater. `image-graph-private.json` mit vollständiger lokaler Docker-Inspektion ist **nicht** im Repository; Plan und veröffentlichte Nachweise enthalten nur feste IDs/Tags, Layersummen und Statuswerte, keine Zugangsdaten oder privaten Archiv-/Quelltexte. Beide Image-Archive liegen außerhalb des Repositorys.
