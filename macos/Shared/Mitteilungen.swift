import Foundation

// Mitteilungen auf dem Mac (Etappe 5, docs/24-weg-zum-jarvis.md): die reine Logik ohne AppKit und ohne
// UserNotifications, damit sie außerhalb des Macs prüfbar ist (macos/tests/main.swift). Liegt wie PowerReportRequest
// unter Shared, weil beide Fenster (macos/App und KingfisherApp.swift) alle Shared-Quellen übersetzen. Die Pfade und Grenzen sind
// dieselben wie in sidecar/icarus_memory/mitteilungen_routes.py und mitteilungen.py. Alles Unbekannte oder zu Große
// ergibt keine Mitteilung: Lieber eine Mitteilung weniger als eine, die nicht aus dem Sidecar stammt.

enum MitteilungenPfad {
    static let faellig = "/api/v1/mitteilungen/faellig"
    static let einstellung = "/api/v1/mitteilungen/einstellung"
    static let erlaubnis = "/api/v1/mitteilungen/erlaubnis"
    static let kategorie = "KINGFISHER_MITTEILUNG"
    static let aktionOeffnen = "oeffnen"
    static let aktionUeberfluessig = "ueberfluessig"
    /// Alle fünf Minuten; der Sidecar gibt jede Mitteilung nur einmal heraus, gleich wie oft gefragt wird.
    static let interval: TimeInterval = 300
    static let maxJeAbruf = 3
    static let maxTitel = 60
    static let maxSatz = 140
    static let maxKennung = 64
    static let maxPfad = 200

    static func zugestellt(_ roh: String) -> String? {
        guard let kennung = Mitteilung.kodiert(roh) else { return nil }
        return "/api/v1/mitteilungen/" + kennung + "/zugestellt"
    }

    static func rueckmeldung(_ roh: String) -> String? {
        guard let kennung = Mitteilung.kodiert(roh) else { return nil }
        return "/api/v1/mitteilungen/" + kennung + "/rueckmeldung"
    }
}

struct Mitteilung: Equatable {
    let id: String
    let art: String
    let titel: String
    let satz: String
    /// Die Seite in der App, die „Öffnen“ zeigt; immer ein Pfad der eigenen Adresse, nie eine fremde.
    let pfad: String

    static let arten: Set<String> = ["termin", "zusage", "morgen"]
    private static let kennungZeichen = CharacterSet.alphanumerics.union(CharacterSet(charactersIn: ":_-"))
    private static let unkodiert = CharacterSet.alphanumerics.union(CharacterSet(charactersIn: "-_"))

    static func gueltigeKennung(_ kennung: String) -> Bool {
        !kennung.isEmpty && kennung.count <= MitteilungenPfad.maxKennung
            && kennung.unicodeScalars.allSatisfy { kennungZeichen.contains($0) }
    }

    /// Die Kennung für einen Pfad: nur Buchstaben, Ziffern, Bindestrich und Unterstrich bleiben, der Rest wird kodiert.
    static func kodiert(_ kennung: String) -> String? {
        guard gueltigeKennung(kennung) else { return nil }
        return kennung.addingPercentEncoding(withAllowedCharacters: unkodiert)
    }

    /// Ein Pfad innerhalb der eigenen Seite: beginnt mit einem Schrägstrich, kein Schema, keine zweite Adresse, kein Aufstieg.
    static func gueltigerPfad(_ pfad: String) -> Bool {
        guard pfad.hasPrefix("/"), !pfad.hasPrefix("//"), pfad.count <= MitteilungenPfad.maxPfad,
              !pfad.contains(":"), !pfad.contains("\\"), !pfad.contains(".."), !pfad.contains("#") else { return false }
        return pfad.unicodeScalars.allSatisfy { $0.value > 0x20 && $0.value < 0x7f }
    }

    init?(dictionary: [String: Any]) {
        guard let id = dictionary["id"] as? String, Mitteilung.gueltigeKennung(id),
              let art = dictionary["art"] as? String, Mitteilung.arten.contains(art),
              let titel = dictionary["titel"] as? String, !titel.isEmpty, titel.count <= MitteilungenPfad.maxTitel,
              let satz = dictionary["satz"] as? String, satz.count <= MitteilungenPfad.maxSatz,
              let pfad = dictionary["pfad"] as? String, Mitteilung.gueltigerPfad(pfad) else { return nil }
        self.id = id; self.art = art; self.titel = titel; self.satz = satz; self.pfad = pfad
    }

    /// Die Antwort von `GET …/faellig`: höchstens drei. Eine unbrauchbare Antwort ergibt keine Mitteilung.
    static func parse(_ data: Data) -> [Mitteilung] {
        guard let objekt = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
              let liste = objekt["mitteilungen"] as? [Any], liste.count <= MitteilungenPfad.maxJeAbruf else { return [] }
        var ergebnis: [Mitteilung] = []
        for eintrag in liste {
            guard let felder = eintrag as? [String: Any], let mitteilung = Mitteilung(dictionary: felder) else { return [] }
            ergebnis.append(mitteilung)
        }
        return ergebnis
    }
}

struct MitteilungenEinstellung: Equatable {
    /// Der Schalter in den Einstellungen; aus ist die Vorgabe. Erst mit ihm fragt die App das System nach der Erlaubnis.
    let an: Bool

    static func parse(_ data: Data) -> MitteilungenEinstellung? {
        guard let objekt = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
              let an = objekt["an"] as? Bool else { return nil }
        return MitteilungenEinstellung(an: an)
    }
}

enum MitteilungenRequest {
    /// Dieselbe Adressprüfung wie der Energiebericht (nur 127.0.0.1, Token im Kopf); danach nur Pfad, Methode und Körper.
    static func make(origin: URL, path: String, method: String, body: [String: Any]? = nil, token: String) -> URLRequest? {
        guard path.hasPrefix("/api/v1/mitteilungen/"), ["GET", "POST"].contains(method),
              var request = PowerReportRequest.make(origin: origin, source: .unknown, token: token),
              let url = URL(string: path, relativeTo: origin)?.absoluteURL, url.host == origin.host, url.port == origin.port else { return nil }
        request.url = url
        request.httpMethod = method
        request.httpBody = nil
        request.setValue(nil, forHTTPHeaderField: "Content-Type")
        if let body = body {
            guard let data = try? JSONSerialization.data(withJSONObject: body) else { return nil }
            request.httpBody = data
            request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        }
        return request
    }

    /// Was die App dem Sidecar über die Erlaubnis des Systems sagt (`POST …/erlaubnis`).
    static func erlaubnis(_ status: Bool?) -> [String: Any] {
        guard let status = status else { return ["status": "unbekannt"] }
        return ["status": status ? "erlaubt" : "abgelehnt"]
    }
}
