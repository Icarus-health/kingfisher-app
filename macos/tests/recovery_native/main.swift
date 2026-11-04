import Foundation

func expect(_ condition: @autoclosure () -> Bool, _ message: String) {
    if !condition() { fatalError(message) }
}
let file: [String: Any] = ["name": "tasks.sqlite3", "status": "verified"]
func fixture(_ changes: [String: Any] = [:]) -> [String: Any] {
    var value: [String: Any] = ["version": 1, "mode": "inspection", "operational": false,
        "report_fingerprint": String(repeating: "a", count: 64), "restore_id": String(repeating: "b", count: 32),
        "unresolved": ["current_authority_unverified", "no_comparison_state"],
        "restored": ["files": [file]], "comparison_groups": []]
    changes.forEach { value[$0] = $1 }; return value
}
let report = RecoveryReport(fixture())!
expect(report.choices.count == 1, "restored available")
expect(report.choices[0].eligible, "verified DB usable")
var selection = RecoverySelection()
selection.replace(report)
expect(!selection.canPrepare, "never select or acknowledge implicitly")
selection.choose("restored")
expect(!selection.canPrepare, "ack required")
selection.acknowledged = true
expect(selection.canPrepare, "reviewed choice and ack")
selection.replace(report)
expect(selection.selectedID == nil && !selection.acknowledged, "new report invalidates consent")
selection.choose("missing")
selection.acknowledged = true
expect(!selection.canPrepare, "foreign choice rejected")
let bad = RecoveryReport(fixture(["restored": ["files": [file, ["name":"knowledge.sqlite3", "status":"corrupt"]]]]))!
expect(!bad.choices[0].eligible, "present invalid files block")
let missing = RecoveryReport(fixture(["restored": ["files": [file, ["name":"knowledge.sqlite3", "status":"missing"]]]]))!
expect(missing.choices[0].eligible && missing.choices[0].missing == 1, "missing explicit")
let noDB = RecoveryReport(fixture(["restored": ["files": [["name":"einstellungen.json", "status":"verified"]]]]))!
expect(!noDB.choices[0].eligible, "needs DB")
let unstable = RecoveryReport(fixture(["unresolved":["changed_during_read"]]))!
expect(!unstable.choices[0].eligible, "unstable global report")
let groups: [[String: Any]] = [["group":"20261104T120000Z", "files":[file], "tables":[], "unresolved":["lineage_and_recency_unverified"]]]
let compared = RecoveryReport(fixture(["comparison_groups":groups]))!
expect(compared.choices.count == 2 && compared.choices[1].eligible, "explicit comparison selection")
expect(RecoveryReport(fixture(["report_fingerprint":"../invalid"])) == nil, "invalid fingerprint")
expect(RecoveryReport(fixture(["version":true])) == nil, "boolean version")
expect(RecoveryReport(fixture(["comparison_groups":[["group":"../escape", "files":[file], "unresolved":[]]]])) == nil, "invalid group")
expect(RecoveryReport(fixture(["restored":["files":[file,file]]])) == nil, "duplicate filenames")
expect(RecoveryReport(fixture(["restored":["files":[["name":"outside.sqlite3", "status":"verified"]]]])) == nil, "unknown files")
expect(RecoveryReport(fixture(["comparison_groups":groups+groups])) == nil, "duplicate groups")
expect(RecoveryLocation.loopback("http://127.0.0.1:32123") != nil, "loopback URL")
for value in ["https://example.com", "http://localhost:1234", "http://127.0.0.1:1234/a", "http://user@127.0.0.1:1234", "http://127.0.0.1:1234?key=secret", "http://127.0.0.1"] {
    expect(RecoveryLocation.loopback(value) == nil, "reject foreign or decorated URL")
}
print("Recovery selection, consent and loopback boundaries passed")

let firstCopy = UUID(), secondCopy = UUID()
expect(RecoveryReloadTarget.resolve(mainIsKey: true, mainBusy: false, recoveryID: nil, recoveryReady: false) == .main,
       "main reload requires main focus")
expect(RecoveryReloadTarget.resolve(mainIsKey: true, mainBusy: true, recoveryID: nil, recoveryReady: false) == .none,
       "busy main cannot reload")
expect(RecoveryReloadTarget.resolve(mainIsKey: false, mainBusy: true, recoveryID: firstCopy, recoveryReady: true) == .recovery(firstCopy),
       "active copy independent of main startup")
expect(RecoveryReloadTarget.resolve(mainIsKey: false, mainBusy: false, recoveryID: secondCopy, recoveryReady: true) == .recovery(secondCopy),
       "only active copy reloads")
expect(RecoveryReloadTarget.resolve(mainIsKey: true, mainBusy: false, recoveryID: firstCopy, recoveryReady: false) == .none,
       "review must never fall through to main")
expect(RecoveryReloadTarget.resolve(mainIsKey: false, mainBusy: false, recoveryID: nil, recoveryReady: false) == .none,
       "foreign or no window cannot reload main")
