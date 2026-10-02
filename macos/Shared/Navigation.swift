import Foundation

// Reine Regeln des Fensters: wohin eine Navigation darf und wie ein Download ans Ziel kommt.
// Kein AppKit, damit sie sich ohne Fenster prüfen lassen (sidecar/tests/test_mac_window.py).

enum NavigationDisposition: String { case local, external, download, blocked }

func finishDownload(staged: URL, destination: URL) throws {
    if FileManager.default.fileExists(atPath: destination.path) {
        _ = try FileManager.default.replaceItemAt(destination, withItemAt: staged)
    } else {
        try FileManager.default.moveItem(at: staged, to: destination)
    }
}

func sameOrigin(_ url: URL, _ origin: URL) -> Bool {
    url.scheme == origin.scheme && url.host == origin.host &&
        (url.port ?? 80) == (origin.port ?? 80) && url.user == nil && url.password == nil
}

func navigationDisposition(_ url: URL, origin: URL, topLevel: Bool, download: Bool) -> NavigationDisposition {
    if sameOrigin(url, origin) { return .local }
    // Backups may be generated in the page as blobs. Only a blob owned by our origin can download.
    if download, url.scheme == "blob", let inner = URL(string: String(url.absoluteString.dropFirst(5))),
       sameOrigin(inner, origin) { return .download }
    if topLevel, url.scheme == "https", url.host != nil, url.user == nil, url.password == nil {
        return .external
    }
    return .blocked
}
