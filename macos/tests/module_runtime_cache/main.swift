import Foundation
import Darwin

// Real native cache implementation; no Docker command, SDK package or user's settings are executed.
struct Docker { let executable: String }
let scenario = CommandLine.arguments[1]
let root = URL(fileURLWithPath: CommandLine.arguments[2])
let source = URL(fileURLWithPath: CommandLine.arguments[3])
let image = "sha256:" + String(repeating: "a", count: 64)
let fm = FileManager.default
try fm.createDirectory(at: root, withIntermediateDirectories: true)
func expect(_ condition: @autoclosure () -> Bool, _ message: String) {
    if !condition() { print(message); exit(1) }
}
func refuses(_ expected: ModuleRuntimeCacheError, _ operation: () throws -> Void) {
    do { try operation(); print("expected \(expected)"); exit(1) }
    catch let error as ModuleRuntimeCacheError { expect(error == expected, "got \(error), expected \(expected)") }
    catch { print("unexpected error type"); exit(1) }
}

final class FixtureSystem: ModuleRuntimeCacheSystem {
    let cacheRoot: URL
    let userID: UInt32 = 501
    var commands: [[String]] = []
    var downloads = 0
    var removeAfterMetadata: URL?
    init(_ root: URL) { cacheRoot = root }
    func command(_ executable: String, _ arguments: [String], deadline: Date,
                 cancelled: @escaping () -> Bool) throws -> String {
        commands.append(arguments)
        if arguments.first == "info" { return "linux|aarch64\n" }
        if arguments.prefix(2) == ["image", "inspect"] {
            if let target = removeAfterMetadata { try FileManager.default.removeItem(at: target) }
            return image + "|linux|arm64\n"
        }
        throw ModuleRuntimeCacheError.builderFailed
    }
    func download(_ pin: ModuleRuntimeNodePin, to destination: URL, deadline: Date,
                  cancelled: @escaping () -> Bool) throws {
        downloads += 1
        try Data("wrong public archive".utf8).write(to: destination)
    }
}

let resources = root.appendingPathComponent("bundle/module-runtime")
try fm.createDirectory(at: resources, withIntermediateDirectories: true)
for name in ModuleRuntimeContract.resourceNames {
    let original = source.appendingPathComponent(name.hasSuffix("json") ? "integrations/harness/" + name : "scripts/" + name)
    try fm.copyItem(at: original, to: resources.appendingPathComponent(name))
}
let paths = AppPaths(support: root.appendingPathComponent("private-unused"),
                     envFile: root.appendingPathComponent("private-unused/never-read.env"),
                     composeFile: root.appendingPathComponent("bundle/compose.yaml"))
let system = FixtureSystem(root.appendingPathComponent("cache"))
let cache = ModuleRuntimeCache(system: system)
let recipe = try ModuleRuntimeCache.recipe(resources: resources, architecture: .arm64)

func populatedCache() throws -> URL {
    let runtime = system.cacheRoot.appendingPathComponent(recipe.directoryName)
    try fm.createDirectory(at: runtime.appendingPathComponent("node/bin"), withIntermediateDirectories: true)
    try fm.createDirectory(at: runtime.appendingPathComponent("bin"), withIntermediateDirectories: true)
    try Data("synthetic Linux node, never executed".utf8).write(to: runtime.appendingPathComponent("node/bin/node"))
    try Data("public license".utf8).write(to: runtime.appendingPathComponent("node/LICENSE"))
    try fm.createSymbolicLink(atPath: runtime.appendingPathComponent("bin/node").path,
                             withDestinationPath: "../node/bin/node")
    for name in ModuleRuntimeContract.resourceNames {
        try fm.copyItem(at: resources.appendingPathComponent(name), to: runtime.appendingPathComponent(name))
    }
    try fm.createDirectory(at: runtime.appendingPathComponent("node_modules"), withIntermediateDirectories: true)
    let files = try ModuleRuntimeCache.inventory(root: runtime, normalize: true)
    let data = try ModuleRuntimeContract.manifestData(recipe: recipe, files: files)
    try data.write(to: runtime.appendingPathComponent("manifest.json"))
    try fm.setAttributes([.posixPermissions: 0o644], ofItemAtPath: runtime.appendingPathComponent("manifest.json").path)
    return runtime
}

final class FixtureHTTP: URLProtocol {
    static var mode = "status"
    override class func canInit(with request: URLRequest) -> Bool { true }
    override class func canonicalRequest(for request: URLRequest) -> URLRequest { request }
    override func startLoading() {
        if Self.mode == "active-cancel" { return }
        let status = Self.mode == "status" ? 503 : Self.mode == "redirect" ? 302 : 200
        let headers = Self.mode == "length" ? ["Content-Length": "999999999"] : ["Location": "https://example.invalid/"]
        let response = HTTPURLResponse(url: request.url!, statusCode: status, httpVersion: "HTTP/1.1", headerFields: headers)!
        client!.urlProtocol(self, didReceive: response, cacheStoragePolicy: .notAllowed)
        client!.urlProtocol(self, didLoad: Data("public bytes".utf8))
        client!.urlProtocolDidFinishLoading(self)
    }
    override func stopLoading() {}
}

switch scenario {
case "pins":
    expect(ModuleRuntimeNodePin(architecture: .arm64).sha256 == "95c264150aceb7f3437a29fd6984924f5f8d1511ea3cbd6c508b83f6c555dae2", "arm64 primary pin")
    expect(ModuleRuntimeNodePin(architecture: .x64).sha256 == "361718c444e49af2ca5a110c83ba6a8901143f23ab285ebbef0341f391f482a9", "x64 primary pin")
    expect(ModuleRuntimeArchitecture(engine: "aarch64") == .arm64, "engine arm64")
    expect(ModuleRuntimeArchitecture(engine: "x86_64") == .x64, "engine x64")
    expect(ModuleRuntimeArchitecture(engine: "darwin") == nil, "unsupported engine")
case "builder":
    let args = try ModuleRuntimeContract.builderArguments(image: image, architecture: .arm64, userID: 501,
        bootstrap: root.appendingPathComponent("bootstrap"), sdk: root.appendingPathComponent("sdk"), nonce: String(repeating: "b", count: 32))
    expect(args.filter { $0 == "--mount" }.count == 2, "only two public binds")
    expect(args.contains("type=bind,source=" + root.appendingPathComponent("bootstrap").path + ",target=/bootstrap,readonly"), "bootstrap read only")
    expect(args.contains("type=bind,source=" + root.appendingPathComponent("sdk").path + ",target=/sdk"), "sdk bind")
    for value in ["--read-only", "ALL", "no-new-privileges:true", "0.5", "512m", "64", "501:501", "linux/arm64",
                  "/data:rw,noexec,nosuid,nodev,size=1m,mode=000", "--ignore-scripts", "--omit=dev", "--no-audit", "--no-fund",
                  "--registry=https://registry.npmjs.org/", "-i", "/bootstrap/node/bin/node",
                  "/bootstrap/node/lib/node_modules/npm/bin/npm-cli.js", "NPM_CONFIG_GLOBALCONFIG=/tmp/npm-globalrc"] { expect(args.contains(value), "missing " + value) }
    expect(!args.contains("--env-file") && !args.contains("-v") && !args.joined().contains("docker.sock"), "private input")
    expect(!args.joined().contains("harness_run") && !args.joined().contains("sh -c"), "no SDK/shell execution")
case "invalid-images":
    for value in ["latest", "ghcr.io/icarus-health/kingfisher-app:1.0.0", image + "x"] {
        refuses(.invalidImage) { _ = try ModuleRuntimeContract.builderArguments(image: value, architecture: .arm64,
            userID: 501, bootstrap: root, sdk: root, nonce: String(repeating: "b", count: 32)) }
    }
case "archive-paths":
    let pin = ModuleRuntimeNodePin(architecture: .arm64)
    try ModuleRuntimeContract.validateArchiveListing("drwxr-xr-x 0 iojs iojs 0 Oct 28 00:33 \(pin.archiveRoot)/\n-rw-r--r-- 0 iojs iojs 1 Oct 28 00:33 \(pin.archiveRoot)/LICENSE\n", pin: pin)
    for line in ["-rw-r--r-- 0 iojs iojs 1 Oct 28 00:33 \(pin.archiveRoot)/../../escape",
                 "prw-r--r-- 0 iojs iojs 1 Oct 28 00:33 \(pin.archiveRoot)/fifo",
                 "lrwxrwxrwx 0 iojs iojs 0 Oct 28 00:33 \(pin.archiveRoot)/bin/npm -> ../../escape",
                 "-rw-r--r-- 0 iojs iojs 1 Oct 28 00:33 /\(pin.archiveRoot)/absolute",
                 "-rw-r--r-- 0 iojs iojs 1 Oct 28 00:33 prefix-\(pin.archiveRoot)/wrong-root"] {
        refuses(.unsafeCache) { try ModuleRuntimeContract.validateArchiveListing(line, pin: pin) }
    }
case "inventory":
    let runtime = try populatedCache()
    let files = try ModuleRuntimeCache.inventory(root: runtime, normalize: false)
    let license = files.first { $0.path == "node/LICENSE" }!
    expect(license.bytes == 14 && license.sha256 == ModuleRuntimeCache.digest(Data("public license".utf8)), "file bytes/hash")
    expect(files.first { $0.path == "bin/node" }?.target == "../node/bin/node", "safe symlink target")
    expect(files.first { $0.path == "node/bin/node" }?.mode == 0o755, "node executable")
    expect(license.mode == 0o644, "public file mode")
case "escaping-link", "special-file", "hard-link":
    let runtime = try populatedCache()
    let bad = runtime.appendingPathComponent("bad")
    if scenario == "escaping-link" { try fm.createSymbolicLink(atPath: bad.path, withDestinationPath: "../../outside") }
    else if scenario == "special-file" { expect(mkfifo(bad.path, 0o600) == 0, "fixture fifo") }
    else { try fm.linkItem(at: runtime.appendingPathComponent("node/LICENSE"), to: bad) }
    refuses(.unsafeCache) { _ = try ModuleRuntimeCache.inventory(root: runtime, normalize: false) }
case "cache-hit":
    let runtime = try populatedCache()
    let result = try cache.prepare(paths: paths, docker: Docker(executable: "/synthetic/docker"), currentImmutableImage: image, progress: { _ in }, cancelled: { false })
    expect(result.hostPath == runtime.path && result.architecture == "arm64", "verified host path")
    expect(result.manifestDigest.count == 64, "manifest digest")
    expect(!result.builtFresh, "an existing cache never supplies first-approval provenance")
    expect(system.downloads == 0 && system.commands.count == 2, "skip download and builder for existing cache")
case "cache-tamper", "extra-file":
    let runtime = try populatedCache()
    try Data("changed".utf8).write(to: runtime.appendingPathComponent(scenario == "extra-file" ? "extra" : "node/LICENSE"))
    refuses(.integrityFailed) { _ = try cache.prepare(paths: paths, docker: Docker(executable: "/synthetic/docker"), currentImmutableImage: image, progress: { _ in }, cancelled: { false }) }
    expect(system.downloads == 0 && fm.fileExists(atPath: runtime.path), "do not remove/adopt damaged cache")
case "resource-tamper":
    try Data("changed lock".utf8).write(to: resources.appendingPathComponent("package-lock.json"))
    refuses(.invalidResources) { _ = try cache.prepare(paths: paths, docker: Docker(executable: "/synthetic/docker"), currentImmutableImage: image, progress: { _ in }, cancelled: { false }) }
    expect(system.commands.isEmpty, "reject resource change before Docker")
case "root-symlink":
    let outside = root.appendingPathComponent("outside")
    try fm.createDirectory(at: outside, withIntermediateDirectories: true)
    try fm.createSymbolicLink(atPath: system.cacheRoot.path, withDestinationPath: outside.path)
    refuses(.unsafeCache) { _ = try cache.prepare(paths: paths, docker: Docker(executable: "/synthetic/docker"), currentImmutableImage: image, progress: { _ in }, cancelled: { false }) }
    let contents = try fm.contentsOfDirectory(atPath: outside.path)
    expect(contents.isEmpty, "no write through cache root symlink")
case "manifest-mode":
    let runtime = try populatedCache()
    try fm.setAttributes([.posixPermissions: 0o666], ofItemAtPath: runtime.appendingPathComponent("manifest.json").path)
    refuses(.unsafeCache) { _ = try cache.prepare(paths: paths, docker: Docker(executable: "/synthetic/docker"), currentImmutableImage: image, progress: { _ in }, cancelled: { false }) }
case "mutable-manifest":
    let runtime = try populatedCache()
    let old = ModuleRuntimeCache.digest(try Data(contentsOf: runtime.appendingPathComponent("manifest.json")))
    try Data("changed public license".utf8).write(to: runtime.appendingPathComponent("node/LICENSE"))
    let files = try ModuleRuntimeCache.inventory(root: runtime, normalize: false)
    try ModuleRuntimeContract.manifestData(recipe: recipe, files: files).write(to: runtime.appendingPathComponent("manifest.json"))
    let result = try cache.prepare(paths: paths, docker: Docker(executable: "/synthetic/docker"), currentImmutableImage: image, progress: { _ in }, cancelled: { false })
    expect(result.manifestDigest != old, "private approved digest must detect public tree plus manifest replacement")
    expect(!result.builtFresh, "mutable public manifest cannot enroll itself")
    refuses(.integrityFailed) {
        _ = try cache.verifiedExisting(paths: paths, docker: Docker(executable: "/synthetic/docker"), currentImmutableImage: image,
            approvedHostPath: runtime.path, expectedManifestDigest: old)
    }
case "verified-existing", "verified-existing-digest", "verified-existing-deleted", "verified-existing-path":
    let runtime = try populatedCache()
    let expected = ModuleRuntimeCache.digest(try Data(contentsOf: runtime.appendingPathComponent("manifest.json")))
    if scenario == "verified-existing-deleted" { system.removeAfterMetadata = runtime }
    func verify() throws -> VerifiedRuntime {
        try cache.verifiedExisting(paths: paths, docker: Docker(executable: "/synthetic/docker"), currentImmutableImage: image,
            approvedHostPath: scenario == "verified-existing-path" ? root.path : runtime.path,
            expectedManifestDigest: scenario == "verified-existing-digest" ? String(repeating: "b", count: 64) : expected)
    }
    if scenario == "verified-existing" {
        let result = try verify()
        expect(result.hostPath == runtime.path && result.manifestDigest == expected && !result.builtFresh, "read-only private digest binding")
    } else { refuses(scenario == "verified-existing-digest" ? .integrityFailed : .unsafeCache) { _ = try verify() } }
    expect(system.downloads == 0 && system.commands.allSatisfy { $0.first == "info" || $0.prefix(2) == ["image", "inspect"] }, "no download/build/start fallback, even after deletion")
case "publish-cancel", "publish-deadline", "publish-commit-cancel", "publish-commit-deadline", "publish-cleanup-retry", "publish-existing":
    let final = try populatedCache()
    let template = root.appendingPathComponent("template")
    try fm.moveItem(at: final, to: template)
    func stage(_ character: String) throws -> (root: URL, sdk: URL, identity: String) {
        let folder = system.cacheRoot.appendingPathComponent(".prepare-" + String(repeating: character, count: 32))
        try fm.createDirectory(at: folder, withIntermediateDirectories: true)
        let sdk = folder.appendingPathComponent("sdk")
        try fm.copyItem(at: template, to: sdk)
        var info = stat(); expect(lstat(folder.path, &info) == 0, "owned publishing stage")
        return (folder, sdk, "\(info.st_dev):\(info.st_ino)")
    }
    let prepared = try stage("f")
    let pending = system.cacheRoot.appendingPathComponent(".pending-" + String(repeating: "f", count: 32))
    var replaced = false
    func check() throws {
        if scenario == "publish-cancel" && ModuleRuntimeCache.exists(pending) { throw ModuleRuntimeCacheError.cancelled }
        if scenario == "publish-deadline" && ModuleRuntimeCache.exists(pending) { throw ModuleRuntimeCacheError.timedOut }
        if scenario == "publish-commit-cancel" && ModuleRuntimeCache.exists(final) { throw ModuleRuntimeCacheError.cancelled }
        if scenario == "publish-commit-deadline" && ModuleRuntimeCache.exists(final) { throw ModuleRuntimeCacheError.timedOut }
        if scenario == "publish-cleanup-retry" && ModuleRuntimeCache.exists(pending) && !replaced {
            replaced = true
            try fm.moveItem(at: prepared.root, to: root.appendingPathComponent("saved-owned-stage"))
            try fm.createDirectory(at: prepared.root, withIntermediateDirectories: true)
            try Data("foreign replacement".utf8).write(to: prepared.root.appendingPathComponent("sentinel"))
        }
    }
    func publish() throws -> VerifiedRuntime {
        try ModuleRuntimeCache.publishVerifiedStage(sdk: prepared.sdk, stage: prepared.root,
            stageIdentity: prepared.identity, final: final, recipe: recipe, deadline: Date().addingTimeInterval(10), check: check)
    }
    if ["publish-cancel", "publish-deadline", "publish-cleanup-retry"].contains(scenario) {
        let error: ModuleRuntimeCacheError = scenario == "publish-cancel" ? .cancelled : scenario == "publish-deadline" ? .timedOut : .cleanupRequired
        refuses(error) { _ = try publish() }
        expect(!ModuleRuntimeCache.exists(final) && !ModuleRuntimeCache.exists(pending), "failed fresh operation cannot block the final cache path")
        if scenario == "publish-cleanup-retry" {
            expect(fm.fileExists(atPath: prepared.root.appendingPathComponent("sentinel").path), "preserve replacement directory")
        }
        let retry = try stage("d")
        let result = try ModuleRuntimeCache.publishVerifiedStage(sdk: retry.sdk, stage: retry.root,
            stageIdentity: retry.identity, final: final, recipe: recipe, deadline: Date().addingTimeInterval(10))
        expect(result.builtFresh && ModuleRuntimeCache.exists(final), "retry remains a provable fresh build")
    } else {
        var existingDigest: String?
        var existingInode: UInt64?
        if scenario == "publish-existing" {
            try fm.copyItem(at: template, to: final)
            try Data("unapproved existing public license".utf8).write(to: final.appendingPathComponent("node/LICENSE"))
            let inventory = try ModuleRuntimeCache.inventory(root: final, normalize: false)
            let manifest = try ModuleRuntimeContract.manifestData(recipe: recipe, files: inventory)
            try manifest.write(to: final.appendingPathComponent("manifest.json"))
            existingDigest = ModuleRuntimeCache.digest(manifest)
            var info = stat(); expect(lstat(final.path, &info) == 0, "existing cache stat")
            existingInode = UInt64(info.st_ino)
        }
        let result = try publish()
        expect(result.builtFresh == (scenario != "publish-existing"), "only own atomic publication earns fresh provenance")
        if scenario == "publish-existing" {
            var info = stat(); expect(lstat(final.path, &info) == 0, "existing cache still present")
            expect(result.manifestDigest == existingDigest && UInt64(info.st_ino) == existingInode, "never replace or enroll unknown existing cache")
            let license = try ModuleRuntimeCache.readRegular(final.appendingPathComponent("node/LICENSE"), limit: 100)
            expect(license == Data("unapproved existing public license".utf8), "existing contents unchanged")
        }
        expect(!ModuleRuntimeCache.exists(pending) && !ModuleRuntimeCache.exists(prepared.root), "staging is cleaned before final publication")
        _ = try ModuleRuntimeCache.verify(final, recipe: recipe)
    }
case "staging-metadata":
    let runtime = try populatedCache()
    let stage = root.appendingPathComponent(".prepare-" + String(repeating: "e", count: 32))
    try fm.createDirectory(at: stage, withIntermediateDirectories: true)
    let sdk = stage.appendingPathComponent("sdk")
    try fm.copyItem(at: runtime, to: sdk)
    for path in [".DS_Store", "node_modules/.DS_Store"] { try Data("synthetic OS metadata".utf8).write(to: sdk.appendingPathComponent(path)) }
    refuses(.unsafeCache) { try ModuleRuntimeCache.cleanStagingMetadata(runtime) }
    try ModuleRuntimeCache.cleanStagingMetadata(sdk)
    expect(!fm.fileExists(atPath: sdk.appendingPathComponent(".DS_Store").path), "remove only staged OS metadata")
    let license = try ModuleRuntimeCache.readRegular(sdk.appendingPathComponent("node/LICENSE"), limit: 100)
    expect(license == Data("public license".utf8), "preserve license")
    _ = try ModuleRuntimeCache.verify(sdk, recipe: recipe)
    try Data("late OS metadata".utf8).write(to: sdk.appendingPathComponent(".DS_Store"))
    refuses(.integrityFailed) { _ = try ModuleRuntimeCache.verify(sdk, recipe: recipe) }
case "manifest-fifo":
    let runtime = try populatedCache()
    let manifest = runtime.appendingPathComponent("manifest.json")
    try fm.removeItem(at: manifest)
    expect(mkfifo(manifest.path, 0o644) == 0, "manifest fifo fixture")
    refuses(.unsafeCache) { _ = try ModuleRuntimeCache.verify(runtime, recipe: recipe) }
case "resource-fifo":
    let package = resources.appendingPathComponent("package.json")
    try fm.removeItem(at: package)
    expect(mkfifo(package.path, 0o644) == 0, "resource fifo fixture")
    refuses(.invalidResources) { _ = try ModuleRuntimeCache.recipe(resources: resources, architecture: .arm64) }
case "hash-fifo":
    let file = root.appendingPathComponent("fifo")
    expect(mkfifo(file.path, 0o644) == 0, "hash fifo fixture")
    refuses(.unsafeCache) { _ = try ModuleRuntimeCache.hashFile(file) }
case "cleanup-scope":
    let stage = root.appendingPathComponent(".prepare-" + String(repeating: "d", count: 32))
    try fm.createDirectory(at: stage, withIntermediateDirectories: true)
    try Data("owned public data".utf8).write(to: stage.appendingPathComponent("file"))
    refuses(.cleanupRequired) { try ModuleRuntimeCache.removeOwnedStage(stage, identity: "not-owned", deadline: Date().addingTimeInterval(1)) }
    expect(fm.fileExists(atPath: stage.appendingPathComponent("file").path), "never remove a different inode")
    var info = stat(); expect(lstat(stage.path, &info) == 0, "owned fixture stat")
    try ModuleRuntimeCache.removeOwnedStage(stage, identity: "\(info.st_dev):\(info.st_ino)", deadline: Date().addingTimeInterval(1))
    expect(!fm.fileExists(atPath: stage.path), "owned stage removed")
case "cancelled":
    refuses(.cancelled) { _ = try cache.prepare(paths: paths, docker: Docker(executable: "/synthetic/docker"), currentImmutableImage: image, progress: { _ in }, cancelled: { true }) }
    expect(system.commands.isEmpty && !fm.fileExists(atPath: system.cacheRoot.path), "cancel before side effects")
case "wrong-download":
    refuses(.integrityFailed) { _ = try cache.prepare(paths: paths, docker: Docker(executable: "/synthetic/docker"), currentImmutableImage: image, progress: { _ in }, cancelled: { false }) }
    expect(system.downloads == 1 && system.commands.count == 2, "no builder for bad archive")
    let remaining = try fm.contentsOfDirectory(atPath: system.cacheRoot.path)
    expect(remaining.isEmpty, "owned staging removed")
case "http-status", "http-redirect", "http-length", "http-cancelled", "http-active-cancel":
    FixtureHTTP.mode = String(scenario.dropFirst(5))
    let configuration = URLSessionConfiguration.ephemeral
    configuration.protocolClasses = [FixtureHTTP.self]
    let download = ModuleRuntimeHTTPS(configuration: configuration)
    let started = Date()
    refuses(scenario.contains("cancel") ? .cancelled : .downloadFailed) {
        try download.download(ModuleRuntimeNodePin(architecture: .arm64), to: root.appendingPathComponent("download"),
                              deadline: Date().addingTimeInterval(5),
                              cancelled: { scenario == "http-cancelled" || (scenario == "http-active-cancel" && Date().timeIntervalSince(started) > 0.1) })
    }
case "process-environment":
    setenv("KF_TEST_API_KEY", "synthetic-never-forward", 1)
    setenv("DOCKER_HOST", "synthetic-never-forward", 1)
    let command = ModuleRuntimeProcess()
    let output = try command.run("/usr/bin/env", [], deadline: Date().addingTimeInterval(3), cancelled: { false })
    expect(!output.contains("ICARUS_") && !output.contains("API_KEY") && !output.contains("DOCKER_HOST"), "no inherited private environment")
    expect(output.contains("PATH="), "fixed process path")
case "process-cancelled", "process-active-cancel", "process-timeout":
    let command = ModuleRuntimeProcess()
    let started = Date()
    refuses(scenario == "process-timeout" ? .timedOut : .cancelled) {
        _ = try command.run("/bin/sleep", ["10"], deadline: started.addingTimeInterval(scenario == "process-timeout" ? 0.1 : 3),
                            cancelled: { scenario == "process-cancelled" || (scenario == "process-active-cancel" && Date().timeIntervalSince(started) > 0.1) })
    }
default: print("unknown scenario"); exit(1)
}
print("{\"passed\":\"\(scenario)\"}")
