import Foundation
#if canImport(Darwin)
import Darwin
#else
import Glibc
#endif

/// A private stdin channel to the bundled helper. No shell, command-line secret,
/// raw stderr, or provider environment crosses this boundary.
struct RecoveryHelperClient {
    let script: URL
    let docker: String
    let image: String
    var timeout: TimeInterval = 450

    func request(_ operation: String, fields: [String: Any] = [:]) -> Result<[String: Any], RecoveryFailure> {
        var body = fields
        body["operation"] = operation; body["docker"] = docker; body["image"] = image
        guard let input = try? JSONSerialization.data(withJSONObject: body), input.count <= 64 * 1024 else {
            return .failure(RecoveryFailure("Die Eingabe ist zu groß oder unvollständig."))
        }
        let process = Process(), incoming = Pipe(), outgoing = Pipe()
        process.executableURL = URL(fileURLWithPath: "/usr/bin/python3")
        process.arguments = [script.path]
        process.standardInput = incoming; process.standardOutput = outgoing
        process.standardError = FileHandle.nullDevice
        process.environment = ProcessInfo.processInfo.environment.filter { key, _ in
            ["HOME", "USER", "LOGNAME", "TMPDIR", "LANG", "TZ"].contains(key) || key.hasPrefix("LC_")
        }
        process.environment?["PATH"] = "/usr/bin:/bin:/usr/sbin:/sbin:/usr/local/bin:/opt/homebrew/bin"
        let completed = DispatchSemaphore(value: 0), reader = RecoveryOutput(), drained = DispatchGroup()
        process.terminationHandler = { _ in completed.signal() }
        do {
            try process.run()
            try outgoing.fileHandleForWriting.close()
            drained.enter()
            DispatchQueue.global(qos: .utility).async {
                defer { drained.leave() }
                while let value = try? outgoing.fileHandleForReading.read(upToCount: 64 * 1024), !value.isEmpty {
                    reader.append(value)
                }
            }
            try incoming.fileHandleForWriting.write(contentsOf: input)
            try incoming.fileHandleForWriting.close()
        } catch {
            try? incoming.fileHandleForWriting.close()
            if process.isRunning { process.terminate() }
            return .failure(RecoveryFailure("Der Wiederherstellungshelfer konnte nicht gestartet werden. Bitte die App-Installation prüfen."))
        }
        // The helper bounds each Docker step. This outer deadline only catches
        // a wedged helper and must exceed its longest operation.
        if completed.wait(timeout: .now() + timeout) == .timedOut {
            process.terminate()
            if completed.wait(timeout: .now() + 5) == .timedOut { _ = kill(process.processIdentifier, SIGKILL) }
            try? outgoing.fileHandleForReading.close()
            return .failure(RecoveryFailure("Der Schritt dauert ungewöhnlich lange. Die angelegten Ordner bleiben erhalten; bitte Docker und den Stand prüfen, bevor du erneut startest."))
        }
        guard drained.wait(timeout: .now() + 5) == .success else {
            try? outgoing.fileHandleForReading.close()
            return .failure(RecoveryFailure("Die Antwort konnte nicht vollständig gelesen werden. Bitte den angelegten Ordner prüfen."))
        }
        guard let output = reader.result(), let response = try? JSONSerialization.jsonObject(with: output) as? [String: Any] else {
            return .failure(RecoveryFailure("Der Wiederherstellungshelfer hat keine lesbare Antwort geliefert. Deine Ordner bleiben erhalten."))
        }
        if process.terminationStatus == 0 && response["ok"] as? Bool == true { return .success(response) }
        // Helper errors are closed, human-readable messages. Do not display
        // arbitrary subprocess output or include the submitted request.
        let message = (response["error"] as? String).flatMap { $0.count <= 500 ? $0 : nil }
        return .failure(RecoveryFailure(message ?? "Der Schritt wurde nicht abgeschlossen. Bitte den gewählten Ordner und Docker prüfen."))
    }
}

struct RecoveryFailure: Error {
    let message: String
    init(_ message: String) { self.message = message }
}

private final class RecoveryOutput {
    private let lock = NSLock()
    private var data = Data()
    private var overflow = false
    func append(_ value: Data) {
        lock.lock(); defer { lock.unlock() }
        if data.count + value.count > 8 * 1024 * 1024 { overflow = true; return }
        if !overflow { data.append(value) }
    }
    func result() -> Data? { lock.lock(); defer { lock.unlock() }; return overflow ? nil : data }
}
