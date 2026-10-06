import Foundation

// Prüfprogramm für die reine Logik der Mac-App (macos/App/Logic). Läuft überall, wo swiftc da ist, auch
// unter Linux:
//
//   swiftc macos/App/Logic/*.swift macos/tests/main.swift -o /tmp/kingfisher-logic && /tmp/kingfisher-logic
//
// Ausgeführt von macos/test_mac_app_logic.py und in .github/workflows/mac-app.yml. Jede Abweichung beendet
// das Programm mit einem Fehler und nennt die Stelle.

var failures = 0

func expect(_ condition: Bool, _ what: String, line: Int = #line) {
    if !condition {
        failures += 1
        print("FEHLER Zeile \(line): \(what)")
    }
}

// MARK: Env-Datei

do {
    var env = EnvFile(text: "# Kommentar\nICARUS_SIDECAR_TOKEN=abc\nICARUS_SECRETS_PASSPHRASE=\"def\"\nANDERES=1\n")
    expect(env.value(EnvKey.token) == "abc", "Token lesen")
    expect(env.value(EnvKey.passphrase) == "def", "Anführungszeichen um den Wert werden entfernt")
    expect(env.hasKeys, "beide Schlüssel vorhanden")
    expect(env.value(EnvKey.image) == nil, "kein Bild gesetzt")
    expect(env.set(EnvKey.image, "ghcr.io/icarus-health/kingfisher-app:1.0.0"), "Bild setzen")
    expect(env.text.hasSuffix("KINGFISHER_IMAGE=ghcr.io/icarus-health/kingfisher-app:1.0.0\n"), "neue Zeile am Ende")
    expect(env.text.hasPrefix("# Kommentar\nICARUS_SIDECAR_TOKEN=abc\n"), "fremde Zeilen bleiben erhalten")
    expect(env.set(EnvKey.image, "ghcr.io/icarus-health/kingfisher-app:1.0.1"), "Bild ersetzen")
    expect(env.text.components(separatedBy: "KINGFISHER_IMAGE=").count == 2, "Bild steht genau einmal da")
    expect(env.value(EnvKey.image) == "ghcr.io/icarus-health/kingfisher-app:1.0.1", "ersetzter Wert gilt")
    expect(!env.set(EnvKey.image, "x\nICARUS_SIDECAR_TOKEN=boese"), "Zeilenumbruch im Wert wird abgewiesen")
    expect(env.value(EnvKey.token) == "abc", "abgewiesener Wert ändert nichts")

    let doppelt = EnvFile(text: "ICARUS_SIDECAR_TOKEN=alt\nICARUS_SIDECAR_TOKEN=neu\n")
    expect(doppelt.value(EnvKey.token) == "neu", "die letzte Zeile gilt wie bei Compose")
    expect(!EnvFile(text: "ICARUS_SIDECAR_TOKEN=\nICARUS_SECRETS_PASSPHRASE=x\n").hasKeys, "leerer Token zählt nicht")
    expect(EnvFile(text: "export ICARUS_SIDECAR_TOKEN=t\n").value(EnvKey.token) == "t", "export-Präfix")
    expect(EnvFile(text: "ICARUS_SIDECAR_TOKEN_ALT=x\n").value(EnvKey.token) == nil, "nur der genaue Name")

    let neu = EnvFile.generated(token: hexString([0, 1, 254, 255]), passphrase: "p")
    expect(neu.value(EnvKey.token) == "0001feff", "Hex wie secrets.token_hex")
    expect(neu.hasKeys, "erzeugte Datei hat beide Schlüssel")
    let uebernommen = EnvFile.adopted(env, from: "/Users/x/Kingfisher/.kingfisher.env")
    expect(uebernommen.value(EnvKey.token) == "abc" && uebernommen.value("ANDERES") == "1", "Übernahme vollständig")
    expect(uebernommen.text.hasPrefix("# Von der Kingfisher-App übernommen aus /Users/x/Kingfisher/.kingfisher.env\n"),
           "Übernahme vermerkt die Herkunft")
}

// MARK: Env-Datei auf der Platte

do {
    let folder = URL(fileURLWithPath: NSTemporaryDirectory()).appendingPathComponent("kf-logic-\(UUID().uuidString)")
    defer { try? FileManager.default.removeItem(at: folder) }
    let store = EnvStore(file: folder.appendingPathComponent("Kingfisher/kingfisher.env"))
    expect(store.read() == nil, "fehlende Datei ergibt nil")
    let env = EnvFile.generated(token: "t", passphrase: "p")
    try store.write(env)
    expect(store.read() == env, "geschriebene Datei liest sich gleich")
    let fileMode = (try FileManager.default.attributesOfItem(atPath: store.file.path)[.posixPermissions] as? NSNumber)?.intValue
    let folderMode = (try FileManager.default.attributesOfItem(atPath: store.file.deletingLastPathComponent().path)[.posixPermissions] as? NSNumber)?.intValue
    expect(fileMode == 0o600, "Datei nur für den Benutzer (0600), ist \(String(fileMode ?? -1, radix: 8))")
    expect(folderMode == 0o700, "Ordner nur für den Benutzer (0700), ist \(String(folderMode ?? -1, radix: 8))")
    var updated = env
    updated.set(EnvKey.image, "ghcr.io/icarus-health/kingfisher-app:1.0.1")
    try store.write(updated)
    expect(store.read() == updated, "vorhandene Datei atomar ersetzen, Schlüssel erhalten")
    let replacedMode = (try FileManager.default.attributesOfItem(atPath: store.file.path)[.posixPermissions] as? NSNumber)?.intValue
    expect(replacedMode == 0o600, "ersetzte Datei bleibt privat (0600)")
} catch {
    expect(false, "Env-Datei schreiben: \(error)")
}

// MARK: Fassungen

do {
    let geordnet = ["0.9.9", "1.0.0-alpha", "1.0.0-alpha.1", "1.0.0-alpha.beta", "1.0.0-beta", "1.0.0-beta.2",
                    "1.0.0-beta.11", "1.0.0-rc.1", "1.0.0", "1.0.1", "1.2.0", "1.10.0", "2.0.0"]
    let fassungen = geordnet.compactMap(SemVer.init)
    expect(fassungen.count == geordnet.count, "alle Beispielfassungen gültig")
    for (a, b) in zip(fassungen, fassungen.dropFirst()) { expect(a < b, "\(a) < \(b)") }
    expect(SemVer("1.0.0") == SemVer("1.0.0"), "Gleichheit")
    expect(SemVer("1.2.3")?.description == "1.2.3", "Text")
    for ungueltig in ["", "1", "1.0", "1.0.0.0", "01.0.0", "1.0.0+build", "1.0.0-", "1.0.0-01", "v1.0.0",
                      "1.0.0-a..b", "1.0.0-ä", " 1.0.0", "1.-1.0", "١.0.0"] {
        expect(SemVer(ungueltig) == nil, "„\(ungueltig)“ ist keine Fassung")
    }
}

// MARK: Bildnamen

do {
    expect(ImageName.isValid("ghcr.io/icarus-health/kingfisher-app:1.0.1", fassung: "1.0.1"), "eigenes Bild")
    expect(!ImageName.isValid("ghcr.io/icarus-health/kingfisher-app:1.0.2", fassung: "1.0.1"), "Tag passt nicht")
    expect(!ImageName.isValid("ghcr.io/boese/kingfisher:1.0.1", fassung: "1.0.1"), "fremdes Bild")
    expect(!ImageName.isValid("ghcr.io/icarus-health/kingfisher-x:1.0.1", fassung: "1.0.1"), "ähnlicher Name")
    expect(!ImageName.isValid("ghcr.io/icarus-health/kingfisher-app:latest", fassung: "latest"), "kein fester Tag")
    expect(!ImageName.isValid("ghcr.io/icarus-health/kingfisher-app:1.0.1@sha256:00", fassung: "1.0.1@sha256:00"), "keine Prüfsumme")
    expect(!ImageName.isValid("evil.io/x ghcr.io/icarus-health/kingfisher-app:1.0.1", fassung: "1.0.1"), "Präfix am Anfang")
    expect(ImageName.fassung(of: "ghcr.io/icarus-health/kingfisher-app:1.0.0") == "1.0.0", "Fassung aus dem Bild")
    expect(ImageName.fassung(of: "kingfisher:local") == nil, "lokales Bild hat keine Fassung")
}

// MARK: Manifest und erstes Bild

do {
    let json = Data(#"{"fassung":"1.2.0","datum":"2026-10-02","image":"ghcr.io/icarus-health/kingfisher-app:1.2.0","dmg":"x","hinweise":["a"],"app_mindestens":"1.1.0"}"#.utf8)
    let manifest = Manifest.decode(json)
    expect(manifest?.fassung == "1.2.0" && manifest?.appMindestens == "1.1.0", "Manifest lesen")
    expect(firstImage(manifest: manifest, appFassung: "1.1.0") == "ghcr.io/icarus-health/kingfisher-app:1.2.0", "neu genug")
    expect(firstImage(manifest: manifest, appFassung: "1.0.0") == "ghcr.io/icarus-health/kingfisher-app:1.0.0", "App zu alt")
    expect(firstImage(manifest: nil, appFassung: "1.0.0") == "ghcr.io/icarus-health/kingfisher-app:1.0.0", "ohne Manifest")
    let fremd = Manifest.decode(Data(#"{"fassung":"1.2.0","image":"ghcr.io/boese/kingfisher:1.2.0"}"#.utf8))
    expect(firstImage(manifest: fremd, appFassung: "1.0.0") == "ghcr.io/icarus-health/kingfisher-app:1.0.0", "fremdes Bild abgewiesen")
    let ohneMindest = Manifest.decode(Data(#"{"fassung":"1.2.0","image":"ghcr.io/icarus-health/kingfisher-app:1.2.0"}"#.utf8))
    expect(firstImage(manifest: ohneMindest, appFassung: "1.0.0") == "ghcr.io/icarus-health/kingfisher-app:1.2.0", "ohne Mindestfassung")
    expect(Manifest.decode(Data("kaputt".utf8)) == nil, "kaputtes Manifest")
    expect(Manifest.url.absoluteString == "https://icarus-health.github.io/kingfisher-app/latest.json", "Adresse des Manifests")
}

// MARK: Brücke

do {
    let gut: [String: Any] = ["aktion": "aktualisieren", "fassung": "1.0.1", "image": "ghcr.io/icarus-health/kingfisher-app:1.0.1"]
    let anfrage = UpdateRequest(message: gut)
    expect(anfrage?.fassung == "1.0.1" && anfrage?.image == "ghcr.io/icarus-health/kingfisher-app:1.0.1", "gültige Anfrage")
    var andere = gut; andere["aktion"] = "loeschen"
    expect(UpdateRequest(message: andere) == nil, "andere Aktion wird ignoriert")
    var falschesBild = gut; falschesBild["image"] = "ghcr.io/icarus-health/kingfisher-app:9.9.9"
    expect(UpdateRequest(message: falschesBild) == nil, "Tag muss zur Fassung passen")
    var ohneFassung = gut; ohneFassung.removeValue(forKey: "fassung")
    expect(UpdateRequest(message: ohneFassung) == nil, "unvollständige Anfrage")
    expect(UpdateRequest(message: "aktualisieren") == nil, "kein Objekt")
    expect(UpdateRequest.bridgeName == "kingfisher" && UpdateRequest.action == "aktualisieren", "Namen der Schnittstelle")
}

// MARK: Zustandsfolge des Updates

func ablauf(_ ergebnisse: [Bool]) -> (schritte: [String], ende: UpdatePhase) {
    var machine = UpdateMachine()
    var schritte: [String] = []
    var rest = ergebnisse[...]
    while !machine.phase.isOver, let ok = rest.popFirst() {
        if case .running(let step) = machine.phase { schritte.append(step.rawValue) } else { schritte.append("zurueck") }
        machine.report(success: ok)
    }
    return (schritte, machine.phase)
}

do {
    let alles = ablauf([true, true, true, true, true])
    expect(alles.schritte == ["backup", "pull", "switchImage", "restart", "waitForHealth"], "Reihenfolge \(alles.schritte)")
    expect(alles.ende == .finished, "fertig")
    let keineSicherung = ablauf([false])
    expect(keineSicherung.ende == .notStarted && keineSicherung.schritte == ["backup"], "ohne Sicherung nichts weiter")
    let ladenScheitert = ablauf([true, false])
    expect(ladenScheitert.schritte == ["backup", "pull"], "beim Laden kein Rückfall \(ladenScheitert.schritte)")
    expect(ladenScheitert.ende == .notStarted, "altes Bild bleibt beim Ladefehler unberührt")
    expect(ablauf([true, true, false]).ende == .notStarted, "Schreibfehler lässt den Container unberührt")
    let startScheitert = ablauf([true, true, true, true, false, false])
    expect(startScheitert.ende == .broken, "auch der Rückweg scheitert")
    for fehler in 3...4 {
        let ergebnisse = Array(repeating: true, count: fehler) + [false, true]
        expect(ablauf(ergebnisse).ende == .rolledBack, "Fehler in Schritt \(fehler + 1) führt zurück")
    }
    var fertig = UpdateMachine()
    for _ in 0..<5 { fertig.report(success: true) }
    fertig.report(success: false)
    expect(fertig.phase == .finished, "nach dem Ende ändert nichts mehr den Zustand")
}

// MARK: Name der Offline-Sicherung
do {
    expect(UpdateSnapshotName.isValid("vor-update-20261006T120000Z"), "gültiger Snapshotname")
    for unsafe in ["../vor-update-20261006T120000Z", "vor-update-20261006T120000Z/extra",
                   "vor-update-20261306T120000Z", "vor-update-latest", "vor-update-20261006T120000Z\n"] {
        expect(!UpdateSnapshotName.isValid(unsafe), "unsicherer Snapshotname abgewiesen")
    }
}

// MARK: Vorhandene Installation

do {
    let labels = [Installation.workingDirLabel: "/Users/x/Kingfisher",
                  Installation.envFileLabel: "/Users/x/Kingfisher/.kingfisher.env,anders.env"]
    expect(Installation.envCandidates(labels: labels) == ["/Users/x/Kingfisher/.kingfisher.env", "/Users/x/Kingfisher/anders.env"],
           "Kandidaten aus Compose-Labels: \(Installation.envCandidates(labels: labels))")
    expect(Installation.envCandidates(labels: [:]).isEmpty, "ohne Labels wird nichts geraten")
    expect(Installation.envCandidates(labels: [Installation.envFileLabel: "relativ.env"]).isEmpty,
           "relativer Pfad ohne Arbeitsordner wird nicht geraten")
    let aus = Installation.keys(fromContainerEnvironment: ["PATH=/usr/bin", "ICARUS_SIDECAR_TOKEN=t=1", "ICARUS_SECRETS_PASSPHRASE=p"])
    expect(aus?.value(EnvKey.token) == "t=1" && aus?.value(EnvKey.passphrase) == "p", "Schlüssel aus dem Container")
    expect(Installation.keys(fromContainerEnvironment: ["ICARUS_SIDECAR_TOKEN=t"]) == nil, "ohne Passphrase nichts")
    expect(Installation.keys(fromContainerEnvironment: ["ICARUS_SIDECAR_TOKEN=", "ICARUS_SECRETS_PASSPHRASE=p"]) == nil,
           "leerer Token zählt nicht")
    expect(Installation.project == "kingfisher" && Installation.dataVolume == "kingfisher_kingfisher-data", "Projekt und Volume")
}

// MARK: Sätze

do {
    expect(Satz.updateGescheitert(alteFassung: "1.0.0") ==
           "Das Update hat nicht geklappt. Der gesicherte Stand ist mit dem bisherigen Bild im Prüfmodus geöffnet. Prüfe die historischen Daten; frühere Freigaben sind ausgeschaltet.",
           "Satz nach gescheitertem Update")
    expect(Satz.laden == "Kingfisher wird geladen. Beim ersten Mal dauert das einige Minuten.", "Satz beim Laden")
    for step in UpdateStep.allCases { expect(!Satz.schritt(step).isEmpty, "Satz für \(step)") }
}

if failures > 0 {
    print("\(failures) Prüfung(en) fehlgeschlagen")
    exit(1)
}
print("Logik der Mac-App: alle Prüfungen bestanden")
