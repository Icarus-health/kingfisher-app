import EventKit
import Foundation

// Read-only JSON adapter. No network, writes or credentials. Participants stay calendar metadata.
// Notes are read only when the caller asks for them (`with_notes`, memory sync); the live view never gets them.
func output(_ value: [String: Any], _ code: Int32 = 0) -> Never {
    let data = try! JSONSerialization.data(withJSONObject: value, options: [.sortedKeys])
    print(String(decoding: data, as: UTF8.self))
    exit(code)
}

func status() -> String {
    switch EKEventStore.authorizationStatus(for: .event) {
    case .fullAccess: return "granted"
    case .writeOnly: return "write_only"
    case .denied: return "denied"
    case .restricted: return "restricted"
    case .notDetermined: return "not_determined"
    default: return "unknown"
    }
}

let command = CommandLine.arguments.dropFirst().first ?? "status"
guard ["status", "authorize", "calendars", "events"].contains(command) else {
    output(["ok": false, "error": "Unsupported command"], 2)
}
if command == "status" {
    output(["ok": true, "status": status(), "read_only": true])
}

let formatter = ISO8601DateFormatter()
var selected: [String] = []
var start = Date()
var end = Date()
var withNotes = false
if command == "events" {
    let data = FileHandle.standardInput.readDataToEndOfFile()
    guard data.count <= 65_536,
          let input = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
          let ids = input["calendar_ids"] as? [String], !ids.isEmpty, ids.count <= 100,
          ids.allSatisfy({ !$0.isEmpty }),
          let from = input["start"] as? String, let to = input["end"] as? String,
          let parsedStart = formatter.date(from: from), let parsedEnd = formatter.date(from: to),
          parsedEnd > parsedStart, parsedEnd.timeIntervalSince(parsedStart) <= 31 * 86400 else {
        output(["ok": false, "error": "Select calendars and a valid ISO-8601 window of at most 31 days"], 2)
    }
    selected = ids
    withNotes = (input["with_notes"] as? Bool) ?? false
    start = parsedStart
    end = parsedEnd
}

let store = EKEventStore()
if command == "authorize" {
    store.requestFullAccessToEvents { granted, error in
        var result: [String: Any] = ["ok": granted, "status": status()]
        if let error { result["error"] = error.localizedDescription }
        output(result, granted ? 0 : 1)
    }
    RunLoop.current.run(until: Date().addingTimeInterval(120))
    output(["ok": false, "error": "Authorization timed out"], 1)
}
guard status() == "granted" else {
    output(["ok": false, "status": status(), "error": "Calendar permission required"], 3)
}
let available = store.calendars(for: .event)
if command == "calendars" {
    output(["ok": true, "calendars": available.map {
        ["id": $0.calendarIdentifier, "name": $0.title, "source": $0.source.title]
    }])
}
let calendars = available.filter { selected.contains($0.calendarIdentifier) }
guard Set(calendars.map(\.calendarIdentifier)) == Set(selected) else {
    output(["ok": false, "error": "A selected calendar is unavailable; select again"], 2)
}
let predicate = store.predicateForEvents(withStart: start, end: end, calendars: calendars)
let events = store.events(matching: predicate).sorted { $0.startDate < $1.startDate }
guard events.count <= 10_000 else {
    output(["ok": false, "error": "Too many events; use a smaller window"], 2)
}
output(["ok": true, "start": formatter.string(from: start), "end": formatter.string(from: end),
        "events": events.map { event -> [String: Any] in
    // Calendar + item + occurrence prevent collisions between recurring instances.
    // Only recurring or detached occurrences need their start in the identity. A single event keeps
    // its identity when it is moved, so the memory records a new version instead of a second event.
    var identity = [event.calendar.calendarIdentifier, event.calendarItemIdentifier]
    if event.hasRecurrenceRules || event.isDetached {
        identity.append(formatter.string(from: event.startDate))
    }
    let uid = try! JSONSerialization.data(withJSONObject: identity).base64EncodedString()
    var entry: [String: Any] = ["uid": uid, "external_uid": event.calendarItemExternalIdentifier ?? "",
            "summary": event.title ?? "", "start": formatter.string(from: event.startDate),
            "end": formatter.string(from: event.endDate), "all_day": event.isAllDay,
            "location": event.location ?? "", "source_id": event.calendar.calendarIdentifier,
            "source_label": event.calendar.title,
            "attendees": (event.attendees ?? []).map { participant -> String in
                let name = participant.name?.trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
                let address = participant.url.scheme?.lowercased() == "mailto"
                    ? String(participant.url.absoluteString.dropFirst(7)).removingPercentEncoding ?? "" : ""
                if name.isEmpty { return address }
                return address.isEmpty || name == address ? name : "\(name) <\(address)>"
            }.filter { !$0.isEmpty }]
    if withNotes {
        entry["notes"] = String((event.notes ?? "").prefix(20_000))
    }
    return entry
}])
