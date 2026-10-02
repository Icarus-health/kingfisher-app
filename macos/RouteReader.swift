import CoreLocation
import Foundation
import MapKit

// Fahrzeit-Adapter über Apple Karten (MapKit). UNGEPRÜFT: Dieser Code wurde in einer Linux-Umgebung
// geschrieben und nie übersetzt oder ausgeführt (siehe docs/33-briefing-und-vorbereitung.md).
//
// Nur zwei Adressen kommen hinein (JSON auf stdin), nur eine Zahl geht heraus. Keine Termine, keine Namen,
// keine Zugangsdaten, kein Schreiben. Die Adressen werden nie ausgegeben und nicht protokolliert.
//
// Eingabe:  {"von": "<Adresse>", "nach": "<Adresse>", "verkehrsmittel": "auto" | "oepnv" | "fuss",
//            "abfahrt": "<ISO-8601 mit Zeitzone, optional>"}
// Ausgabe:  {"ok": true, "minuten": 35}  oder  {"ok": false, "error": "<Kürzel>"}
func output(_ value: [String: Any], _ code: Int32 = 0) -> Never {
    let data = try! JSONSerialization.data(withJSONObject: value, options: [.sortedKeys])
    print(String(decoding: data, as: UTF8.self))
    exit(code)
}

let command = CommandLine.arguments.dropFirst().first ?? "route"
guard command == "route" else {
    output(["ok": false, "error": "Unsupported command"], 2)
}

let data = FileHandle.standardInput.readDataToEndOfFile()
guard data.count <= 16_384,
      let input = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
      let from = (input["von"] as? String)?.trimmingCharacters(in: .whitespacesAndNewlines),
      let to = (input["nach"] as? String)?.trimmingCharacters(in: .whitespacesAndNewlines),
      !from.isEmpty, !to.isEmpty, from.count <= 300, to.count <= 300,
      let mode = input["verkehrsmittel"] as? String, ["auto", "oepnv", "fuss"].contains(mode) else {
    output(["ok": false, "error": "Zwei Adressen und ein Verkehrsmittel sind nötig"], 2)
}

var departure: Date? = nil
if let text = input["abfahrt"] as? String {
    departure = ISO8601DateFormatter().date(from: text)
}

let transport: MKDirectionsTransportType
switch mode {
case "oepnv": transport = .transit
case "fuss": transport = .walking
default: transport = .automobile
}

// Adresse -> Ort. CLGeocoder fragt Apples Ortsdienst; dafür ist keine Standortfreigabe nötig.
func place(_ address: String, _ done: @escaping (MKMapItem?) -> Void) {
    CLGeocoder().geocodeAddressString(address) { marks, _ in
        guard let mark = marks?.first else { return done(nil) }
        done(MKMapItem(placemark: MKPlacemark(placemark: mark)))
    }
}

var finished = false
place(from) { source in
    place(to) { destination in
        guard let source, let destination else {
            output(["ok": false, "error": "adresse_unbekannt"], 1)
        }
        let request = MKDirections.Request()
        request.source = source
        request.destination = destination
        request.transportType = transport
        if let departure, departure > Date() { request.departureDate = departure }
        // Nur die Dauer: calculateETA liefert sie auch für Bus und Bahn, wo keine Route berechnet wird.
        MKDirections(request: request).calculateETA { response, error in
            finished = true
            if let response {
                let minutes = max(1, Int((response.expectedTravelTime / 60).rounded()))
                output(["ok": true, "minuten": minutes])
            }
            if let error = error as? MKError, error.code == .directionsNotFound {
                output(["ok": false, "error": mode == "oepnv" ? "nicht_unterstuetzt" : "keine_route"], 1)
            }
            output(["ok": false, "error": "dienst_nicht_erreichbar"], 1)
        }
    }
}
RunLoop.current.run(until: Date().addingTimeInterval(20))
if !finished { output(["ok": false, "error": "zeitueberschreitung"], 1) }
