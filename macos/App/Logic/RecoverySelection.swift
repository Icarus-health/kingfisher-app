import Foundation
import CoreFoundation

/// A presentation of the backend's read-only report. This is not permission to
/// restore: the helper rechecks the selected fingerprint before copying.
struct RecoveryChoice {
    let id: String
    let title: String
    let files: [(name: String, status: String)]
    let eligible: Bool
    let detail: String
    var readable: Int { files.filter { $0.status == "verified" }.count }
    var missing: Int { files.filter { $0.status == "missing" }.count }
    var summary: String { "\(readable) Bereiche lesbar · \(missing) nicht enthalten · \(files.count - readable - missing) ungeklärt" }
}

struct RecoveryReport {
    let fingerprint: String
    let choices: [RecoveryChoice]
    static let labels = ["tasks.sqlite3":"Aufgaben", "knowledge.sqlite3":"Gedächtnis",
        "episodes.sqlite3":"Originalquellen", "self-model.sqlite3":"Bestätigte Angaben",
        "conversations.sqlite3":"Gespräche", "workspace.sqlite3":"Projekte und Notizen",
        "workspace-views.sqlite3":"Ablage und Ansichten", "procedures.sqlite3":"Skills",
        "rueckmeldungen.sqlite3":"Korrekturen", "regeln.sqlite3":"Dauerfreigaben",
        "proposals.sqlite3":"Vorschläge", "audit.sqlite3":"Aktionsnachweise",
        "mac-calendar.sqlite3":"Mac-Kalender", "calendar-actions.sqlite3":"Kalenderaktionen",
        "gespraeche.sqlite3":"Transkriptzuordnung", "logbuch.sqlite3":"Verlauf",
        "lint.sqlite3":"Pflegehinweise", "cloud-memory-jobs.sqlite3":"Cloudpakete",
        "einstellungen.json":"Einstellungen", "schluessel.icarus":"Schlüsselspeicher"]
    static func matches(_ value: String, _ pattern: String) -> Bool {
        value.range(of: pattern, options: .regularExpression) != nil
    }
    init?(_ body: [String: Any]) {
        guard let version = body["version"] as? NSNumber, CFGetTypeID(version) != CFBooleanGetTypeID(),
              version.intValue == 1, version.doubleValue == 1,
              body["mode"] as? String == "inspection", let operational = body["operational"] as? NSNumber,
              CFGetTypeID(operational) == CFBooleanGetTypeID(), !operational.boolValue,
              let fingerprint = body["report_fingerprint"] as? String, Self.matches(fingerprint, "^[a-f0-9]{64}$"),
              let restoreID = body["restore_id"] as? String, Self.matches(restoreID, "^[a-f0-9]{32}$"),
              let unresolved = body["unresolved"] as? [String],
              let restored = body["restored"] as? [String: Any],
              let groups = body["comparison_groups"] as? [[String: Any]], groups.count <= 32 else { return nil }
        let globalOK = Set(unresolved).subtracting(["current_authority_unverified", "no_comparison_state"]).isEmpty
        func choice(_ value: [String: Any], id: String, title: String, groupOK: Bool) -> RecoveryChoice? {
            guard let raw = value["files"] as? [[String: Any]], raw.count <= Self.labels.count else { return nil }
            var names = Set<String>(), files: [(name: String, status: String)] = []
            for item in raw {
                guard let name = item["name"] as? String, Self.labels[name] != nil,
                      names.insert(name).inserted, let status = item["status"] as? String,
                      !status.isEmpty, status.count <= 80 else { return nil }
                files.append((name, status))
            }
            let eligible = globalOK && groupOK && files.contains { $0.name.hasSuffix(".sqlite3") && $0.status == "verified" }
                && files.allSatisfy { ["verified", "missing"].contains($0.status) }
            var detail = files.map { (Self.labels[$0.name] ?? $0.name) + ": " +
                ($0.status == "verified" ? "lesbar" : $0.status == "missing" ? "nicht enthalten" : "ungeklärt – erneute Prüfung erforderlich") }.joined(separator: "\n")
            if let tables = value["tables"] as? [[String: Any]] {
                let changed = tables.filter { table in
                    ["changed_rows", "only_in_restored", "only_in_comparison"].contains { (table[$0] as? Int ?? 0) > 0 }
                }.count
                detail += "\n\n\(changed) Tabellen mit Unterschieden zum Sicherungsstand. Herkunft und zeitliche Reihenfolge sind nicht bestätigt."
            }
            return RecoveryChoice(id: id, title: title, files: files, eligible: eligible, detail: detail)
        }
        guard let first = choice(restored, id: "restored", title: "Wiederhergestellte Sicherung", groupOK: true) else { return nil }
        var choices = [first], identifiers = Set(["restored"])
        for group in groups {
            guard let id = group["group"] as? String, Self.matches(id, "^[0-9]{8}T[0-9]{6}Z$"),
                  identifiers.insert(id).inserted, let unresolved = group["unresolved"] as? [String],
                  let value = choice(group, id: id, title: "Vergleichsstand \(id)",
                      groupOK: Set(unresolved).subtracting(["lineage_and_recency_unverified"]).isEmpty) else { return nil }
            choices.append(value)
        }
        self.fingerprint = fingerprint; self.choices = choices
    }
}

struct RecoverySelection {
    private(set) var report: RecoveryReport?
    private(set) var selectedID: String?
    var acknowledged = false
    var selected: RecoveryChoice? { report?.choices.first { $0.id == selectedID } }
    var canPrepare: Bool { acknowledged && selected?.eligible == true }
    mutating func replace(_ value: RecoveryReport) { report = value; selectedID = nil; acknowledged = false }
    mutating func choose(_ id: String?) { selectedID = id; acknowledged = false }
}

enum RecoveryLocation {
    static func loopback(_ value: String) -> URL? {
        guard let url = URL(string: value), url.scheme == "http", url.host == "127.0.0.1",
              let port = url.port, (1...65535).contains(port), url.user == nil, url.password == nil,
              url.query == nil, url.fragment == nil, url.path.isEmpty || url.path == "/" else { return nil }
        return url
    }
    static func storeIdentifier(_ value: String) -> UUID? {
        guard RecoveryReport.matches(value, "^[a-f0-9]{32}$") else { return nil }
        var formatted = value
        for offset in [20,16,12,8] { formatted.insert("-", at: formatted.index(formatted.startIndex, offsetBy: offset)) }
        return UUID(uuidString: formatted)
    }
}

/// Global menu actions must never fall back to the personal service when a
/// working copy or a native selection dialog owns keyboard focus.
enum RecoveryReloadTarget: Equatable {
    case none, main, recovery(UUID)

    static func resolve(mainIsKey: Bool, mainBusy: Bool, recoveryID: UUID?, recoveryReady: Bool) -> Self {
        if let identifier = recoveryID { return recoveryReady ? .recovery(identifier) : .none }
        return mainIsKey && !mainBusy ? .main : .none
    }
}
