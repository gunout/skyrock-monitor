#!/usr/bin/env python3
"""
Exporte les données de skyrock.db en JSON statique pour GitHub Pages.
Produit un seul fichier : data.json
"""

import sqlite3
import json
import os
from datetime import datetime

DOSSIER = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(DOSSIER, 'skyrock.db')
SORTIE = os.path.join(DOSSIER, 'data.json')

conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row
c = conn.cursor()

def rows_to_list(rows):
    return [dict(r) for r in rows]

data = {
    'genere_le': datetime.now().isoformat(),
    'genere_ts': int(datetime.now().timestamp()),
}

# Volume global
data['volume'] = dict(c.execute("""
    SELECT COUNT(*) AS nb_diffusions,
           COUNT(DISTINCT artistes) AS nb_artistes,
           COUNT(DISTINCT titre) AS nb_titres,
           MIN(date) AS premiere_date,
           MAX(date) AS derniere_date,
           ROUND(SUM(duree)/3600.0, 2) AS heures_antenne,
           ROUND(AVG(duree), 1) AS duree_moy_s
    FROM diffusions
    WHERE artistes IS NOT NULL AND artistes != ''
""").fetchone() or {})

# Top artistes
data['top_artistes'] = rows_to_list(c.execute("""
    SELECT artistes, COUNT(*) AS nb_diffusions,
           COUNT(DISTINCT titre) AS titres_differents,
           ROUND(SUM(duree)/60.0, 1) AS minutes_antenne
    FROM diffusions
    WHERE artistes IS NOT NULL AND artistes != ''
    GROUP BY artistes
    ORDER BY minutes_antenne DESC, nb_diffusions DESC
    LIMIT 20
""").fetchall())

# Top titres
data['top_titres'] = rows_to_list(c.execute("""
    SELECT artistes, titre, COUNT(*) AS nb_diffusions,
           ROUND(SUM(duree)/60.0, 1) AS minutes_antenne
    FROM diffusions
    WHERE artistes IS NOT NULL AND artistes != ''
    GROUP BY artistes, titre
    ORDER BY nb_diffusions DESC
    LIMIT 20
""").fetchall())

# Répartition horaire
data['heures'] = rows_to_list(c.execute("""
    SELECT heure, COUNT(*) AS nb_diffusions
    FROM diffusions
    WHERE heure IS NOT NULL
    GROUP BY heure
    ORDER BY heure
""").fetchall())

# Répartition journalière
data['jours'] = rows_to_list(c.execute("""
    SELECT date, COUNT(*) AS nb_diffusions,
           COUNT(DISTINCT titre) AS titres_differents
    FROM diffusions
    WHERE date IS NOT NULL
    GROUP BY date
    ORDER BY date
""").fetchall())

# Jour de la semaine
data['semaine'] = rows_to_list(c.execute("""
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
        COUNT(*) AS nb_diffusions
    FROM diffusions
    WHERE date IS NOT NULL
    GROUP BY strftime('%w', date)
    ORDER BY CAST(strftime('%w', date) AS INTEGER)
""").fetchall())

# Artistes récurrents
data['recurrents'] = rows_to_list(c.execute("""
    SELECT artistes, COUNT(DISTINCT date) AS nb_jours,
           COUNT(*) AS nb_diffusions,
           ROUND(SUM(duree)/60.0, 1) AS minutes
    FROM diffusions
    WHERE artistes IS NOT NULL AND artistes != ''
    GROUP BY artistes
    HAVING nb_jours >= 2
    ORDER BY nb_jours DESC, nb_diffusions DESC
    LIMIT 20
""").fetchall())

# Titres récurrents
data['titres_recurrents'] = rows_to_list(c.execute("""
    SELECT artistes, titre, COUNT(DISTINCT date) AS nb_jours,
           COUNT(*) AS nb_diffusions
    FROM diffusions
    WHERE artistes IS NOT NULL AND artistes != ''
    GROUP BY artistes, titre
    HAVING nb_jours >= 2
    ORDER BY nb_jours DESC, nb_diffusions DESC
    LIMIT 20
""").fetchall())

# Artistes diversifiés
data['diversifies'] = rows_to_list(c.execute("""
    SELECT artistes, COUNT(DISTINCT titre) AS nb_titres_differents,
           COUNT(*) AS nb_diffusions
    FROM diffusions
    WHERE artistes IS NOT NULL AND artistes != ''
    GROUP BY artistes
    HAVING nb_titres_differents >= 2
    ORDER BY nb_titres_differents DESC, nb_diffusions DESC
    LIMIT 20
""").fetchall())

# Émissions
data['emissions'] = rows_to_list(c.execute("""
    SELECT titre, animateurs, COUNT(*) AS nb_passages
    FROM emissions
    GROUP BY titre, animateurs
    ORDER BY nb_passages DESC
    LIMIT 20
""").fetchall())

# Années
data['annees'] = rows_to_list(c.execute("""
    SELECT annee, COUNT(*) AS nb_diffusions
    FROM diffusions
    WHERE annee IS NOT NULL
    GROUP BY annee
    ORDER BY annee DESC
""").fetchall())

# Explicit
data['explicit'] = rows_to_list(c.execute("""
    SELECT
        CASE explicit_lyrics
            WHEN 1 THEN 'Explicit'
            WHEN 0 THEN 'Clean'
            ELSE 'Inconnu'
        END AS type_contenu,
        COUNT(*) AS nb
    FROM diffusions
    WHERE explicit_lyrics IS NOT NULL
    GROUP BY explicit_lyrics
""").fetchall())

# Top albums
data['albums'] = rows_to_list(c.execute("""
    SELECT album, artistes, COUNT(*) AS nb_diffusions
    FROM diffusions
    WHERE album IS NOT NULL AND album != ''
    GROUP BY album
    ORDER BY nb_diffusions DESC
    LIMIT 20
""").fetchall())

# Dernier morceau
dernier = c.execute("""
    SELECT titre, artistes, cover_deezer, cover_uri, preview_mp3,
           date, heure, album, annee, start_ts, end_ts
    FROM diffusions
    ORDER BY start_ts DESC
    LIMIT 1
""").fetchone()
data['dernier_morceau'] = dict(dernier) if dernier else {}

# Derniers 10 morceaux (pour la modale "en direct")
data['derniers_morceaux'] = rows_to_list(c.execute("""
    SELECT titre, artistes, cover_deezer, cover_uri, preview_mp3,
           date, heure, album, annee, start_ts, end_ts
    FROM diffusions
    ORDER BY start_ts DESC
    LIMIT 10
""").fetchall())

conn.close()

with open(SORTIE, 'w', encoding='utf-8') as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

print(f"✅ Export JSON : {SORTIE}")
print(f"   - {data['volume'].get('nb_diffusions', 0)} diffusions")
print(f"   - {data['volume'].get('nb_artistes', 0)} artistes")
print(f"   - {data['volume'].get('nb_titres', 0)} titres")

