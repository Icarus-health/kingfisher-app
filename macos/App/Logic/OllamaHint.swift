import Foundation

enum OllamaHintState: Equatable {
    case none
    case start
    case download

    static func select(isRunning: Bool, appInstalled: Bool) -> OllamaHintState {
        if isRunning { return .none }
        return appInstalled ? .start : .download
    }
}
