# Kreuzworträtsel-Generator – Anleitung

## Eingabe: `raetsel.config.json`
| Feld | Bedeutung |
|---|---|
| `loesungswort` | Wort aus den markierten Feldern (wird klein geschrieben zum Ordner der Lösungsseite) |
| `github_user` | GitHub-Nutzer |
| `projekt` | Repo-Name = Adresse der Eingabeseite `<user>.github.io/<projekt>/` (nur Kleinbuchstaben) |
| `form` | `zeilen`, `spalten`, optional `maske` (Liste von Strings, `#` = gesperrt, `.` = frei), `zuschneiden` (leere Ränder entfernen, Standard: an) |
| `loesungswoerter` | Wörter, die auf jeden Fall ins Raster müssen (`[]` = freie Wahl aus der Wortliste) |
| `wortliste` | Kandidaten `{ "wort", "hinweis" }` – Wortlänge `(n)` wird automatisch angehängt, Ä/Ö/Ü/ß → AE/OE/UE/SS |
| `generator` | `seed`, `versuche`, `max_woerter`, `alle_pflicht` (jedes Wort der Liste muss rein), `suche_knoten` / `suche_breite` (Suchtiefe für Pflichtwörter) |
| `druck` | `hinweis_mm` (Schriftgröße der Fragen), `min_feld_mm` (kleinste erlaubte Feldgröße), `blockfarbe` (Blockfelder, Standard `#D9D9D9`; dunkler z. B. `#BDBDBD`) |
| `blatt` | Kopf rechts auf dem Druckblatt (`nummer`, `widmung`) |
| `seite` | **Texte der Lösungsseite:** `intro`, `wann`, `wo`, `was` |

## Verweise in Fragen
Kommt eine andere Antwort in einer Frage vor, in geschweifte Klammern setzen:
`"Landessprachlich korrekte Begrüßung in {Torredembarra}"` → „… in 2 senkrecht“.
`pruefen` meldet jede Frage, die eine Antwort im Klartext verrät.

## Befehle
```bash
python3 tools/kreuzwort.py alles
```
`alles` = `erzeugen` (→ `puzzle.json`) + `rendern` (→ HTML) + `pruefen`. **Achtung:** `alles` baut das Raster neu. Nur Hinweise korrigiert? Dann `python3 tools/kreuzwort.py texte` – Raster bleibt gleich. Seiten-Texte (Wann/Wo/Was) übernehmen:
```bash
python3 tools/kreuzwort.py rendern
```
Anderes Raster ausprobieren: `python3 tools/kreuzwort.py alles --seed 3`.

Lässt sich das Lösungswort nicht auf eigene Felder verteilen (Buchstabe fehlt in der Wortliste oder in keinem gültigen Raster), bricht das Skript mit einer Fehlermeldung und Exit-Code 1 ab.

## Ausgabe
- `puzzle.json` – Raster (`#` = Blockfeld), Einträge mit Nummer/Position/Antwort/Hinweis, Lösungsfelder 1…n
- `raetsel.html` – Druckblatt A4 (HTML/CSS in mm, vektoriell) – im Browser drucken, Ränder „Keine“, Hintergrundgrafiken an
- `raetsel-loesung.html` – dasselbe mit eingetragenen Buchstaben
- `docs/` – wird von GitHub Pages veröffentlicht:
  - `index.html` – Eingabeseite mit 8 Kästchen (richtig → Lösungsseite, falsch → „Noch nicht ganz“)
  - `<loesungswort>/index.html` – Lösungsseite (Wann / Wo / Was)
  - `tipps/index.html` – Tipps: zu jeder Frage zufällige Buchstaben aufdecken (bleibt pro Gerät gespeichert; Antworten nur verschleiert im Quelltext)
  - `404.html` – falsche Adressen unter dem Projekt; leitet das richtige Wort in jeder Schreibweise weiter

## Texte Wann / Wo / Was
Entweder in `raetsel.config.json` → `seite` eintragen und `rendern`, oder direkt oben in
`docs/mahlzeit/index.html` im Block `const TEXTE = { … }` ändern (Zeilenumbruch: `\n`).
Achtung: `rendern` überschreibt direkte Änderungen in der HTML-Datei. Danach veröffentlichen:
```bash
git commit -am "Texte" && git push
```
Das Repo ist öffentlich – die Texte sind dort für jeden lesbar.

## GitHub Pages
Repo `rgn24/romanhatgeburtstag` (dieses Projekt) → Pages aus `main` / `docs`:
- **https://rgn24.github.io/romanhatgeburtstag/** – hier wird das Lösungswort eingetippt (steht so auf dem Blatt)
- Eingabe- und 404-Seite enthalten nur den SHA-256-Hash des Worts, nicht das Wort selbst.
