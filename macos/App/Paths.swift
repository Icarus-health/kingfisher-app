import Foundation

// Wo die App ihre Dateien hat, und die lokale Adresse von Kingfisher.

struct AppPaths {
    /// Wie compose.yaml und `make start`: nur an 127.0.0.1, Port 8890.
    static let origin = URL(string: "http://127.0.0.1:8890")!
    static let startPage = "today"

    /// `~/Library/Application Support/Kingfisher`, nur für den Benutzer zugänglich.
    let support: URL
    /// Token, Passphrase und Bild; dieselben Namen wie `.kingfisher.env` des Starters.
    let envFile: URL
    /// `deploy/compose.app.yaml`, beim Bauen als `Contents/Resources/compose.yaml` ins Bündel gelegt.
    let composeFile: URL

    static func standard() -> AppPaths? {
        guard let library = FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask).first,
              let compose = Bundle.main.url(forResource: "compose", withExtension: "yaml") else { return nil }
        let support = library.appendingPathComponent("Kingfisher", isDirectory: true)
        return AppPaths(support: support, envFile: support.appendingPathComponent("kingfisher.env"),
                        composeFile: compose)
    }

    /// Die eigene Fassung der App (CFBundleShortVersionString, beim Bauen aus der Datei VERSION).
    static var appFassung: String {
        Bundle.main.object(forInfoDictionaryKey: "CFBundleShortVersionString") as? String ?? "0.0.0"
    }
}
