#!/usr/bin/env python3
"""Kreuzworträtsel-Generator „Um die Ecke gedacht“ (Design 1a „Raster“).

Eingabe  (raetsel.config.json):
  wortliste        – Kandidaten {wort, hinweis}, aus denen das Raster gefüllt wird
  loesungswoerter  – Wörter, die auf jeden Fall ins Raster müssen (optional, [] = freie Wahl)
  form             – zeilen × spalten, optional maske ('#' = gesperrtes Feld, '.' = frei)
  loesungswort     – Wort aus markierten Feldern (jeder Buchstabe genau ein Feld)

Befehle:
  erzeugen  – Raster bauen, Lösungsfelder paaren, puzzle.json schreiben
  pruefen   – puzzle.json (und vorhandene HTML-Dateien) gegenprüfen
  rendern   – raetsel.html, raetsel-loesung.html und die GitHub-Pages-Seite schreiben
  alles     – erzeugen + rendern + pruefen

Nur Python-Standardbibliothek. Ausgabe ist HTML/CSS in mm – vektoriell, beliebig skalierbar.
"""
import argparse
import hashlib
import html
import json
import random
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# --- Druckmaße (mm). Mock 560 px ≙ 210 mm → 1 px = 0,375 mm -----------------
PX = 0.375
SEITE_B, SEITE_H = 210.0, 297.0
RAND_O, RAND_S, RAND_U = 40 * PX, 44 * PX, 36 * PX      # 15 / 16,5 / 13,5
BLOCK_ABSTAND = 20 * PX                                  # 7,5
FELD_MM = 30 * PX                                        # 11,25
LINIE_MM = 1 * PX                                        # 0,375
HINWEIS_FS = 10.5 * PX                                   # 3,9375
HINWEIS_LH = 1.4
HINWEIS_KOPF_FS = 9.5 * PX
HINWEIS_GAP = 6 * PX
HINWEIS_SPALTEN_GAP = 24 * PX
HINWEIS_NR_B = 14 * PX
# Höhen von Kopf und Fuß (gemessen am gerenderten Blatt, mit kleiner Reserve)
KOPF_H = 34 * PX * 0.95 * 2 + 12 * PX + 2 * PX + 0.5
FUSS_H = 2 * PX + 12 * PX + 9.5 * PX * 1.4 + 8 * PX + 26 * PX + 0.5
# mittlere Zeichenbreite von Hanken Grotesk 400 in em (konservativ)
ZEICHEN_EM = 0.50

H, V = 0, 1                       # Richtung waagerecht / senkrecht
SCHRITT = {H: (0, 1), V: (1, 0)}
BLOCK = '#'


class Fehler(Exception):
    pass


# --------------------------------------------------------------------------- Eingabe

UMLAUTE = {'Ä': 'AE', 'Ö': 'OE', 'Ü': 'UE', 'ß': 'SS', 'ẞ': 'SS'}


def normalisiere(wort):
    w = wort.strip().upper()
    for k, v in UMLAUTE.items():
        w = w.replace(k, v)
    w = re.sub(r'[\s\-]', '', w)
    if not re.fullmatch(r'[A-Z]+', w):
        raise Fehler(f'Ungültiges Wort {wort!r}: nur Buchstaben (Umlaute werden zu AE/OE/UE) erlaubt.')
    return w


def lade_config(pfad):
    try:
        cfg = json.loads(Path(pfad).read_text(encoding='utf-8'))
    except FileNotFoundError:
        raise Fehler(f'Konfiguration {pfad} nicht gefunden.')
    except json.JSONDecodeError as e:
        raise Fehler(f'Konfiguration {pfad} ist kein gültiges JSON: {e}')

    for key in ('loesungswort', 'github_user', 'form', 'wortliste'):
        if key not in cfg:
            raise Fehler(f'Konfiguration: Feld "{key}" fehlt.')

    hinweise = {}
    for e in cfg['wortliste']:
        w = normalisiere(e['wort'])
        if len(w) < 2:
            raise Fehler(f'Wort {e["wort"]!r} ist zu kurz (mind. 2 Buchstaben).')
        if not e.get('hinweis', '').strip():
            raise Fehler(f'Wort {e["wort"]!r} hat keinen Hinweis.')
        hinweise[w] = e['hinweis'].strip()

    pflicht = []
    for e in cfg.get('loesungswoerter', []) or []:
        if isinstance(e, str):
            w = normalisiere(e)
            if w not in hinweise:
                raise Fehler(f'Lösungswort-Eintrag {e!r} steht nicht in der Wortliste (Hinweis fehlt).')
        else:
            w = normalisiere(e['wort'])
            hinweise[w] = e['hinweis'].strip()
        pflicht.append(w)

    loesung = normalisiere(cfg['loesungswort'])
    url_wort = loesung.lower()
    if not re.fullmatch(r'[a-z]+', url_wort):
        raise Fehler('Lösungswort muss in der URL nur aus a–z bestehen.')

    form = cfg['form']
    R, C = int(form['zeilen']), int(form['spalten'])
    maske = form.get('maske')
    frei = [[True] * C for _ in range(R)]
    if maske:
        if len(maske) != R or any(len(z) != C for z in maske):
            raise Fehler(f'Maske muss {R} Zeilen à {C} Zeichen haben.')
        frei = [[ch != '#' for ch in z] for z in maske]

    user = cfg['github_user'].strip()
    if not re.fullmatch(r'[A-Za-z0-9-]+', user):
        raise Fehler('github_user ist ungültig.')
    projekt = str(cfg.get('projekt', '')).strip()
    if not re.fullmatch(r'[a-z0-9-]+', projekt):
        raise Fehler('projekt (Repo-Name) fehlt oder enthält andere Zeichen als a–z, 0–9, -. '
                     'Nur Kleinbuchstaben: GitHub Pages unterscheidet Groß/Klein in der Adresse.')

    return {
        'roh': cfg, 'hinweise': hinweise, 'pflicht': pflicht, 'loesung': loesung,
        'url_wort': url_wort, 'R': R, 'C': C, 'frei': frei, 'user': user.lower(), 'projekt': projekt,
        'gen': cfg.get('generator', {}),
    }


def hinweis_text(hinweis, wort):
    return f'{hinweis} ({len(wort)})'


# --------------------------------------------------------------------------- Platzbudget Druck

def feld_mm(R, C):
    """Feldgröße: 11,25 mm laut Design, nur verkleinern, wenn das Raster sonst nicht passt."""
    inhalt_b = SEITE_B - 2 * RAND_S
    max_raster_h = 11 * FELD_MM + 12 * LINIE_MM          # Höhe des 11×11-Referenzrasters
    f = min(FELD_MM,
            (inhalt_b - (C + 1) * LINIE_MM) / C,
            (max_raster_h - (R + 1) * LINIE_MM) / R)
    return round(f, 3)


def hinweis_budget(R, C):
    f = feld_mm(R, C)
    raster_h = R * f + (R + 1) * LINIE_MM
    inhalt_h = SEITE_H - RAND_O - RAND_U
    return inhalt_h - KOPF_H - raster_h - FUSS_H - 3 * BLOCK_ABSTAND


def zeilen_fuer(text):
    spalte_b = (SEITE_B - 2 * RAND_S - HINWEIS_SPALTEN_GAP) / 2 - HINWEIS_NR_B - HINWEIS_GAP
    max_z = spalte_b / (HINWEIS_FS * ZEICHEN_EM)
    zeilen, laenge = 1, 0
    for wort in text.split():
        n = len(wort) if laenge == 0 else laenge + 1 + len(wort)
        if n > max_z and laenge:
            zeilen, laenge = zeilen + 1, len(wort)
        else:
            laenge = n
    return zeilen


def spalten_hoehe(texte):
    h = HINWEIS_KOPF_FS * HINWEIS_LH
    for t in texte:
        h += HINWEIS_GAP + zeilen_fuer(t) * HINWEIS_FS * HINWEIS_LH
    return h


# --------------------------------------------------------------------------- Layout

class Layout:
    def __init__(self, R, C, frei):
        self.R, self.C, self.frei = R, C, frei
        self.g = [[None] * C for _ in range(R)]
        self.richt = [[0] * C for _ in range(R)]     # Bitmaske 1=H, 2=V
        self.woerter = []                           # (wort, r, c, d)
        self.nach_buchstabe = defaultdict(list)
        self.benutzt = set()
        self.texte = {H: [], V: []}

    def drin(self, r, c):
        return 0 <= r < self.R and 0 <= c < self.C

    def pruefe(self, w, r, c, d):
        """Anzahl Kreuzungen oder -1, wenn das Wort dort nicht regelkonform liegt."""
        dr, dc = SCHRITT[d]
        L = len(w)
        er, ec = r + dr * (L - 1), c + dc * (L - 1)
        if not (self.drin(r, c) and self.drin(er, ec)):
            return -1
        if self.drin(r - dr, c - dc) and self.g[r - dr][c - dc] is not None:
            return -1
        if self.drin(er + dr, ec + dc) and self.g[er + dr][ec + dc] is not None:
            return -1
        bit = 1 << d
        x = 0
        for i, ch in enumerate(w):
            rr, cc = r + dr * i, c + dc * i
            if not self.frei[rr][cc]:
                return -1
            cur = self.g[rr][cc]
            if cur is None:
                for s in (-1, 1):
                    ar, ac = rr + dc * s, cc + dr * s
                    if self.drin(ar, ac) and self.g[ar][ac] is not None:
                        return -1
            else:
                if cur != ch or self.richt[rr][cc] & bit:
                    return -1
                x += 1
        if x == L:
            return -1
        return x

    def setze(self, w, r, c, d, text):
        dr, dc = SCHRITT[d]
        for i, ch in enumerate(w):
            rr, cc = r + dr * i, c + dc * i
            if self.g[rr][cc] is None:
                self.g[rr][cc] = ch
                self.nach_buchstabe[ch].append((rr, cc))
            self.richt[rr][cc] |= 1 << d
        self.woerter.append((w, r, c, d))
        self.benutzt.add(w)
        self.texte[d].append(text)

    def kandidaten(self, w):
        for i, ch in enumerate(w):
            for (rr, cc) in self.nach_buchstabe.get(ch, ()):
                m = self.richt[rr][cc]
                for d in (H, V):
                    if m & (1 << d):
                        continue
                    dr, dc = SCHRITT[d]
                    r, c = rr - dr * i, cc - dc * i
                    x = self.pruefe(w, r, c, d)
                    if x > 0:
                        yield (x, r, c, d)

    def raster(self):
        return [''.join(ch if ch else BLOCK for ch in zeile) for zeile in self.g]


def versuch(rng, cfg, budget):
    R, C = cfg['R'], cfg['C']
    hinweise = cfg['hinweise']
    max_w = int(cfg['gen'].get('max_woerter', 16))
    lay = Layout(R, C, cfg['frei'])

    pflicht = sorted(set(cfg['pflicht']), key=lambda w: (-len(w), rng.random()))
    pool = [w for w in hinweise if w not in pflicht and len(w) <= max(R, C)]
    for w in pflicht:
        if len(w) > max(R, C):
            raise Fehler(f'Lösungswort {w} ist länger als das Raster.')

    def passt_text(w, d):
        t = hinweis_text(hinweise[w], w)
        return spalten_hoehe(lay.texte[d] + [t]) <= budget

    # Startwort: längstes Pflichtwort oder ein zufälliges langes Wort
    if pflicht:
        start = pflicht[0]
    else:
        lang = sorted(pool, key=len, reverse=True)[:12]
        start = rng.choice(lang)
    d0 = rng.choice((H, V))
    gesetzt = False
    for _ in range(200):
        dr, dc = SCHRITT[d0]
        L = len(start)
        mitte_r = rng.randint(max(0, R // 2 - 2), min(R - 1, R // 2 + 2))
        mitte_c = rng.randint(max(0, C // 2 - 2), min(C - 1, C // 2 + 2))
        r = mitte_r - dr * (L // 2) if d0 == V else mitte_r
        c = mitte_c - dc * (L // 2) if d0 == H else mitte_c
        r = min(max(r, 0), R - 1 - dr * (L - 1))
        c = min(max(c, 0), C - 1 - dc * (L - 1))
        if lay.pruefe(start, r, c, d0) == 0 and passt_text(start, d0):
            lay.setze(start, r, c, d0, hinweis_text(hinweise[start], start))
            gesetzt = True
            break
    if not gesetzt:
        return None

    offen_pflicht = [w for w in pflicht if w != start]
    while len(lay.woerter) < max_w:
        ziele = offen_pflicht if offen_pflicht else [w for w in pool if w not in lay.benutzt]
        kands = []
        zeilen_belegt = {r for r in range(R) if any(lay.g[r])}
        spalten_belegt = {c for c in range(C) if any(lay.g[r][c] for r in range(R))}
        for w in ziele:
            for (x, r, c, d) in lay.kandidaten(w):
                dr, dc = SCHRITT[d]
                neu_z = len({r + dr * i for i in range(len(w))} - zeilen_belegt)
                neu_s = len({c + dc * i for i in range(len(w))} - spalten_belegt)
                n_d = len(lay.texte[d])
                score = (4 * x + 0.6 * len(w) + 1.2 * (neu_z + neu_s)
                         - 1.5 * max(0, n_d - len(lay.texte[1 - d]))
                         + rng.random() * 3)
                kands.append((score, w, r, c, d))
        if not kands:
            break
        kands.sort(reverse=True)
        gewaehlt = None
        for (_, w, r, c, d) in kands:
            if passt_text(w, d):
                gewaehlt = (w, r, c, d)
                break
        if not gewaehlt:
            break
        w, r, c, d = gewaehlt
        lay.setze(w, r, c, d, hinweis_text(hinweise[w], w))
        if w in offen_pflicht:
            offen_pflicht.remove(w)

    if offen_pflicht:
        return None
    return lay


def bewerte(lay):
    raster = lay.raster()
    R, C = lay.R, lay.C
    buchstaben = sum(ch != BLOCK for z in raster for ch in z)
    kreuz = sum(1 for r in range(R) for c in range(C) if lay.richt[r][c] == 3)
    leer_z = sum(1 for z in raster if set(z) == {BLOCK})
    leer_s = sum(1 for c in range(C) if all(raster[r][c] == BLOCK for r in range(R)))
    # große schwarze Flächen vermeiden: leere 3×3-Fenster zählen
    leer_fenster = sum(
        1 for r in range(R - 2) for c in range(C - 2)
        if all(raster[r + i][c + j] == BLOCK for i in range(3) for j in range(3)))
    nh, nv = len(lay.texte[H]), len(lay.texte[V])
    return (1.0 * buchstaben + 5 * kreuz - 25 * (leer_z + leer_s) - 4 * leer_fenster
            - 3 * abs(nh - nv) + 2 * len(lay.woerter))


# --------------------------------------------------------------------------- Nummerierung

def nummeriere(raster):
    """Standard-Nummerierung (zeilenweise). Liefert (nummern, waagerecht, senkrecht)."""
    R, C = len(raster), len(raster[0])
    offen = lambda r, c: 0 <= r < R and 0 <= c < C and raster[r][c] != BLOCK
    nummern, waag, senk = {}, [], []
    n = 0
    for r in range(R):
        for c in range(C):
            if not offen(r, c):
                continue
            beginnt_h = not offen(r, c - 1) and offen(r, c + 1)
            beginnt_v = not offen(r - 1, c) and offen(r + 1, c)
            if not (beginnt_h or beginnt_v):
                continue
            n += 1
            nummern[(r, c)] = n
            if beginnt_h:
                w, cc = '', c
                while offen(r, cc):
                    w += raster[r][cc]
                    cc += 1
                waag.append({'nr': n, 'zeile': r, 'spalte': c, 'antwort': w})
            if beginnt_v:
                w, rr = '', r
                while offen(rr, c):
                    w += raster[rr][c]
                    rr += 1
                senk.append({'nr': n, 'zeile': r, 'spalte': c, 'antwort': w})
    return nummern, waag, senk


# --------------------------------------------------------------------------- Lösungsfelder

def felder_nach_buchstabe(raster):
    d = defaultdict(list)
    for r, z in enumerate(raster):
        for c, ch in enumerate(z):
            if ch != BLOCK:
                d[ch].append((r, c))
    return d


def paarung(raster, loesung, rng=None):
    """Ordnet jedem Buchstaben des Lösungsworts ein eigenes Feld zu (Backtracking)."""
    fb = felder_nach_buchstabe(raster)
    reihenfolge = sorted(range(len(loesung)), key=lambda i: len(fb[loesung[i]]))
    zuordnung = [None] * len(loesung)
    belegt = set()

    def bt(k):
        if k == len(reihenfolge):
            return True
        i = reihenfolge[k]
        kand = list(fb[loesung[i]])
        if rng:
            rng.shuffle(kand)
        for f in kand:
            if f in belegt:
                continue
            belegt.add(f)
            zuordnung[i] = f
            if bt(k + 1):
                return True
            belegt.discard(f)
        return False

    return list(zuordnung) if bt(0) else None


def streuung(felder, wort_von):
    ds = [abs(a[0] - b[0]) + abs(a[1] - b[1])
          for i, a in enumerate(felder) for b in felder[i + 1:]]
    woerter = {w for f in felder for w in wort_von[f]}
    return 10 * min(ds) + sum(ds) / len(ds) + 2 * len(woerter)


def waehle_loesungsfelder(raster, loesung, eintraege, rng, versuche=400):
    wort_von = defaultdict(set)
    for e in eintraege:
        dr, dc = SCHRITT[e['richtung']]
        for i in range(len(e['antwort'])):
            wort_von[(e['zeile'] + dr * i, e['spalte'] + dc * i)].add((e['richtung'], e['nr']))
    beste, beste_s = None, None
    for _ in range(versuche):
        p = paarung(raster, loesung, rng)
        if p is None:
            return None
        s = streuung(p, wort_von)
        if beste_s is None or s > beste_s:
            beste, beste_s = p, s
    return beste


def fehlende_buchstaben(woerter, loesung):
    vorrat = defaultdict(int)
    for w in woerter:
        for ch in w:
            vorrat[ch] += 1
    bedarf = defaultdict(int)
    for ch in loesung:
        bedarf[ch] += 1
    return [ch for ch in bedarf if vorrat[ch] < 1]


# --------------------------------------------------------------------------- erzeugen

def erzeugen(cfg, ausgabe, seed=None, versuche=None):
    loesung = cfg['loesung']
    fehlt = fehlende_buchstaben(cfg['hinweise'], loesung)
    if fehlt:
        raise Fehler('Keine Paarung möglich: Buchstabe(n) ' + ', '.join(fehlt)
                     + f' aus „{loesung}“ kommen in keinem Wort der Wortliste vor.')

    seed = int(seed if seed is not None else cfg['gen'].get('seed', 1))
    versuche = int(versuche if versuche is not None else cfg['gen'].get('versuche', 600))
    budget = hinweis_budget(cfg['R'], cfg['C'])
    rng = random.Random(seed)

    beste, beste_s, gueltig, ohne_paarung = None, None, 0, 0
    for _ in range(versuche):
        lay = versuch(rng, cfg, budget)
        if lay is None or len(lay.woerter) < 2:
            continue
        raster = lay.raster()
        if paarung(raster, loesung) is None:
            ohne_paarung += 1
            continue
        gueltig += 1
        s = bewerte(lay)
        if beste_s is None or s > beste_s:
            beste, beste_s = lay, s

    if beste is None:
        grund = (f'In {versuche} Versuchen ließ sich „{loesung}“ in keinem Raster auf '
                 'eindeutige Felder verteilen.' if ohne_paarung else
                 f'In {versuche} Versuchen entstand kein gültiges Raster '
                 '(Lösungswörter passen nicht in die Form?).')
        raise Fehler('Keine Paarung zwischen Lösungswort und Lösungswörtern gefunden. ' + grund
                     + ' Tipp: Wortliste erweitern, Form vergrößern oder --versuche erhöhen.')

    raster = beste.raster()
    nummern, waag, senk = nummeriere(raster)
    gesetzt = {(w, r, c, d) for (w, r, c, d) in beste.woerter}
    eintraege = []
    for d, liste in ((H, waag), (V, senk)):
        for e in liste:
            assert (e['antwort'], e['zeile'], e['spalte'], d) in gesetzt, e
            e['richtung'] = d
            e['laenge'] = len(e['antwort'])
            e['hinweis'] = hinweis_text(cfg['hinweise'][e['antwort']], e['antwort'])
            eintraege.append(e)

    felder = waehle_loesungsfelder(raster, loesung, eintraege, rng)
    if felder is None:
        raise Fehler(f'Keine Paarung für „{loesung}“ im gewählten Raster gefunden.')

    def ohne_richtung(e):
        return {k: e[k] for k in ('nr', 'zeile', 'spalte', 'antwort', 'laenge', 'hinweis')}

    puzzle = {
        'version': 1,
        'loesungswort': loesung,
        'url_wort': cfg['url_wort'],
        'github_user': cfg['user'],
        'projekt': cfg['projekt'],
        'url': f'https://{cfg["user"]}.github.io/{cfg["projekt"]}/',
        'zeilen': cfg['R'],
        'spalten': cfg['C'],
        'feld_mm': feld_mm(cfg['R'], cfg['C']),
        'raster': raster,
        'legende': {'#': 'Blockfeld', 'A–Z': 'Buchstabe (Ä/Ö/Ü = AE/OE/UE)'},
        'waagerecht': [ohne_richtung(e) for e in eintraege if e['richtung'] == H],
        'senkrecht': [ohne_richtung(e) for e in eintraege if e['richtung'] == V],
        'loesungsfelder': [
            {'index': i + 1, 'buchstabe': loesung[i], 'zeile': f[0], 'spalte': f[1]}
            for i, f in enumerate(felder)
        ],
        'generator': {'seed': seed, 'versuche': versuche, 'gueltige_raster': gueltig,
                      'bewertung': round(beste_s, 1)},
    }
    Path(ausgabe).write_text(json.dumps(puzzle, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'✓ {ausgabe}: {len(eintraege)} Wörter '
          f'({len(puzzle["waagerecht"])} waagerecht / {len(puzzle["senkrecht"])} senkrecht), '
          f'{gueltig} gültige Raster aus {versuche} Versuchen.')
    for z in raster:
        print('   ' + ' '.join('·' if ch == BLOCK else ch for ch in z))
    return puzzle


# --------------------------------------------------------------------------- prüfen

def pruefen(puzzle_pfad, html_pruefen=True):
    p = json.loads(Path(puzzle_pfad).read_text(encoding='utf-8'))
    fehler = []
    ok = lambda bed, msg: bed or fehler.append(msg)

    R, C, raster = p['zeilen'], p['spalten'], p['raster']
    ok(len(raster) == R, f'Raster hat {len(raster)} statt {R} Zeilen.')
    for i, z in enumerate(raster):
        ok(len(z) == C, f'Zeile {i} hat {len(z)} statt {C} Felder.')
        ok(re.fullmatch(r'[A-Z#]+', z) is not None, f'Zeile {i} enthält ungültige Zeichen: {z}')
    if fehler:
        return melde(fehler)

    # Nummerierung neu berechnen und vergleichen
    _, waag, senk = nummeriere(raster)
    for name, soll, ist in (('waagerecht', waag, p['waagerecht']), ('senkrecht', senk, p['senkrecht'])):
        ok(len(soll) == len(ist), f'{name}: {len(ist)} Einträge, Raster ergibt {len(soll)}.')
        for a, b in zip(soll, ist):
            for k in ('nr', 'zeile', 'spalte', 'antwort'):
                ok(a[k] == b[k], f'{name} {b.get("nr")}: {k} ist {b[k]!r}, erwartet {a[k]!r}.')
            ok(b['laenge'] == len(b['antwort']), f'{name} {b["nr"]}: Länge stimmt nicht.')
            ok(b['hinweis'].endswith(f'({len(b["antwort"])})'),
               f'{name} {b["nr"]}: Hinweis endet nicht auf „({len(b["antwort"])})“.')
        nrs = [e['nr'] for e in ist]
        ok(nrs == sorted(nrs), f'{name}: Nummern nicht aufsteigend.')

    # jedes Buchstabenfeld gehört zu mindestens einem Wort
    abgedeckt = set()
    for e in waag:
        abgedeckt |= {(e['zeile'], e['spalte'] + i) for i in range(len(e['antwort']))}
    for e in senk:
        abgedeckt |= {(e['zeile'] + i, e['spalte']) for i in range(len(e['antwort']))}
    for r in range(R):
        for c in range(C):
            if raster[r][c] != BLOCK:
                ok((r, c) in abgedeckt, f'Feld ({r},{c}) gehört zu keinem Wort.')

    # keine Antwort doppelt
    alle = [e['antwort'] for e in p['waagerecht'] + p['senkrecht']]
    ok(len(alle) == len(set(alle)), 'Eine Antwort kommt doppelt vor.')

    # Lösungsfelder
    lw = p['loesungswort']
    lf = p['loesungsfelder']
    ok(len(lf) == len(lw), f'{len(lf)} Lösungsfelder, Lösungswort hat {len(lw)} Buchstaben.')
    ok([f['index'] for f in lf] == list(range(1, len(lw) + 1)), 'Lösungsindizes nicht 1…n.')
    pos = [(f['zeile'], f['spalte']) for f in lf]
    ok(len(set(pos)) == len(pos), 'Ein Feld ist mehrfach als Lösungsfeld markiert.')
    gelesen = ''
    for f in lf:
        r, c = f['zeile'], f['spalte']
        ch = raster[r][c] if 0 <= r < R and 0 <= c < C else BLOCK
        ok(ch != BLOCK, f'Lösungsfeld {f["index"]} liegt auf einem Blockfeld.')
        ok(ch == f['buchstabe'], f'Lösungsfeld {f["index"]}: Raster hat {ch}, erwartet {f["buchstabe"]}.')
        gelesen += ch
    ok(gelesen == lw, f'Lösungsfelder ergeben „{gelesen}“ statt „{lw}“.')
    ok(p['url_wort'] == lw.lower() and re.fullmatch(r'[a-z]+', p['url_wort']) is not None,
       'url_wort passt nicht zum Lösungswort.')

    # HTML-Dateien (falls schon gerendert)
    if html_pruefen:
        basis = Path(puzzle_pfad).resolve().parent
        blatt = basis / 'raetsel.html'
        if blatt.exists():
            t = blatt.read_text(encoding='utf-8')
            ok(lw.lower() not in t.lower(), 'raetsel.html verrät das Lösungswort.')
            ok('class="l"' not in t, 'raetsel.html enthält eingetragene Buchstaben.')
            ok(t.count('class="f s"') == len(lw), 'raetsel.html: Anzahl Lösungsfelder stimmt nicht.')
            ok(t.count('class="slot"') == len(lw), 'raetsel.html: Anzahl Adress-Kästchen stimmt nicht.')
        loes = basis / 'raetsel-loesung.html'
        if loes.exists():
            t = loes.read_text(encoding='utf-8')
            ok(t.count('class="l"') == sum(ch != BLOCK for z in raster for ch in z),
               'raetsel-loesung.html: nicht alle Buchstaben eingetragen.')
        docs = basis / 'docs'
        if docs.exists():
            for datei in ('index.html', '404.html', f'{p["url_wort"]}/index.html'):
                ok((docs / datei).exists(), f'docs/{datei} fehlt.')
            # Eingabe- und Fehlerseite dürfen das Wort nicht verraten (nur der Hash steht drin)
            for datei in ('index.html', '404.html'):
                if (docs / datei).exists():
                    t = (docs / datei).read_text(encoding='utf-8')
                    ok(lw.lower() not in t.lower(), f'docs/{datei} verrät das Lösungswort.')
                    ok(hashlib.sha256(p['url_wort'].encode()).hexdigest() in t,
                       f'docs/{datei}: Hash des Lösungsworts fehlt.')
        if blatt.exists():
            ok(f'{p["github_user"]}.github.io/{p["projekt"]}' in blatt.read_text(encoding='utf-8'),
               'raetsel.html: Adresse der Eingabeseite fehlt.')

    if fehler:
        return melde(fehler)
    n = len(p['waagerecht']) + len(p['senkrecht'])
    print(f'✓ Prüfung bestanden: {R}×{C}-Raster, {n} Wörter, Nummerierung korrekt, '
          f'Lösungsfelder ergeben „{gelesen}“.')
    return True


def melde(fehler):
    print('✗ Prüfung fehlgeschlagen:', file=sys.stderr)
    for f in fehler:
        print('  – ' + f, file=sys.stderr)
    return False


# --------------------------------------------------------------------------- rendern

FONT_LINK = ('<link rel="preconnect" href="https://fonts.googleapis.com">\n'
             '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>\n'
             '<link href="https://fonts.googleapis.com/css2?family=Hanken+Grotesk:wght@400;500;700;800'
             '&display=swap" rel="stylesheet">')

BLATT_CSS = """
:root{
  --ink:#111111; --paper:#FFFFFF; --accent:#E2401C;
  --cell:%(cell)smm; --line:0.375mm; --cols:%(cols)s;
}
@page{size:A4;margin:0}
*{box-sizing:border-box}
html,body{margin:0;padding:0}
body{font-family:'Hanken Grotesk',sans-serif;color:var(--ink);
  -webkit-print-color-adjust:exact;print-color-adjust:exact;-webkit-font-smoothing:antialiased}
@media screen{
  body{background:#F2F2F2;padding:10mm 0}
  .blatt{margin:0 auto;outline:1px solid #E5E5E5}
}
.blatt{width:210mm;height:297mm;background:var(--paper);overflow:hidden;
  padding:15mm 16.5mm 13.5mm;display:flex;flex-direction:column;gap:7.5mm}

/* Kopf */
.kopf{display:flex;justify-content:space-between;align-items:flex-end;
  border-bottom:0.75mm solid var(--ink);padding-bottom:4.5mm}
.titel{font-size:12.75mm;font-weight:800;letter-spacing:-.03em;line-height:.95}
.meta{font-size:3.75mm;font-weight:500;text-align:right;line-height:1.5;
  text-transform:uppercase;letter-spacing:.08em}

/* Raster */
.raster{display:grid;grid-template-columns:repeat(var(--cols),var(--cell));
  grid-auto-rows:var(--cell);gap:var(--line);background:var(--ink);
  border:var(--line) solid var(--ink);width:max-content}
.f{position:relative;background:var(--paper)}
.f.b{background:var(--ink)}
.f .n{position:absolute;top:calc(var(--cell) * .0667);left:calc(var(--cell) * .1);
  font-size:calc(var(--cell) * .25);font-weight:700}
.f.s::after{content:"";position:absolute;inset:0;
  border:calc(var(--cell) * .0667) solid var(--accent)}
.f .si{position:absolute;right:calc(var(--cell) * .1);bottom:calc(var(--cell) * .0667);
  font-size:calc(var(--cell) * .25);font-weight:800;color:var(--accent);line-height:1}
.f .l{position:absolute;inset:0;display:flex;align-items:center;justify-content:center;
  font-size:calc(var(--cell) * .5);font-weight:700}

/* Hinweise */
.hinweise{display:grid;grid-template-columns:1fr 1fr;gap:9mm;font-size:3.9375mm;line-height:1.4}
.spalte{display:flex;flex-direction:column;gap:2.25mm}
.spalte h2{margin:0;font-weight:800;text-transform:uppercase;letter-spacing:.1em;font-size:3.5625mm}
.h{display:flex;gap:2.25mm}
.h .nr{width:5.25mm;flex:none;font-weight:700}

/* Fuß: Lösungswort → Adresse der Eingabeseite */
.fuss{margin-top:auto;border-top:0.75mm solid var(--ink);padding-top:4.5mm;
  display:flex;flex-direction:column;gap:3mm}
.fuss .label{font-size:3.5625mm;font-weight:800;text-transform:uppercase;letter-spacing:.1em}
.adresse{display:flex;align-items:flex-end;flex-wrap:wrap;gap:2.25mm 4.5mm;font-size:4.875mm;font-weight:500}
.ziel{padding-bottom:1.5mm;white-space:nowrap}
.slots{display:flex;gap:0.75mm}
.slot{position:relative;width:9mm;height:9.75mm;border-bottom:0.75mm solid var(--accent);
  display:flex;align-items:flex-end;justify-content:center;font-weight:700;font-size:5.25mm;
  padding-bottom:0.75mm}
.slot .si{position:absolute;top:0;left:0.375mm;font-size:2.625mm;color:var(--accent);
  font-weight:800;line-height:1.2}
"""


def esc(s):
    return html.escape(str(s), quote=True)


def blatt_html(p, cfg_roh, mit_loesung):
    blatt = cfg_roh.get('blatt', {})
    nummer = blatt.get('nummer', 'Nº 01')
    widmung = 'Lösung' if mit_loesung else blatt.get('widmung', 'Für dich')
    raster = p['raster']
    nummern, _, _ = nummeriere(raster)
    loes = {(f['zeile'], f['spalte']): f['index'] for f in p['loesungsfelder']}

    zellen = []
    for r, z in enumerate(raster):
        for c, ch in enumerate(z):
            if ch == BLOCK:
                zellen.append('<div class="f b"></div>')
                continue
            innen = ''
            if (r, c) in nummern:
                innen += f'<span class="n">{nummern[(r, c)]}</span>'
            if mit_loesung:
                innen += f'<span class="l">{ch}</span>'
            klasse = 'f'
            if (r, c) in loes:
                klasse = 'f s'
                innen += f'<span class="si">{loes[(r, c)]}</span>'
            zellen.append(f'<div class="{klasse}">{innen}</div>')

    def spalte(titel, liste):
        zeilen = ''.join(
            f'\n      <div class="h"><span class="nr">{e["nr"]}</span><span>{esc(e["hinweis"])}</span></div>'
            for e in liste)
        return f'<div class="spalte">\n      <h2>{titel}</h2>{zeilen}\n    </div>'

    slots = ''.join(
        f'<div class="slot"><span class="si">{i + 1}</span>{esc(ch.lower()) if mit_loesung else ""}</div>'
        for i, ch in enumerate(p['loesungswort']))

    css = BLATT_CSS % {'cell': p['feld_mm'], 'cols': p['spalten']}
    titel = 'Um die Ecke gedacht – Lösung' if mit_loesung else 'Um die Ecke gedacht'
    return f"""<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex">
<title>{titel}</title>
{FONT_LINK}
<style>{css}</style>
</head>
<body>
<main class="blatt">
  <header class="kopf">
    <div class="titel">Um die Ecke<br>gedacht.</div>
    <div class="meta">{esc(nummer)}<br>{esc(widmung)}</div>
  </header>

  <div class="raster" role="img" aria-label="Kreuzworträtsel {p['zeilen']} mal {p['spalten']} Felder">
    {''.join(zellen)}
  </div>

  <section class="hinweise">
    {spalte('Waagerecht', p['waagerecht'])}
    {spalte('Senkrecht', p['senkrecht'])}
  </section>

  <footer class="fuss">
    <div class="label">Lösungswort → eingeben auf</div>
    <div class="adresse"><div class="slots">{slots}</div><span class="ziel">→ {esc(p['github_user'])}.github.io/{esc(p['projekt'])}</span></div>
  </footer>
</main>
</body>
</html>
"""


SEITE_CSS = """
:root{--ink:#111111;--paper:#FFFFFF;--accent:#E2401C;--text:#333333;--text-2:#555555}
*{box-sizing:border-box}
html,body{margin:0;background:var(--paper)}
body{font-family:'Hanken Grotesk',sans-serif;color:var(--ink);-webkit-font-smoothing:antialiased}
.seite{min-height:100vh;min-height:100svh;max-width:1040px;margin:0 auto;padding:48px 56px;
  display:flex;flex-direction:column}
.kopf{display:flex;justify-content:space-between;gap:16px;font-size:12px;font-weight:700;
  text-transform:uppercase;letter-spacing:.1em}
.status{color:var(--accent)}
h1{font-size:104px;font-weight:800;letter-spacing:-.05em;line-height:.9;margin:96px 0 0}
.punkt{color:var(--accent)}
.intro{font-size:17px;line-height:1.5;max-width:420px;margin:28px 0 0;color:var(--text);
  text-wrap:pretty;white-space:pre-line}
.infos{margin-top:auto;padding-top:64px;display:grid;grid-template-columns:repeat(3,1fr);gap:24px}
.info{border-top:2px solid var(--ink);padding-top:12px;display:flex;flex-direction:column;gap:6px}
.info .nr{font-size:11px;font-weight:700;color:var(--accent)}
.info h2{margin:0;font-size:18px;font-weight:700}
.info p{margin:0;font-size:14px;line-height:1.45;color:var(--text-2);white-space:pre-line}
@media (max-width:639px){
  .seite{padding:32px 24px}
  h1{font-size:60px;margin-top:64px}
  .intro{font-size:16px}
  .infos{grid-template-columns:1fr;gap:20px;padding-top:56px}
}
"""


def seite_html(p, texte):
    t = {k: str(texte.get(k, 'Text folgt')) for k in ('intro', 'wann', 'wo', 'was')}
    js = json.dumps(t, ensure_ascii=False, indent=2)
    js = js.replace('</', '<\\/')
    infos = ''.join(
        f'\n    <div class="info"><span class="nr">0{i + 1}</span><h2>{titel}</h2>'
        f'<p data-text="{key}">{esc(t[key])}</p></div>'
        for i, (key, titel) in enumerate((('wann', 'Wann'), ('wo', 'Wo'), ('was', 'Was'))))
    return f"""<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex, nofollow">
<title>Richtig gedacht.</title>
<script>
/* ============================================================
   TEXTE DER LÖSUNGSSEITE – hier einsetzen.
   intro = Einleitung unter der Headline
   wann / wo / was = die drei Infoblöcke 01 / 02 / 03
   Zeilenumbrüche mit \\n. (Alternativ in raetsel.config.json →
   "seite" pflegen und `python3 tools/kreuzwort.py rendern`.)
   ============================================================ */
const TEXTE = {js};
</script>
{FONT_LINK}
<style>{SEITE_CSS}</style>
</head>
<body>
<main class="seite">
  <div class="kopf"><span>{esc(p['loesungswort'])}</span><span class="status">● Gelöst</span></div>
  <h1>Richtig<br>gedacht<span class="punkt">.</span></h1>
  <p class="intro" data-text="intro">{esc(t['intro'])}</p>
  <section class="infos">{infos}
  </section>
</main>
<script>
document.querySelectorAll('[data-text]').forEach(function (el) {{
  var v = TEXTE[el.dataset.text];
  if (v != null) el.textContent = v;
}});
</script>
</body>
</html>
"""


# Gemeinsames JS: Eingabe normalisieren und SHA-256 bilden. Im öffentlichen Quelltext steht nur
# der Hash des Lösungsworts, nie das Wort selbst.
HASH_JS = """
function normalisiere(s) {
  return String(s).trim().toLowerCase()
    .replace(/ä/g, 'ae').replace(/ö/g, 'oe').replace(/ü/g, 'ue').replace(/ß/g, 'ss')
    .replace(/[^a-z]/g, '');
}
function sha256(s) {
  return crypto.subtle.digest('SHA-256', new TextEncoder().encode(s)).then(function (buf) {
    return Array.prototype.map.call(new Uint8Array(buf), function (b) {
      return ('0' + b.toString(16)).slice(-2);
    }).join('');
  });
}
"""


def soll_hash(p):
    return hashlib.sha256(p['url_wort'].encode('utf-8')).hexdigest()


EINGABE_CSS = """
.eingabe{margin-top:auto;padding-top:64px}
.eingabe .rahmen{border-top:2px solid var(--ink);padding-top:12px;display:flex;flex-direction:column;gap:14px}
.label{font-size:11px;font-weight:800;text-transform:uppercase;letter-spacing:.1em}
.zeile{display:flex;align-items:flex-end;flex-wrap:wrap;gap:16px 24px}
.kaestchen{display:flex;gap:6px}
.k{position:relative;display:block;width:48px;height:60px;border-bottom:2px solid var(--accent)}
.k:focus-within{border-bottom-color:var(--ink)}
.k .si{position:absolute;top:2px;left:2px;font-size:10px;font-weight:800;color:var(--accent);pointer-events:none}
.k input{box-sizing:border-box;width:100%;height:100%;margin:0;padding:14px 0 0;border:0;border-radius:0;
  background:transparent;outline:none;text-align:center;text-transform:uppercase;
  font:700 32px/1 'Hanken Grotesk',sans-serif;color:var(--ink);caret-color:var(--accent)}
.knopf{display:inline-flex;align-items:center;height:48px;padding:0 22px;border:0;border-radius:0;
  background:var(--ink);color:var(--paper);font:700 12px 'Hanken Grotesk',sans-serif;
  text-transform:uppercase;letter-spacing:.1em;text-decoration:none;cursor:pointer}
.knopf:hover{opacity:.85}
.meldung{margin:0;min-height:1.5em;font-size:15px;line-height:1.5;color:var(--text)}
@media (max-width:639px){
  .kaestchen{display:grid;grid-template-columns:repeat(__N__,1fr);gap:4px;width:100%}
  .k{width:auto;height:52px}
  .k input{font-size:24px;padding-top:12px}
  .knopf{width:100%;justify-content:center}
}
"""


def eingabe_html(p, cfg_roh):
    blatt = cfg_roh.get('blatt', {})
    n = len(p['loesungswort'])
    kaestchen = ''.join(
        f'\n        <label class="k"><span class="si">{i + 1}</span>'
        f'<input type="text" inputmode="text" autocomplete="off" autocorrect="off" '
        f'autocapitalize="characters" spellcheck="false" aria-label="Buchstabe {i + 1} von {n}"></label>'
        for i in range(n))
    return f"""<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex, nofollow">
<title>Um die Ecke gedacht.</title>
{FONT_LINK}
<style>{SEITE_CSS}{EINGABE_CSS.replace('__N__', str(n))}</style>
</head>
<body>
<main class="seite">
  <div class="kopf"><span>{esc(blatt.get('nummer', 'Nº 01'))} · {esc(blatt.get('widmung', 'Für dich'))}</span><span class="status" id="status" aria-live="polite"></span></div>
  <h1>Um die Ecke<br>gedacht<span class="punkt">.</span></h1>
  <p class="intro">Trag das Lösungswort aus dem Rätsel ein – Buchstabe für Buchstabe, in der Reihenfolge der roten Zahlen.</p>
  <form class="eingabe" id="form" autocomplete="off" novalidate>
    <div class="rahmen">
      <div class="label">Lösungswort</div>
      <div class="zeile">
        <div class="kaestchen">{kaestchen}
        </div>
        <button class="knopf" type="submit">Prüfen →</button>
      </div>
      <p class="meldung" id="meldung" aria-live="polite"></p>
    </div>
  </form>
</main>
<script>
{HASH_JS}
(function () {{
  var SOLL = '{soll_hash(p)}';
  var felder = Array.prototype.slice.call(document.querySelectorAll('.k input'));
  var status = document.getElementById('status');
  var meldung = document.getElementById('meldung');
  var BUCHSTABE = /[a-zäöüß]/i;

  function zeige(stat, text) {{ status.textContent = stat; meldung.textContent = text; }}
  function buchstaben(s) {{ return String(s).split('').filter(function (c) {{ return BUCHSTABE.test(c); }}); }}
  function gross(c) {{ return c === 'ß' ? c : c.toUpperCase(); }}
  function verteile(text, ab) {{
    var cs = buchstaben(text);
    for (var k = 0; k < cs.length && ab + k < felder.length; k++) felder[ab + k].value = gross(cs[k]);
    felder[Math.min(ab + cs.length, felder.length - 1)].focus();
  }}
  function vollstaendig() {{ return felder.every(function (f) {{ return f.value; }}); }}

  felder.forEach(function (f, i) {{
    f.addEventListener('focus', function () {{ f.select(); }});
    f.addEventListener('input', function () {{
      var cs = buchstaben(f.value), alt = f.dataset.alt || '';
      zeige('', '');
      // mehrere Zeichen auf einmal (Autokorrektur, Diktat …) → auf die folgenden Kästchen verteilen;
      // altes + neues Zeichen → nur das neue behalten
      if (cs.length > 2 || (cs.length === 2 && !alt)) {{
        verteile(cs.join(''), i);
      }} else {{
        f.value = cs.length ? gross(cs[cs.length - 1]) : '';
        if (f.value && i < felder.length - 1) felder[i + 1].focus();
      }}
      felder.forEach(function (g) {{ g.dataset.alt = g.value; }});
      if (f.value && vollstaendig() && document.activeElement === felder[felder.length - 1]) pruefe();
    }});
    f.addEventListener('paste', function (e) {{
      e.preventDefault();
      verteile((e.clipboardData || window.clipboardData).getData('text'), i);
      felder.forEach(function (g) {{ g.dataset.alt = g.value; }});
      if (vollstaendig()) pruefe();
    }});
    f.addEventListener('keydown', function (e) {{
      if (e.key === 'Backspace' && !f.value && i > 0) {{
        e.preventDefault(); felder[i - 1].value = felder[i - 1].dataset.alt = ''; felder[i - 1].focus();
      }} else if (e.key === 'ArrowLeft' && i > 0) {{ e.preventDefault(); felder[i - 1].focus(); }}
      else if (e.key === 'ArrowRight' && i < felder.length - 1) {{ e.preventDefault(); felder[i + 1].focus(); }}
    }});
  }});

  function pruefe() {{
    if (!vollstaendig()) {{ zeige('', 'Es fehlen noch Buchstaben.'); return; }}
    if (!window.crypto || !crypto.subtle) {{ zeige('', 'Bitte die Seite über https:// öffnen.'); return; }}
    var wort = normalisiere(felder.map(function (f) {{ return f.value; }}).join(''));
    sha256(wort).then(function (ist) {{
      if (ist === SOLL) {{
        zeige('● Gelöst', 'Richtig gedacht!');
        location.href = './' + wort + '/';
      }} else {{
        zeige('● Noch nicht', 'Noch nicht ganz – nochmal um die Ecke denken.');
      }}
    }});
  }}
  document.getElementById('form').addEventListener('submit', function (e) {{ e.preventDefault(); pruefe(); }});
}})();
</script>
</body>
</html>
"""


def fehlerseite_html(p):
    basis = f"/{p['projekt']}/"
    return f"""<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex, nofollow">
<title>Noch nicht ganz.</title>
<script>
{HASH_JS}
/* Lösungswort direkt an die Adresse gehängt, in anderer Schreibweise (Großbuchstaben,
   Ä statt AE …) → zur Lösungsseite. Verglichen wird nur der SHA-256-Hash. */
(function () {{
  var SOLL = '{soll_hash(p)}', BASIS = '{basis}';
  var pfad = location.pathname;
  if (pfad.toLowerCase().indexOf(BASIS) !== 0 || !window.crypto || !crypto.subtle) return;
  var seg = pfad.slice(BASIS.length).split('/').filter(Boolean)[0];
  var wort;
  try {{ wort = normalisiere(decodeURIComponent(seg || '')); }} catch (e) {{ return; }}
  if (!wort) return;
  var html = document.documentElement;
  html.style.visibility = 'hidden';
  sha256(wort).then(function (ist) {{
    if (ist === SOLL && pfad !== BASIS + wort + '/') location.replace(BASIS + wort + '/');
    else html.style.visibility = '';
  }}, function () {{ html.style.visibility = ''; }});
}})();
</script>
{FONT_LINK}
<style>{SEITE_CSS}{EINGABE_CSS.replace('__N__', str(len(p['loesungswort'])))}</style>
</head>
<body>
<main class="seite">
  <div class="kopf"><span>404</span><span class="status">● Noch nicht</span></div>
  <h1>Noch nicht<br>ganz<span class="punkt">.</span></h1>
  <p class="intro">Noch nicht ganz – nochmal um die Ecke denken.</p>
  <section class="eingabe">
    <div class="rahmen">
      <div class="label">Lösungswort eingeben</div>
      <div class="zeile"><a class="knopf" href="{basis}">Zur Eingabe →</a></div>
    </div>
  </section>
</main>
</body>
</html>
"""


def rendern(puzzle_pfad, cfg_roh, basis):
    p = json.loads(Path(puzzle_pfad).read_text(encoding='utf-8'))
    basis = Path(basis)
    (basis / 'raetsel.html').write_text(blatt_html(p, cfg_roh, False), encoding='utf-8')
    (basis / 'raetsel-loesung.html').write_text(blatt_html(p, cfg_roh, True), encoding='utf-8')
    # GitHub Pages veröffentlicht docs/ unter https://<user>.github.io/<projekt>/
    docs = basis / 'docs'
    (docs / p['url_wort']).mkdir(parents=True, exist_ok=True)
    (docs / 'index.html').write_text(eingabe_html(p, cfg_roh), encoding='utf-8')
    (docs / p['url_wort'] / 'index.html').write_text(seite_html(p, cfg_roh.get('seite', {})),
                                                     encoding='utf-8')
    (docs / '404.html').write_text(fehlerseite_html(p), encoding='utf-8')
    (docs / '.nojekyll').write_text('', encoding='utf-8')
    print(f'✓ raetsel.html, raetsel-loesung.html, docs/index.html (Eingabe), '
          f'docs/{p["url_wort"]}/index.html (Lösung), docs/404.html → {p["url"]}')


# --------------------------------------------------------------------------- CLI

def main(argv=None):
    ap = argparse.ArgumentParser(description='Kreuzworträtsel „Um die Ecke gedacht“')
    ap.add_argument('befehl', choices=['erzeugen', 'pruefen', 'rendern', 'alles'])
    ap.add_argument('--config', default=str(ROOT / 'raetsel.config.json'))
    ap.add_argument('--puzzle', default=str(ROOT / 'puzzle.json'))
    ap.add_argument('--ausgabe', default=str(ROOT), help='Zielordner für HTML-Dateien')
    ap.add_argument('--seed', type=int)
    ap.add_argument('--versuche', type=int)
    a = ap.parse_args(argv)

    try:
        if a.befehl in ('erzeugen', 'alles'):
            cfg = lade_config(a.config)
            erzeugen(cfg, a.puzzle, a.seed, a.versuche)
        if a.befehl in ('rendern', 'alles'):
            cfg = lade_config(a.config)
            rendern(a.puzzle, cfg['roh'], a.ausgabe)
        if a.befehl in ('pruefen', 'alles'):
            if not pruefen(a.puzzle):
                return 1
    except Fehler as e:
        print(f'✗ Fehler: {e}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
