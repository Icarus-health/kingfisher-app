#if canImport(EventKit)
import EventKit
import Foundation

/// Im Hauptprogramm gebündelt: dieselbe TCC-Identität wie das sichtbare Kingfisher-Fenster.
final class EventKitCalendar: NativeCalendarReading {
    private lazy var store = EKEventStore()
    private let formatter = ISO8601DateFormatter()

    var status: String {
        guard #available(macOS 14, *) else { return "error" }
        switch EKEventStore.authorizationStatus(for: .event) {
        case .fullAccess: return "granted"
        case .writeOnly: return "write_only"
        case .denied: return "denied"
        case .restricted: return "restricted"
        case .notDetermined: return "not_determined"
        default: return "unknown"
        }
    }

    func authorize(if allowed: @escaping () -> Bool, _ completion: @escaping () -> Void) {
        guard #available(macOS 14, *) else { completion(); return }
        // Ein eigenes kurzlebiges Store vermeidet einen Zugriff vom Dialog-Callback auf die Leser-Queue.
        DispatchQueue.main.async {
            guard allowed() else { completion(); return }
            let permissionStore = EKEventStore()
            permissionStore.requestFullAccessToEvents { _, _ in
                withExtendedLifetime(permissionStore) { completion() }
            }
        }
    }

    func calendars() throws -> [[String: Any]] {
        guard status == "granted" else { throw NativeCalendarError.invalidState }
        let calendars = store.calendars(for: .event)
        guard calendars.count <= 100 else { throw NativeCalendarError.oversizedSnapshot }
        return calendars.map { ["id": $0.calendarIdentifier, "name": $0.title, "source": $0.source.title] }
    }

    func events(ids: [String], from: Date, to: Date, notes: Bool) throws -> [[String: Any]] {
        guard status == "granted", !ids.isEmpty, ids.count <= 100, Set(ids).count == ids.count,
              ids.allSatisfy({ !$0.isEmpty }), to > from, to.timeIntervalSince(from) <= 31 * 86400 else {
            throw NativeCalendarError.invalidState
        }
        let selected = store.calendars(for: .event).filter { ids.contains($0.calendarIdentifier) }
        guard Set(selected.map(\.calendarIdentifier)) == Set(ids) else { throw NativeCalendarError.invalidState }
        let predicate = store.predicateForEvents(withStart: from, end: to, calendars: selected)
        let events = store.events(matching: predicate)
        guard events.count <= 10000 else { throw NativeCalendarError.oversizedSnapshot }
        return try events.map { event in
            guard let calendar = event.calendar, let start = event.startDate, let end = event.endDate,
                  end >= start, ids.contains(calendar.calendarIdentifier) else { throw NativeCalendarError.invalidState }
            var identity = [calendar.calendarIdentifier, event.calendarItemIdentifier]
            if event.hasRecurrenceRules || event.isDetached { identity.append(formatter.string(from: start)) }
            let uid = try JSONSerialization.data(withJSONObject: identity).base64EncodedString()
            var entry: [String: Any] = ["uid": uid, "external_uid": event.calendarItemExternalIdentifier ?? "",
                "summary": event.title ?? "", "start": formatter.string(from: start),
                "end": formatter.string(from: end), "all_day": event.isAllDay, "location": event.location ?? "",
                "source_id": calendar.calendarIdentifier, "source_label": calendar.title,
                "attendees": (event.attendees ?? []).map { participant -> String in
                    let name = participant.name?.trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
                    let address = participant.url.scheme?.lowercased() == "mailto"
                        ? String(participant.url.absoluteString.dropFirst(7)).removingPercentEncoding ?? "" : ""
                    if name.isEmpty { return address }
                    return address.isEmpty || name == address ? name : "\(name) <\(address)>"
                }.filter { !$0.isEmpty }]
            if notes { entry["notes"] = String((event.notes ?? "").prefix(20000)) }
            return entry
        }
    }
}
#endif
