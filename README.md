# 3 choses positives

Application web responsive pour noter chaque jour 3 choses positives, avec stockage dans PostgreSQL.

- authentification utilisateur (session cookie)
- calendrier mensuel des jours complets
- rappels quotidiens configurables

## Stack technique

- Frontend: HTML/CSS/JS (dans `public/`)
- Backend: Python 3 + Flask + Gunicorn
- Base de donnees: PostgreSQL 16
- Deploiement: Docker Compose

## Structure

- `app.py`: point d'entree de l'application
- `positives/app_factory.py`: routes Flask et composition de l'app
- `positives/repository.py`: acces PostgreSQL
- `positives/validation.py`: validation et parsing des entrees
- `positives/types.py`: types partages (contrat repository)
- `requirements.txt`: dependances Python
- `public/`: interface utilisateur
- `docker-compose.yml`: services `app` et `db`
- `.env`: variables d'environnement

## Qualite du code

Outils inclus:

- `pytest`: tests unitaires backend
- `ruff`: linter Python
- `eslint`: linter JavaScript frontend

Installation des dependances :

```bash
python3 -m venv .venv
./.venv/bin/pip install -r requirements-dev.txt
npm install
```

Executer les tests unitaires :

```bash
./.venv/bin/pytest
```

Executer les linters :

```bash
./.venv/bin/ruff check .
npm run lint:js
```

## Lancer en local avec Docker

1. Ouvre un terminal dans ce dossier:
   `/Users/fabien/Documents/Developments/3-positifs-app`
2. Verifie ou adapte `.env` (mot de passe, port)
3. Lance:

```bash
docker compose up -d --build
```

4. Ouvre:
   `http://localhost:8080`

## API disponible

- `GET /api/health`
- `POST /api/auth/register`
- `POST /api/auth/login`
- `POST /api/auth/logout`
- `GET /api/auth/me`
- `GET /api/entries?q=mot&limit=20&offset=0`
- `GET /api/entries/:date` (format date: `YYYY-MM-DD`)
- `PUT /api/entries/:date` avec body JSON: `{ "items": ["...", "...", "..."] }`
- `DELETE /api/entries/:date`
- `GET /api/calendar?month=YYYY-MM`
- `GET /api/reminder`
- `PUT /api/reminder` avec body JSON: `{ "enabled": true|false, "time": "HH:MM" }`

Codes d'erreur REST appliques:
- `400 Bad Request`: JSON invalide
- `401 Unauthorized`: authentification requise / identifiants invalides
- `404 Not Found`: ressource inexistante
- `409 Conflict`: email deja utilise
- `415 Unsupported Media Type`: contenu non JSON sur `PUT`
- `422 Unprocessable Entity`: erreurs de validation (format/date future/payload metier)
- `500 Internal Server Error`: erreur interne non prevue
- `503 Service Unavailable`: service indisponible (ex: healthcheck KO)

`GET /api/entries` retourne:
- `entries`: liste des elements
- `hasMore`: `true` s'il reste des elements a charger
- `nextOffset`: offset pour l'appel suivant (ou `null`)

## Deploiement sur Proxmox (LXC + Docker)

### 1) Creer le conteneur LXC

- Template: Debian 12
- Ressources conseillees:
  - 1 vCPU
  - 1 GB RAM
  - 8 GB disque
- Reseau: bridge local (ex: `vmbr0`) avec IP fixe conseillee
- Option importante: activer `Nesting` (Options > Features)

### 2) Installer Docker dans le LXC

```bash
apt update
apt install -y ca-certificates curl gnupg
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/debian/gpg -o /etc/apt/keyrings/docker.asc
chmod a+r /etc/apt/keyrings/docker.asc
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/debian $(. /etc/os-release && echo $VERSION_CODENAME) stable" > /etc/apt/sources.list.d/docker.list
apt update
apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
systemctl enable docker
systemctl start docker
```

### 3) Copier le projet dans le CT

Depuis ton Mac:

```bash
scp -r /Users/fabien/Documents/Developments/3-positifs-app root@IP_DU_CT:/opt/
```

### 4) Configurer l'environnement dans le CT

```bash
cd /opt/3-positifs-app
cp .env.example .env
nano .env
```

A modifier en priorite:

- `POSTGRES_PASSWORD`
- `APP_PORT` (si 8080 est deja pris)

### 5) Lancer l'app

```bash
docker compose up -d --build
```

### 6) Acces

Depuis le LAN:

`http://IP_DU_CT:8080`

## Persistance et sauvegarde

La base PostgreSQL est persistante via le volume Docker `postgres_data`.

Backup simple:

```bash
docker exec -t three-positives-db pg_dump -U <POSTGRES_USER> <POSTGRES_DB> > backup.sql
```

Restauration:

```bash
cat backup.sql | docker exec -i three-positives-db psql -U <POSTGRES_USER> -d <POSTGRES_DB>
```

## Notes

- Historique stocke en PostgreSQL (centralise pour tous tes appareils).
- Si tu veux une installation mobile PWA plus fiable hors localhost, ajoute HTTPS (Caddy ou Traefik).
