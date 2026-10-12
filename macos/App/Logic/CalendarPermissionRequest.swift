import Foundation
import CoreFoundation

struct CalendarPermissionRequest {
    let generation: Int
    init?(message: Any) {
        guard let body = message as? [String: Any], Set(body.keys) == ["aktion", "generation"],
              body["aktion"] as? String == "kalenderFreigeben",
              let number = body["generation"] as? NSNumber,
              CFGetTypeID(number) != CFBooleanGetTypeID(),
              number.doubleValue >= 0, number.doubleValue <= 9_007_199_254_740_991,
              number.doubleValue.rounded(.towardZero) == number.doubleValue else { return nil }
        generation = number.intValue
    }
}
