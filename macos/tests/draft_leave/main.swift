import Foundation

func expect(_ condition: @autoclosure () -> Bool, _ message: String) {
    if !condition() { fatalError(message) }
}
for value: Any? in [nil, false, NSNumber(value: 1), "true", NSNull()] {
    var calls: [Bool] = []
    let attempt = DraftLeaveAttempt { calls.append($0) }
    attempt.finish(value)
    attempt.finish(true)
    expect(calls == [false], "unknown, numeric or failed result must preserve the window; late success ignored")
}
var saved: [Bool] = []
let success = DraftLeaveAttempt { saved.append($0) }
success.finish(true)
success.finish(nil)
expect(saved == [true], "acknowledged save wins once, timeout cannot undo it")
var expired: [Bool] = []
let timeout = DraftLeaveAttempt { expired.append($0) }
timeout.finish(nil)
timeout.finish(true)
expect(expired == [false], "timeout must not later close a retained window")
print("Draft leave acknowledgement and timeout boundaries passed")
