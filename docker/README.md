# Docker & Déploiement Google Cloud Run

## Structure du dossier

```
docker/
├── .env.example          # Variables d'environnement (template)
├── .env                  # Variables d'environnement (créé par vous, ignoré par git)
├── Dockerfile            # Image Docker multi-stage
├── docker-compose.yml    # Pour tester localement
├── deploy-cloudrun.ps1   # Script de déploiement Cloud Run (PowerShell)
└── README.md             # Ce fichier
```

---

## 1. Tester localement avec Docker

### Prérequis
- [Docker Desktop](https://www.docker.com/products/docker-desktop/) installé

### Étapes

```powershell
# Depuis la racine du projet
cd c:\Users\kjjdfianko\Documents\APPLICATION\med_search_app

# Copier et adapter le fichier d'environnement
cp docker/.env.example docker/.env
# Éditer docker/.env avec vos valeurs

# Construire et lancer
docker compose -f docker/docker-compose.yml up --build
```

L'application est accessible sur **http://localhost:8080**

Pour arrêter :
```powershell
docker compose -f docker/docker-compose.yml down
```

---

## 2. Déployer sur Google Cloud Run

### Prérequis
1. Un compte Google Cloud avec un projet actif
2. [Google Cloud SDK (gcloud)](https://cloud.google.com/sdk/docs/install) installé
3. Facturation activée sur le projet GCP

### Déploiement en une commande

```powershell
# Depuis la racine du projet
.\docker\deploy-cloudrun.ps1 -ProjectId "votre-projet-gcp"
```

### Options du script

| Paramètre       | Défaut           | Description                          |
|------------------|------------------|--------------------------------------|
| `-ProjectId`     | *(obligatoire)*  | ID du projet Google Cloud            |
| `-Region`        | `europe-west1`   | Région de déploiement                |
| `-ServiceName`   | `medsearch`      | Nom du service Cloud Run             |
| `-MaxInstances`  | `3`              | Nombre max d'instances               |
| `-Memory`        | `512`            | Mémoire par instance (Mi)            |
| `-Cpu`           | `1`              | vCPUs par instance                   |
| `-Timeout`       | `300`            | Timeout des requêtes (secondes)      |
| `-SecretKey`     | *(auto-généré)*  | Django SECRET_KEY                    |

### Exemple complet

```powershell
.\docker\deploy-cloudrun.ps1 `
    -ProjectId "chu-medsearch-2025" `
    -Region "europe-west1" `
    -ServiceName "medsearch" `
    -MaxInstances 5 `
    -Memory 1024
```

### Après le déploiement

Le script affiche l'URL du service (ex: `https://medsearch-xxxxx-ew.a.run.app`).

**Important** — Mettre à jour `CSRF_TRUSTED_ORIGINS` :
```powershell
gcloud run services update medsearch `
    --region europe-west1 `
    --update-env-vars "CSRF_TRUSTED_ORIGINS=https://medsearch-xxxxx-ew.a.run.app"
```

---

## 3. Gérer le déploiement

### Voir les logs
```powershell
gcloud run services logs read medsearch --region europe-west1 --limit 50
```

### Mettre à jour une variable d'environnement
```powershell
gcloud run services update medsearch `
    --region europe-west1 `
    --update-env-vars "DEBUG=false,RATELIMIT_RATE=500/h"
```

### Supprimer le service (arrêter les coûts)
```powershell
gcloud run services delete medsearch --region europe-west1 --quiet
```

### Redéployer après des changements de code
```powershell
.\docker\deploy-cloudrun.ps1 -ProjectId "votre-projet-gcp"
```

---

## 4. Notes importantes

### Base de données
- Par défaut, **SQLite** est utilisé. Sur Cloud Run, la base est **éphémère** (perdue à chaque redéploiement/redémarrage).
- Pour des données persistantes, utiliser **Cloud SQL (PostgreSQL)** :
  1. Créer une instance Cloud SQL
  2. Ajouter la variable `DATABASE_URL` au service Cloud Run
  3. Connecter via le [Cloud SQL Auth Proxy](https://cloud.google.com/sql/docs/postgres/connect-run)

### Cache
- En mode `DEBUG=true` : cache local en mémoire
- En mode `DEBUG=false` sans Redis : le cache Django par défaut est utilisé
- Pour Redis : déployer [Memorystore](https://cloud.google.com/memorystore) et configurer `REDIS_URL`

### Coûts estimés (Cloud Run)
- Cloud Run facture **uniquement quand le service traite des requêtes**
- Avec le free tier : ~2 millions de requêtes/mois gratuites
- Pour un test temporaire avec peu de trafic : **quasi-gratuit**

### Sécurité
- Toujours définir un vrai `DJANGO_SECRET_KEY` (le script en génère un automatiquement)
- Garder `DEBUG=false` en production
- Limiter `ALLOWED_HOSTS` au domaine Cloud Run si possible
