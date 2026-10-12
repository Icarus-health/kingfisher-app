# Unabhängige statische Prüfung

Native Grundlage `0496d4d`, danach Frontend und Reviewkorrekturen auf derselben Branch. Wiederverwendeter Reviewagent; nur Code-/Testlektüre, keine eigenen Testläufe, Gerätezugriffe oder produktiven Inhalte.

Native Prüfung: keine wichtigen Blocker im geprüften Umfang gefunden. Strikte Hauptframe-/Origin-/UUID-Brücke, Geräteerkennung zwingend, installierte deutsche Stimme, begrenzte Aufnahme/Finalisierung und dokumentgebundene Rückmeldungen. Dieser Befund allein war noch keine nutzbare Sprachoberfläche.

Frontendprüfung fand drei konkrete Punkte:

1. Eine Statusprobe erzeugte vor der Bridgeprüfung eine ID mittels `crypto.randomUUID`; ältere Browser ohne diese API konnten im Mount-Effekt abbrechen und Cleanup verlieren.
2. Vorlesen wurde still durch den ausgeschalteten KI-Chat blockiert, obwohl der Wiedergabeknopf nicht gesperrt war.
3. Die UI übernahm Fähigkeitsflags aus einem passenden `unavailable`-Ereignis nicht und bot nach verweigerter Speech-Freigabe weiter Diktieren an.

Korrekturen: ohne echte Bridge und ID-Unterstützung keine Probe/Listener; gültiger UUID-Fallback für älteres WebKit. Lokales Vorlesen unabhängig von Chatverfügbarkeit, Diktieren/Senden weiterhin über das Eingabefeld gesperrt. Fähigkeitsrückmeldung aktualisiert die UI; der Apple-Adapter berücksichtigt zusätzlich verweigerte Mikrofonfreigabe. Browser- und verweigerte-Freigabe-Fälle scheiterten vor dieser Korrektur und bestehen danach.

Gezielte unabhängige Nachprüfung: keine neuen konkreten Blocker gefunden. Entwurf, ausdrückliches Senden und frische vollständige Nachrichten-/Quellenprojektion bleiben erhalten. Kein echter Mikrofon-, TCC-/Berechtigungsdialog-, Hör-, React-Runtime-, DOM- oder Fensternachweis durch diese statische Prüfung.
