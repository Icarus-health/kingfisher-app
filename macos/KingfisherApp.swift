import AppKit
import WebKit
import Darwin

// Fenster für eine vorhandene Kingfisher-Installation aus der Arbeitskopie (scripts/build_mac_window.py).
// Startet die Laufzeit über scripts/start_mac_app.py. Die Seite selbst steckt in Shared/WebSurface.swift,
// die Regeln für Navigation und Downloads in Shared/Navigation.swift. Die geladene App liegt in macos/App.

struct AppConfiguration: Decodable {
    let repo: String
    let envFile: String
    let container: String
    let url: String

    var origin: URL? {
        guard let value = URL(string: url), value.scheme == "http", value.host == "127.0.0.1",
              value.user == nil, value.password == nil, ["", "/"].contains(value.path),
              value.query == nil, value.fragment == nil else { return nil }
        return value
    }
}

@available(macOS 11.3, *)
final class AppDelegate: NSObject, NSApplicationDelegate {
    var window: NSWindow!
    var surface: WebSurface?
    var status: NSTextField!
    var retry: NSButton!
    var loadingView: NSView!
    var configuration: AppConfiguration!
    var startup: Process?
    var starting = false
    var powerReporter: PowerReporter?

    func applicationDidFinishLaunching(_ notification: Notification) {
        installMenu()
        window = NSWindow(contentRect: NSRect(x: 0, y: 0, width: 1280, height: 860),
                          styleMask: [.titled, .closable, .miniaturizable, .resizable], backing: .buffered, defer: false)
        window.title = "Kingfisher"
        window.minSize = NSSize(width: 900, height: 620)
        window.center()
        window.isReleasedWhenClosed = false
        let content = NSView()
        window.contentView = content
        loadingView = NSView()
        loadingView.translatesAutoresizingMaskIntoConstraints = false
        status = NSTextField(wrappingLabelWithString: "Kingfisher wird gestartet …")
        status.alignment = .center
        status.font = NSFont.systemFont(ofSize: 18)
        retry = NSButton(title: "Erneut versuchen", target: self, action: #selector(startBackend))
        let stack = NSStackView(views: [status, retry])
        stack.orientation = .vertical
        stack.spacing = 24
        stack.translatesAutoresizingMaskIntoConstraints = false
        loadingView.addSubview(stack)
        NSLayoutConstraint.activate([stack.centerXAnchor.constraint(equalTo: loadingView.centerXAnchor),
                                     stack.centerYAnchor.constraint(equalTo: loadingView.centerYAnchor),
                                     stack.widthAnchor.constraint(lessThanOrEqualToConstant: 620)])
        window.makeKeyAndOrderFront(nil)
        NSApp.activate(ignoringOtherApps: true)
        do {
            guard let configURL = Bundle.main.url(forResource: "WindowConfiguration", withExtension: "json") else {
                throw NSError(domain: "Kingfisher", code: 1)
            }
            configuration = try JSONDecoder().decode(AppConfiguration.self, from: Data(contentsOf: configURL))
            guard let origin = configuration.origin else { throw NSError(domain: "Kingfisher", code: 2) }
            let surface = WebSurface(origin: origin)
            surface.window = window
            surface.onLoaded = { [weak self] in self?.loadingView.isHidden = true }
            surface.onFailure = { [weak self] message in self?.showStartupError(message) }
            self.surface = surface
            fill(content, with: surface.webView)
            fill(content, with: loadingView)
            startBackend()
        } catch {
            fill(content, with: loadingView)
            showStartupError("Die lokale App-Konfiguration fehlt oder ist ungültig. Bitte die App neu erstellen.")
            retry.isEnabled = false
        }
    }

    func fill(_ content: NSView, with view: NSView) {
        view.translatesAutoresizingMaskIntoConstraints = false
        content.addSubview(view)
        NSLayoutConstraint.activate([view.leadingAnchor.constraint(equalTo: content.leadingAnchor),
                                     view.trailingAnchor.constraint(equalTo: content.trailingAnchor),
                                     view.topAnchor.constraint(equalTo: content.topAnchor),
                                     view.bottomAnchor.constraint(equalTo: content.bottomAnchor)])
    }

    func installMenu() {
        let main = NSMenu()
        let appItem = NSMenuItem()
        main.addItem(appItem)
        let appMenu = NSMenu()
        appItem.submenu = appMenu
        appMenu.addItem(withTitle: "Kingfisher beenden", action: #selector(NSApplication.terminate(_:)), keyEquivalent: "q")
        let editItem = NSMenuItem()
        main.addItem(editItem)
        let edit = NSMenu(title: "Bearbeiten")
        editItem.submenu = edit
        edit.addItem(withTitle: "Rückgängig", action: Selector(("undo:")), keyEquivalent: "z")
        edit.addItem(withTitle: "Ausschneiden", action: #selector(NSText.cut(_:)), keyEquivalent: "x")
        edit.addItem(withTitle: "Kopieren", action: #selector(NSText.copy(_:)), keyEquivalent: "c")
        edit.addItem(withTitle: "Einfügen", action: #selector(NSText.paste(_:)), keyEquivalent: "v")
        edit.addItem(withTitle: "Alles auswählen", action: #selector(NSText.selectAll(_:)), keyEquivalent: "a")
        let viewItem = NSMenuItem()
        main.addItem(viewItem)
        let view = NSMenu(title: "Ansicht")
        viewItem.submenu = view
        let reload = view.addItem(withTitle: "Neu laden", action: #selector(reloadPage), keyEquivalent: "r")
        reload.target = self
        NSApp.mainMenu = main
    }

    @objc func reloadPage() { if !starting { surface?.webView.reload() } }

    @objc func startBackend() {
        guard !starting, configuration != nil, let surface = surface else { return }
        starting = true
        retry.isEnabled = false
        loadingView.isHidden = false
        status.stringValue = "Kingfisher wird gestartet …\nDie lokale Docker-Laufzeit kann einen Moment benötigen."
        let config = configuration!
        // Process launch and readiness wait run away from AppKit's main thread.
        DispatchQueue.global(qos: .userInitiated).async { [weak self] in
            let process = Process()
            process.executableURL = URL(fileURLWithPath: "/usr/bin/python3")
            process.arguments = [config.repo + "/scripts/start_mac_app.py", "--env-file", config.envFile,
                                 "--container", config.container, "--url", config.url, "--no-browser"]
            process.currentDirectoryURL = URL(fileURLWithPath: config.repo)
            var env = ProcessInfo.processInfo.environment
            env["PATH"] = "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
            process.environment = env
            let log = FileManager.default.temporaryDirectory.appendingPathComponent("kingfisher-start-\(UUID().uuidString).log")
            FileManager.default.createFile(atPath: log.path, contents: nil, attributes: [.posixPermissions: 0o600])
            defer { try? FileManager.default.removeItem(at: log) }
            do {
                let handle = try FileHandle(forWritingTo: log)
                defer { try? handle.close() }
                process.standardOutput = handle
                process.standardError = handle
                try process.run()
                DispatchQueue.main.async { self?.startup = process }
                DispatchQueue.global().asyncAfter(deadline: .now() + 360) {
                    if process.isRunning {
                        process.terminate()
                        DispatchQueue.global().asyncAfter(deadline: .now() + 3) {
                            if process.isRunning { kill(process.processIdentifier, SIGKILL) }
                        }
                    }
                }
                process.waitUntilExit()
                let result = process.terminationStatus
                DispatchQueue.main.async {
                    guard let self = self else { return }
                    self.startup = nil
                    self.starting = false
                    self.retry.isEnabled = true
                    if result == 0 {
                        if self.powerReporter == nil, let origin = config.origin {
                            let reporter = PowerReporter(origin: origin, tokenFile: URL(fileURLWithPath: config.envFile))
                            self.powerReporter = reporter
                            reporter.start()
                        }
                        surface.load(path: "today")
                    } else {
                        self.showStartupError("Kingfisher konnte nicht gestartet werden. Bitte prüfe Docker und den vorhandenen Projektordner und versuche es erneut.")
                    }
                }
            } catch {
                DispatchQueue.main.async {
                    self?.starting = false
                    self?.retry.isEnabled = true
                    self?.showStartupError("Der lokale Starter konnte nicht ausgeführt werden. Bitte prüfe den vorhandenen Kingfisher-Projektordner.")
                }
            }
        }
    }

    func showStartupError(_ message: String) {
        loadingView.isHidden = false
        status.stringValue = message
    }

    func applicationShouldHandleReopen(_ sender: NSApplication, hasVisibleWindows flag: Bool) -> Bool {
        window.makeKeyAndOrderFront(nil)
        return true
    }
    func applicationWillTerminate(_ notification: Notification) {
        startup?.terminate()
        powerReporter?.stop()
        surface?.cancelDownloads()
    }
}

@main
struct KingfisherApp {
    static func main() {
        if #available(macOS 11.3, *) {
            let application = NSApplication.shared
            let delegate = AppDelegate()
            application.setActivationPolicy(.regular)
            application.delegate = delegate
            withExtendedLifetime(delegate) { application.run() }
        }
    }
}
