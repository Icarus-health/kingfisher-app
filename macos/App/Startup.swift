import Foundation
import Security

// Der Start: Docker finden und starten, Schlüssel bereitstellen, Kingfisher laden und starten, warten.
// Läuft auf einer Hintergrund-Warteschlange; `say` meldet den Satz für die Ansicht.

enum StartOutcome {
    case ready(ollamaMissing: Bool)
    case dockerMissing
    case dockerSilent
    case composeMissing
    /// Es gibt Kingfisher-Daten, aber keinen Schlüssel dazu. Der Mensch muss die Datei zeigen.
    case keysMissing
    case failed(String)
}

final class Startup {
    let paths: AppPaths
    private var store: EnvStore { EnvStore(file: paths.envFile) }

    init(paths: AppPaths) { self.paths = paths }

    func run(say: (String) -> Void) -> StartOutcome {
        guard let docker = Docker.find() else { return .dockerMissing }
        if !docker.isRunning() {
            say(Satz.dockerStartet)
            guard docker.start() else { return .dockerSilent }
        }
        guard docker.hasCompose() else { return .composeMissing }

        let env: EnvFile
        switch provideKeys(docker) {
        case .ready(let found): env = found
        case .missing: return .keysMissing
        case .unwritable: return .failed(Satz.schluesselNichtGespeichert)
        }

        if !(env.value(EnvKey.image) ?? "").isEmpty {
            // Später: Läuft Kingfisher schon, gibt es nichts zu tun; sonst starten (lädt nur, was fehlt).
            if !Loopback.healthy() {
                say(Satz.starten)
                guard docker.compose(["up", "-d"], paths: paths, timeout: 1800).ok else {
                    return .failed(Satz.startGescheitert)
                }
            }
        } else {
            // Erster Start: welches Bild, laden, dann dauerhaft merken. Auch eine laufende Installation aus der
            // Arbeitskopie wird hier auf das fertige Bild umgestellt – mit denselben Schlüsseln und Daten.
            let image = firstImage(manifest: Loopback.manifest(), appFassung: AppPaths.appFassung)
            say(Satz.laden)
            guard docker.compose(["pull"], paths: paths, image: image, timeout: 3600).ok else {
                return .failed(Satz.ladenGescheitert)
            }
            var updated = env
            updated.set(EnvKey.image, image)
            do { try store.write(updated) } catch { return .failed(Satz.schluesselNichtGespeichert) }
            guard docker.compose(["up", "-d"], paths: paths, timeout: 1800).ok else {
                return .failed(Satz.startGescheitert)
            }
        }
        guard Loopback.waitUntilHealthy() else { return .failed(Satz.nichtErreichbar) }
        let ollamaMissing = !Loopback.ollamaRunning() && !FileManager.default.fileExists(atPath: "/Applications/Ollama.app")
        return .ready(ollamaMissing: ollamaMissing)
    }

    // MARK: Schlüssel

    enum Keys {
        case ready(EnvFile)
        case missing
        case unwritable
    }

    /// Token und Passphrase: vorhandene Datei der App, sonst die einer Installation aus der Arbeitskopie,
    /// sonst neu – aber nur, wenn es noch keine Kingfisher-Daten gibt. Sonst wären die Schlüssel im Datenvolume
    /// nicht mehr lesbar.
    func provideKeys(_ docker: Docker) -> Keys {
        if let existing = store.read(), existing.hasKeys { return .ready(existing) }
        let adopted: EnvFile?
        if let container = docker.projectContainer() {
            adopted = starterFile(labels: docker.labels(of: container))
                ?? Installation.keys(fromContainerEnvironment: docker.environment(of: container))
        } else {
            adopted = nil
        }
        if let adopted = adopted { return save(adopted) }
        if docker.volumeExists(Installation.dataVolume) { return .missing }
        guard let token = randomHex(), let passphrase = randomHex() else { return .unwritable }
        return save(EnvFile.generated(token: token, passphrase: passphrase))
    }

    /// Übernimmt eine Datei, die der Mensch ausgewählt hat. false, wenn darin keine Schlüssel stehen.
    func adopt(fileAt url: URL) -> Bool {
        guard let chosen = EnvStore(file: url).read(), chosen.hasKeys else { return false }
        if case .ready = save(EnvFile.adopted(chosen, from: url.path)) { return true }
        return false
    }

    private func starterFile(labels: [String: String]) -> EnvFile? {
        for path in Installation.envCandidates(labels: labels) {
            if let file = EnvStore(file: URL(fileURLWithPath: path)).read(), file.hasKeys {
                return EnvFile.adopted(file, from: path)
            }
        }
        return nil
    }

    private func save(_ env: EnvFile) -> Keys {
        do {
            try store.write(env)
            return .ready(env)
        } catch {
            return .unwritable
        }
    }

    /// 32 Zufallsbytes als Hex, wie `secrets.token_hex(32)` im Starter.
    private func randomHex() -> String? {
        var bytes = [UInt8](repeating: 0, count: 32)
        guard SecRandomCopyBytes(kSecRandomDefault, bytes.count, &bytes) == errSecSuccess else { return nil }
        return hexString(bytes)
    }
}
