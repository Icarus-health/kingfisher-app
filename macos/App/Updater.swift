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
        guard let oldFassung = oldFassung, let previous = docker.runningImage(paths: paths),
              docker.hasAdditionalMounts(paths: paths) == false,
              previous.name == original.value(EnvKey.image),
              Loopback.authenticatedVersion(token: token) == oldFassung,
              let pinnedTag = docker.pin(previous) else {
            return .notStarted(oldFassung: oldFassung)
        }
        var snapshotName: String?
        var machine = UpdateMachine()
        while case .running(let step) = machine.phase {
            say(Satz.schritt(step))
            machine.report(success: execute(step, request: request, original: original, token: token,
                                            docker: docker, snapshotName: &snapshotName))
        }
        if machine.phase == .rollingBack {
            say(Satz.zurueckRollen)
            machine.report(success: snapshotName.map { rollBack(to: original, previous: previous, pinnedTag: pinnedTag,
                                                               snapshotName: $0, token: token, docker: docker) } ?? false)
        }
        switch machine.phase {
        case .finished: return .updated
        case .notStarted: return .notStarted(oldFassung: oldFassung)
        case .rolledBack: return .rolledBack(oldFassung: oldFassung)
        default: return .broken
        }
    }

    private func execute(_ step: UpdateStep, request: UpdateRequest, original: EnvFile, token: String,
                         docker: Docker, snapshotName: inout String?) -> Bool {
        switch step {
        case .backup:
            snapshotName = Loopback.backupName(token: token)
            return snapshotName != nil
        case .pull:
            return docker.compose(["pull"], paths: paths, image: request.image, timeout: 3600).ok
        case .switchImage:
            var updated = original
            guard updated.set(EnvKey.image, request.image) else { return false }
            return (try? store.write(updated)) != nil
        case .restart:
            return docker.compose(["up", "-d"], paths: paths, timeout: 1800).ok
        case .waitForHealth:
            return Loopback.waitForVersion(request.fassung, token: token)
                && docker.runningImage(paths: paths)?.name == request.image
        }
    }

    /// Erst offline den Datenstand wiederherstellen, dann das exakte alte Bild im Prüfmodus öffnen.
    private func rollBack(to original: EnvFile, previous: Docker.RunningImage, pinnedTag: String,
                          snapshotName: String, token: String, docker: Docker) -> Bool {
        guard UpdateSnapshotName.isValid(snapshotName),
              docker.compose(["stop", "kingfisher"], paths: paths, timeout: 180).ok else { return false }
        let restore = docker.compose(["run", "--rm", "--no-deps", "-T", "--entrypoint", "python", "kingfisher",
                                      "-m", "icarus_memory.update_restore", snapshotName], paths: paths, timeout: 1800)
        guard restore.ok else { return false }
        var restored = original
        guard restored.set(EnvKey.image, pinnedTag), (try? store.write(restored)) != nil else { return false }
        guard docker.compose(["up", "-d"], paths: paths, timeout: 1800).ok else { return false }
        return docker.runningImage(paths: paths)?.id == previous.id && Loopback.inspectionMode(token: token)
    }
}
