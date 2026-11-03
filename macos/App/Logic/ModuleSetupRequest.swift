import Foundation
import CoreFoundation

/// The page can request three fixed actions; it cannot provide a command,
/// model, filesystem path, download URL, provider credential or runtime mode.
struct ModuleSetupRequest {
    enum Action: String {
        case status = "lokaleWerkzeugeStatus"
        case setup = "lokaleWerkzeugeEinrichten"
        case cancel = "lokaleWerkzeugeAbbrechen"
    }
    let action: Action
    let generation: Int

    init?(message: Any) {
        guard let body = message as? [String: Any], Set(body.keys) == ["aktion", "generation"],
              let name = body["aktion"] as? String, let action = Action(rawValue: name),
              let number = body["generation"] as? NSNumber,
              CFGetTypeID(number) != CFBooleanGetTypeID(),
              number.doubleValue.isFinite, number.doubleValue >= 0,
              number.doubleValue <= 9_007_199_254_740_991,
              number.doubleValue.rounded(.towardZero) == number.doubleValue else { return nil }
        self.action = action
        self.generation = number.intValue
    }
}

/// Only this private cancellation bit crosses into the background setup queue.
/// JavaScript never gets process identifiers or access to Docker.
final class ModuleSetupCancellation {
    private let lock = NSLock()
    private var cancelled = false
    func cancel() { lock.lock(); cancelled = true; lock.unlock() }
    func isCancelled() -> Bool { lock.lock(); defer { lock.unlock() }; return cancelled }
}
