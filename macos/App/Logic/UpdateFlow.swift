import Foundation

// Das Update über die Brücke: welche Nachricht gilt und in welcher Reihenfolge die Schritte laufen.
// Reine Logik; was ein Schritt tut, steht in macos/App/Updater.swift.

/// Die Nachricht der Oberfläche: `window.webkit.messageHandlers.kingfisher.postMessage({aktion: "aktualisieren", …})`.
struct UpdateRequest: Equatable {
    /// Name des `WKScriptMessageHandler`, unter dem die App hört.
    static let bridgeName = "kingfisher"
    /// Die einzige Aktion; jede andere wird ignoriert.
    static let action = "aktualisieren"

    let fassung: String
    let image: String

    /// Nur eine vollständige Nachricht mit gültigem Bild wird zur Anfrage; alles andere ergibt nil.
    init?(message body: Any) {
        guard let fields = body as? [String: Any], fields["aktion"] as? String == UpdateRequest.action,
              let fassung = fields["fassung"] as? String, let image = fields["image"] as? String,
              ImageName.isValid(image, fassung: fassung) else { return nil }
        self.fassung = fassung
        self.image = image
    }
}

/// Die Schritte in ihrer Reihenfolge. Die Sicherung kommt zuerst; ohne sie wird nichts verändert.
enum UpdateStep: String, CaseIterable {
    case backup        // (a) Sicherung über den Sidecar
    case pull          // (b) neues Bild laden
    case switchImage   // (c) KINGFISHER_IMAGE in der Env-Datei setzen
    case restart       // (d) up -d
    case waitForHealth // (e) Fassung und Bild nach dem Start prüfen
}

enum UpdateSnapshotName {
    static func isValid(_ name: String) -> Bool {
        guard name.range(of: #"\Avor-update-[0-9]{8}T[0-9]{6}Z\z"#, options: .regularExpression) != nil,
              let stamp = DateFormatter.updateSnapshot.date(from: String(name.dropFirst("vor-update-".count))) else {
            return false
        }
        return DateFormatter.updateSnapshot.string(from: stamp) == String(name.dropFirst("vor-update-".count))
    }
}

private extension DateFormatter {
    static var updateSnapshot: DateFormatter {
        let formatter = DateFormatter()
        formatter.locale = Locale(identifier: "en_US_POSIX")
        formatter.timeZone = TimeZone(secondsFromGMT: 0)
        formatter.dateFormat = "yyyyMMdd'T'HHmmss'Z'"
        formatter.isLenient = false
        return formatter
    }
}

enum UpdatePhase: Equatable {
    case running(UpdateStep)
    /// Die Sicherung ist gescheitert; es wurde nichts verändert.
    case notStarted
    /// Ein Schritt nach der Sicherung ist gescheitert; die alte Fassung wird wieder gestartet.
    case rollingBack
    /// Die alte Fassung läuft wieder.
    case rolledBack
    /// Auch die alte Fassung startet nicht.
    case broken
    /// Die neue Fassung läuft; die Seite wird neu geladen.
    case finished

    var isOver: Bool {
        switch self {
        case .running, .rollingBack: return false
        default: return true
        }
    }
}

/// Zustandsfolge eines Updates. Jeder Schritt meldet Erfolg oder Misserfolg, die Maschine sagt, was folgt.
struct UpdateMachine {
    private(set) var phase: UpdatePhase = .running(UpdateStep.allCases[0])

    mutating func report(success: Bool) {
        switch phase {
        case .running(let step):
            if success {
                let steps = UpdateStep.allCases
                let index = steps.firstIndex(of: step)!
                phase = index + 1 < steps.count ? .running(steps[index + 1]) : .finished
            } else {
                phase = [.backup, .pull, .switchImage].contains(step) ? .notStarted : .rollingBack
            }
        case .rollingBack:
            phase = success ? .rolledBack : .broken
        default:
            break
        }
    }
}
