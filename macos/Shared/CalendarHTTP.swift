import Foundation
#if canImport(FoundationNetworking)
import FoundationNetworking
#endif

/// Nur vorhandene Kalenderendpunkte am selben Loopback-Origin; niemals Proxy oder Redirect.
final class CalendarHTTP: NSObject, URLSessionDataDelegate {
    private final class Response {
        let done = DispatchSemaphore(value: 0)
        var data = Data()
        var status = 0
        var failed = false
    }
    private let origin: URL
    private let tokenFile: URL
    private let lock = NSLock()
    private var responses: [Int: Response] = [:]
    private var session: URLSession!
    private let limit = 8 * 1024 * 1024

    init(origin: URL, tokenFile: URL) {
        self.origin = origin; self.tokenFile = tokenFile
        super.init()
        let configuration = URLSessionConfiguration.ephemeral
        configuration.connectionProxyDictionary = [:]
        configuration.httpCookieStorage = nil; configuration.urlCache = nil
        configuration.timeoutIntervalForRequest = 5; configuration.timeoutIntervalForResource = 10
        let queue = OperationQueue(); queue.maxConcurrentOperationCount = 1
        session = URLSession(configuration: configuration, delegate: self, delegateQueue: queue)
    }

    func stop() { session.invalidateAndCancel() }

    func request(_ path: String, _ body: [String: Any]?) throws -> [String: Any] {
        guard ["", "/worker", "/memory"].contains(path),
              let text = try? String(contentsOf: tokenFile, encoding: .utf8),
              let token = PowerReportRequest.token(from: text),
              var request = PowerReportRequest.make(origin: origin, source: .unknown, token: token),
              let url = URL(string: "/api/v1/mac-calendar" + path, relativeTo: origin)?.absoluteURL else {
            throw NativeCalendarError.invalidState
        }
        request.url = url
        request.httpMethod = body == nil ? "GET" : "POST"
        // Die letzte Freigabeprüfung vor dem Systemdialog bleibt kurz und scheitert geschlossen.
        request.timeoutInterval = body == nil ? 1 : 5
        request.httpBody = try body.map { try JSONSerialization.data(withJSONObject: $0) }
        guard (request.httpBody?.count ?? 0) <= limit else { throw NativeCalendarError.oversizedSnapshot }
        let response = Response()
        let task = session.dataTask(with: request)
        lock.lock(); responses[task.taskIdentifier] = response; lock.unlock()
        task.resume()
        guard response.done.wait(timeout: .now() + (body == nil ? 2 : 12)) == .success else {
            task.cancel()
            lock.lock(); responses.removeValue(forKey: task.taskIdentifier); lock.unlock()
            throw NativeCalendarError.interrupted
        }
        lock.lock(); responses.removeValue(forKey: task.taskIdentifier)
        let data = response.data, status = response.status, failed = response.failed
        lock.unlock()
        guard !failed, (200..<300).contains(status),
              let result = try JSONSerialization.jsonObject(with: data) as? [String: Any] else {
            throw NativeCalendarError.invalidState
        }
        return result
    }

    func urlSession(_ session: URLSession, task: URLSessionTask, willPerformHTTPRedirection response: HTTPURLResponse,
                    newRequest request: URLRequest, completionHandler: @escaping (URLRequest?) -> Void) { completionHandler(nil) }
    func urlSession(_ session: URLSession, dataTask: URLSessionDataTask, didReceive response: URLResponse,
                    completionHandler: @escaping (URLSession.ResponseDisposition) -> Void) {
        lock.lock(); responses[dataTask.taskIdentifier]?.status = (response as? HTTPURLResponse)?.statusCode ?? 0; lock.unlock()
        completionHandler(response.expectedContentLength > Int64(limit) ? .cancel : .allow)
    }
    func urlSession(_ session: URLSession, dataTask: URLSessionDataTask, didReceive data: Data) {
        lock.lock()
        let response = responses[dataTask.taskIdentifier]
        if let response = response, response.data.count + data.count <= limit { response.data.append(data) }
        else { response?.failed = true }
        let cancel = response?.failed ?? true
        lock.unlock()
        if cancel { dataTask.cancel() }
    }
    func urlSession(_ session: URLSession, task: URLSessionTask, didCompleteWithError error: Error?) {
        lock.lock(); let response = responses[task.taskIdentifier]
        if error != nil { response?.failed = true }
        lock.unlock(); response?.done.signal()
    }
}
