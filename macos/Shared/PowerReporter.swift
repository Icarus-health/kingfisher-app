import Foundation
#if canImport(Darwin)
import Darwin
#elseif canImport(Glibc)
import Glibc
#endif
#if canImport(FoundationNetworking)
import FoundationNetworking
#endif

enum PowerSource: String {
    case ac
    case battery
    case unknown

    /// Nimmt nur die eindeutige, bekannte Zeile von `pmset -g batt` an.
    static func parse(_ output: String) -> PowerSource {
        let lines = output.split(whereSeparator: \.isNewline).map(String.init)
        let matches = lines.filter { $0.hasPrefix("Now drawing from '") }
        guard matches.count == 1, let line = matches.first else { return .unknown }
        switch line {
        case "Now drawing from 'AC Power'": return .ac
        case "Now drawing from 'Battery Power'": return .battery
        default: return .unknown
        }
    }
}

enum PowerReportRequest {
    static let path = "/api/v1/device/power"
    static let interval: TimeInterval = 30

    /// Liest ausschließlich den Sidecar-Token. Bei doppelten Einträgen gilt die letzte Zeile wie bei Compose.
    static func token(from text: String) -> String? {
        let values = text.replacingOccurrences(of: "\r\n", with: "\n").split(separator: "\n").compactMap { raw -> String? in
            var line = raw.trimmingCharacters(in: .whitespaces)
            if line.hasPrefix("#") { return nil }
            if line.hasPrefix("export ") { line = String(line.dropFirst(7)) }
            guard line.hasPrefix("ICARUS_SIDECAR_TOKEN=") else { return nil }
            var value = String(line.dropFirst("ICARUS_SIDECAR_TOKEN=".count)).trimmingCharacters(in: .whitespaces)
            if value.count >= 2, (value.first == "'" && value.last == "'" || value.first == "\"" && value.last == "\"") {
                value.removeFirst()
                value.removeLast()
            }
            return value
        }
        guard let value = values.last, validToken(value) else { return nil }
        return value
    }

    static func make(origin: URL, source: PowerSource, token: String) -> URLRequest? {
        guard origin.scheme == "http", origin.host == "127.0.0.1", origin.user == nil, origin.password == nil,
              ["", "/"].contains(origin.path), origin.query == nil, origin.fragment == nil, validToken(token),
              let url = URL(string: path, relativeTo: origin)?.absoluteURL,
              let body = try? JSONSerialization.data(withJSONObject: ["source": source.rawValue]) else { return nil }
        var request = URLRequest(url: url, timeoutInterval: 3)
        request.httpMethod = "POST"
        request.httpBody = body
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.setValue(token, forHTTPHeaderField: "x-icarus-token")
        request.cachePolicy = .reloadIgnoringLocalCacheData
        return request
    }

    private static func validToken(_ token: String) -> Bool {
        !token.isEmpty && token.utf8.count <= 512 && !token.contains("\r") && !token.contains("\n")
    }
}

/// Sendet die knappe Energiequelle in festen Abständen an den lokalen Sidecar.
/// Es werden weder Prozentwerte noch andere Geräte- oder Nutzungsdaten erfasst.
final class PowerReporter: NSObject, URLSessionDataDelegate {
    private let origin: URL
    private let tokenFile: URL
    private let queue = DispatchQueue(label: "local.kingfisher.power-reporter", qos: .utility)
    private let lock = NSLock()
    private var timer: DispatchSourceTimer?
    private var session: URLSession!
    private var running = false
    private var inFlight = false
    private var responseSizes: [Int: Int] = [:]
    private let maximumResponseBytes = 512

    init(origin: URL, tokenFile: URL) {
        self.origin = origin
        self.tokenFile = tokenFile
        super.init()
        let configuration = URLSessionConfiguration.ephemeral
        configuration.connectionProxyDictionary = [:]
        configuration.timeoutIntervalForRequest = 3
        configuration.timeoutIntervalForResource = 4
        configuration.httpCookieStorage = nil
        configuration.urlCache = nil
        let delegateQueue = OperationQueue()
        delegateQueue.maxConcurrentOperationCount = 1
        session = URLSession(configuration: configuration, delegate: self, delegateQueue: delegateQueue)
    }

    func start() {
        lock.lock()
        guard !running else { lock.unlock(); return }
        running = true
        lock.unlock()
        let timer = DispatchSource.makeTimerSource(queue: queue)
        timer.schedule(deadline: .now(), repeating: PowerReportRequest.interval, leeway: .seconds(3))
        timer.setEventHandler { [weak self] in self?.reportIfNeeded() }
        self.timer = timer
        timer.resume()
    }

    func stop() {
        lock.lock()
        running = false
        lock.unlock()
        timer?.setEventHandler {}
        timer?.cancel()
        timer = nil
        session.invalidateAndCancel()
    }

    private func reportIfNeeded() {
        lock.lock()
        guard running, !inFlight else { lock.unlock(); return }
        inFlight = true
        lock.unlock()

        guard let text = try? String(contentsOf: tokenFile, encoding: .utf8),
              let token = PowerReportRequest.token(from: text),
              let request = PowerReportRequest.make(origin: origin, source: Self.currentSource(), token: token) else {
            finishRequest()
            return
        }
        session.dataTask(with: request).resume()
    }

    private func finishRequest() {
        lock.lock()
        inFlight = false
        lock.unlock()
    }

    private static func currentSource(timeout: TimeInterval = 0.8) -> PowerSource {
        let process = Process()
        let output = Pipe()
        let completed = DispatchSemaphore(value: 0)
        let resultLock = NSLock()
        var result: (Int32, Data)?
        process.executableURL = URL(fileURLWithPath: "/usr/bin/pmset")
        process.arguments = ["-g", "batt"]
        process.standardOutput = output
        process.standardError = FileHandle.nullDevice
        process.terminationHandler = { child in
            let bytes = output.fileHandleForReading.readData(ofLength: 4096)
            resultLock.lock()
            result = (child.terminationStatus, bytes)
            resultLock.unlock()
            completed.signal()
        }
        do { try process.run() } catch { return .unknown }
        guard completed.wait(timeout: .now() + timeout) == .success else {
            process.terminate()
            DispatchQueue.global(qos: .utility).asyncAfter(deadline: .now() + 0.2) {
                if process.isRunning { kill(process.processIdentifier, SIGKILL) }
            }
            return .unknown
        }
        resultLock.lock()
        let captured = result
        resultLock.unlock()
        guard let (status, data) = captured, status == 0, let text = String(data: data, encoding: .utf8) else { return .unknown }
        return PowerSource.parse(text)
    }

    // HTTP redirects can carry the authorization header to another endpoint; refuse all of them.
    func urlSession(_ session: URLSession, task: URLSessionTask,
                    willPerformHTTPRedirection response: HTTPURLResponse, newRequest request: URLRequest,
                    completionHandler: @escaping (URLRequest?) -> Void) {
        completionHandler(nil)
    }

    func urlSession(_ session: URLSession, dataTask: URLSessionDataTask,
                    didReceive response: URLResponse, completionHandler: @escaping (URLSession.ResponseDisposition) -> Void) {
        responseSizes[dataTask.taskIdentifier] = 0
        completionHandler(.allow)
    }

    func urlSession(_ session: URLSession, dataTask: URLSessionDataTask, didReceive data: Data) {
        let size = (responseSizes[dataTask.taskIdentifier] ?? 0) + data.count
        responseSizes[dataTask.taskIdentifier] = size
        if size > maximumResponseBytes { dataTask.cancel() }
    }

    func urlSession(_ session: URLSession, task: URLSessionTask, didCompleteWithError error: Error?) {
        responseSizes.removeValue(forKey: task.taskIdentifier)
        finishRequest()
    }
}
