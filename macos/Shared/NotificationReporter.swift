import Foundation
import UserNotifications
#if canImport(FoundationNetworking)
import FoundationNetworking
#endif

/// Fragt den lokalen Sidecar alle fünf Minuten nach fälligen Mitteilungen (`GET /api/v1/mitteilungen/faellig`) und zeigt
/// jede als Systemmitteilung mit „Öffnen“ und „War überflüssig“ (Etappe 5, docs/24-weg-zum-jarvis.md).
///
/// Regeln: Es wird nur mit 127.0.0.1 gesprochen, nie mit einem anderen Rechner. Die Erlaubnis des Systems wird erst
/// erfragt, wenn der Schalter in den Einstellungen an ist, und nur einmal je Lauf; ihr Stand geht an den Sidecar, damit
/// die Einstellungen sagen können, wo man sie gibt. Kein Inhalt einer Mitteilung geht in ein Protokoll. Die Antwort ist
/// auf 4 KB begrenzt; eine größere wird verworfen. Jede Mitteilung bekommt der Sidecar nur einmal heraus; nach dem
/// Zeigen meldet die App „zugestellt“, nach dem Klick auf „War überflüssig“ die Rückmeldung.
final class NotificationReporter: NSObject, UNUserNotificationCenterDelegate {
    private let tokenFile: URL
    private let http: MitteilungenHTTP
    private let center: UNUserNotificationCenter
    private let onOpen: (String) -> Void
    private let queue = DispatchQueue(label: "local.kingfisher.mitteilungen", qos: .utility)
    private let lock = NSLock()
    private var timer: DispatchSourceTimer?
    private var running = false
    private var asked = false

    init(origin: URL, tokenFile: URL, onOpen: @escaping (String) -> Void) {
        self.tokenFile = tokenFile
        self.http = MitteilungenHTTP(origin: origin)
        self.center = UNUserNotificationCenter.current()
        self.onOpen = onOpen
        super.init()
        center.delegate = self
        let oeffnen = UNNotificationAction(identifier: MitteilungenPfad.aktionOeffnen, title: "Öffnen", options: [.foreground])
        let ueberfluessig = UNNotificationAction(identifier: MitteilungenPfad.aktionUeberfluessig, title: "War überflüssig", options: [])
        center.setNotificationCategories([UNNotificationCategory(identifier: MitteilungenPfad.kategorie, actions: [oeffnen, ueberfluessig],
                                                                 intentIdentifiers: [], options: [])])
    }

    private var isRunning: Bool { lock.lock(); defer { lock.unlock() }; return running }

    func start() {
        lock.lock(); guard !running else { lock.unlock(); return }; running = true; lock.unlock()
        let timer = DispatchSource.makeTimerSource(queue: queue)
        timer.schedule(deadline: .now() + 5, repeating: MitteilungenPfad.interval, leeway: .seconds(10))
        timer.setEventHandler { [weak self] in self?.tick() }
        self.timer = timer
        timer.resume()
    }

    func stop() {
        lock.lock(); running = false; lock.unlock()
        timer?.setEventHandler {}; timer?.cancel(); timer = nil
        http.stop()
    }

    private func token() -> String? {
        guard let text = try? String(contentsOf: tokenFile, encoding: .utf8) else { return nil }
        return PowerReportRequest.token(from: text)
    }

    /// Ein Durchgang: Schalter lesen; nur wenn er an ist, Erlaubnis klären und Fälliges zeigen.
    private func tick() {
        guard isRunning, let token = token(),
              let data = http.get(MitteilungenPfad.einstellung, token: token),
              let einstellung = MitteilungenEinstellung.parse(data), einstellung.an else { return }
        permission(token: token) { [weak self] granted in
            guard granted, let self = self, self.isRunning else { return }
            self.queue.async { self.deliverDue(token: token) }
        }
    }

    /// Fragt das System nur, solange es noch nie gefragt wurde, und nur einmal je Lauf; meldet den Stand dem Sidecar.
    private func permission(token: String, _ then: @escaping (Bool) -> Void) {
        center.getNotificationSettings { [weak self] settings in
            guard let self = self else { return }
            switch settings.authorizationStatus {
            case .notDetermined:
                self.lock.lock(); let already = self.asked; self.asked = true; self.lock.unlock()
                guard !already else { then(false); return }
                self.center.requestAuthorization(options: [.alert, .sound]) { granted, _ in
                    self.report(erlaubnis: granted, token: token)
                    then(granted)
                }
            case .denied:
                self.report(erlaubnis: false, token: token)
                then(false)
            default:
                self.report(erlaubnis: true, token: token)
                then(true)
            }
        }
    }

    private func report(erlaubnis: Bool?, token: String) {
        queue.async { [weak self] in
            _ = self?.http.post(MitteilungenPfad.erlaubnis, body: MitteilungenRequest.erlaubnis(erlaubnis), token: token)
        }
    }

    private func deliverDue(token: String) {
        guard let data = http.get(MitteilungenPfad.faellig, token: token) else { return }
        for mitteilung in Mitteilung.parse(data) {
            show(mitteilung, token: token)
        }
    }

    private func show(_ mitteilung: Mitteilung, token: String) {
        let content = UNMutableNotificationContent()
        content.title = mitteilung.titel
        content.body = mitteilung.satz
        content.categoryIdentifier = MitteilungenPfad.kategorie
        content.userInfo = ["id": mitteilung.id, "pfad": mitteilung.pfad]
        let request = UNNotificationRequest(identifier: mitteilung.id, content: content, trigger: nil)
        center.add(request) { [weak self] error in
            guard error == nil, let self = self, let path = MitteilungenPfad.zugestellt(mitteilung.id) else { return }
            self.queue.async { _ = self.http.post(path, body: [:], token: token) }
        }
    }

    // MARK: Klick auf die Mitteilung

    func userNotificationCenter(_ center: UNUserNotificationCenter, willPresent notification: UNNotification,
                                withCompletionHandler completionHandler: @escaping (UNNotificationPresentationOptions) -> Void) {
        // Auch bei offenem Fenster zeigen: Die Mitteilung gilt dem Menschen, nicht dem Fenster.
        if #available(macOS 11.0, *) { completionHandler([.banner, .sound]) } else { completionHandler([.alert, .sound]) }
    }

    func userNotificationCenter(_ center: UNUserNotificationCenter, didReceive response: UNNotificationResponse,
                                withCompletionHandler completionHandler: @escaping () -> Void) {
        defer { completionHandler() }
        let info = response.notification.request.content.userInfo
        guard let id = info["id"] as? String, Mitteilung.gueltigeKennung(id) else { return }
        switch response.actionIdentifier {
        case MitteilungenPfad.aktionUeberfluessig:
            guard let path = MitteilungenPfad.rueckmeldung(id), let token = token() else { return }
            queue.async { [weak self] in _ = self?.http.post(path, body: ["ueberfluessig": true], token: token) }
        case MitteilungenPfad.aktionOeffnen, UNNotificationDefaultActionIdentifier:
            guard let pfad = info["pfad"] as? String, Mitteilung.gueltigerPfad(pfad) else { return }
            DispatchQueue.main.async { [weak self] in self?.onOpen(pfad) }
        default:
            break
        }
    }
}

/// Nur die Mitteilungsrouten am selben Loopback-Origin; niemals Proxy oder Weiterleitung; Antwort höchstens 4 KB.
final class MitteilungenHTTP: NSObject, URLSessionDataDelegate {
    private final class Response {
        let done = DispatchSemaphore(value: 0)
        var data = Data()
        var status = 0
        var failed = false
    }
    private let origin: URL
    private let lock = NSLock()
    private var responses: [Int: Response] = [:]
    private var session: URLSession!
    private let maximumResponseBytes = 4096

    init(origin: URL) {
        self.origin = origin
        super.init()
        let configuration = URLSessionConfiguration.ephemeral
        configuration.connectionProxyDictionary = [:]
        configuration.httpCookieStorage = nil
        configuration.urlCache = nil
        configuration.timeoutIntervalForRequest = 5
        configuration.timeoutIntervalForResource = 20
        let queue = OperationQueue()
        queue.maxConcurrentOperationCount = 1
        session = URLSession(configuration: configuration, delegate: self, delegateQueue: queue)
    }

    func stop() { session.invalidateAndCancel() }

    func get(_ path: String, token: String) -> Data? {
        guard let request = MitteilungenRequest.make(origin: origin, path: path, method: "GET", token: token) else { return nil }
        return perform(request)
    }

    func post(_ path: String, body: [String: Any], token: String) -> Bool {
        guard let request = MitteilungenRequest.make(origin: origin, path: path, method: "POST", body: body, token: token) else { return false }
        return perform(request) != nil
    }

    private func perform(_ request: URLRequest) -> Data? {
        let response = Response()
        let task = session.dataTask(with: request)
        lock.lock(); responses[task.taskIdentifier] = response; lock.unlock()
        task.resume()
        guard response.done.wait(timeout: .now() + 25) == .success else {
            task.cancel()
            lock.lock(); responses.removeValue(forKey: task.taskIdentifier); lock.unlock()
            return nil
        }
        lock.lock(); responses.removeValue(forKey: task.taskIdentifier)
        let data = response.data, status = response.status, failed = response.failed
        lock.unlock()
        guard !failed, (200..<300).contains(status) else { return nil }
        return data
    }

    // Eine Weiterleitung könnte den Token woanders hintragen; alle werden abgelehnt.
    func urlSession(_ session: URLSession, task: URLSessionTask, willPerformHTTPRedirection response: HTTPURLResponse,
                    newRequest request: URLRequest, completionHandler: @escaping (URLRequest?) -> Void) { completionHandler(nil) }

    func urlSession(_ session: URLSession, dataTask: URLSessionDataTask, didReceive response: URLResponse,
                    completionHandler: @escaping (URLSession.ResponseDisposition) -> Void) {
        lock.lock(); responses[dataTask.taskIdentifier]?.status = (response as? HTTPURLResponse)?.statusCode ?? 0; lock.unlock()
        completionHandler(response.expectedContentLength > Int64(maximumResponseBytes) ? .cancel : .allow)
    }

    func urlSession(_ session: URLSession, dataTask: URLSessionDataTask, didReceive data: Data) {
        lock.lock()
        let response = responses[dataTask.taskIdentifier]
        if let response = response, response.data.count + data.count <= maximumResponseBytes { response.data.append(data) }
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
