import Foundation

// Fassungen, Bildnamen und das Manifest der Download-Seite. Reine Logik, unter Linux prüfbar.

/// Eine Fassung nach SemVer: `MAJOR.MINOR.PATCH`, optional `-vorabkennung`. Build-Angaben (`+…`) sind
/// ausgeschlossen, weil Docker-Tags kein `+` erlauben und die Fassung zugleich der Tag des Bildes ist.
struct SemVer: Comparable, CustomStringConvertible {
    let major: Int
    let minor: Int
    let patch: Int
    let prerelease: [String]

    init?(_ text: String) {
        let parts = text.split(separator: "-", maxSplits: 1, omittingEmptySubsequences: false)
        let core = parts[0].split(separator: ".", omittingEmptySubsequences: false)
        guard core.count == 3, let major = SemVer.number(core[0]), let minor = SemVer.number(core[1]),
              let patch = SemVer.number(core[2]) else { return nil }
        var prerelease: [String] = []
        if parts.count == 2 {
            prerelease = parts[1].split(separator: ".", omittingEmptySubsequences: false).map(String.init)
            let allowed = CharacterSet(charactersIn: "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-")
            for identifier in prerelease {
                guard !identifier.isEmpty, identifier.unicodeScalars.allSatisfy({ allowed.contains($0) }) else { return nil }
                if identifier.allSatisfy({ $0.isASCII && $0.isNumber }) && SemVer.number(Substring(identifier)) == nil {
                    return nil
                }
            }
        }
        self.major = major
        self.minor = minor
        self.patch = patch
        self.prerelease = prerelease
    }

    var description: String {
        "\(major).\(minor).\(patch)" + (prerelease.isEmpty ? "" : "-" + prerelease.joined(separator: "."))
    }

    static func < (left: SemVer, right: SemVer) -> Bool {
        if (left.major, left.minor, left.patch) != (right.major, right.minor, right.patch) {
            return (left.major, left.minor, left.patch) < (right.major, right.minor, right.patch)
        }
        // Eine Vorabfassung liegt vor der fertigen Fassung.
        if left.prerelease.isEmpty || right.prerelease.isEmpty { return !left.prerelease.isEmpty && right.prerelease.isEmpty }
        for (a, b) in zip(left.prerelease, right.prerelease) where a != b {
            switch (Int(a), Int(b)) {
            case let (x?, y?): return x < y
            case (.some, nil): return true
            case (nil, .some): return false
            default: return a < b
            }
        }
        return left.prerelease.count < right.prerelease.count
    }

    static func == (left: SemVer, right: SemVer) -> Bool {
        (left.major, left.minor, left.patch) == (right.major, right.minor, right.patch) && left.prerelease == right.prerelease
    }

    /// Eine Zahl ohne führende Null (außer „0“ selbst), nur ASCII-Ziffern.
    private static func number(_ text: Substring) -> Int? {
        guard !text.isEmpty, text.allSatisfy({ $0.isASCII && $0.isNumber }),
              text == "0" || !text.hasPrefix("0") else { return nil }
        return Int(text)
    }
}

/// Welche Bilder die App starten darf: nur das eigene, mit der Fassung als Tag.
enum ImageName {
    static let prefix = "ghcr.io/icarus-health/kingfisher-app:"

    /// Das Bild beginnt mit dem eigenen Präfix, und sein Tag ist genau diese Fassung.
    static func isValid(_ image: String, fassung: String) -> Bool {
        guard SemVer(fassung) != nil, image.hasPrefix(prefix) else { return false }
        return String(image.dropFirst(prefix.count)) == fassung
    }

    static func forFassung(_ fassung: String) -> String { prefix + fassung }

    /// Die Fassung aus einem gültigen Bildnamen, sonst nil.
    static func fassung(of image: String) -> String? {
        guard image.hasPrefix(prefix) else { return nil }
        let tag = String(image.dropFirst(prefix.count))
        return isValid(image, fassung: tag) ? tag : nil
    }
}

/// `latest.json` der Download-Seite. Die App braucht es nur beim ersten Start.
struct Manifest: Decodable {
    static let url = URL(string: "https://icarus-health.github.io/kingfisher-app/latest.json")!

    let fassung: String
    let image: String
    let appMindestens: String?

    enum CodingKeys: String, CodingKey {
        case fassung, image
        case appMindestens = "app_mindestens"
    }

    static func decode(_ data: Data) -> Manifest? { try? JSONDecoder().decode(Manifest.self, from: data) }
}

/// Das Bild für den ersten Start: das aus dem Manifest, wenn es gültig ist und diese App neu genug dafür ist;
/// sonst das Bild mit der eigenen Fassung der App.
func firstImage(manifest: Manifest?, appFassung: String) -> String {
    let fallback = ImageName.forFassung(appFassung)
    guard let manifest = manifest, ImageName.isValid(manifest.image, fassung: manifest.fassung) else { return fallback }
    if let minimum = manifest.appMindestens {
        guard let needed = SemVer(minimum), let own = SemVer(appFassung), own >= needed else { return fallback }
    }
    return manifest.image
}
