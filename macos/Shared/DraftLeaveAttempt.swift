import Foundation
import CoreFoundation

/// Main-thread acknowledgement shared by the bounded WebKit callback and timeout.
/// Only an actual JavaScript boolean true permits leaving without a warning.
final class DraftLeaveAttempt {
    private var completion: ((Bool) -> Void)?
    init(_ completion: @escaping (Bool) -> Void) { self.completion = completion }
    func finish(_ value: Any?) {
        guard let callback = completion else { return }
        completion = nil
        let number = value as? NSNumber
        callback(number.map { CFGetTypeID($0) == CFBooleanGetTypeID() && $0.boolValue } ?? false)
    }
}
