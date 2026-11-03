import Foundation
import Darwin

// Explicit public-only integration probe, never run by the synthetic pytest suite.
// Every cache/staging path is inside an explicitly owned public probe root. No app is installed or started.
struct Docker { let executable: String }
let root = URL(fileURLWithPath: CommandLine.arguments[1])
let source = URL(fileURLWithPath: CommandLine.arguments[2])
let archive = URL(fileURLWithPath: CommandLine.arguments[3])
let docker = Docker(executable: CommandLine.arguments[4])
let image = "sha256:6624c90d391bf226a4e0541df7ed96d08a3785ca0681da6b9330ab16dc1f45a0"
final class PublicProbeSystem: ModuleRuntimeCacheSystem {
    let cacheRoot = root.appendingPathComponent("cache")
    var userID: UInt32 { getuid() }
    var commands: [[String]] = []
    var receipts: [[String: Any]] = []
    var downloads = 0
    func capturePublicMetadata() {
        guard let create = commands.first(where: { $0.first == "create" }),
              let bind = create.first(where: { $0.hasPrefix("type=bind,source=") && $0.hasSuffix(",target=/sdk") }) else { return }
        let path = String(bind.dropFirst("type=bind,source=".count).dropLast(",target=/sdk".count))
        let sdk = URL(fileURLWithPath: path)
        var bad: [[String: Any]] = [], count = 0, bytes: Int64 = 0, modes: [String: Int] = [:]
        if let items = FileManager.default.enumerator(at: sdk, includingPropertiesForKeys: nil) {
            while let item = items.nextObject() as? URL {
                var info = stat(); if lstat(item.path, &info) != 0 { continue }
                count += 1
                let relative = String(item.path.dropFirst(sdk.path.count + 1))
                let kind = info.st_mode & S_IFMT
                let mode = String(info.st_mode & 0o7777, radix: 8)
                modes["\(kind):\(mode)", default: 0] += 1
                var reason = ""
                if kind == S_IFREG {
                    bytes += info.st_size
                    if info.st_nlink != 1 { reason = "hardlink" }
                    if UInt64(info.st_size) > ModuleRuntimeContract.fileLimit { reason = "file-bound" }
                    if info.st_mode & 0o400 == 0 { reason = "not-owner-readable" }
                } else if kind == S_IFLNK {
                    let target = (try? FileManager.default.destinationOfSymbolicLink(atPath: item.path)) ?? ""
                    if !ModuleRuntimeContract.containedTarget(path: relative, target: target) { reason = "escaping-link" }
                    if let resolved = realpath(item.path, nil) {
                        if !String(cString: resolved).hasPrefix(sdk.path + "/") { reason = "escaping-link" }; free(resolved)
                    } else { reason = "dangling-link" }
                } else if kind != S_IFDIR { reason = "special" }
                if !reason.isEmpty { bad.append(["path": relative, "reason": reason, "mode": mode, "links": info.st_nlink, "bytes": info.st_size]) }
            }
        }
        if let data = try? JSONSerialization.data(withJSONObject: ["entries": count, "bytes": bytes, "bad": bad, "modes": modes], options: [.sortedKeys]) {
            try? data.write(to: root.appendingPathComponent("public-metadata.json"))
        }
    }
    func command(_ executable: String, _ arguments: [String], deadline: Date,
                 cancelled: @escaping () -> Bool) throws -> String {
        commands.append(arguments)
        // Public probe diagnostics only. Product preparation never exposes npm output.
        let capture = root.appendingPathComponent("public-command-\(commands.count).out")
        FileManager.default.createFile(atPath: capture.path, contents: nil, attributes: [.posixPermissions: 0o644])
        let handle = try FileHandle(forWritingTo: capture)
        defer { try? handle.close() }
        let process = Process()
        process.executableURL = URL(fileURLWithPath: executable)
        process.arguments = arguments
        process.environment = ["PATH": "/opt/homebrew/bin:/usr/bin:/bin", "HOME": FileManager.default.homeDirectoryForCurrentUser.path,
            "TMPDIR": root.path, "LC_ALL": "C", "LANG": "C"]
        process.standardInput = FileHandle.nullDevice
        process.standardOutput = handle
        process.standardError = handle
        try process.run()
        while process.isRunning {
            if Date() >= deadline || cancelled() { process.terminate(); Thread.sleep(forTimeInterval: 0.1); if process.isRunning { kill(process.processIdentifier, SIGKILL) }; break }
            if ((try? FileManager.default.attributesOfItem(atPath: capture.path)[.size] as? NSNumber)?.intValue ?? 0) > 8 * 1024 * 1024 {
                kill(process.processIdentifier, SIGKILL); break
            }
            Thread.sleep(forTimeInterval: 0.05)
        }
        process.waitUntilExit()
        receipts.append(["arguments": arguments, "status": process.terminationStatus, "output": capture.lastPathComponent])
        try JSONSerialization.data(withJSONObject: receipts, options: [.sortedKeys]).write(to: root.appendingPathComponent("commands.json"))
        guard process.terminationStatus == 0 else { throw ModuleRuntimeCacheError.builderFailed }
        let result = String(data: try ModuleRuntimeCache.readRegular(capture, limit: 8 * 1024 * 1024), encoding: .utf8)!
        if arguments.first == "create" {
            let id = result.trimmingCharacters(in: .whitespacesAndNewlines)
            guard ModuleRuntimeContract.validDigest(id) else { throw ModuleRuntimeCacheError.builderFailed }
            let format = #"{"mounts":{{json .Mounts}},"host":{{json .HostConfig}},"user":{{json .Config.User}},"entrypoint":{{json .Config.Entrypoint}},"command":{{json .Config.Cmd}},"health":{{json .Config.Healthcheck}}}"#
            let inspected = try ModuleRuntimeProcess().run(executable, ["inspect", "--format", format, id], deadline: deadline, cancelled: cancelled)
            let object = try JSONSerialization.jsonObject(with: Data(inspected.utf8)) as! [String: Any]
            let host = object["host"] as! [String: Any]
            let mounts = object["mounts"] as! [[String: Any]]
            guard mounts.count == 2, Set(mounts.compactMap { $0["Destination"] as? String }) == Set(["/bootstrap", "/sdk"]),
                  mounts.allSatisfy({ $0["Type"] as? String == "bind" }),
                  host["ReadonlyRootfs"] as? Bool == true, host["Privileged"] as? Bool == false,
                  (host["Memory"] as? NSNumber)?.intValue == 512 * 1024 * 1024,
                  (host["NanoCpus"] as? NSNumber)?.intValue == 500_000_000,
                  (host["PidsLimit"] as? NSNumber)?.intValue == 64,
                  host["CapDrop"] as? [String] == ["ALL"], host["SecurityOpt"] as? [String] == ["no-new-privileges:true"],
                  object["entrypoint"] as? [String] == ["/usr/bin/env"], (object["command"] as? [String])?.first == "-i" else {
                throw ModuleRuntimeCacheError.builderFailed
            }
            try Data(inspected.utf8).write(to: root.appendingPathComponent("builder-boundary.json"))
        }
        return result
    }
    func download(_ pin: ModuleRuntimeNodePin, to destination: URL, deadline: Date,
                  cancelled: @escaping () -> Bool) throws {
        guard pin.architecture == .arm64 else { throw ModuleRuntimeCacheError.unsupportedArchitecture }
        downloads += 1
        if CommandLine.arguments.count > 5 && CommandLine.arguments[5] == "official-https" {
            try ModuleRuntimeHTTPS().download(pin, to: destination, deadline: deadline, cancelled: cancelled)
        } else { try FileManager.default.copyItem(at: archive, to: destination) }
        // prepare still performs its real hardcoded official archive SHA256 check.
    }
}
do {
    guard root.path.hasPrefix("/private/tmp/kf-native-runtime-cache-work-20261102/")
        || root.path.hasPrefix("/Users/sorenkube/Documents/Codex/2026-09-19/github-plugin-github-openai-curated-remote-3/.superpowers/kf-native-runtime-cache-probe-")
        || root.path.hasPrefix("/Users/sorenkube/Library/Caches/KingfisherModulesProbe-") else { exit(2) }
    let resources = root.appendingPathComponent("bundle/module-runtime")
    try FileManager.default.createDirectory(at: resources, withIntermediateDirectories: true)
    for name in ModuleRuntimeContract.resourceNames {
        let original = source.appendingPathComponent(name.hasSuffix("json") ? "integrations/harness/" + name : "scripts/" + name)
        let target = resources.appendingPathComponent(name)
        if !FileManager.default.fileExists(atPath: target.path) { try FileManager.default.copyItem(at: original, to: target) }
    }
    let paths = AppPaths(support: root.appendingPathComponent("private-unused"),
        envFile: root.appendingPathComponent("private-unused/never-read.env"), composeFile: root.appendingPathComponent("bundle/compose.yaml"))
    let system = PublicProbeSystem()
    let started = Date()
    let result = try ModuleRuntimeCache(system: system).prepare(paths: paths, docker: docker,
        currentImmutableImage: image, progress: {
            print($0.message); fflush(stdout)
            if $0 == .verifying {
                system.capturePublicMetadata()
                if CommandLine.arguments.contains("preserve-stage") { print("public-stage-preserved"); exit(90) }
            }
        }, cancelled: { false })
    let firstCommands = system.commands
    let second = try ModuleRuntimeCache(system: system).prepare(paths: paths, docker: docker,
        currentImmutableImage: image, progress: { _ in }, cancelled: { false })
    guard result.hostPath == second.hostPath, result.manifestDigest == second.manifestDigest,
          result.architecture == second.architecture, result.builtFresh, !second.builtFresh, system.downloads == 1,
          !system.commands.dropFirst(firstCommands.count).contains(where: { $0.first == "create" }) else { exit(3) }
    let data = try JSONSerialization.data(withJSONObject: ["hostPath": result.hostPath, "manifestDigest": result.manifestDigest,
        "architecture": result.architecture, "seconds": Date().timeIntervalSince(started),
        "downloads": system.downloads, "commands": system.commands, "reuseVerified": true,
        "builtFresh": result.builtFresh, "reuseBuiltFresh": second.builtFresh], options: [.sortedKeys])
    try data.write(to: root.appendingPathComponent("result.json"))
    print("public-cache-ready " + result.manifestDigest)
} catch let error as ModuleRuntimeCacheError {
    print("public-cache-failed " + error.rawValue)
    exit(1)
} catch {
    print("public-cache-failed unexpected-test-io")
    exit(1)
}
