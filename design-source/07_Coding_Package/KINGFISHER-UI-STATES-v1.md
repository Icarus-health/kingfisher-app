# Kingfisher UI States v1

Diese Zustände sind absichtlich zurückhaltend. Sie leiten sich aus den kanonischen hellen und dunklen Oberflächen ab und dürfen nicht mit neuen Illustrationen, Bildwelten oder neuen Komponenten beantwortet werden.

## Laden

- Zeige die spätere Card-Struktur bereits als ruhige Fläche mit `surface` bzw. dunkler Card-Fläche.
- Verwende 2–4 dezente, abgerundete Skeleton-Zeilen in der tatsächlichen Textposition.
- Kein Spinner im Mittelpunkt einer Seite, keine Animation außerhalb des bestehenden Motion Tokens.

## Leer

- Halte dieselbe Fläche und Seitenhierarchie wie in der Referenz.
- Eine kurze sachliche Zeile plus genau eine erlaubte Folgeaktion.
- Keine Illustration, kein Emoji und kein neues Hintergrundbild.

## Fehler

- Die vorhandene Card oder Zeile bleibt sichtbar; ergänze eine kurze Fehlerzeile mit `danger` und eine Wiederholen-Aktion.
- Keine vollflächige rote Fläche, kein technischer Stack Trace und keine neue Warnillustration.

## Erfolg

- Nutze einen kompakten Status innerhalb des bestehenden Kontextes: `success` + Klartext.
- Kein Konfetti, kein Modal und keine neue Erfolgsszene.

## Deaktiviert

- Gleiche Komponente, reduzierter Kontrast, nicht anklickbar; Grund direkt daneben oder im Hilfetext.
- Deaktivierung darf nicht nur über Farbe erkennbar sein.

Beispiel: Wenn für „Brauchst dich“ keine Aufgabe vorliegt, bleibt die bekannte Card an derselben Stelle. Sie zeigt nur „Keine offenen Punkte für dich“ und keinen neu erfundenen leeren Dashboard-Bereich.
