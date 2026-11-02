import Foundation

// Exercise production Docker, Startup, Updater and EnvStore; only command/HTTP boundaries are synthetic.
// Nothing here launches Docker, reads a user's environment file, or contacts the real loopback service.
let directory = URL(fileURLWithPath: CommandLine.arguments[2])
let scenario = CommandLine.arguments[1]
let oldImage = "ghcr.io/icarus-health/kingfisher-app:1.0.0"
let oldID = "sha256:" + String(repeating: "a", count: 64)
let newID = "sha256:" + String(repeating: "b", count: 64)
let paths = AppPaths(support: directory, envFile: directory.appendingPathComponent("kingfisher.env"),
                     composeFile: directory.appendingPathComponent("compose.yaml"))
var currentImage = oldImage
var currentID = oldID
var mainPresent = scenario != "worker-only" && scenario != "startup-first"
var mainRunning = scenario != "startup-existing" && scenario != "startup-first"
var events: [[String]] = []
var unexpected: [[String]] = []
var workerStarted = false
var workerPulled = false

// Shadow the Foundation lookup: compose uses a fixed synthetic name and an explicit fixture timezone.
func NSFullUserName() -> String { "Synthetic User" }

struct CommandResult {
    let status: Int32
    let output: String
    var ok: Bool { status == 0 }
}

enum Shell {
    static var searchPath: String { directory.path }
    static func run(_ executable: String, _ arguments: [String], environment: [String: String] = [:],
                    timeout: TimeInterval = 30) -> CommandResult {
        func ok(_ output: String = "") -> CommandResult { CommandResult(status: 0, output: output) }
        guard executable == directory.appendingPathComponent("docker").path else {
            unexpected.append([executable] + arguments)
            return CommandResult(status: 1, output: "external executable forbidden")
        }
        if arguments == ["info"] || arguments == ["compose", "version"] { return ok() }
        if arguments.first == "compose" {
            guard Array(arguments.prefix(7)) == ["compose", "-p", "kingfisher", "-f", paths.composeFile.path,
                                                "--env-file", paths.envFile.path] else {
                unexpected.append(arguments)
                return CommandResult(status: 1, output: "unexpected compose prefix")
            }
            let command = Array(arguments.dropFirst(7))
            events.append(command)
            switch command.first {
            case "ps":
                return ok(mainPresent && (command.contains("-a") || mainRunning) ? "main-container\n" : "")
            case "pull":
                workerPulled = !command.contains("kingfisher")
                return ok()
            case "up":
                // An enabled optional service, including a dependency, must not be selected implicitly.
                workerStarted = workerStarted || !command.contains("kingfisher") || !command.contains("--no-deps")
                currentImage = EnvStore(file: paths.envFile).read()!.value(EnvKey.image)!
                currentID = currentImage.hasPrefix("kingfisher:rollback-") && scenario != "rollback-wrong-image"
                    ? oldID : newID
                mainPresent = true
                mainRunning = true
                return ok()
            case "stop": mainRunning = false; return ok()
            case "run": return ok()
            default: unexpected.append(command); return CommandResult(status: 1, output: "unexpected compose operation")
            }
        }
        if arguments.first == "ps" {
            events.append(arguments)
            if scenario == "lookup-failed" { return CommandResult(status: 1, output: "main-container\n") }
            guard arguments.contains("label=com.docker.compose.project=kingfisher") else { return ok("") }
            let scoped = arguments.contains("label=com.docker.compose.service=kingfisher")
            if scoped { return ok(mainPresent ? "main-container\n" : "") }
            return ok(scenario == "main-only" ? "main-container\n"
                : "worker-container\n" + (mainPresent ? "main-container\n" : ""))
        }
        if arguments.first == "inspect" {
            events.append(arguments)
            switch arguments[2] {
            case "{{json .Mounts}}": return ok("[{\"Destination\":\"/data\"}]")
            case "{{.Image}}|{{.Config.Image}}": return ok(currentID + "|" + currentImage)
            case "{{json .Config.Labels}}": return ok("{}")
            case "{{json .Config.Env}}":
                return ok(arguments.last == "main-container"
                    ? "[\"ICARUS_SIDECAR_TOKEN=synthetic-main-token\",\"ICARUS_SECRETS_PASSPHRASE=synthetic-main-passphrase\"]"
                    : "[]")
            default: break
            }
        }
        if arguments.prefix(2) == ["volume", "inspect"] {
            return CommandResult(status: scenario == "adopt-keys" ? 0 : 1, output: "synthetic volume status")
        }
        if arguments.prefix(2) == ["image", "tag"] { events.append(arguments); return ok() }
        if arguments.first == "exec" {
            return ok("{\"root_available_bytes\":8589934592,\"root_available_inodes\":10000,\"data_available_bytes\":8589934592,\"data_available_inodes\":10000,\"backup_bytes\":10485760,\"backup_files\":10}")
        }
        unexpected.append(arguments)
        return CommandResult(status: 1, output: "unexpected command")
    }
}

enum Loopback {
    static func healthy() -> Bool { false }
    // Stop before optional Mac-app discovery; this fixture tests the compose boundary, not readiness.
    static func waitUntilHealthy() -> Bool { false }
    static func ollamaRunning() -> Bool { false }
    static func manifest() -> Manifest? { nil }
    static func authenticatedVersion(token: String) -> String? { "1.0.0" }
    static func backupName(token: String) -> String? {
        events.append(["backup"])
        return "vor-update-20261008T120000Z"
    }
    static func waitForVersion(_ version: String, token: String) -> Bool {
        scenario != "update-rollback" && scenario != "rollback-wrong-image"
    }
    static func inspectionMode(token: String) -> Bool { true }
}

try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
let dockerFile = directory.appendingPathComponent("docker")
try Data("synthetic executable placeholder; never launched".utf8).write(to: dockerFile)
try FileManager.default.setAttributes([.posixPermissions: 0o700], ofItemAtPath: dockerFile.path)
try Data("services: {}\n".utf8).write(to: paths.composeFile)
try Data("synthetic storage probe; never executed".utf8).write(to: paths.updateStorageProbeFile)
if scenario != "adopt-keys" {
    var env = EnvFile.generated(token: "synthetic-token", passphrase: "synthetic-passphrase")
    env.set(EnvKey.zeitzone, "Europe/Berlin")
    if scenario != "startup-first" { env.set(EnvKey.image, oldImage) }
    try EnvStore(file: paths.envFile).write(env)
} else {
    // provideKeys adopts known fixture keys; compose is not called in this scenario.
}

var outcome = ""
let docker = Docker(executable: dockerFile.path)
if ["multiple", "main-only", "worker-only", "lookup-failed"].contains(scenario) {
    outcome = docker.projectContainer() ?? "none"
} else if scenario == "adopt-keys" {
    switch Startup(paths: paths).provideKeys(docker) {
    case .ready(let env): outcome = env.value(EnvKey.token) ?? "missing-token"
    default: outcome = "missing"
    }
} else if scenario.hasPrefix("startup-") {
    outcome = String(describing: Startup(paths: paths).run { _ in })
} else {
    let request = UpdateRequest(message: ["aktion": "aktualisieren", "fassung": "1.0.1",
                                         "image": ImageName.forFassung("1.0.1")])!
    outcome = String(describing: Updater(paths: paths).perform(request) { _ in })
}
let result: [String: Any] = ["outcome": outcome, "events": events, "unexpected": unexpected,
                           "worker_started": workerStarted, "worker_pulled": workerPulled,
                           "image": currentImage, "image_id": currentID,
                           "environment": (try? String(contentsOf: paths.envFile, encoding: .utf8)) ?? ""]
print(String(data: try JSONSerialization.data(withJSONObject: result, options: [.sortedKeys]), encoding: .utf8)!)
