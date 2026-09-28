<div align="center">

# 📻 Skyrock Monitor

**Collecteur & Dashboard de la programmation musicale de Skyrock**

[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![SQLite](https://img.shields.io/badge/SQLite-003B57?style=for-the-badge&logo=sqlite&logoColor=white)](https://sqlite.org/)
[![Plotly](https://img.shields.io/badge/Plotly-3F4F75?style=for-the-badge&logo=plotly&logoColor=white)](https://plotly.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=for-the-badge)](https://opensource.org/licenses/MIT)
[![Made with ❤️](https://img.shields.io/badge/Made%20with-%E2%9D%A4%EF%B8%8F-red?style=for-the-badge)](https://github.com/gunout)
[![Maintained](https://img.shields.io/badge/Maintained-yes-success?style=for-the-badge)](https://github.com/gunout/skyrock-monitor)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg?style=for-the-badge)](https://github.com/gunout/skyrock-monitor/pulls)

---

*Collecte en continu · Enrichissement Deezer · Dashboard interactif · Analyse complète*

</div>

---

## 📖 Table des matières

- [Aperçu](#-aperçu)
- [Fonctionnalités](#-fonctionnalités)
- [Architecture](#️-architecture)
- [Installation](#-installation)
- [Utilisation](#-utilisation)
- [Automatisation](#-automatisation)
- [Sources de données](#-sources-de-données)
- [Contribuer](#-contribuer)
- [Licence](#-licence)

---

## 🎯 Aperçu

<img width="1683" height="3008" alt="Screenshot 2026-09-29 at 03-01-24 Skyrock — Monitor" src="https://github.com/user-attachments/assets/0309c29d-113c-4ab0-a2c4-dd5ff6913228" />




**Skyrock Monitor** est un pipeline complet qui :

1. **Collecte** en temps réel les morceaux diffusés sur Skyrock via l'API non officielle du site
2. **Enrichit** automatiquement chaque morceau (artiste, album, année, pochette, extrait audio) via l'API publique Deezer
3. **Analyse** les données pour produire 19 fichiers CSV (tops, répartitions, statistiques)
4. **Affiche** le tout dans un dashboard HTML futuriste avec graphiques interactifs Plotly

Idéal pour suivre les tendances musicales, analyser la rotation des titres, ou simplement découvrir ce qui passe sur Skyrock.

---

## ✨ Fonctionnalités

### 🎧 Collecte & Enrichissement

- [x] Interrogation automatique de l'API Skyrock toutes les 2 minutes
- [x] Stockage incrémental dans une base SQLite
- [x] Détection automatique des nouveaux morceaux (pas de doublons)
- [x] Enrichissement Deezer : artiste, album, année, pochette, extrait 30s
- [x] Filtre de similarité de titre (score de correspondance)
- [x] Filtre de popularité (rank Deezer supérieur à 0)
- [x] Calcul de la durée de diffusion (start_ts / end_ts)
- [x] Distinction musique / parole

### 📊 Analyses (19 CSV)

- [x] Volume global (diffusions, artistes, titres, heures)
- [x] Top artistes (temps d'antenne)
- [x] Top titres (nombre de diffusions)
- [x] Répartition horaire (24h)
- [x] Répartition journalière (évolution par date)
- [x] Top artiste par heure
- [x] Artistes récurrents (multi-jours)
- [x] Titres récurrents (multi-jours)
- [x] Durée moyenne par titre
- [x] Répartition par jour de la semaine
- [x] Émissions diffusées
- [x] Top likes Skyrock
- [x] Répartition par année de sortie
- [x] Ratio Clean / Explicit
- [x] Top albums
- [x] Dernier morceau (bandeau On Air)

### 🎨 Dashboard

- [x] Design futuriste (glassmorphism, néons, animations)
- [x] Bandeau **On Air** avec pochette et compteur temps réel
- [x] Auto-refresh toutes les 60 secondes
- [x] Graphiques interactifs Plotly
- [x] Tableaux cliquables (modale artiste)
- [x] Responsive (mobile / desktop)

---

## 🏗️ Architecture

| Fichier | Rôle |
|---------|------|
| collecteur.py | Collecte + enrichissement en boucle |
| enrichir.py | Module d'enrichissement Deezer (importé) |
| analyser.py | Génère les 19 CSV dans resultats/ |
| dashboard.html | Dashboard interactif Plotly |
| skyrock.db | Base SQLite (non versionnée) |
| resultats/ | CSV générés (non versionnés) |

**Flux de données :**

1. L'API Skyrock est interrogée toutes les 2 minutes
2. Les nouveaux morceaux sont insérés dans skyrock.db
3. enrichir.py complète les métadonnées via Deezer
4. analyser.py produit 19 CSV dans resultats/
5. dashboard.html lit les CSV et affiche les graphiques

---

## 🚀 Installation

### Prérequis

- Python 3.10 ou supérieur
- pip

### Cloner le dépôt

Ouvrez un terminal et tapez :

`git clone https://github.com/gunout/skyrock-monitor.git`

Puis :

`cd skyrock-monitor`

### Installer les dépendances

`pip install requests pandas`

---

## 🎮 Utilisation

### Étape 1 — Lancer le collecteur

`python3 collecteur.py`

Le collecteur tourne en boucle, interroge l'API toutes les 2 minutes, stocke les nouveaux morceaux, et les enrichit automatiquement.

**Pour le lancer en arrière-plan :**

`nohup python3 collecteur.py > /dev/null 2>&1 &`

### Étape 2 — Générer les analyses

`python3 analyser.py`

Produit 19 CSV dans le dossier `resultats/`.

### Étape 3 — Lancer le dashboard

`python3 -m http.server 8005`

Puis ouvrez dans votre navigateur :

[http://localhost:8005/dashboard.html](http://localhost:8005/dashboard.html)

---

## ⏰ Automatisation

Pour régénérer les analyses automatiquement toutes les heures, éditez votre crontab avec :

`crontab -e`

Puis ajoutez la ligne suivante :

`* * * * * cd /chemin/vers/skyrock-monitor && /usr/bin/python3 analyser.py >> analyser.log 2>&1`

---

## 🌐 Sources de données

| Source | Endpoint | Authentification |
|--------|----------|------------------|
| Skyrock | https://skyrock.fm/api/v3/player/onair/parisidf | ❌ Aucune (non officielle) |
| Deezer | https://api.deezer.com/search | ❌ Aucune (publique) |

---

## 🤝 Contribuer

Les contributions sont les bienvenues !

1. Fork le projet
2. Créez une branche : `git checkout -b feature/ma-fonctionnalite`
3. Committez : `git commit -m "feat: ajoute ma fonctionnalité"`
4. Pushez : `git push origin feature/ma-fonctionnalite`
5. Ouvrez une Pull Request

### Convention de commit

- feat: nouvelle fonctionnalité
- fix: correction de bug
- docs: documentation
- chore: tâches diverses

---

## 📄 Licence

Ce projet est sous licence **MIT**. Voir le fichier [LICENSE](LICENSE) pour plus de détails.

---

## ⚠️ Avertissement

- L'API Skyrock utilisée n'est **pas officielle** et peut changer sans préavis.
- Ce projet est destiné à un **usage personnel et éducatif**.
- Les données musicales collectées restent la propriété de leurs ayants droit respectifs.
- L'auteur n'est pas affilié à Skyrock ni à Deezer.

---

<div align="center">

**⭐ Si ce projet vous plaît, mettez-lui une étoile ! ⭐**

[🔝 Retour en haut](#-skyrock-monitor)

</div>

---

<div align="center">

### 🇫🇷 Gunout · 2026

![Made in France](https://img.shields.io/badge/Made_in-France-002395?style=flat-square&labelColor=FFFFFF&logo=data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCA5MDAgNjAwIj48cmVjdCB3aWR0aD0iOTAwIiBoZWlnaHQ9IjYwMCIgZmlsbD0iIzAwMjM5NSIvPjxyZWN0IHdpZHRoPSI5MDAiIGhlaWdodD0iNDAwIiB5PSIxMDAiIGZpbGw9IiNmZmYiLz48cmVjdCB3aWR0aD0iOTAwIiBoZWlnaHQ9IjIwMCIgeT0iNDAwIiBmaWxsPSIjZWQyOTM5Ii8+PC9zdmc+)
![GitHub](https://img.shields.io/badge/GitHub-gunout-181717?style=flat-square&logo=github&logoColor=white)
![Year](https://img.shields.io/badge/2026-ED2939?style=flat-square&labelColor=FFFFFF)

<sub>© 2026 <strong>Gunout</strong> — Tous droits réservés.</sub>

</div>
