import Foundation

final class Reader: NativeCalendarReading {
    var status = "granted"
    var authorizations = 0
    var reads = 0
    var notesRead: [Bool] = []
    var onRead: (() -> Void)?
    var deferPermission = false
    var failRead = false
    var permissionCheck: (() -> Bool)?
    func authorize(if allowed: @escaping () -> Bool, _ completion: @escaping () -> Void) {
        if deferPermission { permissionCheck = allowed; return }
        if allowed() { authorizations += 1 }; completion()
    }
    func calendars() throws -> [[String: Any]] { [["id": "chosen", "name": "Synthetic"]] }
    func events(ids: [String], from: Date, to: Date, notes: Bool) throws -> [[String: Any]] {
        precondition(ids == ["chosen"] && to > from && to.timeIntervalSince(from) <= 31 * 86400)
        if failRead { throw NativeCalendarError.invalidState }
        reads += 1
        notesRead.append(notes)
        onRead?()
        return []
    }
}
var failures = 0
func expect(_ value: Bool, _ message: String) { if !value { failures += 1; print(message) } }
var state: [String: Any] = ["generation": 1, "enabled": true, "authorize": true,
                           "selected": [], "memory_allowed": false, "synced_at": NSNull(),
                           "memory_window": ["days_back": 1095, "days_ahead": 365]]
var posts: [(String, [String: Any])] = []
var refuseMemory = false
var failHeartbeat = false
let reader = Reader()
var active = true
let engine = NativeCalendarEngine(reader: reader, request: { path, body in
    if let body = body {
        if path == "/worker" && failHeartbeat { failHeartbeat = false; throw NativeCalendarError.interrupted }
        posts.append((path, body))
        if path == "/memory" { return ["stored": true, "keine_freigabe": refuseMemory, "fehler": []] }
        return [:]
    }
    return state
}, active: { active })
try engine.tick()
expect(reader.authorizations == 0, "old pending authorization must not prompt at startup")
expect(reader.reads == 0, "empty selection must not read events")
engine.requestPermission(generation: 0)
expect(reader.authorizations == 0, "stale connect generation must not prompt")
engine.requestPermission(generation: 1)
expect(reader.authorizations == 1, "current explicit connect must authorize")
state["authorize"] = false
engine.requestPermission(generation: 1)
expect(reader.authorizations == 1, "consumed authorization must not repeat")
state["selected"] = ["chosen"]
for _ in 0..<14 { try engine.tick() }
expect(reader.reads > 0, "selected live calendar must be read")
expect(posts.contains { $0.0 == "/worker" && $0.1["events"] != nil }, "complete live snapshot must be uploaded")
expect(!posts.contains { $0.0 == "/memory" }, "paused history must never upload")
state["memory_allowed"] = true
for _ in 0..<4 { try engine.tick() }
expect(posts.contains { $0.0 == "/memory" }, "idle selected history must be uploaded")
expect(reader.notesRead.contains(true) && reader.notesRead.contains(false), "notes only belong to history reads")
refuseMemory = true
var interruptionSeen = false
for _ in 0..<4 {
    do { try engine.tick() } catch { interruptionSeen = true; engine.recoverAfterFailure() }
}
expect(interruptionSeen, "partial history acceptance must not be treated as completed")
expect(posts.contains { $0.0 == "/worker" && $0.1["status"] as? String == "granted" &&
    ($0.1["memory_error"] as? String)?.isEmpty == false }, "history failure must be visible without invalidating live view")
refuseMemory = false
state["generation"] = 2
state["memory_allowed"] = false
reader.onRead = { state["generation"] = 3; state["enabled"] = false; state["selected"] = [] }
let eventsBeforeDisconnect = posts.filter { $0.1["events"] != nil }.count
try engine.tick()
try engine.tick()
expect(posts.filter { $0.1["events"] != nil }.count == eventsBeforeDisconnect, "disconnect discards partial snapshot")
let oldCount = posts.count
active = false
try engine.tick()
engine.requestPermission(generation: 1)
expect(posts.count == oldCount && reader.authorizations == 1, "stopped lifecycle must do no work")
for bad: Any in [true, -1, 2.5, "1", 9_007_199_254_740_992 as Double] {
    expect(CalendarPermissionRequest(message: ["aktion": "kalenderFreigeben", "generation": bad]) == nil,
           "malformed permission message must be rejected")
}
expect(CalendarPermissionRequest(message: ["aktion": "kalenderFreigeben", "generation": 9])?.generation == 9,
       "valid permission message must preserve generation")
active = true
state = ["generation": 4, "enabled": true, "authorize": true, "selected": []]
reader.deferPermission = true
engine.requestPermission(generation: 4)
state["generation"] = 5
state["enabled"] = false
expect(reader.permissionCheck?() == false, "disconnect before main-queue dialog must cancel permission")
state = ["generation": 6, "enabled": true, "authorize": false, "selected": ["chosen"], "memory_allowed": false]
reader.onRead = nil
reader.failRead = true
do { try engine.tick() } catch { engine.recoverAfterFailure() }
expect(posts.last?.0 == "/worker" && (posts.last?.1["error"] as? String)?.isEmpty == false,
       "failed live read must report visible error")
reader.failRead = false
state["generation"] = 7
failHeartbeat = true
let beforeTransportFailure = posts.count
do { try engine.tick() } catch { engine.recoverAfterFailure() }
expect(posts.count == beforeTransportFailure, "transport failure must not invent a permission/read failure")
if failures > 0 { exit(1) }
print("Native calendar behavior passed")
