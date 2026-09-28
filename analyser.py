#!/usr/bin/env python3
"""
Analyse de la base skyrock.db collectée par collecteur.py et enrichie
par enrichir.py.
Génère des CSV dans le dossier resultats/.
"""

import sqlite3
import os
import pandas as pd

# ============================================================
# CONFIGURATION
# ============================================================
DOSSIER = os.path.expanduser('~/Desktop/APPS/skyrock/Bases')
DB      = os.path.join(DOSSIER, 'skyrock.db')
RES     = os.path.join(DOSSIER, 'resultats')
os.makedirs(RES, exist_ok=True)

if not os.path.exists(DB):
    print(f"❌ Base introuvable : {DB}")
    raise SystemExit(1)

conn = sqlite3.connect(DB)

# ============================================================
# VÉRIFICATION DES DONNÉES
# ============================================================
try:
    total = conn.execute("SELECT COUNT(*) FROM diffusions").fetchone()[0]
except sqlite3.OperationalError as e:
    print(f"❌ Table 'diffusions' introuvable : {e}")
    raise SystemExit(1)

if total == 0:
    print("⚠️  La table 'diffusions' est vide. Lancez d'abord collecteur.py.")
    raise SystemExit(1)

sans_artiste = conn.execute(
    "SELECT COUNT(*) FROM diffusions WHERE artistes IS NULL OR artistes = ''"
).fetchone()[0]

print(f"Base : {total} diffusions, dont {sans_artiste} sans artiste")
if sans_artiste > 0:
    print(f"⚠️  {sans_artiste} morceaux sans artiste — "
          f"lancez enrichir.py pour les compléter")

# ============================================================
# FONCTION D'EXPORT
# ============================================================
def export(nom, requete):
    try:
        df = pd.read_sql_query(requete, conn)
    except Exception as e:
        print(f"❌ Erreur sur {nom} : {e}")
        return None
    chemin = os.path.join(RES, f'{nom}.csv')
    df.to_csv(chemin, index=False, encoding='utf-8-sig')
    print(f"\n=== {nom.replace('_', ' ').upper()} ===")
    print(df.head(15).to_string(index=False))
    return df

# ============================================================
# 1. VOLUME GLOBAL
# ============================================================
export('00_volume_global', """
    SELECT COUNT(*)                          AS nb_diffusions,
           COUNT(DISTINCT artistes)          AS nb_artistes,
           COUNT(DISTINCT titre)             AS nb_titres,
           MIN(date)                         AS premiere_date,
           MAX(date)                         AS derniere_date,
           ROUND(SUM(duree)/3600.0, 2)       AS heures_antenne,
           ROUND(AVG(duree), 1)              AS duree_moy_s
    FROM diffusions
    WHERE artistes IS NOT NULL AND artistes != ''
""")

# ============================================================
# 2. TOP ARTISTES
# ============================================================
export('01_top_artistes', """
    SELECT artistes,
           COUNT(*)                          AS nb_diffusions,
           COUNT(DISTINCT titre)             AS titres_differents,
           ROUND(SUM(duree)/60.0, 1)         AS minutes_antenne
    FROM diffusions
    WHERE artistes IS NOT NULL AND artistes != ''
    GROUP BY artistes
    ORDER BY minutes_antenne DESC, nb_diffusions DESC
""")

# ============================================================
# 3. TOP TITRES
# ============================================================
export('02_top_titres', """
    SELECT artistes, titre,
           COUNT(*)                          AS nb_diffusions,
           ROUND(SUM(duree)/60.0, 1)         AS minutes_antenne
    FROM diffusions
    WHERE artistes IS NOT NULL AND artistes != ''
    GROUP BY artistes, titre
    ORDER BY nb_diffusions DESC, minutes_antenne DESC
""")

# ============================================================
# 4. RÉPARTITION HORAIRE
# ============================================================
export('03_repartition_horaire', """
    SELECT heure,
           COUNT(*)                          AS nb_diffusions,
           ROUND(SUM(duree)/60.0, 1)         AS minutes
    FROM diffusions
    WHERE heure IS NOT NULL
    GROUP BY heure
    ORDER BY heure
""")

# ============================================================
# 5. RÉPARTITION JOURNALIÈRE
# ============================================================
export('04_repartition_journaliere', """
    SELECT date,
           COUNT(*)                          AS nb_diffusions,
           COUNT(DISTINCT titre)             AS titres_differents,
           COUNT(DISTINCT artistes)          AS artistes_differents,
           ROUND(SUM(duree)/3600.0, 2)       AS heures
    FROM diffusions
    WHERE date IS NOT NULL
    GROUP BY date
    ORDER BY date
""")

# ============================================================
# 6. TOP ARTISTE PAR HEURE
# ============================================================
export('05_top_artiste_par_heure', """
    SELECT heure, artistes, nb_diffusions
    FROM (
        SELECT heure, artistes,
               COUNT(*) AS nb_diffusions,
               ROW_NUMBER() OVER (
                   PARTITION BY heure
                   ORDER BY COUNT(*) DESC
               ) AS rang
        FROM diffusions
        WHERE artistes IS NOT NULL AND artistes != ''
          AND heure IS NOT NULL
        GROUP BY heure, artistes
    )
    WHERE rang = 1
    ORDER BY heure
""")

# ============================================================
# 7. ARTISTES RÉCURRENTS
# ============================================================
export('06_artistes_recurrents', """
    SELECT artistes,
           COUNT(DISTINCT date)              AS nb_jours,
           COUNT(*)                          AS nb_diffusions,
           ROUND(SUM(duree)/60.0, 1)         AS minutes
    FROM diffusions
    WHERE artistes IS NOT NULL AND artistes != ''
    GROUP BY artistes
    HAVING nb_jours >= 2
    ORDER BY nb_jours DESC, nb_diffusions DESC
""")

# ============================================================
# 8. TITRES RÉCURRENTS
# ============================================================
export('07_titres_recurrents', """
    SELECT artistes, titre,
           COUNT(DISTINCT date)              AS nb_jours,
           COUNT(*)                          AS nb_diffusions
    FROM diffusions
    WHERE artistes IS NOT NULL AND artistes != ''
    GROUP BY artistes, titre
    HAVING nb_jours >= 2
    ORDER BY nb_jours DESC, nb_diffusions DESC
""")

# ============================================================
# 9. DURÉE MOYENNE PAR TITRE
# ============================================================
export('08_duree_moyenne', """
    SELECT artistes, titre,
           COUNT(*)                          AS nb_diffusions,
           ROUND(AVG(duree), 1)              AS duree_moy_s,
           MIN(duree)                        AS duree_min_s,
           MAX(duree)                        AS duree_max_s
    FROM diffusions
    WHERE duree IS NOT NULL
      AND artistes IS NOT NULL AND artistes != ''
    GROUP BY artistes, titre
    HAVING nb_diffusions >= 2
    ORDER BY duree_moy_s DESC
""")

# ============================================================
# 10. RÉPARTITION PAR JOUR DE LA SEMAINE
# ============================================================
export('09_jour_semaine', """
    SELECT
        CASE CAST(strftime('%w', date) AS INTEGER)
            WHEN 0 THEN 'Dimanche'
            WHEN 1 THEN 'Lundi'
            WHEN 2 THEN 'Mardi'
            WHEN 3 THEN 'Mercredi'
            WHEN 4 THEN 'Jeudi'
            WHEN 5 THEN 'Vendredi'
            WHEN 6 THEN 'Samedi'
        END AS jour,
        COUNT(*)                             AS nb_diffusions,
        ROUND(SUM(duree)/3600.0, 2)          AS heures
    FROM diffusions
    WHERE date IS NOT NULL
    GROUP BY strftime('%w', date)
    ORDER BY CAST(strftime('%w', date) AS INTEGER)
""")

# ============================================================
# 11. ÉMISSIONS DIFFUSÉES
# ============================================================
export('10_emissions', """
    SELECT titre, animateurs,
           COUNT(*)                          AS nb_passages,
           MIN(datetime(start_ts, 'unixepoch')) AS premiere,
           MAX(datetime(start_ts, 'unixepoch')) AS derniere
    FROM emissions
    GROUP BY titre, animateurs
    ORDER BY nb_passages DESC
""")

# ============================================================
# 12. HEURES CRÊTES / PLEINES
# ============================================================
export('11_heures_activite', """
    SELECT heure,
           COUNT(*)                          AS nb_diffusions,
           ROUND(SUM(duree)/60.0, 1)         AS minutes
    FROM diffusions
    WHERE heure IS NOT NULL
    GROUP BY heure
    ORDER BY nb_diffusions ASC
""")

# ============================================================
# 13. MORCEAUX SANS ARTISTE
# ============================================================
export('12_sans_artiste', """
    SELECT uid, titre, duree, date, heure
    FROM diffusions
    WHERE artistes IS NULL OR artistes = ''
    ORDER BY start_ts DESC
""")

# ============================================================
# 14. ARTISTES LES PLUS DIVERSIFIÉS
# ============================================================
export('13_artistes_diversifies', """
    SELECT artistes,
           COUNT(DISTINCT titre)             AS nb_titres_differents,
           COUNT(*)                          AS nb_diffusions,
           ROUND(COUNT(*) * 1.0 /
                 COUNT(DISTINCT titre), 2)   AS ratio
    FROM diffusions
    WHERE artistes IS NOT NULL AND artistes != ''
    GROUP BY artistes
    HAVING nb_titres_differents >= 2
    ORDER BY nb_titres_differents DESC, ratio DESC
""")

# ============================================================
# 15. TOP MORCEAUX PAR LIKES SKYROCK
# ============================================================
export('14_top_likes', """
    SELECT artistes, titre, likes
    FROM diffusions
    WHERE likes > 0
    ORDER BY likes DESC
    LIMIT 20
""")

# ============================================================
# 16. RÉPARTITION PAR ANNÉE DE SORTIE
# ============================================================
export('15_par_annee', """
    SELECT annee, COUNT(*) AS nb_diffusions
    FROM diffusions
    WHERE annee IS NOT NULL
    GROUP BY annee
    ORDER BY annee DESC
""")

# ============================================================
# 17. CONTENU EXPLICITE
# ============================================================
export('16_explicit', """
    SELECT
        CASE explicit_lyrics
            WHEN 1 THEN 'Explicit'
            WHEN 0 THEN 'Clean'
            ELSE 'Inconnu'
        END AS type_contenu,
        COUNT(*) AS nb,
        ROUND(100.0 * COUNT(*) /
              (SELECT COUNT(*) FROM diffusions
               WHERE explicit_lyrics IS NOT NULL), 1) AS pct
    FROM diffusions
    WHERE explicit_lyrics IS NOT NULL
    GROUP BY explicit_lyrics
""")

# ============================================================
# 18. ALBUMS LES PLUS DIFFUSÉS
# ============================================================
export('17_top_albums', """
    SELECT album, artistes, COUNT(*) AS nb_diffusions
    FROM diffusions
    WHERE album IS NOT NULL AND album != ''
    GROUP BY album
    ORDER BY nb_diffusions DESC
    LIMIT 20
""")

# ============================================================
# 19. DERNIER MORCEAU DIFFUSÉ
# ============================================================
export('18_dernier_morceau', """
    SELECT titre, artistes, cover_deezer, cover_uri, preview_mp3,
           date, heure, album, annee, start_ts
    FROM diffusions
    ORDER BY start_ts DESC
    LIMIT 1
""")

conn.close()
print(f"\n✅ Analyse terminée. Résultats dans : {RES}")
print(f"   18 fichiers CSV générés.")
