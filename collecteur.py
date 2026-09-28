#!/usr/bin/env python3
"""
Collecteur de la programmation Skyrock via l'API non officielle.
Interroge l'API toutes les N secondes et stocke les nouveaux morceaux en SQLite.
Enrichit automatiquement les artistes via Deezer (option A).
Version enrichie : stocke id_selector, cover_uri, likes, type, artistes_uid.
"""

import requests
import sqlite3
import time
import os
import sys
import signal
from datetime import datetime

# ============================================================
# IMPORT DE L'ENRICHISSEMENT (option A)
# ============================================================
sys.path.insert(0, os.path.expanduser('~/Desktop/APPS/skyrock/Bases'))
try:
    from enrichir import enrichir as enrichir_morceaux
except ImportError as e:
    print(f"[AVERTISSEMENT] enrichir.py non trouvé : {e}")
    enrichir_morceaux = None

# ============================================================
# CONFIGURATION
# ============================================================
API_URL     = "https://skyrock.fm/api/v3/player/onair/parisidf"
DOSSIER     = os.path.expanduser('~/Desktop/APPS/skyrock/Bases')
DB          = os.path.join(DOSSIER, 'skyrock.db')
LOG         = os.path.join(DOSSIER, 'collecteur.log')
INTERVALLE  = 60      # secondes entre deux appels
TIMEOUT     = 10       # timeout HTTP
MAX_ERREURS = 10       # après N erreurs consécutives, on s'arrête

# ============================================================
# BASE DE DONNÉES
# ============================================================
def init_db():
    os.makedirs(DOSSIER, exist_ok=True)
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS diffusions (
            uid             INTEGER PRIMARY KEY,
            titre           TEXT    NOT NULL,
            artistes        TEXT,
            artistes_uid    TEXT,
            start_ts        INTEGER NOT NULL,
            end_ts          INTEGER,
            duree           INTEGER,
            date            TEXT,
            heure           INTEGER,
            id_selector     TEXT,
            cover_uri       TEXT,
            likes           INTEGER DEFAULT 0,
            type            TEXT    DEFAULT 'record',
            album           TEXT,
            cover_deezer    TEXT,
            annee           INTEGER,
            preview_mp3     TEXT,
            deezer_rank     INTEGER,
            explicit_lyrics INTEGER,
            collecte        INTEGER
        )
    ''')
    c.execute('CREATE INDEX IF NOT EXISTS idx_start_ts ON diffusions(start_ts)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_artistes ON diffusions(artistes)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_likes ON diffusions(likes)')
    c.execute('''
        CREATE TABLE IF NOT EXISTS emissions (
            uid        INTEGER PRIMARY KEY,
            titre      TEXT,
            start_ts   INTEGER,
            end_ts     INTEGER,
            animateurs TEXT,
            collecte   INTEGER
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS erreurs (
            ts         INTEGER,
            message    TEXT
        )
    ''')
    conn.commit()
    return conn

# ============================================================
# LOG
# ============================================================
def log(message):
    horodatage = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    ligne = f"[{horodatage}] {message}"
    print(ligne, flush=True)
    try:
        with open(LOG, 'a', encoding='utf-8') as f:
            f.write(ligne + '\n')
    except Exception:
        pass

# ============================================================
# APPEL API
# ============================================================
def recuperer_programmation():
    try:
        r = requests.get(API_URL, timeout=TIMEOUT,
                         headers={'User-Agent': 'Mozilla/5.0'})
        r.raise_for_status()
        return r.json()
    except requests.exceptions.RequestException as e:
        return {'_erreur': str(e)}
    except ValueError as e:
        return {'_erreur': f"Réponse JSON invalide : {e}"}

# ============================================================
# UTILITAIRES DE CONVERSION
# ============================================================
def to_int(valeur, defaut=0):
    """Convertit une valeur en entier de manière robuste."""
    if valeur is None:
        return defaut
    try:
        return int(valeur)
    except (ValueError, TypeError):
        try:
            return int(float(valeur))
        except (ValueError, TypeError):
            return defaut

# ============================================================
# EXTRACTION DES MORCEAUX
# ============================================================
def extraire_morceaux(data):
    """Retourne une liste de dicts prêts à insérer."""
    morceaux = []
    if not data or 'schedule' not in data:
        return morceaux

    for item in data['schedule']:
        if item.get('type') != 'record':
            continue

        info = item.get('info', {})
        uid = to_int(info.get('uid'))
        if uid == 0:
            continue

        titre = (info.get('title') or '').strip()
        start_ts = to_int(info.get('start_ts'))
        end_ts = to_int(info.get('end_ts'))

        if not titre or not start_ts:
            continue

        # Artistes : liste de dicts avec 'name' et 'uid'
        artistes_list = info.get('artists', []) or []
        artistes = ", ".join(
            (a.get('name') or '').strip()
            for a in artistes_list
            if isinstance(a, dict)
        ).strip(', ')

        artistes_uid = ",".join(
            str(a.get('uid')) for a in artistes_list
            if isinstance(a, dict) and a.get('uid')
        )

        # Calculs dérivés
        duree = (end_ts - start_ts) if (end_ts and start_ts and
                                        end_ts > start_ts) else None

        try:
            dt = datetime.fromtimestamp(start_ts)
            date = dt.strftime('%Y-%m-%d')
            heure = dt.hour
        except (OSError, OverflowError, ValueError):
            date = None
            heure = None

        morceaux.append({
            'uid':          uid,
            'titre':        titre,
            'artistes':     artistes if artistes else None,
            'artistes_uid': artistes_uid or None,
            'start_ts':     start_ts,
            'end_ts':       end_ts if end_ts else None,
            'duree':        duree,
            'date':         date,
            'heure':        heure,
            'id_selector':  (info.get('id_selector') or '').strip() or None,
            'cover_uri':    (info.get('cover_uri') or '').strip() or None,
            'likes':        to_int(info.get('likes')) or 0,
            'type':         item.get('type') or 'record',
            'collecte':     int(time.time())
        })

    return morceaux

# ============================================================
# EXTRACTION DES ÉMISSIONS
# ============================================================
def extraire_emission(data, cle):
    """Extrait on_air_program ou next_program."""
    if not data or cle not in data or not data[cle]:
        return None

    p = data[cle]
    uid = to_int(p.get('uid'))
    if uid == 0:
        return None

    animateurs = ", ".join(
        (a.get('name') or '').strip()
        for a in (p.get('presenters') or [])
        if isinstance(a, dict)
    )

    return {
        'uid':        uid,
        'titre':      (p.get('title') or '').strip(),
        'start_ts':   to_int(p.get('start_ts')),
        'end_ts':     to_int(p.get('end_ts')),
        'animateurs': animateurs,
        'collecte':   int(time.time())
    }

# ============================================================
# INSERTION
# ============================================================
def inserer_morceaux(conn, morceaux):
    if not morceaux:
        return 0
    c = conn.cursor()
    nouveaux = 0
    for m in morceaux:
        try:
            c.execute('''
                INSERT OR IGNORE INTO diffusions
                (uid, titre, artistes, artistes_uid, start_ts, end_ts, duree,
                 date, heure, id_selector, cover_uri, likes, type, collecte)
                VALUES (:uid, :titre, :artistes, :artistes_uid, :start_ts,
                        :end_ts, :duree, :date, :heure, :id_selector,
                        :cover_uri, :likes, :type, :collecte)
            ''', m)
            if c.rowcount > 0:
                nouveaux += 1
                artiste_aff = m['artistes'] if m['artistes'] else '?'
                log(f"  + {artiste_aff} – {m['titre']}")
        except sqlite3.Error as e:
            log(f"  ! Erreur insertion uid={m.get('uid')} : {e}")
    conn.commit()
    return nouveaux

def inserer_emission(conn, emission):
    if not emission or not emission.get('uid'):
        return
    try:
        c = conn.cursor()
        c.execute('''
            INSERT OR IGNORE INTO emissions
            (uid, titre, start_ts, end_ts, animateurs, collecte)
            VALUES (:uid, :titre, :start_ts, :end_ts, :animateurs, :collecte)
        ''', emission)
        conn.commit()
    except sqlite3.Error as e:
        log(f"  ! Erreur insertion émission uid={emission.get('uid')} : {e}")

def enregistrer_erreur(conn, message):
    try:
        c = conn.cursor()
        c.execute('INSERT INTO erreurs (ts, message) VALUES (?, ?)',
                  (int(time.time()), message))
        conn.commit()
    except sqlite3.Error:
        pass

# ============================================================
# BOUCLE PRINCIPALE
# ============================================================
arret_demande = False

def gerer_signal(sig, frame):
    global arret_demande
    log("Signal d'arrêt reçu, fermeture propre...")
    arret_demande = True

signal.signal(signal.SIGINT,  gerer_signal)
signal.signal(signal.SIGTERM, gerer_signal)

def boucle(intervalle=INTERVALLE, max_erreurs=MAX_ERREURS):
    conn = init_db()
    log(f"Démarrage du collecteur (intervalle = {intervalle}s)")
    if enrichir_morceaux:
        log("Enrichissement automatique via Deezer : ACTIVÉ")
    else:
        log("Enrichissement automatique : DÉSACTIVÉ (enrichir.py manquant)")

    erreurs_consecutives = 0
    total_nouveaux = 0
    total_enrichis = 0
    cycles = 0

    while not arret_demande:
        cycles += 1
        data = recuperer_programmation()

        if '_erreur' in data:
            erreurs_consecutives += 1
            message = data['_erreur']
            log(f"Erreur API ({erreurs_consecutives}/{max_erreurs}) : {message}")
            enregistrer_erreur(conn, message)
            if erreurs_consecutives >= max_erreurs:
                log("Trop d'erreurs consécutives, arrêt.")
                break
        else:
            erreurs_consecutives = 0
            morceaux = extraire_morceaux(data)
            nouveaux = inserer_morceaux(conn, morceaux)
            total_nouveaux += nouveaux
            inserer_emission(conn, extraire_emission(data, 'on_air_program'))

            # Enrichissement automatique (option A)
            if nouveaux > 0 and enrichir_morceaux:
                try:
                    log(f"Enrichissement de {nouveaux} nouveau(x) morceau(x)...")
                    enrichis = enrichir_morceaux(limite=nouveaux, verbeux=False)
                    total_enrichis += enrichis if enrichis else 0
                except Exception as e:
                    log(f"  ! Enrichissement échoué : {e}")

            if nouveaux > 0:
                log(f"Cycle {cycles} : {nouveaux} nouveau(x), "
                    f"total = {total_nouveaux}")
            else:
                log(f"Cycle {cycles} : aucun nouveau")

        # Attente découpée pour répondre au Ctrl+C
        for _ in range(intervalle):
            if arret_demande:
                break
            time.sleep(1)

    conn.close()
    log(f"Arrêt. Total collecté : {total_nouveaux} morceaux. "
        f"Total enrichis : {total_enrichis}.")

# ============================================================
# MODE TEST (un seul appel)
# ============================================================
def test_unique():
    log("Mode test : un seul appel API")
    data = recuperer_programmation()

    if '_erreur' in data:
        log(f"Erreur : {data['_erreur']}")
        return

    emission = extraire_emission(data, 'on_air_program')
    if emission:
        log(f"Émission en cours : {emission['titre']} "
            f"(animateurs : {emission['animateurs']})")

    morceaux = extraire_morceaux(data)
    log(f"Morceaux présents dans le schedule : {len(morceaux)}")
    for m in morceaux:
        try:
            debut = datetime.fromtimestamp(m['start_ts']).strftime('%H:%M:%S')
            fin = (datetime.fromtimestamp(m['end_ts']).strftime('%H:%M:%S')
                   if m['end_ts'] else '?')
        except Exception:
            debut, fin = '?', '?'
        artiste_aff = m['artistes'] if m['artistes'] else '?'
        likes_aff = f" ({m['likes']} likes)" if m['likes'] else ''
        log(f"  [{debut} → {fin}] {artiste_aff} – {m['titre']}{likes_aff}")

    conn = init_db()
    n = inserer_morceaux(conn, morceaux)
    log(f"Enregistré dans la base : {n} nouveau(x)")

    if n > 0 and enrichir_morceaux:
        log(f"Enrichissement de {n} morceau(x)...")
        try:
            enrichis = enrichir_morceaux(limite=n, verbeux=True)
            log(f"Enrichissement terminé : {enrichis} morceau(x)")
        except Exception as e:
            log(f"  ! Enrichissement échoué : {e}")

    conn.close()

# ============================================================
# POINT D'ENTRÉE
# ============================================================
if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == 'test':
        test_unique()
    else:
        boucle()
