import Foundation

// Docker finden, starten und Compose aufrufen – dieselben Orte und Schritte wie scripts/kingfisher_starten.py.

struct Docker {
    /// Dieselben Orte wie `DOCKER_ORTE` in scripts/kingfisher_starten.py.
    static let places = ["/usr/local/bin/docker", "/opt/homebrew/bin/docker",
                         "/Applications/Docker.app/Contents/Resources/bin/docker"]
    static let desktopApp = "/Applications/Docker.app"

    let executable: String

    /// Erst der Suchweg, dann die festen Orte; nil, wenn Docker nicht installiert ist.
    static func find() -> Docker? {
        let onPath = Shell.searchPath.split(separator: ":").map { "\($0)/docker" }
        let found = (onPath + places).first { FileManager.default.isExecutableFile(atPath: $0) }
        return found.map(Docker.init(executable:))
    }

    func run(_ arguments: [String], environment: [String: String] = [:], timeout: TimeInterval = 30) -> CommandResult {
        Shell.run(executable, arguments, environment: environment, timeout: timeout)
    }

    func isRunning() -> Bool { run(["info"], timeout: 20).ok }

    func hasCompose() -> Bool { run(["compose", "version"], timeout: 20).ok }

    /// Startet die Laufzeit (Docker Desktop oder Colima, wenn das der eingestellte Kontext ist) und wartet.
    func start(seconds: Int = 120) -> Bool {
        if isRunning() { return true }
        let context = run(["context", "show"], timeout: 10).output.trimmingCharacters(in: .whitespacesAndNewlines)
        let colima = ["/opt/homebrew/bin/colima", "/usr/local/bin/colima"]
            .first { FileManager.default.isExecutableFile(atPath: $0) }
        if context == "colima", let colima = colima {
            _ = Shell.run(colima, ["start"], timeout: 300)
        } else if FileManager.default.fileExists(atPath: Docker.desktopApp) {
            _ = Shell.run("/usr/bin/open", ["-g", "-a", "Docker"], timeout: 20)
        }
        let deadline = Date().addingTimeInterval(TimeInterval(seconds))
        while Date() < deadline {
            if isRunning() { return true }
            Thread.sleep(forTimeInterval: 2)
        }
        return false
    }

    // MARK: Compose

    /// `docker compose -p kingfisher -f <compose.yaml der App> --env-file <Env-Datei> …`.
    /// `image` setzt KINGFISHER_IMAGE nur für diesen Aufruf (etwa zum Laden vor dem Umstellen).
    func compose(_ arguments: [String], paths: AppPaths, image: String? = nil,
                 timeout: TimeInterval) -> CommandResult {
        var environment: [String: String] = [:]
        if let image = image { environment[EnvKey.image] = image }
        return run(["compose", "-p", Installation.project, "-f", paths.composeFile.path,
                    "--env-file", paths.envFile.path] + arguments,
                   environment: environment, timeout: timeout)
    }

    // MARK: Vorhandene Installation

    /// Die Kennung eines Containers aus dem Compose-Projekt `kingfisher`, auch wenn er angehalten ist.
    func projectContainer() -> String? {
        let result = run(["ps", "-a", "--filter", "label=com.docker.compose.project=\(Installation.project)",
                          "--format", "{{.ID}}"])
        guard result.ok else { return nil }
        return result.output.split(whereSeparator: \.isNewline).first.map(String.init)
    }

    /// Die Labels des Containers (darin Arbeitsordner und Env-Datei des Starters).
    func labels(of container: String) -> [String: String] {
        let result = run(["inspect", "--format", "{{json .Config.Labels}}", container])
        guard result.ok, let data = result.output.data(using: .utf8),
              let labels = try? JSONDecoder().decode([String: String].self, from: data) else { return [:] }
        return labels
    }

    /// Die Umgebung des Containers als `NAME=wert`-Zeilen.
    func environment(of container: String) -> [String] {
        let result = run(["inspect", "--format", "{{json .Config.Env}}", container])
        guard result.ok, let data = result.output.data(using: .utf8),
              let entries = try? JSONDecoder().decode([String].self, from: data) else { return [] }
        return entries
    }

    func volumeExists(_ name: String) -> Bool {
        run(["volume", "inspect", name], timeout: 20).ok
    }
}
