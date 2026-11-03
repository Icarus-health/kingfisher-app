import Foundation

enum ModuleSetupPhase: String {
    case checking, downloading, installing, verifying, ready, cancelled, failed, unavailable
    var message: String {
        switch self {
        case .checking: return "Öffentliche Laufzeit prüfen …"
        case .downloading: return "Node-Laufzeit laden …"
        case .installing: return "Öffentliche Pakete vorbereiten …"
        case .verifying: return "Laufzeit prüfen …"
        case .ready: return "Lokale Laufzeit ist bereit."
        case .cancelled: return "Die Vorbereitung wurde abgebrochen."
        case .failed: return "Die lokale Laufzeit konnte nicht vorbereitet werden."
        case .unavailable: return "Die lokale Laufzeit ist noch nicht eingerichtet."
        }
    }
}

// Closed public-runtime inputs. This contract carries no provider, key, personal path or worker authority.
enum ModuleRuntimeCacheError: String, Error {
    case cancelled, timedOut, unsupportedArchitecture, invalidImage, invalidResources
    case downloadFailed, integrityFailed, unsafeCache, builderFailed, unavailable, cleanupRequired, busy

    var message: String {
        switch self {
        case .cancelled: return "Die Vorbereitung wurde abgebrochen."
        case .timedOut: return "Die Vorbereitung hat zu lange gedauert. Bitte versuche es erneut."
        case .cleanupRequired: return "Die Vorbereitung konnte ihre eigenen Testressourcen nicht vollständig aufräumen."
        case .busy: return "Die lokale Laufzeit wird bereits vorbereitet."
        default: return "Die öffentliche Laufzeit konnte nicht sicher vorbereitet werden."
        }
    }
}

enum ModuleRuntimeArchitecture: String, Codable {
    case arm64, x64
    init?(engine: String) {
        switch engine {
        case "arm64", "aarch64": self = .arm64
        case "amd64", "x86_64", "x64": self = .x64
        default: return nil
        }
    }
    var dockerPlatform: String { self == .arm64 ? "linux/arm64" : "linux/amd64" }
}

struct ModuleRuntimeNodePin {
    let architecture: ModuleRuntimeArchitecture
    static let version = "24.22.2"
    // Primary source verified 2026-11-02: https://nodejs.org/dist/v24.22.2/SHASUMS256.txt
    var sha256: String {
        architecture == .arm64
            ? "95c264150aceb7f3437a29fd6984924f5f8d1511ea3cbd6c508b83f6c555dae2"
            : "361718c444e49af2ca5a110c83ba6a8901143f23ab285ebbef0341f391f482a9"
    }
    var archiveRoot: String { "node-v\(Self.version)-linux-\(architecture.rawValue)" }
    var url: URL { URL(string: "https://nodejs.org/dist/v\(Self.version)/\(archiveRoot).tar.gz")! }
}

struct VerifiedRuntime: Equatable {
    let hostPath: String
    /// Integrity digest; the caller must bind this to private approved state. It is not OS attestation.
    let manifestDigest: String
    let architecture: String
    /// Native operation provenance only; never encoded in or recovered from the mutable public manifest.
    let builtFresh: Bool
    init(hostPath: String, manifestDigest: String, architecture: String, builtFresh: Bool = false) {
        self.hostPath = hostPath
        self.manifestDigest = manifestDigest
        self.architecture = architecture
        self.builtFresh = builtFresh
    }
}

struct ModuleRuntimeRecipe {
    let architecture: ModuleRuntimeArchitecture
    let resourceHashes: [String: String]
    let digest: String
    var directoryName: String { "runtime-v1-\(architecture.rawValue)-\(digest)" }
}

struct ModuleRuntimeFile: Codable, Equatable {
    let path: String
    let kind: String
    let bytes: UInt64
    let sha256: String?
    let target: String?
    let mode: UInt16
}

enum ModuleRuntimeContract {
    static let lockSHA256 = "b9c37928b69fc90ea9e8d1f76dabe0696f14c000e36ec54d814e278709ded294"
    static let packageSHA256 = "96540cec1e43381925c2d25624bf3cb08f628d7cdbe44a42150ddcde7c034731"
    static let resourceNames = ["package.json", "package-lock.json", "harness_run.mjs", "harness_service.mjs",
                                "harness_worker.mjs", "harness_gateway.py"]
    static let ownerLabel = "local.kingfisher.module-runtime-builder"
    static let archiveLimit: Int64 = 64 * 1024 * 1024
    static let fileLimit: UInt64 = 256 * 1024 * 1024
    static let treeLimit: UInt64 = 2 * 1024 * 1024 * 1024
    static let entryLimit = 60_000

    static func validDigest(_ value: String) -> Bool {
        value.count == 64 && value.utf8.allSatisfy { (48...57).contains($0) || (97...102).contains($0) }
    }
    static func validImage(_ value: String) -> Bool {
        value.hasPrefix("sha256:") && validDigest(String(value.dropFirst(7)))
    }
    static func validRelativePath(_ value: String) -> Bool {
        !value.isEmpty && value.utf8.count <= 1024 && !value.hasPrefix("/") && !value.contains("\\")
            && !value.unicodeScalars.contains(where: { $0.value < 32 || $0.value == 127 })
            && value.split(separator: "/", omittingEmptySubsequences: false).allSatisfy { !$0.isEmpty && $0 != "." && $0 != ".." }
    }
    static func containedTarget(path: String, target: String) -> Bool {
        guard validRelativePath(path), !target.isEmpty, !target.hasPrefix("/"), !target.contains("\\"),
              !target.unicodeScalars.contains(where: { $0.value < 32 || $0.value == 127 }) else { return false }
        var components = path.split(separator: "/").dropLast().map(String.init)
        for component in target.split(separator: "/", omittingEmptySubsequences: false) {
            if component == ".." { if components.isEmpty { return false }; components.removeLast() }
            else if component != "." && !component.isEmpty { components.append(String(component)) }
        }
        return !components.isEmpty && components.count <= 64
    }

    static func identityData(architecture: ModuleRuntimeArchitecture, hashes: [String: String]) throws -> Data {
        guard Set(hashes.keys) == Set(resourceNames), hashes.values.allSatisfy(validDigest),
              hashes["package.json"] == packageSHA256, hashes["package-lock.json"] == lockSHA256 else {
            throw ModuleRuntimeCacheError.invalidResources
        }
        return try JSONSerialization.data(withJSONObject: ["schema": 1, "nodeVersion": ModuleRuntimeNodePin.version,
            "architecture": architecture.rawValue, "nodeArchiveSHA256": ModuleRuntimeNodePin(architecture: architecture).sha256,
            "resources": hashes], options: [.sortedKeys, .withoutEscapingSlashes])
    }

    static func manifestData(recipe: ModuleRuntimeRecipe, files: [ModuleRuntimeFile]) throws -> Data {
        struct Manifest: Encodable {
            let schema = 1
            let nodeVersion = ModuleRuntimeNodePin.version
            let architecture: String
            let nodeArchiveSHA256: String
            let recipeDigest: String
            let resources: [String: String]
            let files: [ModuleRuntimeFile]
        }
        let encoder = JSONEncoder()
        encoder.outputFormatting = [.sortedKeys, .withoutEscapingSlashes]
        return try encoder.encode(Manifest(architecture: recipe.architecture.rawValue,
            nodeArchiveSHA256: ModuleRuntimeNodePin(architecture: recipe.architecture).sha256,
            recipeDigest: recipe.digest, resources: recipe.resourceHashes, files: files))
    }

    /// Reject traversal, special files and links outside the one verified official archive root before extraction.
    static func validateArchiveListing(_ listing: String, pin: ModuleRuntimeNodePin) throws {
        let lines = listing.split(separator: "\n")
        guard !lines.isEmpty, lines.count <= 30_000, listing.utf8.count <= 8 * 1024 * 1024 else {
            throw ModuleRuntimeCacheError.unsafeCache
        }
        var total: UInt64 = 0
        for line in lines {
            // Fixed LC_ALL=C bsdtar columns: mode, links, user, group, bytes, month, day, time/year, path.
            // Extract the actual path column; a substring search would hide a leading slash or wrong root.
            let columns = line.split(maxSplits: 8, whereSeparator: \.isWhitespace)
            guard columns.count == 9, let type = columns[0].first, ["-", "d", "l"].contains(String(type)),
                  let bytes = UInt64(columns[4]), bytes <= fileLimit else { throw ModuleRuntimeCacheError.unsafeCache }
            total += bytes
            guard total <= treeLimit else { throw ModuleRuntimeCacheError.unsafeCache }
            let payload = String(columns[8])
            let fields = payload.components(separatedBy: " -> ")
            var path = fields[0]
            if path.hasSuffix("/") { path.removeLast() }
            guard validRelativePath(path), path == pin.archiveRoot || path.hasPrefix(pin.archiveRoot + "/"),
                  (type == "l" ? fields.count == 2 : fields.count == 1) else { throw ModuleRuntimeCacheError.unsafeCache }
            if type == "l" {
                let relative = String(path.dropFirst(pin.archiveRoot.count + 1))
                guard containedTarget(path: relative, target: fields[1]) else { throw ModuleRuntimeCacheError.unsafeCache }
            }
        }
    }

    static func builderArguments(image: String, architecture: ModuleRuntimeArchitecture, userID: UInt32,
                                 bootstrap: URL, sdk: URL, nonce: String) throws -> [String] {
        guard validImage(image) else { throw ModuleRuntimeCacheError.invalidImage }
        guard userID > 0, nonce.count == 32, validDigest(nonce + nonce),
              [bootstrap.path, sdk.path].allSatisfy({ $0.hasPrefix("/") && $0 != "/" && !$0.contains(",")
                  && !$0.unicodeScalars.contains(where: { $0.value < 32 || $0.value == 127 }) }) else {
            throw ModuleRuntimeCacheError.unsafeCache
        }
        return ["create", "--name", "kingfisher-runtime-build-" + nonce, "--label", ownerLabel + "=" + nonce,
            "--pull=never", "--platform", architecture.dockerPlatform, "--user", "\(userID):\(userID)",
            "--cap-drop", "ALL", "--security-opt", "no-new-privileges:true", "--read-only",
            "--cpus", "0.5", "--memory", "512m", "--pids-limit", "64", "--log-driver", "none", "--no-healthcheck",
            "--network", "bridge", "--workdir", "/sdk",
            "--tmpfs", "/tmp:rw,noexec,nosuid,nodev,size=256m,mode=1777",
            "--tmpfs", "/data:rw,noexec,nosuid,nodev,size=1m,mode=000",
            "--mount", "type=bind,source=\(bootstrap.path),target=/bootstrap,readonly",
            "--mount", "type=bind,source=\(sdk.path),target=/sdk", "--entrypoint", "/usr/bin/env", image,
            "-i", "PATH=/bootstrap/node/bin:/usr/bin:/bin", "HOME=/tmp", "TMPDIR=/tmp",
            "NPM_CONFIG_USERCONFIG=/dev/null", "NPM_CONFIG_GLOBALCONFIG=/tmp/npm-globalrc", "NPM_CONFIG_CACHE=/tmp/npm-cache",
            "NPM_CONFIG_LOGS_MAX=0", "NPM_CONFIG_UPDATE_NOTIFIER=false", "/bootstrap/node/bin/node",
            "/bootstrap/node/lib/node_modules/npm/bin/npm-cli.js", "ci", "--ignore-scripts", "--omit=dev",
            "--no-audit", "--no-fund", "--registry=https://registry.npmjs.org/", "--loglevel=error"]
    }
}
