import Foundation
import Security
import Darwin

// Native ownership of fixed optional services. Constructing this type does no work.
enum ModuleManagerError: Error { case busy, cancelled, unavailable, failed, cleanupRequired }
enum ModuleHTTPAction { case health, version, status, initialize, shutdown }
struct ModuleHTTPResponse { let status: Int; let data: Data }
final class ModuleManagerLease {
    private var finish: (() -> Void)?
    init(_ finish: @escaping () -> Void) { self.finish = finish }
    func release() { let action = finish; finish = nil; action?() }
    deinit { release() }
}
protocol ModuleManagerSystem: AnyObject {
    func docker() -> Docker?
    func now() -> Date
    func pause(_ seconds: TimeInterval)
    func readEnvironment(_ paths: AppPaths) throws -> EnvFile
    func writeEnvironment(_ env: EnvFile, paths: AppPaths) throws
    func acquire(_ paths: AppPaths) throws -> ModuleManagerLease
    func temporaryEnvironment(_ env: EnvFile, paths: AppPaths) throws -> URL
    func removeTemporary(_ file: URL)
    func command(_ docker: Docker, _ args: [String], deadline: Date, cancelled: @escaping () -> Bool) throws -> String
    func newControlKey() throws -> String
    func prepareCache(paths: AppPaths, docker: Docker, image: String, progress: (ModuleSetupPhase) -> Void, cancelled: @escaping () -> Bool) throws -> VerifiedRuntime
    func verifiedCache(paths: AppPaths, docker: Docker, image: String, path: String, digest: String, cancelled: @escaping () -> Bool) throws -> VerifiedRuntime
    func cacheMetadata(path: String, digest: String) throws -> VerifiedRuntime
    func request(_ action: ModuleHTTPAction, token: String, deadline: Date, cancelled: @escaping () -> Bool) throws -> ModuleHTTPResponse
}

final class ModuleRuntimeManager {
    private static let admission = NSLock()
    private let paths: AppPaths, system: ModuleManagerSystem
    private let state = NSLock()
    private var phase: ModuleSetupPhase = .unavailable
    private var working = false
    private var proof: ModuleIsolationProof?
    init(paths: AppPaths) { self.paths = paths; self.system = LiveModuleManagerSystem() }
    init(paths: AppPaths, system: ModuleManagerSystem) { self.paths = paths; self.system = system }

    func status() -> ModuleSetupPhase {
        state.lock(); let busy = working, current = phase, previous = proof; state.unlock()
        if busy { return current }
        guard let previous = previous else { return .unavailable }
        do { try validateReady(previous); return .ready }
        catch { set(.unavailable); state.lock(); proof = nil; state.unlock(); return .unavailable }
    }
    private func set(_ value: ModuleSetupPhase) { state.lock(); phase = value; state.unlock() }
    private func announce(_ value: ModuleSetupPhase, _ progress: (ModuleSetupPhase) -> Void) { set(value); progress(value) }
    private func run(_ docker: Docker, _ args: [String], seconds: TimeInterval = 20, cancelled: @escaping () -> Bool = { false }) throws -> String {
        try system.command(docker, args, deadline: system.now().addingTimeInterval(seconds), cancelled: cancelled)
    }
    private func json(_ text: String) throws -> Data {
        guard let data = text.data(using: .utf8), data.count <= 8 * 1024 * 1024 else { throw ModuleManagerError.unavailable }
        return data
    }
    private func ids(_ text: String) throws -> [String] {
        let rows = text.split(whereSeparator: \.isNewline).map(String.init)
        guard rows.count <= 2, Set(rows).count == rows.count, rows.allSatisfy(ModuleRuntimeContract.validDigest) else { throw ModuleManagerError.unavailable }
        return rows
    }
    private func main(_ docker: Docker) throws -> ModuleContainer {
        let found = try ids(run(docker, ["ps", "--no-trunc", "--filter", "label=com.docker.compose.project=kingfisher", "--filter", "label=com.docker.compose.service=kingfisher", "--format", "{{.ID}}"]))
        guard found.count == 1 else { throw ModuleManagerError.unavailable }
        return try ModuleContainer(json(run(docker, ["inspect", found[0]])))
    }
    private func roleIDs(_ docker: Docker) throws -> [String] {
        try ids(run(docker, ["ps", "-a", "--no-trunc", "--filter", "label=com.docker.compose.project=kingfisher-modules", "--format", "{{.ID}}"]))
    }
    private func image(_ docker: Docker, _ identifier: String) throws -> Data { try json(run(docker, ["image", "inspect", identifier])) }
    private func token(_ env: EnvFile) throws -> String {
        guard let value = env.value(EnvKey.token), !value.isEmpty, value.utf8.count <= 1024,
              value.utf8.allSatisfy({ (33...126).contains($0) }), env.hasKeys else { throw ModuleManagerError.unavailable }
        return value
    }
    private func enabled(_ env: EnvFile) -> Bool { !(env.value(ModuleIsolation.modeKey) ?? "").isEmpty || !(env.value(ModuleIsolation.controlKey) ?? "").isEmpty }
    private func approved(_ env: EnvFile) throws -> VerifiedRuntime {
        guard let path = env.value(ModuleIsolation.pathKey), let digest = env.value(ModuleIsolation.manifestKey) else { throw ModuleManagerError.unavailable }
        return try system.cacheMetadata(path: path, digest: digest)
    }
    private func cacheApprovals(_ env: EnvFile) -> [VerifiedRuntime] {
        var result: [VerifiedRuntime] = []
        if let path = env.value(ModuleIsolation.preparedPathKey), let digest = env.value(ModuleIsolation.preparedManifestKey),
           let prepared = try? system.cacheMetadata(path: path, digest: digest) { result.append(prepared) }
        // Existing installations predate the prepared receipt. Their exact
        // active approval remains a valid cache-only reuse fallback.
        if let active = try? approved(env) { result.append(active) }
        return result
    }
    private func verifiedApproval(_ env: EnvFile, docker: Docker, image: String, cancelled: @escaping () -> Bool) throws -> VerifiedRuntime {
        for candidate in cacheApprovals(env) {
            if cancelled() { throw ModuleManagerError.cancelled }
            do { return try system.verifiedCache(paths: paths, docker: docker, image: image, path: candidate.hostPath,
                digest: candidate.manifestDigest, cancelled: cancelled) }
            catch {
                if cancelled() || error as? ModuleRuntimeCacheError == .cancelled { throw ModuleManagerError.cancelled }
            }
        }
        throw ModuleManagerError.unavailable
    }
    private func request(_ action: ModuleHTTPAction, _ token: String, seconds: TimeInterval = 3, cancelled: @escaping () -> Bool = { false }) throws -> ModuleHTTPResponse {
        try system.request(action, token: token, deadline: system.now().addingTimeInterval(seconds), cancelled: cancelled)
    }
    private func backend(_ action: ModuleHTTPAction, _ token: String) throws -> ModuleRuntimeStatus {
        let response = try request(action, token)
        guard response.status == 200 else { throw ModuleManagerError.unavailable }
        return try ModuleRuntimeStatus.decode(response.data)
    }
    private func healthy(_ env: EnvFile, token: String) throws {
        guard let tag = env.value(EnvKey.image), let version = ImageName.fassung(of: tag) else { throw ModuleManagerError.unavailable }
        let health = try request(.health, token), reply = try request(.version, token)
        guard health.status == 200, reply.status == 200 else { throw ModuleManagerError.unavailable }
        let h = try ModuleJSON.object(health.data), v = try ModuleJSON.object(reply.data)
        guard h["status"] as? String == "ok", h["mode"] as? String != "inspection", v["fassung"] as? String == version else { throw ModuleManagerError.unavailable }
    }
    private func waitHealthy(_ env: EnvFile, token: String, cancelled: @escaping () -> Bool) throws {
        let deadline = system.now().addingTimeInterval(90)
        for _ in 0..<90 {
            if cancelled() { throw ModuleManagerError.cancelled }
            if system.now() >= deadline { break }
            if (try? healthy(env, token: token)) != nil { return }
            system.pause(1)
        }
        throw ModuleManagerError.unavailable
    }
    private func drain(_ env: EnvFile) -> Bool {
        guard let key = try? token(env) else { return false }
        let deadline = system.now().addingTimeInterval(12)
        do {
            let first = try request(.shutdown, key)
            if first.status == 404 { return !enabled(env) }
            guard first.status == 200 else { return false }
            var value = try ModuleRuntimeStatus.decode(first.data)
            for _ in 0..<40 {
                if value.quiescent { return true }
                if system.now() >= deadline { return false }
                system.pause(0.25)
                value = try backend(.status, key)
            }
        } catch { return false }
        return false
    }
    private func ownedRoles(_ docker: Docker, env: EnvFile) throws -> [ModuleContainer] {
        let found = try roleIDs(docker)
        if found.isEmpty { return [] }
        guard enabled(env), env.value(ModuleIsolation.modeKey) == ModuleRuntimeStatus.mode,
              let key = env.value(ModuleIsolation.controlKey), ModuleIsolation.validKey(key),
              let identifier = env.value(ModuleIsolation.imageKey), ModuleRuntimeContract.validImage(identifier) else { throw ModuleManagerError.unavailable }
        let runtime = try approved(env), imageValue = try ModuleJSON.inspect(image(docker, identifier))
        var result: [ModuleContainer] = [], seen = Set<String>()
        for id in found {
            let value = try ModuleContainer(json(run(docker, ["inspect", id])))
            guard let role = ModuleRole(rawValue: (value.config["Labels"] as? [String: String])?["com.docker.compose.service"] ?? ""), seen.insert(role.rawValue).inserted else { throw ModuleManagerError.unavailable }
            try ModuleIsolation.role(value, role: role, image: imageValue, runtime: runtime, key: key, requireRunning: false)
            result.append(value)
        }
        return result
    }
    private func stopRoles(_ docker: Docker, values: [ModuleContainer], remove: Bool) throws {
        guard !values.isEmpty else { return }
        for value in values {
            let current = try ModuleContainer(json(run(docker, ["inspect", value.id])))
            guard current.id == value.id, current.image == value.image, current.environment == value.environment else { throw ModuleManagerError.unavailable }
        }
        _ = try run(docker, ["stop", "--time", "2"] + values.map(\.id), seconds: 15)
        for value in values {
            guard try !ModuleContainer(json(run(docker, ["inspect", value.id]))).running else { throw ModuleManagerError.unavailable }
        }
        if remove { _ = try run(docker, ["rm"] + values.map(\.id), seconds: 15) }
    }
    private func networksBeforeStart(_ docker: Docker, mainID: String, roles: [ModuleContainer]) throws {
        let names = try run(docker, ["network", "ls", "--filter", "name=^kingfisher-modules-(control|worker)$", "--format", "{{.Name}}"])
            .split(whereSeparator: \.isNewline).map(String.init)
        guard names.count <= 2, Set(names).count == names.count, Set(names).isSubset(of: [ModuleIsolation.control, ModuleIsolation.workerNetwork]) else { throw ModuleManagerError.unavailable }
        let allowed = Set([mainID] + roles.map(\.id))
        for name in names {
            let data = try ModuleJSON.inspect(json(run(docker, ["network", "inspect", name])))
            let members = Set(ModuleJSON.dictionary(data["Containers"]).keys)
            guard members.isSubset(of: allowed) else { throw ModuleManagerError.unavailable }
            _ = try ModuleIsolation.network(data, role: name == ModuleIsolation.control ? "control" : "worker", members: members)
        }
    }
    private func compose(_ docker: Docker, file: URL, env: EnvFile, preserved: [String: String] = [:], modules: Bool, cancelled: @escaping () -> Bool) throws {
        var shadow = env
        for (name, value) in preserved where name != ModuleIsolation.modeKey && name != ModuleIsolation.controlKey {
            guard !value.contains("\n"), !value.contains("\r"), !value.contains("\0") else { throw ModuleManagerError.unavailable }
            // Compose decodes escapes and interpolation in double quotes. Escape
            // each original slash/dollar first, preserving even a trailing slash.
            let literal = "\"" + value.replacingOccurrences(of: "\\", with: "\\\\")
                .replacingOccurrences(of: "\"", with: "\\\"")
                .replacingOccurrences(of: "$", with: "\\$")
                .replacingOccurrences(of: "\t", with: "\\t") + "\""
            guard shadow.set(name, literal) else { throw ModuleManagerError.unavailable }
        }
        let temporary = try system.temporaryEnvironment(shadow, paths: paths)
        defer { system.removeTemporary(temporary) }
        _ = try run(docker, ["compose", "-p", modules ? ModuleIsolation.project : Installation.project,
            "-f", file.path, "--env-file", temporary.path, "up", "-d", "--pull", "never", "--no-build", "--no-deps", "--force-recreate"]
            + (modules ? ["gateway", "worker"] : ["kingfisher"]), seconds: 120, cancelled: cancelled)
    }
    private func snapshot(_ docker: Docker, env: EnvFile, runtime: VerifiedRuntime, imageData: Data) throws -> ModuleIsolationProof {
        let mainValue = try main(docker), found = try roleIDs(docker)
        guard found.count == 2 else { throw ModuleManagerError.unavailable }
        var byRole: [String: Data] = [:]
        for id in found {
            let data = try json(run(docker, ["inspect", id])), value = try ModuleContainer(data)
            guard let role = (value.config["Labels"] as? [String: String])?["com.docker.compose.service"], byRole[role] == nil else { throw ModuleManagerError.unavailable }
            byRole[role] = data
        }
        guard let gateway = byRole["gateway"], let worker = byRole["worker"], let key = env.value(ModuleIsolation.controlKey) else { throw ModuleManagerError.unavailable }
        return try ModuleIsolation.validate(imageData: imageData, mainData: json(run(docker, ["inspect", mainValue.id])),
            gatewayData: gateway, workerData: worker, controlData: json(run(docker, ["network", "inspect", ModuleIsolation.control])),
            workerNetworkData: json(run(docker, ["network", "inspect", ModuleIsolation.workerNetwork])), runtime: runtime, controlKey: key)
    }
    private func validateReady(_ old: ModuleIsolationProof) throws {
        guard let docker = system.docker() else { throw ModuleManagerError.unavailable }
        let env = try system.readEnvironment(paths), key = try token(env)
        guard env.value(ModuleIsolation.modeKey) == ModuleRuntimeStatus.mode, env.value(ModuleIsolation.imageKey) == old.imageID else { throw ModuleManagerError.unavailable }
        let runtime = try system.verifiedCache(paths: paths, docker: docker, image: old.imageID, path: old.runtimePath, digest: old.manifestDigest, cancelled: { false })
        guard try snapshot(docker, env: env, runtime: runtime, imageData: image(docker, old.imageID)) == old,
              try backend(.status, key).ready else { throw ModuleManagerError.unavailable }
        try healthy(env, token: key)
    }

    func prepareAndStart(progress: (ModuleSetupPhase) -> Void, cancelled: @escaping () -> Bool) throws {
        try activate(download: true, progress: progress, cancelled: cancelled)
    }
    func reconcileIfEnabled() {
        guard let env = try? system.readEnvironment(paths), enabled(env), env.value(ModuleIsolation.modeKey) == ModuleRuntimeStatus.mode else { return }
        do { try activate(download: false, progress: { _ in }, cancelled: { false }) } catch { set(.unavailable) }
    }
    func stopBeforeMaintenance() -> Bool {
        guard Self.admission.try() else { return false }
        defer { Self.admission.unlock() }
        do {
            let env = try system.readEnvironment(paths)
            if !enabled(env) { return true }
            guard env.value(ModuleIsolation.modeKey) == ModuleRuntimeStatus.mode,
                  let key = env.value(ModuleIsolation.controlKey), ModuleIsolation.validKey(key) else { return false }
            let lease = try system.acquire(paths); defer { lease.release() }
            guard try system.readEnvironment(paths) == env else { return false }
            guard drain(env) else { return false }
            if enabled(env) {
                guard let docker = system.docker() else { return false }
                try stopRoles(docker, values: ownedRoles(docker, env: env), remove: false)
            }
            state.lock(); proof = nil; phase = .unavailable; state.unlock()
            return true
        } catch { return false }
    }
    private func activate(download: Bool, progress: (ModuleSetupPhase) -> Void, cancelled: @escaping () -> Bool) throws {
        guard Self.admission.try() else { throw ModuleManagerError.busy }
        defer { Self.admission.unlock() }
        state.lock(); let oldProof = proof; working = true; state.unlock()
        defer { state.lock(); working = false; state.unlock() }
        var restore: EnvFile?, originalMain: ModuleContainer?, activeEnv: EnvFile?, changedMain = false
        var dockerValue: Docker?
        var ownershipLease: ModuleManagerLease?
        defer { ownershipLease?.release() }
        do {
            if cancelled() { throw ModuleManagerError.cancelled }
            ownershipLease = try system.acquire(paths)
            if let previous = oldProof, (try? validateReady(previous)) != nil { announce(.ready, progress); return }
            announce(.checking, progress)
            guard let docker = system.docker() else { throw ModuleManagerError.unavailable }; dockerValue = docker
            let original = try system.readEnvironment(paths), master = try token(original), before = try main(docker)
            originalMain = before
            let imageData = try image(docker, before.image), imageObject = try ModuleJSON.inspect(imageData)
            try ModuleIsolation.main(before, image: imageObject, requireControl: false)
            guard before.config["Image"] as? String == original.value(EnvKey.image),
                  before.environment[EnvKey.token] == original.value(EnvKey.token), before.environment[EnvKey.passphrase] == original.value(EnvKey.passphrase),
                  try ModuleJSON.inspect(image(docker, original.value(EnvKey.image) ?? ""))["Id"] as? String == before.image else { throw ModuleManagerError.unavailable }
            try healthy(original, token: master)
            _ = try backend(.status, master) // Feature/version check before downloads or main restart.
            let oldRoles = try ownedRoles(docker, env: original)
            try networksBeforeStart(docker, mainID: before.id, roles: oldRoles)
            let runtime: VerifiedRuntime
            if download {
                runtime = try system.prepareCache(paths: paths, docker: docker, image: before.image,
                    progress: { self.announce($0 == .ready ? .verifying : $0, progress) }, cancelled: cancelled)
                if !runtime.builtFresh {
                    guard cacheApprovals(original).contains(where: { $0.hostPath == runtime.hostPath && $0.manifestDigest == runtime.manifestDigest && $0.architecture == runtime.architecture }) else { throw ModuleManagerError.unavailable }
                }
            } else {
                runtime = try verifiedApproval(original, docker: docker, image: before.image, cancelled: cancelled)
            }
            // A fresh result already completed the pinned build and full verify.
            // Preserve that private provenance before any later cancellation or
            // drain can fail. Active bindings still describe old roles until
            // those roles have actually drained and been removed.
            guard try system.readEnvironment(paths) == original else { throw ModuleManagerError.unavailable }
            var checkpoint = original
            for (name, value) in [(ModuleIsolation.preparedPathKey, runtime.hostPath), (ModuleIsolation.preparedManifestKey, runtime.manifestDigest)] {
                guard !value.contains("$"), !value.contains("#"), !value.contains("'"), !value.contains("\""), checkpoint.set(name, value) else { throw ModuleManagerError.unavailable }
            }
            try system.writeEnvironment(checkpoint, paths: paths); restore = checkpoint
            // Full no-download revalidation against the private result, never the public manifest's own claim.
            let verified = try system.verifiedCache(paths: paths, docker: docker, image: before.image,
                path: runtime.hostPath, digest: runtime.manifestDigest, cancelled: cancelled)
            guard verified.hostPath == runtime.hostPath, verified.manifestDigest == runtime.manifestDigest else { throw ModuleManagerError.unavailable }
            if cancelled() { throw ModuleManagerError.cancelled }
            guard try system.readEnvironment(paths) == checkpoint, try main(docker).id == before.id,
                  try main(docker).image == before.image, drain(original) else { throw ModuleManagerError.unavailable }
            try stopRoles(docker, values: oldRoles, remove: true)
            var active = checkpoint
            for (name, value) in [(ModuleIsolation.pathKey, runtime.hostPath), (ModuleIsolation.manifestKey, runtime.manifestDigest), (ModuleIsolation.imageKey, before.image)] {
                guard active.set(name, value) else { throw ModuleManagerError.unavailable }
            }
            let freshKey = try system.newControlKey()
            guard ModuleIsolation.validKey(freshKey), freshKey != original.value(ModuleIsolation.controlKey),
                  active.set(ModuleIsolation.modeKey, ModuleRuntimeStatus.mode), active.set(ModuleIsolation.controlKey, freshKey) else { throw ModuleManagerError.unavailable }
            try system.writeEnvironment(active, paths: paths); activeEnv = active; changedMain = true
            if cancelled() { throw ModuleManagerError.cancelled }
            announce(.verifying, progress)
            try compose(docker, file: paths.composeFile, env: active, preserved: before.environment, modules: false, cancelled: cancelled)
            try waitHealthy(active, token: master, cancelled: cancelled)
            let after = try main(docker)
            guard after.image == before.image,
                  after.environment.filter({ $0.key != ModuleIsolation.modeKey && $0.key != ModuleIsolation.controlKey }) == before.environment.filter({ $0.key != ModuleIsolation.modeKey && $0.key != ModuleIsolation.controlKey }) else { throw ModuleManagerError.unavailable }
            let composeFile = paths.composeFile.deletingLastPathComponent().appendingPathComponent("compose.modules.yaml")
            try compose(docker, file: composeFile, env: active, modules: true, cancelled: cancelled)
            _ = try run(docker, ["network", "connect", "--alias", "kingfisher-controller", ModuleIsolation.control, after.id], cancelled: cancelled)
            let receipt = try snapshot(docker, env: active, runtime: runtime, imageData: imageData)
            let host = try ModuleJSON.object(json(run(docker, ["exec", receipt.mainID, "python", "-c", ModuleIsolation.hostModelAddressProbe], cancelled: cancelled)))
            guard let hostIP = host["address"] as? String, ModuleIsolation.privateIPv4(hostIP) else { throw ModuleManagerError.unavailable }
            try ModuleIsolation.validateProbe(json(run(docker, ["exec", receipt.gatewayID, "python", "-c", ModuleIsolation.sandboxProbe], seconds: 30, cancelled: cancelled)), role: .gateway)
            try ModuleIsolation.validateProbe(json(run(docker, ["exec", receipt.workerID, "python", "-c", ModuleIsolation.sandboxProbe, receipt.mainControlIP, hostIP], seconds: 30, cancelled: cancelled)), role: .worker)
            guard try snapshot(docker, env: active, runtime: runtime, imageData: imageData) == receipt else { throw ModuleManagerError.unavailable }
            if cancelled() { throw ModuleManagerError.cancelled }
            guard try backend(.initialize, master).ready else { throw ModuleManagerError.unavailable }
            try ModuleIsolation.validateBrokerProbe(json(run(docker, ["exec", receipt.mainID, "python", "-c", ModuleIsolation.brokerProbe], cancelled: cancelled)))
            guard try snapshot(docker, env: active, runtime: runtime, imageData: imageData) == receipt,
                  try backend(.status, master).ready else { throw ModuleManagerError.unavailable }
            _ = try system.verifiedCache(paths: paths, docker: docker, image: before.image, path: runtime.hostPath, digest: runtime.manifestDigest, cancelled: cancelled)
            state.lock(); proof = receipt; state.unlock(); announce(.ready, progress)
        } catch {
            state.lock(); proof = nil; state.unlock()
            if changedMain, let docker = dockerValue, let restore = restore, let current = activeEnv, let before = originalMain {
                // Keep operational state/key intact if physical quiescence is unknown.
                guard drain(current) else { announce(.failed, progress); throw ModuleManagerError.cleanupRequired }
                do {
                    try stopRoles(docker, values: ownedRoles(docker, env: current), remove: true)
                    try system.writeEnvironment(restore, paths: paths)
                    let actual = try main(docker)
                    if actual.id != before.id || actual.image != before.image || actual.environment != before.environment {
                        try compose(docker, file: paths.composeFile, env: restore, preserved: before.environment, modules: false, cancelled: { false })
                        try waitHealthy(restore, token: token(restore), cancelled: { false })
                    }
                    let restored = try main(docker)
                    guard restored.image == before.image,
                          restored.environment.filter({ $0.key != ModuleIsolation.modeKey && $0.key != ModuleIsolation.controlKey }) == before.environment.filter({ $0.key != ModuleIsolation.modeKey && $0.key != ModuleIsolation.controlKey }),
                          (restored.environment[ModuleIsolation.modeKey] ?? "") == (restore.value(ModuleIsolation.modeKey) ?? ""),
                          (restored.environment[ModuleIsolation.controlKey] ?? "") == (restore.value(ModuleIsolation.controlKey) ?? "") else { throw ModuleManagerError.cleanupRequired }
                } catch { announce(.failed, progress); throw ModuleManagerError.cleanupRequired }
            }
            let cancelledNow = cancelled() || (error as? ModuleManagerError) == .cancelled || (error as? ModuleRuntimeCacheError) == .cancelled
            announce(cancelledNow ? .cancelled : .unavailable, progress)
            throw cancelledNow ? ModuleManagerError.cancelled : ModuleManagerError.unavailable
        }
    }
}

final class LiveModuleManagerSystem: ModuleManagerSystem {
    func docker() -> Docker? { Docker.find() }
    func now() -> Date { Date() }
    func pause(_ seconds: TimeInterval) { Thread.sleep(forTimeInterval: min(1, max(0, seconds))) }
    private func privateFolder(_ paths: AppPaths) throws {
        var info = stat()
        guard lstat(paths.support.path, &info) == 0, info.st_mode & S_IFMT == S_IFDIR,
              info.st_uid == getuid(), info.st_mode & 0o7777 == 0o700 else { throw ModuleManagerError.unavailable }
    }
    func readEnvironment(_ paths: AppPaths) throws -> EnvFile {
        try privateFolder(paths)
        var info = stat()
        guard lstat(paths.envFile.path, &info) == 0, info.st_mode & S_IFMT == S_IFREG,
              info.st_uid == getuid(), info.st_nlink == 1, info.st_mode & 0o7777 == 0o600,
              let text = String(data: try ModuleRuntimeCache.readRegular(paths.envFile, limit: 1024 * 1024), encoding: .utf8) else { throw ModuleManagerError.unavailable }
        return EnvFile(text: text)
    }
    func writeEnvironment(_ env: EnvFile, paths: AppPaths) throws {
        _ = try readEnvironment(paths)
        try EnvStore(file: paths.envFile).write(env)
    }
    func acquire(_ paths: AppPaths) throws -> ModuleManagerLease {
        try privateFolder(paths)
        let file = paths.support.appendingPathComponent(".module-runtime.lock")
        let descriptor = open(file.path, O_CREAT | O_RDWR | O_NOFOLLOW | O_CLOEXEC, 0o600)
        guard descriptor >= 0 else { throw ModuleManagerError.unavailable }
        var info = stat()
        guard fstat(descriptor, &info) == 0, info.st_mode & S_IFMT == S_IFREG, info.st_uid == getuid(),
              info.st_nlink == 1, info.st_mode & 0o7777 == 0o600, flock(descriptor, LOCK_EX | LOCK_NB) == 0 else {
            close(descriptor); throw ModuleManagerError.busy
        }
        return ModuleManagerLease { _ = flock(descriptor, LOCK_UN); close(descriptor) }
    }
    func temporaryEnvironment(_ env: EnvFile, paths: AppPaths) throws -> URL {
        try privateFolder(paths)
        let file = paths.support.appendingPathComponent(".module-environment-" + UUID().uuidString + ".env")
        let descriptor = open(file.path, O_CREAT | O_EXCL | O_WRONLY | O_NOFOLLOW | O_CLOEXEC, 0o600)
        guard descriptor >= 0 else { throw ModuleManagerError.unavailable }
        let handle = FileHandle(fileDescriptor: descriptor, closeOnDealloc: true)
        do { try handle.write(contentsOf: Data(env.text.utf8)); try handle.synchronize(); try handle.close(); return file }
        catch { try? handle.close(); try? FileManager.default.removeItem(at: file); throw ModuleManagerError.unavailable }
    }
    func removeTemporary(_ file: URL) { try? FileManager.default.removeItem(at: file) }
    func command(_ docker: Docker, _ args: [String], deadline: Date, cancelled: @escaping () -> Bool) throws -> String {
        try ModuleRuntimeProcess().run(docker.executable, args, deadline: deadline, cancelled: cancelled)
    }
    func newControlKey() throws -> String {
        var bytes = [UInt8](repeating: 0, count: 32)
        guard SecRandomCopyBytes(kSecRandomDefault, bytes.count, &bytes) == errSecSuccess else { throw ModuleManagerError.unavailable }
        return Data(bytes).base64EncodedString().replacingOccurrences(of: "+", with: "-").replacingOccurrences(of: "/", with: "_").replacingOccurrences(of: "=", with: "")
    }
    func prepareCache(paths: AppPaths, docker: Docker, image: String, progress: (ModuleSetupPhase) -> Void, cancelled: @escaping () -> Bool) throws -> VerifiedRuntime {
        try ModuleRuntimeCache().prepare(paths: paths, docker: docker, currentImmutableImage: image, progress: progress, cancelled: cancelled)
    }
    func verifiedCache(paths: AppPaths, docker: Docker, image: String, path: String, digest: String, cancelled: @escaping () -> Bool) throws -> VerifiedRuntime {
        try ModuleRuntimeCache().verifiedExisting(paths: paths, docker: docker, currentImmutableImage: image,
            approvedHostPath: path, expectedManifestDigest: digest, cancelled: cancelled)
    }
    func cacheMetadata(path: String, digest: String) throws -> VerifiedRuntime {
        let root = LiveModuleRuntimeCacheSystem().cacheRoot
        let url = URL(fileURLWithPath: path)
        guard url.path == path, url.deletingLastPathComponent().path == root.path, ModuleRuntimeContract.validDigest(digest) else { throw ModuleManagerError.unavailable }
        let name = url.lastPathComponent
        for arch in [ModuleRuntimeArchitecture.arm64, .x64] {
            let prefix = "runtime-v1-" + arch.rawValue + "-"
            if name.hasPrefix(prefix), ModuleRuntimeContract.validDigest(String(name.dropFirst(prefix.count))) {
                return VerifiedRuntime(hostPath: path, manifestDigest: digest, architecture: arch.rawValue)
            }
        }
        throw ModuleManagerError.unavailable
    }
    func request(_ action: ModuleHTTPAction, token: String, deadline: Date, cancelled: @escaping () -> Bool) throws -> ModuleHTTPResponse {
        try ModuleManagerHTTP().perform(action, token: token, deadline: deadline, cancelled: cancelled)
    }
}

// Fixed loopback-only control plane: no proxies, cookies, redirects or raw diagnostics.
private final class ModuleManagerHTTP: NSObject, URLSessionDataDelegate, URLSessionTaskDelegate {
    private let lock = NSLock(), done = DispatchSemaphore(value: 0)
    private var data = Data(), code: Int?, failed = false
    private var url: URL?
    func perform(_ action: ModuleHTTPAction, token: String, deadline: Date, cancelled: @escaping () -> Bool) throws -> ModuleHTTPResponse {
        let path: String, method: String
        switch action {
        case .health: path = "health"; method = "GET"
        case .version: path = "api/v1/fassung"; method = "GET"
        case .status: path = "api/v1/modules/local-source/runtime/status"; method = "GET"
        case .initialize: path = "api/v1/modules/local-source/runtime/initialize"; method = "POST"
        case .shutdown: path = "api/v1/modules/local-source/runtime/shutdown"; method = "POST"
        }
        guard !cancelled(), Date() < deadline, !token.contains("\n"), !token.contains("\r") else { throw ModuleManagerError.cancelled }
        let target = AppPaths.origin.appendingPathComponent(path); url = target
        let configuration = URLSessionConfiguration.ephemeral
        configuration.connectionProxyDictionary = [:]; configuration.urlCache = nil
        configuration.urlCredentialStorage = nil; configuration.httpCookieStorage = nil; configuration.httpShouldSetCookies = false
        configuration.timeoutIntervalForRequest = min(3, deadline.timeIntervalSinceNow)
        configuration.timeoutIntervalForResource = min(3, deadline.timeIntervalSinceNow)
        let session = URLSession(configuration: configuration, delegate: self, delegateQueue: nil)
        defer { session.invalidateAndCancel() }
        var request = URLRequest(url: target, cachePolicy: .reloadIgnoringLocalCacheData, timeoutInterval: configuration.timeoutIntervalForRequest)
        request.httpMethod = method
        request.setValue("application/json", forHTTPHeaderField: "Accept")
        request.setValue("identity", forHTTPHeaderField: "Accept-Encoding")
        if action != .health { request.setValue(token, forHTTPHeaderField: "x-icarus-token") }
        if method == "POST" { request.httpBody = Data("{}".utf8); request.setValue("application/json", forHTTPHeaderField: "Content-Type") }
        let task = session.dataTask(with: request); task.resume()
        var cancellationDeadline: Date?
        while done.wait(timeout: .now() + .milliseconds(50)) == .timedOut {
            if cancelled() || Date() >= deadline {
                lock.lock(); failed = true; lock.unlock(); task.cancel()
                if cancellationDeadline == nil { cancellationDeadline = Date().addingTimeInterval(1) }
                if let until = cancellationDeadline, Date() >= until { throw ModuleManagerError.unavailable }
            }
        }
        lock.lock(); defer { lock.unlock() }
        guard !failed, let code = code else { throw ModuleManagerError.unavailable }
        return ModuleHTTPResponse(status: code, data: data)
    }
    func urlSession(_ session: URLSession, task: URLSessionTask, willPerformHTTPRedirection response: HTTPURLResponse,
                    newRequest request: URLRequest, completionHandler: @escaping (URLRequest?) -> Void) {
        lock.lock(); failed = true; lock.unlock(); completionHandler(nil)
    }
    func urlSession(_ session: URLSession, task: URLSessionTask, didReceive challenge: URLAuthenticationChallenge,
                    completionHandler: @escaping (URLSession.AuthChallengeDisposition, URLCredential?) -> Void) {
        completionHandler(.cancelAuthenticationChallenge, nil)
    }
    func urlSession(_ session: URLSession, dataTask: URLSessionDataTask, didReceive response: URLResponse,
                    completionHandler: @escaping (URLSession.ResponseDisposition) -> Void) {
        guard let response = response as? HTTPURLResponse, response.url == url,
              response.expectedContentLength <= 65536,
              (response.value(forHTTPHeaderField: "Content-Encoding") ?? "identity").lowercased() == "identity",
              response.statusCode != 200 || response.mimeType?.lowercased() == "application/json" else {
            lock.lock(); failed = true; lock.unlock(); completionHandler(.cancel); return
        }
        lock.lock(); code = response.statusCode; lock.unlock(); completionHandler(.allow)
    }
    func urlSession(_ session: URLSession, dataTask: URLSessionDataTask, didReceive part: Data) {
        lock.lock()
        if data.count + part.count > 65536 { failed = true; lock.unlock(); dataTask.cancel(); return }
        data.append(part); lock.unlock()
    }
    func urlSession(_ session: URLSession, task: URLSessionTask, didCompleteWithError error: Error?) {
        lock.lock(); if error != nil { failed = true }; lock.unlock(); done.signal()
    }
}
