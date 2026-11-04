# Gesprächsentwürfe über Neustarts erhalten

Aus dem freigegebenen Produktplan P3/P4: Entwürfe bleiben bei Fehler, Wechsel und
Neustart erhalten. Die bestehende Map/sessionStorage-Lösung erfüllt das nur
innerhalb einer geöffneten Sitzung. Die Umsetzung ist eine delegierte
Detailentscheidung innerhalb dieses Ziels, keine neue Anbieterfreigabe.

## Entscheidung und Alternativen

Entwürfe gehören als eigener, versionierter Bereich zur vorhandenen lokalen
Gesprächsdatenbank. Sie sind keine Nachricht, Quelle, Suchantwort oder
Modellhistorie. Die bestehende Sicherung nimmt sie damit automatisch mit.
Ein bloßer Wechsel auf localStorage scheitert an nichtpersistenten WebKit-Views
und würde fremde Bestände am selben lokalen Port nicht sauber unterscheiden.
Nur eine Schließwarnung verhindert keinen Neustartverlust.

GET/PUT unter `/api/v1/conversation-drafts/{id}` gelten ausschließlich für ein
vorhandenes Gespräch oder den reservierten Start-Composer `new`. Der Text ist
auf 20.000 Zeichen begrenzt und bleibt unverändert. Eine Server-Startkennung
bindet jeden Schreibauftrag an genau die gelesene laufende Instanz. Eine alte
Kennung wird nach Neustart oder Instanzwechsel abgelehnt; erneut lesen ist
möglich. Persistenz hängt nicht von dieser kurzlebigen Kennung ab.

Schreiben und Leeren prüfen eine monotone Revision atomar. Leere Entwürfe
behalten einen Versionsstand. Nur die genaue Wiederholung des unmittelbar
vorherigen Schreibschritts mit identischem Text gilt als erfolgreiches Retry.
Konflikte ersetzen weder lokale Eingabe noch Serverfassung ungefragt.

## Eingabe und Senden

Der UI-Cache reagiert sofort und sichert nach 250 ms Schreibpause, mit genau
einem ausstehenden Schreibvorgang je Composer. Lokale Eingaberevision und
Serverrevision sind getrennt. Verspätete Antworten überschreiben keine neuere
Eingabe. Speicherzustand ist knapp sichtbar; Fehler bieten Wiederholen und
Konflikte eine bewusste Auswahl. Alte ungebundene Sitzungstexte bleiben zur
bewussten Übernahme verfügbar, werden aber nicht automatisch hochgeladen.

Vor dem Senden wird der konkrete Entwurf gesichert. Nach erfolgreichem Senden
darf nur dessen unveränderte Fassung geleert werden. Währenddessen nachgetippter
Text bleibt. Ein unklarer Sendeausgang löst keine automatische Sendewiederholung
aus. Fehler beim Leeren werden nicht als fehlgeschlagenes Senden ausgegeben.

Der Start-Composer bindet seine gespeicherte Revision vor dem ersten Senden
atomar an ein neues Gespräch. Derselbe Bindungsaufruf liefert auch nach einer
verlorenen Antwort dasselbe Gespräch. Der Starttext bleibt separat mit den
Zuständen `ready`, `started`, `accepted` erhalten. Erst ein atomarer Anspruch
auf `ready` erlaubt genau einem Fenster den Nachrichtenaufruf; nach einem
Neustart wird `started` nicht automatisch erneut gesendet. Ein erfolgreicher
Nachrichten-HTTP-Aufruf bestätigt die Annahme, auch wenn danach eine sichtbare
Modellfehlermeldung entstanden ist. Der normale Nachrichten-Wiederholungsweg
bleibt für solche Antworten zuständig.

Nach der Bindung wechselt die UI sofort in das Gespräch. Während der kurzen
Bindung ist die Start-Eingabe gesperrt; Folgetext danach gehört zum normalen
Gesprächsentwurf und wird nicht beim Abschluss der ersten Antwort gelöscht.
Eine unklare Annahme bleibt mit dem ursprünglichen Text sichtbar prüfbar.
Kein Leergespräch allein durch Öffnen der Seite.

## Schließen

`window.kingfisherDraftsPrepareToLeave(): Promise<boolean>` versucht ausschließlich
lokales Entwurfsspeichern. `true` nur, wenn alle bekannten Entwürfe gesichert
sind; Fehler, Konflikte und unübernommene alte Sitzungstexte bleiben `false`.
Währenddessen ist Bearbeiten kurz gesperrt. Ein abgebrochener Schließversuch
hebt diese rein vorübergehende Sperre über `kingfisherDraftsCancelLeave` auf.
Der native Aufrufer prüft die eigene Herkunft, wartet höchstens drei Sekunden und öffnet bei
fehlendem Nachweis eine verständliche Warnung. Kein Modell-/Mailversand durch
Schließen. Der Browser erhält zusätzlich einen beforeunload-Hinweis bei noch
ungesicherten Fassungen. Ein Prozessabsturz vor bestätigtem Speichern wird nicht
als verlustfrei versprochen.

## Abnahme

Neue JS-/Serverinstanz lädt gespeicherten Text; andere Instanz am gleichen Port
bekommt keine alten Schreibaufträge. Schreiben während Save/Send, verlorene
Antwort, Konkurrenzfenster, Fehler, Startgespräch plus Folgetext und
Sicherung/Wiederherstellung werden getrennt geprüft. Keine privaten Daten,
Anbieterkosten oder Wiederaufnahme des Großimports. Native Logik/Build ersetzen
nicht die weiterhin separat freizugebende echte Fensterprüfung.
