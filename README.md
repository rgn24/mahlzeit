# Handoff: Kreuzworträtsel „Um die Ecke gedacht“ – Design 1a „Raster“

## Überblick
Zwei Artefakte in einem Design:
1. **Rätselblatt (Druck, A4 hochkant)** – Kreuzworträtsel im Stil „Um die Ecke gedacht“ (indirekte, wortspielerische Hinweise). Markierte Felder ergeben ein **Lösungswort**.
2. **Lösungsseite (GitHub Pages)** – liegt unter `https://<user>.github.io/<loesungswort>/`. Das Lösungswort ist der fehlende Teil der Adresse, die unten auf dem Blatt steht.

## Über die Design-Dateien
`Raetsel Designs.dc.html` ist eine **Designreferenz in HTML**, kein Produktionscode. Relevant ist nur Option **1a „Raster“** (Abschnitt `id="1a"`). Raster, Hinweise und Lösungswort im Mock sind **Platzhalter**. Aufgabe: Rätsel und Seite neu bauen – als statisches HTML/CSS (kein Framework nötig).

## Fidelity
**High-fidelity.** Farben, Typo, Linienstärken und Abstände exakt übernehmen.

---

## Design Tokens
| Token | Wert |
|---|---|
| Ink (Text, Linien, Blockfelder) | `#111111` |
| Papier / Hintergrund | `#FFFFFF` |
| Akzent (nur Lösungsfelder / Signal) | `#E2401C` |
| Sekundärtext | `#333333`, `#555555` |
| Hairline (Browser-/Seitenränder) | `#E5E5E5` |
| Schrift | **Hanken Grotesk** (Google Fonts), Gewichte 400 / 500 / 700 / 800 |
| Radien | keine (0) |
| Schatten | keine (im Mock nur Präsentation) |

Grundregel: Schwarz/Weiß, **Rot ausschließlich** als Markierung für Lösungsfelder und Lösungsstatus.

---

## 1 · Rätselblatt (A4)
Mock-Maß 560 × 792 px (≙ 210 × 297 mm, Faktor ≈ 2,667 px/mm). Für Druck in **mm** umsetzen, `@page { size: A4; margin: 0 }`.

**Ränder:** oben 40 px (≈15 mm), seitlich 44 px (≈16,5 mm), unten 36 px (≈13,5 mm). Vertikaler Abstand zwischen Blöcken 20 px (≈7,5 mm). Inhalt als Spalte, Fußzeile per `margin-top:auto` nach unten.

**Kopf**
- Links: „Um die Ecke / gedacht.“ (zweizeilig), 34 px, 800, letter-spacing −0,03em, line-height 0,95
- Rechts, rechtsbündig: „Nº 01 / Für dich“, 10 px, 500, Großbuchstaben, letter-spacing 0,08em, line-height 1,5
- Unter dem Kopf: Linie 2 px `#111`, 12 px Abstand darüber

**Raster**
- 11 × 11 Felder (Größe frei wählbar, wenn das echte Rätsel es braucht), Feld 30 px (≈11,25 mm)
- Linien: 1 px `#111` (CSS-Grid mit `gap:1px` auf schwarzem Hintergrund + 1 px Rahmen)
- Blockfeld: voll `#111`
- Offenes Feld: `#FFF`; Nummer oben links (top 2 px, left 3 px), 7,5 px, 700
- **Lösungsfeld:** zusätzlich innere Kontur 2 px `#E2401C` (`box-shadow: inset 0 0 0 2px`) und Lösungsindex unten rechts (right 3 px, bottom 2 px), 7,5 px, 800, `#E2401C`
- Raster linksbündig

**Hinweise**
- Zwei Spalten (`1fr 1fr`, gap 24 px), Schrift 10,5 px, line-height 1,4
- Spaltenkopf „Waagerecht“ / „Senkrecht“: 9,5 px, 800, Großbuchstaben, letter-spacing 0,1em
- Eintrag: Nummer (14 px breit, 700) + Text, gap 6 px; Einträge mit 6 px Abstand
- Wortlänge in Klammern hinter dem Hinweis, z. B. „Hat Zähne, beißt aber nie (4)“

**Fußzeile (Lösung → Adresse)**
- Linie oben 2 px `#111`, 12 px Innenabstand
- Label „Lösung → Adresse“: 9,5 px, 800, Großbuchstaben, letter-spacing 0,1em
- Zeile: `<user>.github.io/` (13 px, 500) + ein Kästchen pro Buchstabe des Lösungsworts:
  24 × 26 px, nur Unterstrich 2 px `#E2401C`, Index oben links 7 px, 800, `#E2401C`, gap 2 px

## 2 · Lösungsseite (GitHub Pages)
Mock-Maß 720 × 792 px (Desktop). Responsiv bauen.

- Hintergrund `#FFF`, Innenabstand 48 px / 56 px, Inhalt als Spalte
- Kopfzeile: links das Lösungswort, rechts „● Gelöst“ in `#E2401C`; beide 12 px, 700, Großbuchstaben, letter-spacing 0,1em
- Headline „Richtig / gedacht.“: 104 px, 800, letter-spacing −0,05em, line-height 0,9, **Punkt in `#E2401C`**; 96 px Abstand darüber
- Einleitung: 17 px, line-height 1,5, max-width 420 px, `#333`, 28 px Abstand darüber. Text vom Ersteller.
- Unten (`margin-top:auto`): 3-spaltiges Grid, gap 24 px. Jede Spalte: Linie oben 2 px `#111`, padding-top 12 px, Inhalt:
  - Nummer „01 / 02 / 03“ – 11 px, 700, `#E2401C`
  - Titel „Wann / Wo / Was“ – 18 px, 700
  - Text – 14 px, `#555` (Inhalt vom Ersteller)
- Mobil (< 640 px): Headline ca. 56–64 px, Infoblöcke untereinander.

## Verhalten
- Seite ist statisch; Erreichbarkeit nur über die richtige URL ist das „Schloss“.
- Lösungswort: nur Kleinbuchstaben a–z in der URL. **Umlaute vermeiden** (oder ä→ae usw.) und eindeutig wählen.
- Optional: `404.html` im Repo-Root im selben Stil („Noch nicht ganz – nochmal um die Ecke denken.“).
- Optional: `<meta name="robots" content="noindex">`, damit die Seite nicht gefunden wird.

## Dateien
- `Raetsel Designs.dc.html` – Designreferenz (nur Abschnitt `1a`)
