import Foundation

let valid = ["lokaleWerkzeugeStatus", "lokaleWerkzeugeEinrichten", "lokaleWerkzeugeAbbrechen"]
var checked = 0
for action in valid {
    for number in [0, 7, 9_007_199_254_740_991] {
        let request = ModuleSetupRequest(message: ["aktion": action, "generation": number])
        precondition(request?.action.rawValue == action && request?.generation == number)
        checked += 1
    }
}
let rejected: [Any] = [
    ["aktion": "shell", "generation": 1],
    ["aktion": valid[1], "generation": true],
    ["aktion": valid[1], "generation": "1"],
    ["aktion": valid[1], "generation": -1],
    ["aktion": valid[1], "generation": 1.5],
    ["aktion": valid[1], "generation": Double.nan],
    ["aktion": valid[1], "generation": Double.infinity],
    ["aktion": valid[1], "generation": 9_007_199_254_740_992],
    ["aktion": valid[1], "generation": 1, "command": "anything"],
    ["aktion": valid[1], "generation": 1, "model": "remote"],
    ["aktion": valid[1], "generation": 1, "path": "/data"],
    ["aktion": valid[1], "generation": 1, "api_key": "artificial"],
    ["aktion": valid[1]], [], "untrusted", NSNull(),
]
for value in rejected { precondition(ModuleSetupRequest(message: value) == nil); checked += 1 }
let cancellation = ModuleSetupCancellation()
precondition(!cancellation.isCancelled())
cancellation.cancel(); cancellation.cancel()
precondition(cancellation.isCancelled())
print("\(checked) closed-request cases and cancellation passed")
