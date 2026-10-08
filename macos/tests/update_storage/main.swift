import Foundation

// Only external commands and HTTP are fixtures. Docker, Updater and EnvStore are production code.
struct CommandResult {
    let status: Int32
    let output: String
    var ok: Bool { status == 0 }
}
enum Shell {
    static var searchPath: String { ProcessInfo.processInfo.environment["FIXTURE_DIR"]! }
    static func run(_ executable: String, _ arguments: [String], environment: [String: String] = [:],
                    timeout: TimeInterval = 30) -> CommandResult {
        let process = Process()
        process.executableURL = URL(fileURLWithPath: executable)
        process.arguments = arguments
        process.environment = ProcessInfo.processInfo.environment.merging(environment) { _, next in next }
        let pipe = Pipe()
        process.standardOutput = pipe
        process.standardError = pipe
        do { try process.run() } catch { return CommandResult(status: 1, output: "fixture command failed") }
        let output = pipe.fileHandleForReading.readDataToEndOfFile()
        process.waitUntilExit()
        return CommandResult(status: process.terminationStatus, output: String(data: output, encoding: .utf8) ?? "")
    }
}
enum Loopback {
    static func authenticatedVersion(token: String) -> String? { "1.0.0" }
    static func backupName(token: String) -> String? {
        let url = URL(fileURLWithPath: Shell.searchPath).appendingPathComponent("trace")
        let handle = try! FileHandle(forWritingTo: url)
        handle.seekToEndOfFile()
        handle.write(Data("backup\n".utf8))
        handle.closeFile()
        return "vor-update-20261008T120000Z"
    }
    static func waitForVersion(_ version: String, token: String) -> Bool { true }
    static func inspectionMode(token: String) -> Bool { true }
}
if CommandLine.arguments.count == 3 {
    if let status = UpdateStorageStatus.parse(CommandLine.arguments[1]) {
        print(status.issue(beforeBackup: CommandLine.arguments[2] == "before")?.rawValue ?? "ok")
    } else { print("unavailable") }
} else {
let directory = URL(fileURLWithPath: Shell.searchPath)
let paths = AppPaths(support: directory, envFile: directory.appendingPathComponent("kingfisher.env"),
                     composeFile: directory.appendingPathComponent("compose.yaml"))
let request = UpdateRequest(message: ["aktion": "aktualisieren", "fassung": "1.0.1",
                                     "image": ImageName.forFassung("1.0.1")])!
let result = Updater(paths: paths).perform(request) { _ in }
if case .updated = result { print("updated") } else { print(String(describing: result)) }

}
