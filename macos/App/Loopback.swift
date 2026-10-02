import Foundation

// Synchrone HTTP-Aufrufe für Hintergrund-Warteschlangen: Gesundheit, Sicherung, Manifest.

enum Loopback {
    /// Ohne Proxy: Die Adresse ist lokal, und ein eingestellter Proxy darf sie weder sehen noch umleiten.
    private static let session: URLSession = {
        let configuration = URLSessionConfiguration.ephemeral
        configuration.connectionProxyDictionary = [:]
        configuration.requestCachePolicy = .reloadIgnoringLocalCacheData
        return URLSession(configuration: configuration)
    }()

    /// Antwortet Kingfisher auf `/health`?
    static func healthy(timeout: TimeInterval = 2) -> Bool {
        var request = URLRequest(url: AppPaths.origin.appendingPathComponent("health"), timeoutInterval: timeout)
        request.httpMethod = "GET"
        return (status(of: request, session: session).map { 200..<300 ~= $0 }) ?? false
    }

    /// Wartet, bis `/health` antwortet.
    static func waitUntilHealthy(seconds: Int = 180) -> Bool {
        let deadline = Date().addingTimeInterval(TimeInterval(seconds))
        while Date() < deadline {
            if healthy() { return true }
            Thread.sleep(forTimeInterval: 1)
        }
        return false
    }

    /// Vollständige Sicherung über den Sidecar: `POST /backups?vor_update=true` (server.py, „Sicherung“), Token im
    /// Kopf `x-icarus-token` wie bei `make backups`. Dieselbe Sicherung wie bei `make aktualisieren`, damit
    /// `make zurueck-vor-update` sie findet. Erfolg ist 201; 409 heißt, die Sicherung ist gescheitert.
    static func backup(token: String) -> Bool {
        let url = URL(string: "backups?vor_update=true", relativeTo: AppPaths.origin)!.absoluteURL
        var request = URLRequest(url: url, timeoutInterval: 900)
        request.httpMethod = "POST"
        request.setValue(token, forHTTPHeaderField: "x-icarus-token")
        return status(of: request, session: session) == 201
    }

    /// Läuft Ollama auf diesem Mac (wie der Starter: `/api/tags`)?
    static func ollamaRunning() -> Bool {
        let request = URLRequest(url: URL(string: "http://127.0.0.1:11434/api/tags")!, timeoutInterval: 1)
        return status(of: request, session: session) != nil
    }

    /// Das Manifest der Download-Seite; nil, wenn es nicht zu holen ist.
    static func manifest() -> Manifest? {
        let request = URLRequest(url: Manifest.url, cachePolicy: .reloadIgnoringLocalCacheData, timeoutInterval: 10)
        return body(of: request, session: .shared).flatMap(Manifest.decode)
    }

    private static func status(of request: URLRequest, session: URLSession) -> Int? {
        perform(request, session: session)?.status
    }

    private static func body(of request: URLRequest, session: URLSession) -> Data? {
        guard let result = perform(request, session: session), 200..<300 ~= result.status else { return nil }
        return result.data
    }

    private static func perform(_ request: URLRequest, session: URLSession) -> (status: Int, data: Data)? {
        // Eine Schachtel statt einer Variablen: Der Rückruf läuft auf einer anderen Warteschlange.
        final class Answer { var value: (status: Int, data: Data)? }
        let answer = Answer()
        let done = DispatchSemaphore(value: 0)
        session.dataTask(with: request) { data, response, _ in
            if let response = response as? HTTPURLResponse { answer.value = (response.statusCode, data ?? Data()) }
            done.signal()
        }.resume()
        done.wait()
        return answer.value
    }
}
