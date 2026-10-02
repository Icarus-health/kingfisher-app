## Nutzen und Produktpaket

Paket aus [PRODUCT-PLAN.md](../docs/release/PRODUCT-PLAN.md): K…

Welcher konkrete Ablauf funktioniert anschließend für den Nutzer?

## Grundlage und Abhängigkeiten

- Icarus-Funktionsvertrag:
- Kingfisher-Screen / genehmigter Zustand (bei sichtbaren Änderungen):
- Vorherige PRs / noch nicht abgeglichener PC-Stand:

## Änderung und resultierendes Verhalten

Was wird übernommen, ergänzt oder korrigiert? Welche Teile des Pakets bleiben offen?

## Nachweis

Nur tatsächlich bestandene Prüfungen markieren; CI-Link und geprüften Commit nennen.

- [ ] Relevante Backend-Verträge und Regression bestanden
- [ ] Build und Asset-Vertrag bestanden (wenn betroffen)
- [ ] Echter Nutzungsablauf im gebauten Container bestanden (wenn betroffen)
- [ ] Wiederanlauf/Persistenz und Migration geprüft (wenn betroffen)
- [ ] Browserinteraktion, Konsole und Screenshots geprüft (bei UI-Änderungen)
- [ ] Referenzvergleich ohne ungeklärte sichtbare Abweichung (bei UI-Änderungen)

Nicht zutreffende Punkte begründen. Testmodell/Fixtures ausdrücklich von realer Modell-/Quellenabnahme unterscheiden.

## Migration und verbleibende Abnahme

Datenänderung, Rückkehrweg, ungeprüfte Zustände, offene Designentscheidungen und nächster Schritt:
