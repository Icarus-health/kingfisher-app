import Foundation

// Führt ein Update aus, das die Oberfläche über die Brücke angefragt hat. Die Reihenfolge und was nach
// einem Fehler folgt, entscheidet UpdateMachine (Logic/UpdateFlow.swift); hier steht nur, was ein Schritt tut.
// Läuft auf einer Hintergrund-Warteschlange.

enum UpdateResult {
    case updated
    case notStarted(oldFassung: String?)
    case rolledBack(oldFassung: String?)
    case broken
}

final class Updater {
    let paths: AppPaths
    private var store: EnvStore { EnvStore(file: paths.envFile) }

    init(paths: AppPaths) { self.paths = paths }

    /// `say` bekommt den Satz zum aktuellen Schritt.
    func perform(_ request: UpdateRequest, say: (String) -> Void) -> UpdateResult {
        guard let docker = Docker.find(), let original = store.read(), let token = original.value(EnvKey.token) else {
            return .notStarted(oldFassung: nil)
        }
        let oldFassung = original.value(EnvKey.image).flatMap(ImageName.fassung(of:))
        var machine = UpdateMachine()
        while case .running(let step) = machine.phase {
            say(Satz.schritt(step))
            machine.report(success: execute(step, request: request, original: original, token: token, docker: docker))
        }
        if machine.phase == .rollingBack {
            say(Satz.zurueckRollen)
            machine.report(success: rollBack(to: original, docker: docker))
        }
        switch machine.phase {
        case .finished: return .updated
        case .notStarted: return .notStarted(oldFassung: oldFassung)
        case .rolledBack: return .rolledBack(oldFassung: oldFassung)
        default: return .broken
        }
    }

    private func execute(_ step: UpdateStep, request: UpdateRequest, original: EnvFile, token: String,
                         docker: Docker) -> Bool {
        switch step {
        case .backup:
            return Loopback.backup(token: token)
        case .pull:
            return docker.compose(["pull"], paths: paths, image: request.image, timeout: 3600).ok
        case .switchImage:
            var updated = original
            guard updated.set(EnvKey.image, request.image) else { return false }
            return (try? store.write(updated)) != nil
        case .restart:
            return docker.compose(["up", "-d"], paths: paths, timeout: 1800).ok
        case .waitForHealth:
            return Loopback.waitUntilHealthy()
        }
    }

    /// Die alte Env-Datei zurück und die alte Fassung wieder starten.
    private func rollBack(to original: EnvFile, docker: Docker) -> Bool {
        guard (try? store.write(original)) != nil else { return false }
        return docker.compose(["up", "-d"], paths: paths, timeout: 1800).ok && Loopback.waitUntilHealthy()
    }
}
