import Foundation

// Die private Env-Datei der App (Token, Passphrase, Bild). Reine Logik ohne AppKit: Sie läuft auch unter Linux
// im Testprogramm macos/tests/main.swift.

/// Variablennamen wie im Bestand (`scripts/kingfisher_starten.py`, Makefile, compose.yaml). Andere Namen
/// würde der Container nicht lesen, und eine neue Passphrase macht die Schlüsseldatei im Datenvolume unlesbar.
enum EnvKey {
    static let token = "ICARUS_SIDECAR_TOKEN"
    static let passphrase = "ICARUS_SECRETS_PASSPHRASE"
    /// Welches fertige Bild läuft (`deploy/compose.app.yaml`: `image: ${KINGFISHER_IMAGE}`).
    static let image = "KINGFISHER_IMAGE"
}

/// Inhalt im Format von `docker compose --env-file`: Zeilen `NAME=wert`, Kommentare mit `#`.
/// Fremde Zeilen bleiben beim Ändern unverändert, damit ein Schreiben nichts verliert.
struct EnvFile: Equatable {
    private(set) var lines: [String]

    init(text: String) {
        var lines = text.replacingOccurrences(of: "\r\n", with: "\n").components(separatedBy: "\n")
        if lines.last == "" { lines.removeLast() }
        self.lines = lines
    }

    var text: String { lines.isEmpty ? "" : lines.joined(separator: "\n") + "\n" }

    /// Der Wert der letzten Zeile mit diesem Namen (wie bei Compose); umschließende Anführungszeichen entfernt.
    func value(_ name: String) -> String? {
        for line in lines.reversed() {
            guard let value = EnvFile.value(of: name, in: line) else { continue }
            return value
        }
        return nil
    }

    /// Setzt einen Wert. Gibt es den Namen schon, wird die erste Zeile ersetzt und jede weitere entfernt.
    /// Werte mit Zeilenumbruch werden abgewiesen: Sie würden eine zweite Variable einschleusen.
    @discardableResult
    mutating func set(_ name: String, _ value: String) -> Bool {
        guard !value.contains("\n"), !value.contains("\r"), !name.isEmpty else { return false }
        let line = "\(name)=\(value)"
        var replaced = false
        lines = lines.compactMap { current in
            guard EnvFile.value(of: name, in: current) != nil else { return current }
            if replaced { return nil }
            replaced = true
            return line
        }
        if !replaced { lines.append(line) }
        return true
    }

    /// Token und Passphrase sind beide vorhanden und nicht leer.
    var hasKeys: Bool {
        !(value(EnvKey.token) ?? "").isEmpty && !(value(EnvKey.passphrase) ?? "").isEmpty
    }

    /// Eine neue Datei mit frisch erzeugten Werten; die Kopfzeilen sagen, warum sie erhalten bleiben muss.
    static func generated(token: String, passphrase: String) -> EnvFile {
        EnvFile(text: [
            "# Von der Kingfisher-App erzeugt – nicht weitergeben.",
            "#",
            "# Beide Werte müssen erhalten bleiben. Die Passphrase entschlüsselt die Schlüsseldatei im Datenvolume;",
            "# ist sie weg, sind die dort hinterlegten API- und Mailpasswörter unlesbar.",
            "\(EnvKey.token)=\(token)",
            "\(EnvKey.passphrase)=\(passphrase)",
        ].joined(separator: "\n"))
    }

    /// Übernimmt eine vorhandene Datei (etwa `.kingfisher.env` aus `make start`) vollständig, mit einem Vermerk.
    static func adopted(_ existing: EnvFile, from source: String) -> EnvFile {
        var result = EnvFile(text: "# Von der Kingfisher-App übernommen aus \(source.replacingOccurrences(of: "\n", with: " "))\n")
        result.lines += existing.lines
        return result
    }

    private static func value(of name: String, in line: String) -> String? {
        var rest = Substring(line.trimmingCharacters(in: .whitespaces))
        if rest.hasPrefix("export ") { rest = rest.dropFirst(7).drop(while: { $0 == " " }) }
        guard rest.hasPrefix(name + "=") else { return nil }
        var value = String(rest.dropFirst(name.count + 1)).trimmingCharacters(in: .whitespaces)
        for quote in ["\"", "'"] where value.count >= 2 && value.hasPrefix(quote) && value.hasSuffix(quote) {
            value = String(value.dropFirst().dropLast())
        }
        return value
    }
}

/// Bytes als Kleinbuchstaben-Hex, wie `secrets.token_hex` im Starter.
func hexString(_ bytes: [UInt8]) -> String {
    bytes.map { String(format: "%02x", $0) }.joined()
}

/// Liest und schreibt die Env-Datei. Der Ordner ist nur für den Benutzer zugänglich (0700), die Datei 0600.
struct EnvStore {
    let file: URL

    func read() -> EnvFile? {
        guard let data = try? Data(contentsOf: file), let text = String(data: data, encoding: .utf8) else { return nil }
        return EnvFile(text: text)
    }

    func write(_ env: EnvFile) throws {
        let folder = file.deletingLastPathComponent()
        try FileManager.default.createDirectory(at: folder, withIntermediateDirectories: true,
                                                attributes: [.posixPermissions: 0o700])
        try FileManager.default.setAttributes([.posixPermissions: 0o700], ofItemAtPath: folder.path)
        // Atomar ersetzen: Ein Absturz mitten im Schreiben hinterlässt die alte Datei, keine halbe.
        try Data(env.text.utf8).write(to: file, options: .atomic)
        try FileManager.default.setAttributes([.posixPermissions: 0o600], ofItemAtPath: file.path)
    }
}
