import Foundation

// Alle Sätze der App an einer Stelle: Deutsch, Laiensprache, ein Satz je Lage. Deutsche Anführungszeichen
// immer „…“ – ein schließendes ASCII-Anführungszeichen würde die Zeichenkette beenden.

enum Satz {
    static let starten = "Kingfisher wird gestartet …"
    static let dockerFehlt = "Kingfisher braucht Docker Desktop, ein kostenloses Programm. Lade es, installiere es und öffne es einmal; danach geht es hier weiter."
    static let dockerStartet = "Docker Desktop wird gestartet. Beim ersten Mal dauert das bis zu zwei Minuten."
    static let dockerStumm = "Docker Desktop antwortet nicht. Öffne es einmal selbst über Programme → Docker, warte, bis der Wal oben in der Menüleiste ruhig steht, und prüfe dann noch einmal."
    static let composeFehlt = "Diesem Docker fehlt ein Bestandteil („Compose“). Installiere die aktuelle Fassung von Docker Desktop."
    static let laden = "Kingfisher wird geladen. Beim ersten Mal dauert das einige Minuten."
    static let ladenGescheitert = "Kingfisher ließ sich nicht laden. Prüfe die Internetverbindung und versuche es noch einmal."
    static let startGescheitert = "Kingfisher ließ sich nicht starten. Starte Docker Desktop neu und versuche es noch einmal."
    static let nichtErreichbar = "Kingfisher ist gestartet, antwortet aber noch nicht. Versuche es in einer Minute noch einmal."
    static let schluesselNichtGespeichert = "Kingfisher konnte seine Einstellungen nicht speichern. Prüfe, ob auf dem Mac noch Platz frei ist."
    static let schluesselGesucht = "Auf diesem Mac gibt es schon Kingfisher-Daten. Damit sie lesbar bleiben, wähle die Datei „.kingfisher.env“ aus deinem bisherigen Kingfisher-Ordner."
    static let schluesselUngueltig = "In dieser Datei stehen keine Kingfisher-Schlüssel. Wähle die Datei „.kingfisher.env“ aus deinem bisherigen Kingfisher-Ordner."
    static let bestehendeInstallation = "Hier läuft schon eine Kingfisher-Installation aus einer Arbeitskopie. Sie wird nicht automatisch umgestellt. Öffne sie über ihren bisherigen Starter; für einen Wechsel müssen Daten und Ordnerfreigaben geprüft werden."
    static let falscheInstallation = "Die antwortende Kingfisher-Installation passt nicht zu diesem App-Bild und Schlüssel. Prüfe die vorhandene Installation, bevor du fortfährst."
    static let ollamaFehlt = "Installiere außerdem Ollama (kostenlos), damit Kingfisher deine Fragen beantworten kann – bis dahin kommen Mails, Termine und dein Briefing trotzdem."

    static let platzPruefen = "Speicher für das Update wird geprüft."

    static let aktualisieren = "Kingfisher wird aktualisiert …"
    static let updateLaeuft = "Kingfisher wird gerade aktualisiert. Bitte warte, bis es fertig ist."

    static func schritt(_ step: UpdateStep) -> String {
        switch step {
        case .backup: return "Deine Daten werden gesichert."
        case .pull: return "Die neue Fassung wird geladen. Das kann einige Minuten dauern."
        case .switchImage, .restart: return "Kingfisher wird neu gestartet."
        case .waitForHealth: return "Gleich geht es weiter."
        }
    }

    static let zurueckRollen = "Das hat nicht geklappt. Die Sicherung wird offline wiederhergestellt."

    /// Nach einem gescheiterten Update, wenn die alte Fassung wieder läuft.
    static func updateGescheitert(alteFassung: String?) -> String {
        "Das Update hat nicht geklappt. Der gesicherte Stand ist mit dem bisherigen Bild im Prüfmodus geöffnet. Prüfe die historischen Daten; frühere Freigaben sind ausgeschaltet."
    }

    /// Die Sicherung vorab ist gescheitert; deshalb wurde nichts verändert.
    static func updateNichtBegonnen(alteFassung: String?) -> String {
        "Das Update wurde nicht umgeschaltet. \(fassungsText(alteFassung)) bleibt unverändert; prüfe Docker und die Sicherung."
    }

    static func updateSpeicherBlockiert(_ issue: UpdateStorageIssue) -> String {
        let reason: String
        switch issue {
        case .lowSpace: reason = "In Kingfishers Speicherbereich ist zu wenig Platz für ein sicheres Update."
        case .lowInodes: reason = "Kingfishers Speicherbereich kann zu wenige weitere Dateien aufnehmen."
        case .unavailable: reason = "Kingfisher konnte den verfügbaren Speicher nicht zuverlässig prüfen."
        }
        return reason + " Die bisherige Fassung läuft weiter. Es wurde nicht umgeschaltet. Freier Platz auf dem Mac allein reicht dafür nicht aus."
    }

    static let updateKaputt = "Das Update hat nicht geklappt. Der alte Code wurde nicht auf ungeprüften Daten gestartet. Die Sicherung bleibt erhalten; die Wiederherstellung braucht eine technische Prüfung."

    private static func fassungsText(_ fassung: String?) -> String {
        fassung.map { "Fassung \($0)" } ?? "der bisherigen Fassung"
    }
}

/// Beschriftungen der Knöpfe.
enum Knopf {
    static let dockerLaden = "Docker Desktop laden"
    static let nochmalPruefen = "Nochmal prüfen"
    static let nochmalVersuchen = "Erneut versuchen"
    static let dateiWaehlen = "Datei auswählen"
    static let weiter = "Weiter"
    static let ollamaLaden = "Ollama laden"
}

enum Adresse {
    static let dockerDownload = URL(string: "https://www.docker.com/products/docker-desktop/")!
    static let ollamaDownload = URL(string: "https://ollama.com/download")!
}
