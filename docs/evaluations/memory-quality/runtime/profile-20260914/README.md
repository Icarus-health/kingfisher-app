# Profilgültigkeit: tatsächlicher Docker-/Ollama-Ablauf

14.09.2026, eigenes synthetisches Testvolume und nur Loopback-Ports. Kein privater
Bestand, keine verbundenen Konten. Image `6655b4a6401b`, vollständige ID in state.json;
Quellcommit `5c1495b` mit der geprüften M1b-Produktion `dcd52b5`. Vorhandenes lokales
Qwen2.5:14b, keine App-Modellumstellung oder Downloads. Eigene Test-Authentisierung
bleibt außerhalb des Repositorys.

Über die reguläre HTTP-API wurde eine synthetische Kaffeevorliebe angelegt und in einem
Gespräch korrekt beantwortet. Nach explizitem Widerruf verschwand sie bereits beim
Abruf des Gesprächs aus den **aktuellen** Kontextkarten. Eine neue Antwort verwendete
sie nicht mehr; der Profil-Reset ist persistiert, die ursprüngliche Antwort sichtbar.
Nach Container-Neustart blieb die Vorliebe ausgeschlossen, ohne wiederholten Reset.

Danach wurde über dieselbe API eine Teevorliebe mit 80-Sekunden-Gültigkeit angelegt.
Vor Ablauf benannte das Modell Rooibostee. Nach natürlichem Ablauf wurde die Angabe
nicht mehr als aktuelle Vorliebe verwendet und der Verlauf entsprechend zurückgestellt.
Auch ein weiterer Neustart brachte die alte Angabe nicht zurück. Alle sechs
Gesprächsanfragen blieben ohne Action Requests. Die dynamische Portzuordnung wurde
nach jedem Neustart frisch gelesen.

Nachgewiesen sind Antwortverhalten, aktuelle Karten, persistierte Profil-Lineage und
sichtbarer Gesprächserhalt in diesem konkreten Ablauf. Vollständige Provideranfragen
wurden hier nicht zusätzlich abgefangen; dafür bestehen die separaten synthetischen
CapturingProvider-Regressionstests. Interne Provideraufrufzahlen und eine generelle
semantische Modellqualifikation werden aus diesem HTTP-Test nicht abgeleitet.

Die Rohantworten und SHA-256-Prüfsummen sind vollständig erhalten. Die Antwortsprache
ist weiterhin teilweise unnötig ausschweifend bzw. verwendet unpassende Standard-
Einleitungen; der separate Antwortvertrag bleibt deshalb ein offener Arbeitspunkt.
Dies ist noch kein Nachweis der produktiven App-Aktualisierung oder vollständigen
Gedächtnisfreigabe (insbesondere transitive SelfModel-Quellen und Restore).
