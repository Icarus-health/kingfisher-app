import Foundation
let script = URL(fileURLWithPath: CommandLine.arguments[1])
let client = RecoveryHelperClient(script: script, docker: "/usr/bin/synthetic-docker", image: "sha256:" + String(repeating: "a", count: 64))
func success(_ result: Result<[String: Any], RecoveryFailure>) -> [String: Any] {
    switch result { case .success(let value): return value; case .failure(let error): fatalError(error.message) }
}
let response = success(client.request("extract", fields: ["password":"synthetic-$(never-execute)", "bundle":"/synthetic test/package", "target":"/synthetic target"]))
precondition(response["folder"] as? String == "/synthetic target")
for mode in ["bad-json", "private-stderr", "oversized"] {
    switch client.request(mode) {
    case .success: fatalError("bad response accepted")
    case .failure(let failure): precondition(!failure.message.contains("synthetic-private-value"))
    }
}
let output = success(client.request("chunked"))
precondition(output["tail"] as? String == "complete")
let blocked = RecoveryHelperClient(script: script.deletingLastPathComponent().appendingPathComponent("blocked.py"),
    docker: "/synthetic", image: "sha256:" + String(repeating: "a", count: 64), timeout: 0.25)
let started = Date()
switch blocked.request("extract", fields: ["password":String(repeating:"p",count:50_000)]) {
case .success: fatalError("blocked stdin accepted")
case .failure: precondition(Date().timeIntervalSince(started) < 3, "deadline must include blocked stdin")
}
print("Private helper input and bounded output passed")
