import Foundation

/// EventKit bleibt an dieser Grenze; Koordinator und Fenster besitzen keine Schreiboperation.
protocol NativeCalendarReading: AnyObject {
    var status: String { get }
    func authorize(if allowed: @escaping () -> Bool, _ completion: @escaping () -> Void)
    func calendars() throws -> [[String: Any]]
    func events(ids: [String], from: Date, to: Date, notes: Bool) throws -> [[String: Any]]
}

enum NativeCalendarError: Error { case invalidState, oversizedSnapshot, interrupted }

/// Ein Aufruf liest höchstens einen 31-Tage-Abschnitt. Keine Berechtigungsanfrage im Poll.
/// Alle Methoden werden auf derselben seriellen Queue aufgerufen.
final class NativeCalendarEngine {
    typealias Request = (String, [String: Any]?) throws -> [String: Any]
    private let reader: NativeCalendarReading
    private let request: Request
    private let active: () -> Bool
    private let clock: () -> Date
    private var generation = -1
    private var selected: [String] = []
    private var job: Job?
    private var lastLive: Date?
    private var lastMemory: Date?
    private var memoryCursor: Date?
    private var permissionGeneration: Int?
    private enum FailureStage { case transport, liveRead, historyRead }
    private var failureStage = FailureStage.transport
    private var memoryError = ""
    private let formatter = ISO8601DateFormatter()

    private struct Job {
        let memory: Bool
        let from: Date
        let to: Date
        var cursor: Date
        var events: [String: [String: Any]] = [:]
    }

    init(reader: NativeCalendarReading, request: @escaping Request,
         active: @escaping () -> Bool, clock: @escaping () -> Date = Date.init) {
        self.reader = reader; self.request = request; self.active = active; self.clock = clock
    }

    func discardPendingRead() { job = nil }
    func recoverAfterFailure() {
        let history = failureStage == .historyRead
        discardPendingRead()
        guard failureStage != .transport, active(), generation >= 0,
              let fresh = try? request("", nil), active(),
              fresh["generation"] as? Int == generation, fresh["enabled"] as? Bool == true,
              fresh["selected"] as? [String] == selected else { return }
        if history {
            memoryError = "Kalender-Gedächtnisabgleich konnte nicht abgeschlossen werden. Die Live-Anzeige bleibt verfügbar; der Helfer versucht es erneut."
            _ = try? request("/worker", ["generation": generation, "status": reader.status,
                "authorization_attempted": false, "calendars": fresh["calendars"] ?? [], "memory_error": memoryError])
            return
        }
        lastLive = nil
        _ = try? request("/worker", ["generation": generation, "status": reader.status,
            "authorization_attempted": false,
            "calendars": fresh["calendars"] ?? [],
            "error": "Mac-Kalender konnte nicht vollständig gelesen werden. Bitte Freigabe und Auswahl prüfen."])
    }

    /// Nur von der vertrauenswürdigen Fensterbrücke nach der bewussten Connect-Aktion aufrufen.
    func requestPermission(generation wanted: Int) {
        guard active(), permissionGeneration != wanted,
              let state = try? request("", nil),
              let current = state["generation"] as? Int, current == wanted,
              state["enabled"] as? Bool == true, state["authorize"] as? Bool == true,
              active() else { return }
        permissionGeneration = wanted
        reader.authorize(if: { [weak self] in
            guard let self = self, self.active(),
                  let fresh = try? self.request("", nil), self.active() else { return false }
            return fresh["generation"] as? Int == wanted && fresh["enabled"] as? Bool == true &&
                fresh["authorize"] as? Bool == true
        }, {})
    }

    func tick() throws {
        failureStage = .transport
        guard active() else { return }
        let state = try request("", nil)
        guard active(), let current = state["generation"] as? Int, current >= 0,
              let enabled = state["enabled"] as? Bool,
              let ids = state["selected"] as? [String], ids.count <= 100,
              Set(ids).count == ids.count, ids.allSatisfy({ !$0.isEmpty && $0.utf8.count <= 1024 }) else {
            throw NativeCalendarError.invalidState
        }
        if current != generation || ids != selected {
            generation = current; selected = ids; job = nil
            lastLive = nil; lastMemory = nil; memoryCursor = nil
            memoryError = state["memory_error"] as? String ?? ""
        }
        let status = reader.status
        failureStage = .liveRead
        let calendars = enabled && status == "granted" ? try reader.calendars() : []
        failureStage = .transport
        guard active() else { return }
        var heartbeat: [String: Any] = ["generation": current, "status": status, "calendars": calendars,
                                        "authorization_attempted": status != "not_determined", "memory_error": memoryError]
        if status == "error" { heartbeat["error"] = "Der Mac-Kalenderzugriff benötigt macOS 14 oder neuer." }
        _ = try request("/worker", heartbeat)
        guard enabled, status == "granted", !ids.isEmpty else { job = nil; return }
        guard Set(ids).isSubset(of: Set(calendars.compactMap { $0["id"] as? String })) else {
            job = nil; return
        }
        let memoryAllowed = state["memory_allowed"] as? Bool == true
        if job?.memory == true && !memoryAllowed { job = nil }
        let at = clock()
        if job == nil {
            if lastLive == nil || at.timeIntervalSince(lastLive!) >= 60 {
                var calendar = Calendar(identifier: .gregorian)
                calendar.timeZone = TimeZone(secondsFromGMT: 0)!
                let year = calendar.component(.year, from: at)
                let from = calendar.date(from: DateComponents(year: year, month: 1, day: 1))!.addingTimeInterval(-2 * 86400)
                let to = calendar.date(from: DateComponents(year: year + 1, month: 1, day: 1))!.addingTimeInterval(2 * 86400)
                job = Job(memory: false, from: from, to: to, cursor: from)
            } else if memoryAllowed && (lastMemory == nil || at.timeIntervalSince(lastMemory!) >= 1800) {
                guard let window = state["memory_window"] as? [String: Any],
                      let back = window["days_back"] as? Int, let ahead = window["days_ahead"] as? Int,
                      (0...1095).contains(back), (0...365).contains(ahead) else { throw NativeCalendarError.invalidState }
                let from = memoryCursor ?? at.addingTimeInterval(-Double(back) * 86400)
                let end = at.addingTimeInterval(Double(ahead) * 86400)
                if from >= end { lastMemory = at; memoryCursor = nil; return }
                let to = min(from.addingTimeInterval(90 * 86400), end)
                job = Job(memory: true, from: from, to: to, cursor: from)
            }
        }
        guard var chunk = job, active() else { return }
        failureStage = chunk.memory ? .historyRead : .liveRead
        let stop = min(chunk.cursor.addingTimeInterval(31 * 86400), chunk.to)
        let events = try reader.events(ids: ids, from: chunk.cursor, to: stop, notes: chunk.memory)
        guard events.count <= 10000 else { job = nil; throw NativeCalendarError.oversizedSnapshot }
        for event in events {
            guard let uid = event["uid"] as? String, !uid.isEmpty,
                  let source = event["source_id"] as? String, ids.contains(source) else {
                job = nil; throw NativeCalendarError.invalidState
            }
            chunk.events[uid] = event
        }
        guard chunk.events.count <= (chunk.memory ? 20000 : 10000) else {
            job = nil; throw NativeCalendarError.oversizedSnapshot
        }
        chunk.cursor = stop
        job = chunk
        guard stop >= chunk.to else { return }
        failureStage = .transport
        // Vor der Aufnahme erneut prüfen: Auswahl, Trennen oder Pause können sich während des Lesens ändern.
        let fresh = try request("", nil)
        guard active(), fresh["generation"] as? Int == current,
              fresh["enabled"] as? Bool == true, fresh["selected"] as? [String] == ids,
              reader.status == "granted",
              !chunk.memory || fresh["memory_allowed"] as? Bool == true else { job = nil; return }
        var body: [String: Any] = ["generation": current,
            "range_from": formatter.string(from: chunk.from), "range_to": formatter.string(from: chunk.to),
            "events": chunk.events.keys.sorted().compactMap { chunk.events[$0] }]
        if !chunk.memory { body["status"] = status; body["calendars"] = calendars }
        let result: [String: Any]
        do { result = try request(chunk.memory ? "/memory" : "/worker", body) }
        catch NativeCalendarError.oversizedSnapshot {
            failureStage = chunk.memory ? .historyRead : .liveRead
            throw NativeCalendarError.oversizedSnapshot
        }
        if chunk.memory && (result["stored"] as? Bool != true || result["keine_freigabe"] as? Bool != false ||
                            (result["fehler"] as? [String])?.isEmpty != true) {
            failureStage = .historyRead
            job = nil
            throw NativeCalendarError.interrupted
        }
        if chunk.memory { memoryCursor = chunk.to; memoryError = "" } else { lastLive = at }
        job = nil
    }
}
