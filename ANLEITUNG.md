# Kreuzworträtsel-Generator – Anleitung

## Eingabe: `raetsel.config.json`
| Feld | Bedeutung |
|---|---|
| `loesungswort` | Wort aus den markierten Feldern (wird auch zur URL, klein geschrieben) |
| `github_user` | GitHub-Nutzer → `<user>.github.io/<loesungswort>/` |
| `form` | `zeilen`, `spalten`, optional `maske` (Liste von Strings, `#` = gesperrt, `.` = frei) |
| `loesungswoerter` | Wörter, die auf jeden Fall ins Raster müssen (`[]` = freie Wahl aus der Wortliste) |
| `wortliste` | Kandidaten `{ "wort", "hinweis" }` – Wortlänge `(n)` wird automatisch angehängt, Ä/Ö/Ü/ß → AE/OE/UE/SS |
| `generator` | `seed`, `versuche`, `max_woerter` |
| `blatt` | Kopf rechts auf dem Druckblatt (`nummer`, `widmung`) |
| `seite` | **Texte der Lösungsseite:** `intro`, `wann`, `wo`, `was` |

## Befehle
```bash
python3 tools/kreuzwort.py alles
```
`alles` = `erzeugen` (→ `puzzle.json`) + `rendern` (→ HTML) + `pruefen`. Einzeln aufrufbar, z. B. nur neue Texte übernehmen:
```bash
python3 tools/kreuzwort.py rendern
```
Anderes Raster ausprobieren: `python3 tools/kreuzwort.py alles --seed 3`.

Lässt sich das Lösungswort nicht auf eigene Felder verteilen (Buchstabe fehlt in der Wortliste oder in keinem gültigen Raster), bricht das Skript mit einer Fehlermeldung und Exit-Code 1 ab.

## Ausgabe
- `puzzle.json` – Raster (`#` = Blockfeld), Einträge mit Nummer/Position/Antwort/Hinweis, Lösungsfelder 1…n
- `raetsel.html` – Druckblatt A4 (HTML/CSS in mm, vektoriell) – im Browser drucken, Ränder „Keine“, Hintergrundgrafiken an
- `raetsel-loesung.html` – dasselbe mit eingetragenen Buchstaben
- `rgn24.github.io/` – Inhalt des Repos `rgn24.github.io`: `mahlzeit/index.html`, `404.html`, `.nojekyll`

## Texte Wann / Wo / Was
Entweder in `raetsel.config.json` → `seite` eintragen und `rendern`, oder direkt oben in
`rgn24.github.io/mahlzeit/index.html` im Block `const TEXTE = { … }` ändern (Zeilenumbruch: `\n`).
Achtung: `rendern` überschreibt direkte Änderungen in der HTML-Datei.
