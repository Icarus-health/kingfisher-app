import Foundation
import CryptoKit
import Darwin

// Only public Node/npm/package files enter this cache. Setup never executes SDK or npm code on the Mac.
protocol ModuleRuntimeCacheSystem {
    var cacheRoot: URL { get }
    var userID: UInt32 { get }
    func command(_ executable: String, _ arguments: [String], deadline: Date,
                 cancelled: @escaping () -> Bool) throws -> String
    func download(_ pin: ModuleRuntimeNodePin, to destination: URL, deadline: Date,
                  cancelled: @escaping () -> Bool) throws
}

struct LiveModuleRuntimeCacheSystem: ModuleRuntimeCacheSystem {
    var cacheRoot: URL {
        FileManager.default.homeDirectoryForCurrentUser.appendingPathComponent("Library/Caches/KingfisherModules")
    }
    var userID: UInt32 { getuid() }
    func command(_ executable: String, _ arguments: [String], deadline: Date,
                 cancelled: @escaping () -> Bool) throws -> String {
        try ModuleRuntimeProcess().run(executable, arguments, deadline: deadline, cancelled: cancelled)
    }
    func download(_ pin: ModuleRuntimeNodePin, to destination: URL, deadline: Date,
                  cancelled: @escaping () -> Bool) throws {
        try ModuleRuntimeHTTPS().download(pin, to: destination, deadline: deadline, cancelled: cancelled)
    }
}

/// Synchronous background helper. Its only application entry accepts the already-verified immutable main image.
/// Bundle contract: Resources/module-runtime/{package.json,package-lock.json,harness_{run,service,worker}.mjs,harness_gateway.py}.
final class ModuleRuntimeCache {
    private static let admission = NSLock()
    private let system: ModuleRuntimeCacheSystem
    private let fm = FileManager.default
    init(system: ModuleRuntimeCacheSystem = LiveModuleRuntimeCacheSystem()) { self.system = system }

    /// Read-only status/reconcile path: no download, mkdir, builder, service start or repair fallback.
    func verifiedExisting(paths: AppPaths, docker: Docker, currentImmutableImage: String,
                          approvedHostPath: String, expectedManifestDigest: String,
                          cancelled: @escaping () -> Bool = { false }) throws -> VerifiedRuntime {
        let deadline = Date().addingTimeInterval(60)
        func check() throws {
            if cancelled() { throw ModuleRuntimeCacheError.cancelled }
            if Date() >= deadline { throw ModuleRuntimeCacheError.timedOut }
        }
        do {
            try check()
            guard ModuleRuntimeContract.validDigest(expectedManifestDigest) else { throw ModuleRuntimeCacheError.integrityFailed }
            let recipe = try checkedRecipe(paths: paths, docker: docker, image: currentImmutableImage, deadline: deadline, cancelled: cancelled)
            let expectedPath = system.cacheRoot.appendingPathComponent(recipe.directoryName)
            guard approvedHostPath == expectedPath.path else { throw ModuleRuntimeCacheError.unsafeCache }
            let result = try Self.verify(expectedPath, recipe: recipe, check: check)
            guard result.manifestDigest == expectedManifestDigest else { throw ModuleRuntimeCacheError.integrityFailed }
            try check()
            return result
        } catch let error as ModuleRuntimeCacheError { throw error }
        catch { throw ModuleRuntimeCacheError.unavailable }
    }

    private func checkedRecipe(paths: AppPaths, docker: Docker, image: String, deadline: Date,
                               cancelled: @escaping () -> Bool) throws -> ModuleRuntimeRecipe {
        if cancelled() { throw ModuleRuntimeCacheError.cancelled }
        guard ModuleRuntimeContract.validImage(image) else { throw ModuleRuntimeCacheError.invalidImage }
        let resources = paths.composeFile.deletingLastPathComponent().appendingPathComponent("module-runtime")
        // Refuse changed fixed package inputs before any Docker operation.
        let preliminary = try Self.recipe(resources: resources, architecture: .arm64)
        let engine = try system.command(docker.executable, ["info", "--format", "{{.OSType}}|{{.Architecture}}"],
            deadline: min(deadline, Date().addingTimeInterval(30)), cancelled: cancelled)
            .trimmingCharacters(in: .whitespacesAndNewlines).components(separatedBy: "|")
        guard engine.count == 2, engine[0] == "linux", let architecture = ModuleRuntimeArchitecture(engine: engine[1]) else {
            throw ModuleRuntimeCacheError.unsupportedArchitecture
        }
        let installed = try system.command(docker.executable, ["image", "inspect", "--format", "{{.Id}}|{{.Os}}|{{.Architecture}}", image],
            deadline: min(deadline, Date().addingTimeInterval(30)), cancelled: cancelled)
            .trimmingCharacters(in: .whitespacesAndNewlines).components(separatedBy: "|")
        guard installed.count == 3, installed[0] == image, installed[1] == "linux",
              ModuleRuntimeArchitecture(engine: installed[2]) == architecture else { throw ModuleRuntimeCacheError.invalidImage }
        let identity = try ModuleRuntimeContract.identityData(architecture: architecture, hashes: preliminary.resourceHashes)
        return ModuleRuntimeRecipe(architecture: architecture, resourceHashes: preliminary.resourceHashes, digest: Self.digest(identity))
    }

    func prepare(paths: AppPaths, docker: Docker, currentImmutableImage: String, progress: (ModuleSetupPhase) -> Void,
                 cancelled: @escaping () -> Bool) throws -> VerifiedRuntime {
        guard Self.admission.try() else { throw ModuleRuntimeCacheError.busy }
        defer { Self.admission.unlock() }
        let deadline = Date().addingTimeInterval(600)
        let workDeadline = deadline.addingTimeInterval(-15) // Reserve bounded cleanup inside the setup budget.
        func check() throws {
            if cancelled() { throw ModuleRuntimeCacheError.cancelled }
            if Date() >= workDeadline { throw ModuleRuntimeCacheError.timedOut }
        }
        do {
            try check()
            progress(.checking)
            let resources = paths.composeFile.deletingLastPathComponent().appendingPathComponent("module-runtime")
            let recipe = try checkedRecipe(paths: paths, docker: docker, image: currentImmutableImage, deadline: workDeadline, cancelled: cancelled)
            let architecture = recipe.architecture
            guard system.userID > 0 else { throw ModuleRuntimeCacheError.unavailable }
            try check()
            try Self.directory(system.cacheRoot, create: true)
            let final = system.cacheRoot.appendingPathComponent(recipe.directoryName)
            if Self.exists(final) {
                let result = try Self.verify(final, recipe: recipe, check: check)
                try check()
                progress(.ready)
                return result
            }

            let nonce = UUID().uuidString.replacingOccurrences(of: "-", with: "").lowercased()
            let stage = system.cacheRoot.appendingPathComponent(".prepare-" + nonce)
            guard mkdir(stage.path, 0o755) == 0 else { throw ModuleRuntimeCacheError.unavailable }
            let owned = try Self.identity(stage)
            var builderName: String?
            var builderID: String?
            var failure: ModuleRuntimeCacheError?
            do {
                let bootstrap = stage.appendingPathComponent("bootstrap")
                let sdk = stage.appendingPathComponent("sdk")
                try Self.directory(bootstrap, create: true)
                try Self.directory(sdk, create: true)
                let archive = stage.appendingPathComponent("node.tar.gz")
                let pin = ModuleRuntimeNodePin(architecture: architecture)
                progress(.downloading)
                try system.download(pin, to: archive, deadline: min(workDeadline, Date().addingTimeInterval(120)), cancelled: cancelled)
                guard try Self.hashFile(archive, limit: UInt64(ModuleRuntimeContract.archiveLimit), check: check).hash == pin.sha256 else {
                    throw ModuleRuntimeCacheError.integrityFailed
                }
                try check()
                let listing = try system.command("/usr/bin/tar", ["-tvzf", archive.path],
                    deadline: min(workDeadline, Date().addingTimeInterval(60)), cancelled: cancelled)
                try ModuleRuntimeContract.validateArchiveListing(listing, pin: pin)
                _ = try system.command("/usr/bin/tar", ["-xzf", archive.path, "--no-same-owner", "--no-same-permissions", "-C", bootstrap.path],
                    deadline: min(workDeadline, Date().addingTimeInterval(60)), cancelled: cancelled)
                try fm.moveItem(at: bootstrap.appendingPathComponent(pin.archiveRoot), to: bootstrap.appendingPathComponent("node"))
                _ = try Self.inventory(root: bootstrap, normalize: true, check: check)
                for name in ["package.json", "package-lock.json"] {
                    try Self.readRegular(resources.appendingPathComponent(name), limit: 2 * 1024 * 1024).write(to: sdk.appendingPathComponent(name))
                }
                progress(.installing)
                let arguments = try ModuleRuntimeContract.builderArguments(image: currentImmutableImage, architecture: architecture,
                    userID: system.userID, bootstrap: bootstrap, sdk: sdk, nonce: nonce)
                builderName = "kingfisher-runtime-build-" + nonce
                let created = try system.command(docker.executable, arguments,
                    deadline: min(workDeadline, Date().addingTimeInterval(30)), cancelled: cancelled)
                    .trimmingCharacters(in: .whitespacesAndNewlines)
                guard ModuleRuntimeContract.validDigest(created) else { throw ModuleRuntimeCacheError.builderFailed }
                builderID = created
                _ = try system.command(docker.executable, ["start", "--attach", created], deadline: workDeadline, cancelled: cancelled)
                try removeBuilder(docker, name: builderName!, id: builderID, nonce: nonce, deadline: deadline)
                builderName = nil
                builderID = nil
                try check()
                guard try Self.recipe(resources: resources, architecture: architecture).digest == recipe.digest else {
                    throw ModuleRuntimeCacheError.invalidResources
                }
                for name in ["package.json", "package-lock.json"] {
                    guard try Self.hashFile(sdk.appendingPathComponent(name), check: check).hash == recipe.resourceHashes[name] else {
                        throw ModuleRuntimeCacheError.integrityFailed
                    }
                }
                for name in ModuleRuntimeContract.resourceNames where !name.hasSuffix("json") {
                    let data = try Self.readRegular(resources.appendingPathComponent(name), limit: 256 * 1024)
                    guard Self.digest(data) == recipe.resourceHashes[name] else { throw ModuleRuntimeCacheError.invalidResources }
                    try data.write(to: sdk.appendingPathComponent(name))
                }
                try fm.moveItem(at: bootstrap.appendingPathComponent("node"), to: sdk.appendingPathComponent("node"))
                try Self.directory(sdk.appendingPathComponent("bin"), create: true)
                try fm.createSymbolicLink(atPath: sdk.appendingPathComponent("bin/node").path, withDestinationPath: "../node/bin/node")
                progress(.verifying)
                try Self.cleanStagingMetadata(sdk, check: check)
                let files = try Self.inventory(root: sdk, normalize: true, check: check)
                try ModuleRuntimeContract.manifestData(recipe: recipe, files: files).write(to: sdk.appendingPathComponent("manifest.json"))
                try fm.setAttributes([.posixPermissions: 0o644], ofItemAtPath: sdk.appendingPathComponent("manifest.json").path)
                try Self.cleanStagingMetadata(sdk, check: check)
                let complete = try Self.publishVerifiedStage(sdk: sdk, stage: stage, stageIdentity: owned,
                    final: final, recipe: recipe, deadline: deadline, check: check)
                // Publication is the commit point: all cancellable verification and staging cleanup is done.
                // Return native fresh provenance even if cancellation arrives immediately after that commit.
                progress(.ready)
                return complete
            } catch { failure = (error as? ModuleRuntimeCacheError) ?? .builderFailed }

            // Cleanup only this nonce/label and the directory inode created by this invocation.
            do {
                if let name = builderName { try removeBuilder(docker, name: name, id: builderID, nonce: nonce, deadline: deadline) }
                try Self.removeOwnedStage(stage, identity: owned, deadline: deadline)
            } catch { throw ModuleRuntimeCacheError.cleanupRequired }
            if let failure = failure { throw failure }
            throw ModuleRuntimeCacheError.unavailable
        } catch let error as ModuleRuntimeCacheError { throw error }
        catch { throw ModuleRuntimeCacheError.unavailable }
    }

    private func removeBuilder(_ docker: Docker, name: String, id: String?, nonce: String, deadline: Date) throws {
        let query = ["ps", "-a", "--no-trunc", "--filter", "name=^/" + name + "$", "--filter",
                     "label=" + ModuleRuntimeContract.ownerLabel + "=" + nonce, "--format", "{{.ID}}"]
        let found = try system.command(docker.executable, query, deadline: deadline, cancelled: { false })
            .trimmingCharacters(in: .whitespacesAndNewlines)
        if found.isEmpty { return }
        guard ModuleRuntimeContract.validDigest(found), id == nil || id == found else { throw ModuleRuntimeCacheError.cleanupRequired }
        let inspected = try system.command(docker.executable, ["inspect", "--format",
            "{{.Id}}|{{index .Config.Labels \"\(ModuleRuntimeContract.ownerLabel)\"}}", found], deadline: deadline, cancelled: { false })
            .trimmingCharacters(in: .whitespacesAndNewlines)
        guard inspected == found + "|" + nonce else { throw ModuleRuntimeCacheError.cleanupRequired }
        _ = try system.command(docker.executable, ["rm", "--force", found], deadline: deadline, cancelled: { false })
        guard try system.command(docker.executable, query, deadline: deadline, cancelled: { false })
            .trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else { throw ModuleRuntimeCacheError.cleanupRequired }
    }

    static func digest(_ data: Data) -> String { SHA256.hash(data: data).map { String(format: "%02x", $0) }.joined() }

    static func recipe(resources: URL, architecture: ModuleRuntimeArchitecture) throws -> ModuleRuntimeRecipe {
        do {
            try directory(resources, create: false)
            var hashes: [String: String] = [:]
            for name in ModuleRuntimeContract.resourceNames {
                let data = try readRegular(resources.appendingPathComponent(name), limit: name.hasSuffix("json") ? 2 * 1024 * 1024 : 256 * 1024)
                guard !data.isEmpty else { throw ModuleRuntimeCacheError.invalidResources }
                hashes[name] = digest(data)
            }
            return ModuleRuntimeRecipe(architecture: architecture, resourceHashes: hashes,
                digest: digest(try ModuleRuntimeContract.identityData(architecture: architecture, hashes: hashes)))
        } catch { throw ModuleRuntimeCacheError.invalidResources }
    }

    static func verify(_ root: URL, recipe: ModuleRuntimeRecipe, check: () throws -> Void = {}) throws -> VerifiedRuntime {
        try directory(root, create: false)
        var manifestInfo = stat()
        guard lstat(root.appendingPathComponent("manifest.json").path, &manifestInfo) == 0,
              manifestInfo.st_mode & S_IFMT == S_IFREG,
              manifestInfo.st_mode & 0o7777 == 0o644 else { throw ModuleRuntimeCacheError.unsafeCache }
        let recorded = try readRegular(root.appendingPathComponent("manifest.json"), limit: 32 * 1024 * 1024)
        let files = try inventory(root: root, normalize: false, check: check)
        for (name, hash) in recipe.resourceHashes {
            guard files.first(where: { $0.path == name })?.sha256 == hash else { throw ModuleRuntimeCacheError.integrityFailed }
        }
        guard files.first(where: { $0.path == "node/bin/node" })?.kind == "file",
              files.first(where: { $0.path == "bin/node" })?.target == "../node/bin/node",
              files.first(where: { $0.path == "node/LICENSE" })?.kind == "file",
              files.first(where: { $0.path == "node_modules" })?.kind == "directory",
              try ModuleRuntimeContract.manifestData(recipe: recipe, files: files) == recorded else {
            throw ModuleRuntimeCacheError.integrityFailed
        }
        return VerifiedRuntime(hostPath: root.path, manifestDigest: digest(recorded), architecture: recipe.architecture.rawValue)
    }

    static func exists(_ url: URL) -> Bool { var info = stat(); return lstat(url.path, &info) == 0 }
    /// Called only after the fixed fresh construction. Keep its tree unpublished until every fallible
    /// preparation/cleanup step is done; an atomic exclusive rename then commits the fresh return.
    static func publishVerifiedStage(sdk: URL, stage: URL, stageIdentity ownedStage: String, final: URL,
                                     recipe: ModuleRuntimeRecipe, deadline: Date,
                                     check: () throws -> Void = {}) throws -> VerifiedRuntime {
        let nonce = String(stage.lastPathComponent.dropFirst(".prepare-".count))
        guard stage.lastPathComponent.hasPrefix(".prepare-"), nonce.count == 32,
              ModuleRuntimeContract.validDigest(nonce + nonce), sdk.lastPathComponent == "sdk",
              sdk.deletingLastPathComponent().path == stage.path,
              final.deletingLastPathComponent().path == stage.deletingLastPathComponent().path,
              final.lastPathComponent == recipe.directoryName, try identity(stage) == ownedStage else {
            throw ModuleRuntimeCacheError.unsafeCache
        }
        let prepared = try verify(sdk, recipe: recipe, check: check)
        let ownedTree = try identity(sdk)
        let pending = stage.deletingLastPathComponent().appendingPathComponent(".pending-" + nonce)
        try check()
        guard renamex_np(sdk.path, pending.path, UInt32(RENAME_EXCL)) == 0 else { throw ModuleRuntimeCacheError.unavailable }
        var ownsPending = true
        do {
            try check()
            guard try identity(pending) == ownedTree else { throw ModuleRuntimeCacheError.cleanupRequired }
            try removeOwnedStage(stage, identity: ownedStage, deadline: deadline)
            let verified = try verify(pending, recipe: recipe, check: check)
            guard verified.manifestDigest == prepared.manifestDigest else { throw ModuleRuntimeCacheError.integrityFailed }
            try check()
            guard try identity(pending) == ownedTree else { throw ModuleRuntimeCacheError.cleanupRequired }
            if exists(final) {
                // A concurrent or unknown cache never inherits this operation's fresh provenance.
                let existing = try verify(final, recipe: recipe, check: check)
                try removeOwnedStage(pending, identity: ownedTree, deadline: deadline)
                ownsPending = false
                try check()
                return existing
            }
            // RENAME_EXCL cannot overwrite a cache appearing after the existence check.
            guard renamex_np(pending.path, final.path, UInt32(RENAME_EXCL)) == 0 else { throw ModuleRuntimeCacheError.unavailable }
            ownsPending = false
            // No filesystem, deadline or cancellation check after this commit: the caller receives
            // the verified native provenance and can durably checkpoint it before later work.
            return VerifiedRuntime(hostPath: final.path, manifestDigest: verified.manifestDigest,
                architecture: verified.architecture, builtFresh: true)
        } catch {
            let failure = (error as? ModuleRuntimeCacheError) ?? .unavailable
            if ownsPending {
                do { try removeOwnedStage(pending, identity: ownedTree, deadline: deadline) }
                catch { throw ModuleRuntimeCacheError.cleanupRequired }
            }
            throw failure
        }
    }
    /// OS directory-view metadata is not a distributed runtime asset. Strip only in this new SDK stage.
    /// Existing complete caches remain exact: any later extra file or change still fails verify().
    static func cleanStagingMetadata(_ root: URL, check: () throws -> Void = {}) throws {
        let stageName = root.deletingLastPathComponent().lastPathComponent
        let nonce = String(stageName.dropFirst(".prepare-".count))
        guard root.lastPathComponent == "sdk", stageName.hasPrefix(".prepare-"), nonce.count == 32,
              ModuleRuntimeContract.validDigest(nonce + nonce) else { throw ModuleRuntimeCacheError.unsafeCache }
        try directory(root, create: false)
        var count = 0
        func walk(_ folder: URL, depth: Int) throws {
            try check()
            guard depth <= 64 else { throw ModuleRuntimeCacheError.unsafeCache }
            for item in try FileManager.default.contentsOfDirectory(at: folder, includingPropertiesForKeys: nil) {
                try check()
                count += 1
                guard count <= ModuleRuntimeContract.entryLimit else { throw ModuleRuntimeCacheError.unsafeCache }
                var info = stat()
                guard lstat(item.path, &info) == 0 else { throw ModuleRuntimeCacheError.unsafeCache }
                if item.lastPathComponent == ".DS_Store" {
                    guard info.st_mode & S_IFMT == S_IFREG, info.st_nlink == 1, unlink(item.path) == 0 else {
                        throw ModuleRuntimeCacheError.unsafeCache
                    }
                } else if info.st_mode & S_IFMT == S_IFDIR {
                    try walk(item, depth: depth + 1)
                }
            }
        }
        try walk(root, depth: 0)
    }
    static func removeOwnedStage(_ stage: URL, identity owned: String, deadline: Date) throws {
        for attempt in 0..<3 {
            if !exists(stage) { return }
            guard Date() < deadline, try identity(stage) == owned else { throw ModuleRuntimeCacheError.cleanupRequired }
            do { try FileManager.default.removeItem(at: stage); return }
            catch {
                // A last metadata write can race a recursive directory removal on a shared Mac bind.
                // Retry only this same owned inode; never sweep the cache or a replacement directory.
                if attempt == 2 { throw ModuleRuntimeCacheError.cleanupRequired }
                Thread.sleep(forTimeInterval: 0.05)
            }
        }
    }
    private static func identity(_ url: URL) throws -> String {
        var info = stat()
        guard lstat(url.path, &info) == 0, info.st_mode & S_IFMT == S_IFDIR else { throw ModuleRuntimeCacheError.unsafeCache }
        return "\(info.st_dev):\(info.st_ino)"
    }
    /// Walk every ancestor without resolving symlinks; mkdir never adopts a symlink as a cache directory.
    static func directory(_ url: URL, create: Bool) throws {
        // Foundation rewrites /private/tmp to the /tmp symlink when standardizing on macOS.
        // Inspect the supplied absolute components physically instead of resolving that alias.
        guard url.isFileURL, url.path.hasPrefix("/"),
              !url.pathComponents.contains(".."), !url.pathComponents.contains(".") else { throw ModuleRuntimeCacheError.unsafeCache }
        var current = URL(fileURLWithPath: "/")
        for component in url.pathComponents.dropFirst() {
            current.appendPathComponent(component)
            var info = stat()
            if lstat(current.path, &info) != 0 {
                guard create, errno == ENOENT, mkdir(current.path, 0o755) == 0 else { throw ModuleRuntimeCacheError.unsafeCache }
                guard lstat(current.path, &info) == 0 else { throw ModuleRuntimeCacheError.unsafeCache }
            }
            guard info.st_mode & S_IFMT == S_IFDIR else { throw ModuleRuntimeCacheError.unsafeCache }
        }
        if create { guard chmod(url.path, 0o755) == 0 else { throw ModuleRuntimeCacheError.unsafeCache } }
    }

    static func readRegular(_ file: URL, limit: UInt64) throws -> Data {
        let descriptor = open(file.path, O_RDONLY | O_NOFOLLOW | O_NONBLOCK)
        guard descriptor >= 0 else { throw ModuleRuntimeCacheError.unsafeCache }
        let handle = FileHandle(fileDescriptor: descriptor, closeOnDealloc: true)
        defer { try? handle.close() }
        var info = stat()
        guard fstat(descriptor, &info) == 0, info.st_mode & S_IFMT == S_IFREG, info.st_nlink == 1,
              info.st_size >= 0, UInt64(info.st_size) <= limit else { throw ModuleRuntimeCacheError.unsafeCache }
        var data = Data()
        while let part = try handle.read(upToCount: 64 * 1024), !part.isEmpty {
            guard UInt64(data.count + part.count) <= limit else { throw ModuleRuntimeCacheError.unsafeCache }
            data.append(part)
        }
        guard data.count == info.st_size else { throw ModuleRuntimeCacheError.unsafeCache }
        return data
    }

    static func hashFile(_ file: URL, limit: UInt64 = ModuleRuntimeContract.fileLimit,
                         mode: UInt16? = nil, check: () throws -> Void = {}) throws -> (hash: String, bytes: UInt64, mode: UInt16) {
        let descriptor = open(file.path, O_RDONLY | O_NOFOLLOW | O_NONBLOCK)
        guard descriptor >= 0 else { throw ModuleRuntimeCacheError.unsafeCache }
        let handle = FileHandle(fileDescriptor: descriptor, closeOnDealloc: true)
        defer { try? handle.close() }
        var info = stat()
        guard fstat(descriptor, &info) == 0, info.st_mode & S_IFMT == S_IFREG, info.st_nlink == 1,
              info.st_size >= 0, UInt64(info.st_size) <= limit else { throw ModuleRuntimeCacheError.unsafeCache }
        if let mode = mode, fchmod(descriptor, mode_t(mode)) != 0 { throw ModuleRuntimeCacheError.unsafeCache }
        var hash = SHA256()
        var bytes: UInt64 = 0
        while let part = try handle.read(upToCount: 1024 * 1024), !part.isEmpty {
            try check()
            bytes += UInt64(part.count)
            guard bytes <= limit else { throw ModuleRuntimeCacheError.unsafeCache }
            hash.update(data: part)
        }
        var after = stat()
        guard fstat(descriptor, &after) == 0, after.st_size == info.st_size, bytes == UInt64(info.st_size),
              after.st_mtimespec.tv_sec == info.st_mtimespec.tv_sec, after.st_mtimespec.tv_nsec == info.st_mtimespec.tv_nsec else {
            throw ModuleRuntimeCacheError.unsafeCache
        }
        return (hash.finalize().map { String(format: "%02x", $0) }.joined(), bytes, UInt16(after.st_mode & 0o7777))
    }

    static func inventory(root: URL, normalize: Bool, check: () throws -> Void = {}) throws -> [ModuleRuntimeFile] {
        try directory(root, create: false)
        var files: [ModuleRuntimeFile] = []
        var total: UInt64 = 0
        func walk(_ folder: URL, prefix: String, depth: Int) throws {
            try check()
            guard depth <= 64 else { throw ModuleRuntimeCacheError.unsafeCache }
            let descriptor = open(folder.path, O_RDONLY | O_NOFOLLOW | O_DIRECTORY)
            guard descriptor >= 0 else { throw ModuleRuntimeCacheError.unsafeCache }
            defer { close(descriptor) }
            var folderInfo = stat()
            guard fstat(descriptor, &folderInfo) == 0,
                  normalize ? fchmod(descriptor, 0o755) == 0 : folderInfo.st_mode & 0o7777 == 0o755 else {
                throw ModuleRuntimeCacheError.unsafeCache
            }
            for item in try FileManager.default.contentsOfDirectory(at: folder, includingPropertiesForKeys: nil) {
                try check()
                let path = prefix + item.lastPathComponent
                if path == "manifest.json" { continue }
                guard files.count < ModuleRuntimeContract.entryLimit, ModuleRuntimeContract.validRelativePath(path) else {
                    throw ModuleRuntimeCacheError.unsafeCache
                }
                var info = stat()
                guard lstat(item.path, &info) == 0 else { throw ModuleRuntimeCacheError.unsafeCache }
                switch info.st_mode & S_IFMT {
                case S_IFDIR:
                    files.append(ModuleRuntimeFile(path: path, kind: "directory", bytes: 0, sha256: nil, target: nil, mode: 0o755))
                    try walk(item, prefix: path + "/", depth: depth + 1)
                case S_IFREG:
                    let expected: UInt16 = path == "node/bin/node" ? 0o755 : 0o644
                    let file = try hashFile(item, mode: normalize ? expected : nil, check: check)
                    total += file.bytes
                    guard total <= ModuleRuntimeContract.treeLimit, file.mode == expected else { throw ModuleRuntimeCacheError.unsafeCache }
                    files.append(ModuleRuntimeFile(path: path, kind: "file", bytes: file.bytes, sha256: file.hash, target: nil, mode: file.mode))
                case S_IFLNK:
                    let target = try FileManager.default.destinationOfSymbolicLink(atPath: item.path)
                    guard ModuleRuntimeContract.containedTarget(path: path, target: target), let resolved = realpath(item.path, nil) else {
                        throw ModuleRuntimeCacheError.unsafeCache
                    }
                    let destination = String(cString: resolved)
                    free(resolved)
                    guard destination.hasPrefix(root.path + "/") else { throw ModuleRuntimeCacheError.unsafeCache }
                    files.append(ModuleRuntimeFile(path: path, kind: "symlink", bytes: UInt64(target.utf8.count),
                        sha256: digest(Data(target.utf8)), target: target, mode: 0))
                default: throw ModuleRuntimeCacheError.unsafeCache
                }
            }
        }
        try walk(root, prefix: "", depth: 0)
        return files.sorted { $0.path < $1.path }
    }
}

/// Bounded native commands only; no shell interpolation, inherited cloud environment or application log.
struct ModuleRuntimeProcess {
    func run(_ executable: String, _ arguments: [String], deadline: Date,
             cancelled: @escaping () -> Bool) throws -> String {
        if cancelled() { throw ModuleRuntimeCacheError.cancelled }
        if Date() >= deadline { throw ModuleRuntimeCacheError.timedOut }
        let capture = FileManager.default.temporaryDirectory.appendingPathComponent("kf-public-runtime-\(UUID().uuidString).out")
        guard FileManager.default.createFile(atPath: capture.path, contents: nil, attributes: [.posixPermissions: 0o600]),
              let output = try? FileHandle(forWritingTo: capture) else { throw ModuleRuntimeCacheError.unavailable }
        defer { try? output.close(); try? FileManager.default.removeItem(at: capture) }
        let process = Process()
        process.executableURL = URL(fileURLWithPath: executable)
        process.arguments = arguments
        process.environment = ["PATH": "/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin",
            "HOME": FileManager.default.homeDirectoryForCurrentUser.path,
            "TMPDIR": FileManager.default.temporaryDirectory.path, "LC_ALL": "C", "LANG": "C"]
        process.standardInput = FileHandle.nullDevice
        process.standardOutput = output
        process.standardError = output
        do { try process.run() } catch { throw ModuleRuntimeCacheError.unavailable }
        var failure: ModuleRuntimeCacheError?
        while process.isRunning {
            if cancelled() { failure = .cancelled }
            else if Date() >= deadline { failure = .timedOut }
            else if ((try? FileManager.default.attributesOfItem(atPath: capture.path)[.size] as? NSNumber)?.int64Value ?? 0) > 8 * 1024 * 1024 {
                failure = .builderFailed
            }
            if failure != nil {
                process.terminate()
                let grace = Date().addingTimeInterval(1)
                while process.isRunning && Date() < grace { Thread.sleep(forTimeInterval: 0.02) }
                if process.isRunning { kill(process.processIdentifier, SIGKILL) }
                break
            }
            Thread.sleep(forTimeInterval: 0.05)
        }
        process.waitUntilExit()
        if let failure = failure { throw failure }
        guard process.terminationStatus == 0 else { throw ModuleRuntimeCacheError.builderFailed }
        let data = try ModuleRuntimeCache.readRegular(capture, limit: 8 * 1024 * 1024)
        guard let result = String(data: data, encoding: .utf8) else { throw ModuleRuntimeCacheError.builderFailed }
        return result
    }
}

/// Fixed official HTTPS endpoint, streaming byte bound, no redirects/proxies/cookies or raw error output.
final class ModuleRuntimeHTTPS: NSObject, URLSessionDataDelegate, URLSessionTaskDelegate {
    private let configuration: URLSessionConfiguration
    private let lock = NSLock()
    private let done = DispatchSemaphore(value: 0)
    private var failure: ModuleRuntimeCacheError?
    private var output: FileHandle?
    private var bytes: Int64 = 0
    private var pin: ModuleRuntimeNodePin?
    private var cancelled: () -> Bool = { false }
    private var deadline = Date.distantPast
    init(configuration: URLSessionConfiguration = .ephemeral) { self.configuration = configuration; super.init() }

    func download(_ pin: ModuleRuntimeNodePin, to destination: URL, deadline: Date,
                  cancelled: @escaping () -> Bool) throws {
        if cancelled() { throw ModuleRuntimeCacheError.cancelled }
        guard Date() < deadline else { throw ModuleRuntimeCacheError.timedOut }
        self.pin = pin; self.cancelled = cancelled; self.deadline = deadline
        guard FileManager.default.createFile(atPath: destination.path, contents: nil, attributes: [.posixPermissions: 0o644]) else {
            throw ModuleRuntimeCacheError.downloadFailed
        }
        output = try FileHandle(forWritingTo: destination)
        defer { try? output?.close(); output = nil }
        configuration.urlCache = nil
        configuration.httpCookieStorage = nil
        configuration.urlCredentialStorage = nil
        configuration.httpShouldSetCookies = false
        configuration.connectionProxyDictionary = [:]
        configuration.timeoutIntervalForRequest = min(30, deadline.timeIntervalSinceNow)
        configuration.timeoutIntervalForResource = min(120, deadline.timeIntervalSinceNow)
        let session = URLSession(configuration: configuration, delegate: self, delegateQueue: nil)
        defer { session.invalidateAndCancel() }
        var request = URLRequest(url: pin.url, cachePolicy: .reloadIgnoringLocalCacheData, timeoutInterval: configuration.timeoutIntervalForRequest)
        request.setValue("identity", forHTTPHeaderField: "Accept-Encoding")
        let task = session.dataTask(with: request)
        task.resume()
        while done.wait(timeout: .now() + .milliseconds(50)) == .timedOut {
            if cancelled() { setFailure(.cancelled); task.cancel() }
            else if Date() >= deadline { setFailure(.timedOut); task.cancel() }
        }
        lock.lock(); let error = failure; lock.unlock()
        if let error = error { throw error }
    }
    private func setFailure(_ error: ModuleRuntimeCacheError) {
        lock.lock(); if failure == nil { failure = error }; lock.unlock()
    }
    func urlSession(_ session: URLSession, task: URLSessionTask, willPerformHTTPRedirection response: HTTPURLResponse,
                    newRequest request: URLRequest, completionHandler: @escaping (URLRequest?) -> Void) {
        setFailure(.downloadFailed)
        completionHandler(nil)
    }
    func urlSession(_ session: URLSession, dataTask: URLSessionDataTask, didReceive response: URLResponse,
                    completionHandler: @escaping (URLSession.ResponseDisposition) -> Void) {
        guard let response = response as? HTTPURLResponse, response.statusCode == 200, response.url == pin?.url,
              response.expectedContentLength <= ModuleRuntimeContract.archiveLimit else {
            setFailure(.downloadFailed); completionHandler(.cancel); return
        }
        completionHandler(.allow)
    }
    func urlSession(_ session: URLSession, dataTask: URLSessionDataTask, didReceive data: Data) {
        if cancelled() { setFailure(.cancelled); dataTask.cancel(); return }
        if Date() >= deadline { setFailure(.timedOut); dataTask.cancel(); return }
        bytes += Int64(data.count)
        guard bytes <= ModuleRuntimeContract.archiveLimit else { setFailure(.downloadFailed); dataTask.cancel(); return }
        do { try output?.write(contentsOf: data) } catch { setFailure(.downloadFailed); dataTask.cancel() }
    }
    func urlSession(_ session: URLSession, task: URLSessionTask, didCompleteWithError error: Error?) {
        if error != nil { setFailure(.downloadFailed) }
        done.signal()
    }
}
