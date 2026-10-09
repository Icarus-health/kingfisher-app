# Mail-Aufgaben-Quellenbindung – finales enges Review

## Ergebnis

Kein Blocker im geprüften Patch. Manuelle Mail-Aufgaben müssen jetzt den Digest der geöffneten Mailfassung mitsenden. Die UI verweigert lokal fehlende oder nicht mehr passende Digest-Werte und erhält dabei die Formularangaben; der Server weist fehlende Werte sowie geänderte Mailfassungen vor Quellenaufnahme und Aufgabenwrite mit 409 zurück. Der serverseitige Quellvergleich verhindert damit auch den Fall, in dem sich die Mail nach dem Öffnen geändert hat.

## Digest-Erweiterung und Idempotenz

Der Digest umfasst jetzt zusätzlich `date.isoformat()` (oder `None`) und `truncated`. So lösen eine reine Änderung des Quellenzeitpunkts oder des Vollständigkeitsstatus eine Aktualitätsablehnung aus. Der Quick-Accept-Idempotenzschlüssel wird weiterhin aus der alten veröffentlichten sechs Felder umfassenden Digest-Formel plus UID/Titel/Zitat abgeleitet. Im Serverpfad wird dieser stabile Schlüssel erst nach Prüfung des neuen vollständigen Digests und der aktuellen Quick-Accept-Zeitlage verwendet. Der Kompatibilitätstest mit vorbestehender Aufgabe unter altem Schlüssel verhindert eine Dublette.

## Geprüfte Regressionen

- Backend: `pytest tests/test_mail_conversation_flow.py -k 'mail_task or manual_mail_task or quick_mail_task'` – **8 passed, 35 deselected**. Enthält fehlenden/null Digest ohne Writes, veralteten Digest, gültigen manuellen Save ohne Modellzitat, Datum-/Truncated-Änderungen und alte Schlüsselkompatibilität.
- UI: `node --test tests/mail-task-source-binding.test.mjs` – **3 passed**. Das Harness kompiliert den echten TSX-Handler und führt ihn mit isoliertem Hookzustand/API-Aufzeichnung aus; es ist keine Browser-/Renderabnahme.

## Grenzen

Read-only Diffreview; keine Produktdateien geändert. Keine Live-Mail, kein Modell und keine volle Testsuite verwendet. Die UI-Prüfung ist ein Handler-Harness, keine Browserabnahme.
