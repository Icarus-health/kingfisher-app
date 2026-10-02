import Foundation
import Darwin

// Befehle ausführen, ohne die Oberfläche zu blockieren (Aufrufer sind Hintergrund-Warteschlangen).
// Ausgaben gehen in eine Datei statt in eine Pipe: Ein Kindprozess von `docker compose`, der die Pipe offen
// hält, könnte sonst das Warten auf das Ende blockieren. Geheimnisse stehen nie in Argumenten – Token und
// Passphrase liest Compose aus der Env-Datei.

struct CommandResult {
    let status: Int32
    let output: String
    var ok: Bool { status == 0 }
}

enum Shell {
    /// Eine aus dem Finder gestartete App hat einen sehr kurzen PATH. Docker Desktop braucht seine Helfer
    /// (Compose-Plugin, `docker-credential-desktop`) auf dem Weg, sonst scheitert schon das Laden eines
    /// öffentlichen Bildes an der Anmeldehilfe.
    static let searchPath = [
        "/usr/local/bin", "/opt/homebrew/bin", "/Applications/Docker.app/Contents/Resources/bin",
        "/usr/bin", "/bin", "/usr/sbin", "/sbin",
    ].joined(separator: ":")

    static func run(_ executable: String, _ arguments: [String], environment extra: [String: String] = [:],
                    timeout: TimeInterval) -> CommandResult {
        let process = Process()
        process.executableURL = URL(fileURLWithPath: executable)
        process.arguments = arguments
        var environment = ProcessInfo.processInfo.environment
        environment["PATH"] = searchPath
        for (name, value) in extra { environment[name] = value }
        process.environment = environment
        process.standardInput = FileHandle.nullDevice
        let capture = FileManager.default.temporaryDirectory
            .appendingPathComponent("kingfisher-\(UUID().uuidString).out")
        FileManager.default.createFile(atPath: capture.path, contents: nil, attributes: [.posixPermissions: 0o600])
        defer { try? FileManager.default.removeItem(at: capture) }
        guard let handle = try? FileHandle(forWritingTo: capture) else {
            return CommandResult(status: -1, output: "")
        }
        process.standardOutput = handle
        process.standardError = handle
        do {
            try process.run()
        } catch {
            try? handle.close()
            Log.write("\(executable) \(arguments.joined(separator: " ")): \(error.localizedDescription)")
            return CommandResult(status: -1, output: error.localizedDescription)
        }
        let watchdog = DispatchWorkItem {
            guard process.isRunning else { return }
            process.terminate()
            DispatchQueue.global().asyncAfter(deadline: .now() + 5) {
                if process.isRunning { kill(process.processIdentifier, SIGKILL) }
            }
        }
        DispatchQueue.global().asyncAfter(deadline: .now() + timeout, execute: watchdog)
        process.waitUntilExit()
        watchdog.cancel()
        try? handle.close()
        let output = (try? String(contentsOf: capture, encoding: .utf8)) ?? ""
        Log.write("\(executable) \(arguments.joined(separator: " ")) → \(process.terminationStatus)\n\(output)")
        return CommandResult(status: process.terminationStatus, output: output)
    }
}

/// Ein Protokoll für Rückfragen: `~/Library/Logs/Kingfisher/kingfisher.log`, nur für den Benutzer lesbar.
/// Es enthält Befehle und Ausgaben von Docker, nie Token oder Passphrase.
enum Log {
    private static let queue = DispatchQueue(label: "kingfisher.log")
    private static let maximum: UInt64 = 2_000_000

    static var file: URL {
        FileManager.default.homeDirectoryForCurrentUser
            .appendingPathComponent("Library/Logs/Kingfisher/kingfisher.log")
    }

    static func write(_ text: String) {
        queue.async {
            let file = Log.file
            try? FileManager.default.createDirectory(at: file.deletingLastPathComponent(),
                                                     withIntermediateDirectories: true,
                                                     attributes: [.posixPermissions: 0o700])
            // Klein halten: Wird die Datei zu groß, beginnt sie neu.
            let size = (try? FileManager.default.attributesOfItem(atPath: file.path)[.size] as? UInt64) ?? 0
            if size > maximum || !FileManager.default.fileExists(atPath: file.path) {
                FileManager.default.createFile(atPath: file.path, contents: nil, attributes: [.posixPermissions: 0o600])
            }
            guard let handle = try? FileHandle(forWritingTo: file) else { return }
            defer { try? handle.close() }
            handle.seekToEndOfFile()
            let stamp = ISO8601DateFormatter().string(from: Date())
            handle.write(Data("[\(stamp)] \(text)\n".utf8))
        }
    }
}
