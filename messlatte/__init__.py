"""Die Messlatte: ein Messinstrument für das Gedächtnis von Kingfisher.

Sie spielt eine erfundene, zusammenhängende Welt (Format: `FORMAT.md`) über die
echten Produktpfade ein und stellt ihre Fragen über den echten Antwortpfad.
Jede Stufe ist ein eigenes Modul mit einer Aufgabe und tauscht nur Datenklassen
mit den anderen aus:

    welt        laden und streng prüfen          -> Welt
    rauschen    Alltagsquellen für die Skalierung -> Quellen
    aufnahme    über Produktpfade einspielen       -> AufnahmeErgebnis
    abruf       Kandidatensuche ohne Modell        -> AbrufErgebnis
    antwort     Konversations-API mit Modell       -> AntwortErgebnis
    bewertung   reine Funktionen                   -> FrageBewertung
    bericht     JSON und Markdown
    lokal       dieselben Fragen an die laufende Instanz des Nutzers

Die Messlatte ändert keinen Produktcode und keine Produktvorgabe.
"""
