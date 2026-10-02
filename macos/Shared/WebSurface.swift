import AppKit
import WebKit

// Die Seite im Fenster: WKWebView mit den Regeln aus Navigation.swift, Dateiauswahl, Hinweisen der Seite
// und Downloads (etwa die Sicherung). Gemeinsam für das Fenster des Bestands (KingfisherApp.swift) und die
// geladene App (macos/App). Keine Fachlogik und kein Start der Laufzeit – das entscheidet die App.

@available(macOS 11.3, *)
final class WebSurface: NSObject, WKNavigationDelegate, WKUIDelegate, WKDownloadDelegate {
    let webView: WKWebView
    let origin: URL
    weak var window: NSWindow?
    /// Die Seite ist geladen; die App blendet ihre eigene Ansicht aus.
    var onLoaded: (() -> Void)?
    /// Die Seite ließ sich nicht laden; der Satz ist für den Menschen.
    var onFailure: ((String) -> Void)?

    private struct DownloadTarget {
        let download: WKDownload
        let staged: URL
        let destination: URL
    }
    private var downloads: [ObjectIdentifier: DownloadTarget] = [:]

    init(origin: URL, configuration: WKWebViewConfiguration = WKWebViewConfiguration()) {
        self.origin = origin
        webView = WKWebView(frame: .zero, configuration: configuration)
        super.init()
        webView.navigationDelegate = self
        webView.uiDelegate = self
        webView.allowsBackForwardNavigationGestures = true
        webView.translatesAutoresizingMaskIntoConstraints = false
    }

    func load(path: String) {
        webView.load(URLRequest(url: origin.appendingPathComponent(path)))
    }

    /// Lädt die aktuelle Seite neu; ohne bisherige Seite die Startseite.
    func reload(fallbackPath: String) {
        if let url = webView.url, sameOrigin(url, origin) { webView.reload() } else { load(path: fallbackPath) }
    }

    func cancelDownloads() {
        for target in downloads.values {
            target.download.cancel { _ in }
            try? FileManager.default.removeItem(at: target.staged)
        }
        downloads.removeAll()
    }

    // MARK: Navigation

    func webView(_ webView: WKWebView, decidePolicyFor action: WKNavigationAction,
                 decisionHandler: @escaping (WKNavigationActionPolicy) -> Void) {
        guard let url = action.request.url else { decisionHandler(.cancel); return }
        let top = action.targetFrame == nil || action.targetFrame?.isMainFrame == true
        switch navigationDisposition(url, origin: origin, topLevel: top, download: action.shouldPerformDownload) {
        case .local:
            if action.shouldPerformDownload { decisionHandler(.download) }
            else if action.targetFrame == nil { decisionHandler(.cancel); webView.load(action.request) }
            else { decisionHandler(.allow) }
        case .download: decisionHandler(.download)
        case .external: decisionHandler(.cancel); NSWorkspace.shared.open(url)
        case .blocked: decisionHandler(.cancel)
        }
    }

    func webView(_ webView: WKWebView, decidePolicyFor response: WKNavigationResponse,
                 decisionHandler: @escaping (WKNavigationResponsePolicy) -> Void) {
        guard let url = response.response.url else { decisionHandler(.cancel); return }
        let disposition = navigationDisposition(url, origin: origin, topLevel: response.isForMainFrame, download: true)
        guard disposition == .local || disposition == .download else { decisionHandler(.cancel); return }
        let attachment = (response.response as? HTTPURLResponse)?.value(forHTTPHeaderField: "Content-Disposition")?
            .lowercased().hasPrefix("attachment") == true
        decisionHandler(attachment || !response.canShowMIMEType || disposition == .download ? .download : .allow)
    }

    func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) { onLoaded?() }
    func webView(_ webView: WKWebView, didFailProvisionalNavigation navigation: WKNavigation!, withError error: Error) {
        if (error as NSError).code != NSURLErrorCancelled {
            onFailure?("Kingfisher ist noch nicht erreichbar. Bitte erneut versuchen.")
        }
    }
    func webView(_ webView: WKWebView, didFail navigation: WKNavigation!, withError error: Error) {
        if (error as NSError).code != NSURLErrorCancelled {
            onFailure?("Die Seite konnte nicht geladen werden. Bitte erneut versuchen.")
        }
    }
    func webViewWebContentProcessDidTerminate(_ webView: WKWebView) { webView.reload() }

    // MARK: Fenster, Dateiauswahl, Hinweise der Seite

    func webView(_ webView: WKWebView, createWebViewWith configuration: WKWebViewConfiguration,
                 for navigationAction: WKNavigationAction, windowFeatures: WKWindowFeatures) -> WKWebView? {
        // Navigation policy handles new-window links in this window or the system browser.
        return nil
    }

    func webView(_ webView: WKWebView, runOpenPanelWith parameters: WKOpenPanelParameters,
                 initiatedByFrame frame: WKFrameInfo, completionHandler: @escaping ([URL]?) -> Void) {
        guard let window = window, let url = frame.request.url, sameOrigin(url, origin) else {
            completionHandler(nil); return
        }
        let panel = NSOpenPanel()
        panel.canChooseFiles = true
        panel.canChooseDirectories = parameters.allowsDirectories
        panel.allowsMultipleSelection = parameters.allowsMultipleSelection
        panel.beginSheetModal(for: window) { result in completionHandler(result == .OK ? panel.urls : nil) }
    }

    func webView(_ webView: WKWebView, runJavaScriptAlertPanelWithMessage message: String,
                 initiatedByFrame frame: WKFrameInfo, completionHandler: @escaping () -> Void) {
        guard let window = window else { completionHandler(); return }
        let alert = NSAlert(); alert.messageText = "Kingfisher"; alert.informativeText = message
        alert.beginSheetModal(for: window) { _ in completionHandler() }
    }

    func webView(_ webView: WKWebView, runJavaScriptConfirmPanelWithMessage message: String,
                 initiatedByFrame frame: WKFrameInfo, completionHandler: @escaping (Bool) -> Void) {
        guard let window = window else { completionHandler(false); return }
        let alert = NSAlert(); alert.messageText = "Kingfisher"; alert.informativeText = message
        alert.addButton(withTitle: "Bestätigen"); alert.addButton(withTitle: "Abbrechen")
        alert.beginSheetModal(for: window) { result in completionHandler(result == .alertFirstButtonReturn) }
    }

    // MARK: Downloads

    func webView(_ webView: WKWebView, navigationAction: WKNavigationAction, didBecome download: WKDownload) {
        download.delegate = self
    }
    func webView(_ webView: WKWebView, navigationResponse: WKNavigationResponse, didBecome download: WKDownload) {
        download.delegate = self
    }

    func download(_ download: WKDownload, decideDestinationUsing response: URLResponse, suggestedFilename: String,
                  completionHandler: @escaping (URL?) -> Void) {
        guard let window = window else { completionHandler(nil); return }
        let panel = NSSavePanel()
        panel.title = "Datei sichern"
        panel.nameFieldStringValue = (suggestedFilename as NSString).lastPathComponent
        panel.canCreateDirectories = true
        panel.beginSheetModal(for: window) { [weak self] result in
            guard let self = self, result == .OK, let destination = panel.url else { completionHandler(nil); return }
            // WebKit requires a nonexistent path. Stage alongside the chosen file, preserving an existing backup on failure.
            let staged = destination.deletingLastPathComponent()
                .appendingPathComponent(".kingfisher-\(UUID().uuidString).download")
            self.downloads[ObjectIdentifier(download)] = DownloadTarget(download: download, staged: staged,
                                                                       destination: destination)
            completionHandler(staged)
        }
    }

    func download(_ download: WKDownload, willPerformHTTPRedirection response: HTTPURLResponse,
                  newRequest request: URLRequest, decisionHandler: @escaping (WKDownload.RedirectPolicy) -> Void) {
        let allowed = request.url.map { sameOrigin($0, origin) } ?? false
        decisionHandler(allowed ? .allow : .cancel)
    }

    func downloadDidFinish(_ download: WKDownload) {
        guard let target = downloads.removeValue(forKey: ObjectIdentifier(download)) else { return }
        do {
            try finishDownload(staged: target.staged, destination: target.destination)
            showAlert("Datei gesichert", target.destination.lastPathComponent)
        } catch {
            // Retain the completed staged file if the final rename fails so the user can recover it.
            showAlert("Datei konnte nicht am gewählten Ziel gesichert werden",
                      "Die vollständige Datei liegt hier: \(target.staged.path)")
        }
    }

    func download(_ download: WKDownload, didFailWithError error: Error, resumeData: Data?) {
        if let target = downloads.removeValue(forKey: ObjectIdentifier(download)) {
            try? FileManager.default.removeItem(at: target.staged)
        }
        if (error as NSError).code != NSURLErrorCancelled {
            showAlert("Download fehlgeschlagen", "Die Datei wurde nicht gesichert. Bitte erneut versuchen.")
        }
    }

    private func showAlert(_ title: String, _ text: String) {
        guard let window = window else { return }
        let alert = NSAlert(); alert.messageText = title; alert.informativeText = text
        alert.beginSheetModal(for: window)
    }
}
