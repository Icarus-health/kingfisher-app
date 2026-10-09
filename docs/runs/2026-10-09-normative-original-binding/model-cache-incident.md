# Modellcache-Vorfall und Wiederherstellung

Der neue echte Gesamtlauf absolvierte 19 Aufnahme-/Einordnungs-/Themenjobs, scheiterte aber vor Index und Fragen: drei BGE-M3-Blobs fehlen. Es gibt keine neue Antwortqualitätsmessung aus diesem Lauf.

Die Ursache liegt in unserem vorherigen Testaufbau, nicht in einem nachgewiesenen Produktfehler. `phase-real-verifier-20261009/run_native.py` kopierte nur das Qwen-Manifest, verwendete aber `models/blobs` als schreibbaren Symlink auf den nativen Modellcache. Das Ollama-Startlog vom 9. Oktober 01:36:55 nennt `OLLAMA_NOPRUNE:false`, sieben vorhandene Blobs und drei automatisch entfernte ungenutzte Blobs. Genau die drei im unveränderten BGE-Manifest referenzierten Assets fehlen anschließend. Das ist eine unzulässige Nebenwirkung unseres Diagnoseaufbaus. Die persönlichen Kingfisher-Originaldaten sind davon getrennt und werden vor/nach Update vollständig geprüft.

BGE-Manifest SHA256: `7907646426070047a77226ac3e684fbbe8410524f7b4a74d02837e43f2146bab`.

- Konfiguration `0c4c9c2a325fb1cdafec606e6809cb745f1cb26a6d919994400d27372303e276`, 337 Bytes.
- Modell `daec91ffb5dd0c27411bd71f29932917c49cf529a641d0168496c3a501e3062c`, 1.157.671.200 Bytes.
- Lizenz `a406579cd136771c705c521db86ca7d60a6f3de7c9b5460e6193a2df27861bde`, 1.068 Bytes.

Eine reine lesende Suche fand keinen vollständigen eigenen lokalen Ersatzcache. Fremde Javis-Modelle/Volumes wurden nicht verwendet. Der vorbereitete exakte Wiederherstellungsdownload wurde von der automatischen Freigabeprüfung mangels konkreter Nutzerzustimmung abgelehnt; der abgelehnte Aufruf startete keinen Download. Dies beschreibt den damaligen abgelehnten Zustand. Nach ausdrücklicher Zustimmung am 9. Oktober wurden alle drei Originaldateien aus der offiziellen Registry wiederhergestellt und ihre Größen/SHA geprüft; Manifest unverändert. [Wiederherstellung und zwei abgeschlossene Gesamtläufe](../2026-10-09-restored-memory-and-today/README.md). Kein Modellwechsel, keine privaten Datenübertragung und kein produktiver Modellstart.

Künftige eigene Modelltests verwenden echte isolierte Kopien/Dateiklone der erforderlichen Blobs, keine Symlinks oder Hardlinks zum Modellcache. Zusätzlich `OLLAMA_NOPRUNE=1`, vollständige Existenz-/SHA-Prüfung vor Serverstart, Prüfung des ursprünglichen Caches vorher/nachher, eigener Port, Cloud aus und sicheres Beenden. Die historischen Runner bleiben unveränderte Belege des Vorfalls und dürfen nicht erneut ausgeführt werden.

Referenz für den NOPRUNE-Schalter: [Ollama envconfig](https://github.com/ollama/ollama/blob/main/envconfig/config.go).
