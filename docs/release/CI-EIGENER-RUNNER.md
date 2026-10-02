# CI auf dem eigenen Mac

Die GitHub-Prüfungen (`ci.yml`) laufen standardmäßig auf GitHub-Rechnern und
verbrauchen dafür Actions-Minuten. Ist das Kontingent leer, startet kein Job,
und jeder Pull Request zeigt rote Prüfungen ohne Protokoll. Dann laufen die
Prüfungen stattdessen auf dem eigenen Mac. Das kostet keine Minuten.

Das Repository ist privat. Nur deshalb ist ein eigener Runner vertretbar: Er
führt den Code aus, der in einem Pull Request steht. In einem öffentlichen
Repository könnte das jeder Fremde auslösen.

## Einrichten (einmalig, etwa zehn Minuten)

1. **Voraussetzungen auf dem Mac:** Xcode-Kommandozeilenwerkzeuge
   (`xcode-select --install`). Python, Node und Rust holen sich die Jobs selbst.
2. **Runner anlegen:** Auf GitHub im Repository *Settings → Actions → Runners →
   New self-hosted runner* wählen, dann *macOS* und *ARM64*. GitHub zeigt dort
   fünf Befehle zum Kopieren. In einem eigenen Ordner ausführen, etwa
   `~/actions-runner`. Die Rückfrage nach Labels mit Enter bestätigen.
3. **Als Dienst starten**, damit der Runner nach einem Neustart weiterläuft:
   `./svc.sh install && ./svc.sh start` im Runner-Ordner.
4. **Umschalten:** Auf GitHub unter *Settings → Secrets and variables → Actions →
   Variables* die Variable `KINGFISHER_RUNNER` mit dem Wert `self-hosted` anlegen.

Ab dem nächsten Push laufen Sidecar, Desktop-App und Oberfläche auf dem Mac.
Unter *Actions* sieht man jeden Lauf wie bisher.

## Zurück zu den GitHub-Rechnern

Die Variable `KINGFISHER_RUNNER` löschen. Der Runner selbst kann bleiben; er
bekommt dann keine Jobs mehr. Entfernen mit `./svc.sh uninstall` und dem
Befehl, den GitHub unter *Runners → Remove* anzeigt.

## Was dabei anders ist

- Die Jobs laufen nacheinander, nicht parallel. Ein Durchlauf dauert daher
  länger, auf einem aktuellen Mac etwa 15 bis 25 Minuten.
- Der Container-Workflow (`container.yml`) bleibt auf GitHub-Rechnern. Er baut
  ein Linux-Image für zwei Architekturen, das gehört nicht auf den Arbeitsrechner.
  Ohne Minuten bleibt diese eine Prüfung rot.
- Der Mac muss eingeschaltet sein. Sonst warten die Jobs, bis er wieder da ist.

## Ohne GitHub prüfen

`make ci-lokal` führt dieselben Schritte direkt aus, ohne GitHub und ohne
Runner (`scripts/ci_lokal.sh`, kommt mit PR #71).
