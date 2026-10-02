import Foundation

// Eine schon vorhandene Installation aus der Arbeitskopie (`make start`, `Kingfisher starten.command`) erkennen.
// Ihr Token und ihre Passphrase müssen weiterverwendet werden: Die Passphrase entschlüsselt die Schlüsseldatei
// im Datenvolume. Geraten wird nichts – die Pfade kommen aus den Angaben, die Docker Compose selbst am
// Container hinterlegt. Reine Logik; die Docker-Aufrufe stehen in macos/App/Docker.swift.

enum Installation {
    /// Compose-Projekt wie `make start` und der Starter (`-p kingfisher`): dasselbe Datenvolume.
    static let project = "kingfisher"
    /// Name des Volumes, den Compose aus Projekt und `kingfisher-data` (compose.yaml) bildet.
    static let dataVolume = "kingfisher_kingfisher-data"
    /// Name der Env-Datei des Starters neben der Arbeitskopie (Makefile `ENVDATEI`).
    static let starterEnvName = ".kingfisher.env"
    /// Label, unter dem Compose die verwendeten Env-Dateien vermerkt (kommagetrennt).
    static let envFileLabel = "com.docker.compose.project.environment_file"
    /// Label mit dem Arbeitsordner des Compose-Aufrufs, also der Arbeitskopie.
    static let workingDirLabel = "com.docker.compose.project.working_dir"

    /// Mögliche Env-Dateien eines vorhandenen Containers, in dieser Reihenfolge zu versuchen.
    static func envCandidates(labels: [String: String]) -> [String] {
        let workingDir = labels[workingDirLabel].flatMap { $0.isEmpty ? nil : $0 }
        var candidates: [String] = []
        for entry in (labels[envFileLabel] ?? "").split(separator: ",") {
            let path = entry.trimmingCharacters(in: .whitespaces)
            if path.isEmpty { continue }
            if path.hasPrefix("/") {
                candidates.append(path)
            } else if let workingDir = workingDir {
                candidates.append(join(workingDir, path))
            }
        }
        if let workingDir = workingDir {
            candidates.append(join(workingDir, starterEnvName))
        }
        var seen = Set<String>()
        return candidates.filter { seen.insert($0).inserted }
    }

    private static func join(_ folder: String, _ name: String) -> String {
        folder.hasSuffix("/") ? folder + name : folder + "/" + name
    }

    /// Token und Passphrase aus der Umgebung eines vorhandenen Containers (`docker inspect`, `Config.Env`).
    /// Der Rückweg, wenn die Env-Datei des Starters nicht mehr dort liegt, wo Compose sie vermerkt hat.
    static func keys(fromContainerEnvironment entries: [String]) -> EnvFile? {
        var found = EnvFile(text: "# Von der Kingfisher-App aus dem bisherigen Container übernommen.\n")
        for key in [EnvKey.token, EnvKey.passphrase] {
            guard let entry = entries.last(where: { $0.hasPrefix(key + "=") }) else { return nil }
            found.set(key, String(entry.dropFirst(key.count + 1)))
        }
        return found.hasKeys ? found : nil
    }
}
