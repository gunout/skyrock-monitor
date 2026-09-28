#!/usr/bin/env python3
"""
Enrichissement des morceaux sans artiste via l'API publique Deezer.
Version durcie + enrichie :
  - filtre de similarité de titre
  - filtre de popularité Deezer (rank)
  - appel complémentaire à l'API track pour récupérer release_date
  - stocke album, cover, annee, preview, rank, explicit_lyrics
"""

import sqlite3
import requests
import time
import os
import sys
import unicodedata
from datetime import datetime

# ============================================================
# CONFIGURATION
# ============================================================
DOSSIER   = os.path.expanduser('~/Desktop/APPS/skyrock/Bases')
DB        = os.path.join(DOSSIER, 'skyrock.db')
LOG       = os.path.join(DOSSIER, 'enrichir.log')
LOCK      = os.path.join(DOSSIER, '.enrichir.lock')
TOLERANCE_PRECISE = 3
TOLERANCE_LARGE   = 8
SEUIL_SIMILARITE  = 0.6
PAUSE             = 0.3

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
# VERROU
# ============================================================
def acquerir_verrou():
    if os.path.exists(LOCK):
        try:
            with open(LOCK) as f:
                pid = int(f.read().strip())
            os.kill(pid, 0)
            log(f"Verrou actif (PID {pid}), arrêt.")
            return False
        except (ValueError, ProcessLookupError, OSError):
            log("Verrou orphelin détecté, on le supprime.")
            os.remove(LOCK)
    with open(LOCK, 'w') as f:
        f.write(str(os.getpid()))
    return True

def liberer_verrou():
    try:
        os.remove(LOCK)
    except FileNotFoundError:
        pass

# ============================================================
# NORMALISATION & SIMILARITÉ
# ============================================================
def normaliser(texte):
    if not texte:
        return ''
    texte = texte.lower()
    texte = unicodedata.normalize('NFKD', texte)
    texte = ''.join(c for c in texte if not unicodedata.combining(c))
    texte = ''.join(c if c.isalnum() or c.isspace() else ' '
                    for c in texte)
    return ' '.join(texte.split())

def similarite_titre(titre_a, titre_b):
    mots_a = set(normaliser(titre_a).split())
    mots_b = set(normaliser(titre_b).split())
    if not mots_a:
        return 0.0
    return len(mots_a & mots_b) / len(mots_a)

# ============================================================
# DEEZER
# ============================================================
_cache_deezer = {}
_cache_track  = {}

def chercher_deezer(titre, limite=10):
    """Recherche des morceaux par titre."""
    if titre in _cache_deezer:
        return _cache_deezer[titre]
    try:
        r = requests.get(
            'https://api.deezer.com/search',
            params={'q': titre, 'limit': limite},
            timeout=8,
            headers={'User-Agent': 'Mozilla/5.0'}
        )
        r.raise_for_status()
        data = r.json().get('data', [])
    except Exception as e:
        log(f"  ! Erreur Deezer pour '{titre}' : {e}")
        data = []
    _cache_deezer[titre] = data
    return data

def recuperer_track_deezer(track_id):
    """Récupère les détails d'un track (pour release_date notamment)."""
    if not track_id:
        return {}
    if track_id in _cache_track:
        return _cache_track[track_id]
    try:
        r = requests.get(
            f"https://api.deezer.com/track/{track_id}",
            timeout=5,
            headers={'User-Agent': 'Mozilla/5.0'}
        )
        if r.ok:
            data = r.json()
        else:
            data = {}
    except Exception:
        data = {}
    _cache_track[track_id] = data
    time.sleep(0.2)
    return data

def choisir_candidat(candidats, duree_skyrock, titre_skyrock):
    """
    Choisit le meilleur candidat :
    1. filtre similarité de titre
    2. priorité aux candidats avec rank > 0
    3. tri par (écart durée, -popularité)
    """
    if not candidats:
        return None, None, None

    # 1. Filtre similarité de titre
    ok = [c for c in candidats
          if similarite_titre(titre_skyrock, c.get('title', ''))
             >= SEUIL_SIMILARITE]
    if not ok:
        ok = candidats

    # 2. Filtrer : ne garder que ceux avec rank > 0 (popularité Deezer)
    ok_avec_rank = [c for c in ok if (c.get('rank') or 0) > 0]
    if ok_avec_rank:
        ok = ok_avec_rank

    # 3. Tri par (écart durée, -rank)
    def score(c):
        ecart = abs((c.get('duration') or 0) - (duree_skyrock or 0))
        return (ecart, -(c.get('rank') or 0))

    ok.sort(key=score)
    meilleur = ok[0]
    ecart = abs((meilleur.get('duration') or 0) - (duree_skyrock or 0))

    if ecart <= TOLERANCE_PRECISE:
        return meilleur, ecart, 'precise'
    if ecart <= TOLERANCE_LARGE:
        return meilleur, ecart, 'large'
    return None, ecart, None

# ============================================================
# ENRICHISSEMENT
# ============================================================
def enrichir(limite=None, verbeux=True):
    if not acquerir_verrou():
        return 0
    try:
        return _enrichir_interne(limite, verbeux)
    finally:
        liberer_verrou()

def _enrichir_interne(limite, verbeux):
    conn = sqlite3.connect(DB)
    c = conn.cursor()

    requete = """
        SELECT uid, titre, duree
        FROM diffusions
        WHERE artistes IS NULL OR artistes = ''
        ORDER BY start_ts DESC
    """
    if limite:
        requete += f" LIMIT {int(limite)}"

    rows = c.execute(requete).fetchall()

    if not rows:
        if verbeux:
            log("Aucun morceau à enrichir.")
        conn.close()
        return 0

    log(f"Morceaux à enrichir : {len(rows)}")
    enrichis = 0
    approximatifs = 0
    echecs = 0

    for uid, titre, duree in rows:
        candidats = chercher_deezer(titre)
        bon, ecart, confiance = choisir_candidat(candidats, duree, titre)

        if bon is None:
            log(f"  ✗ {titre[:50]:50} (aucun match, écart {ecart}s)")
            echecs += 1
        else:
            artiste = (bon.get('artist') or {}).get('name', '').strip()
            titre_deezer = (bon.get('title') or '').strip()
            duree_deezer = bon.get('duration')

            symbole = '✓' if confiance == 'precise' else '⚠'
            log(f"  {symbole} {titre[:40]:40} → "
                f"{artiste} – {titre_deezer} ({duree_deezer}s)")

            # Extraction des infos complémentaires
            album_info = bon.get('album') or {}
            album = (album_info.get('title') or '').strip() or None
            cover_deezer = (album_info.get('cover_medium') or '').strip() or None
            preview_mp3 = (bon.get('preview') or '').strip() or None
            deezer_rank = int(bon.get('rank') or 0) or None
            explicit_lyrics = 1 if bon.get('explicit_lyrics') else 0

            # Année : d'abord dans la recherche, sinon appel API track
            annee = None
            release_date = (bon.get('release_date') or '').strip()
            if not release_date:
                details = recuperer_track_deezer(bon.get('id'))
                release_date = (details.get('release_date') or '').strip()
            if release_date and len(release_date) >= 4:
                try:
                    annee = int(release_date[:4])
                except (ValueError, TypeError):
                    annee = None

            try:
                c.execute("""
                    UPDATE diffusions
                    SET artistes         = ?,
                        titre            = COALESCE(NULLIF(?, ''), titre),
                        album            = ?,
                        cover_deezer     = ?,
                        preview_mp3      = ?,
                        annee            = ?,
                        deezer_rank      = ?,
                        explicit_lyrics  = ?
                    WHERE uid = ?
                """, (artiste, titre_deezer, album, cover_deezer,
                      preview_mp3, annee, deezer_rank,
                      explicit_lyrics, uid))
                conn.commit()
                enrichis += 1
                if confiance == 'large':
                    approximatifs += 1
            except sqlite3.Error as e:
                log(f"  ! Erreur UPDATE uid={uid} : {e}")

        time.sleep(PAUSE)

    conn.close()
    log(f"Terminé — enrichis : {enrichis} "
        f"(dont {approximatifs} approximatifs), échecs : {echecs}")
    return enrichis

# ============================================================
# POINT D'ENTRÉE
# ============================================================
if __name__ == '__main__':
    limite = None
    verbeux = True
    for arg in sys.argv[1:]:
        if arg.startswith('--limite='):
            try:
                limite = int(arg.split('=', 1)[1])
            except ValueError:
                pass
        elif arg == '--silencieux':
            verbeux = False
    enrichir(limite, verbeux)