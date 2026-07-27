# adminnginx

[![forthebadge](https://forthebadge.com/images/badges/docker-container.svg)](https://forthebadge.com)

Interface graphique Django pour administrer un reverse proxy **Nginx + Docker + Let's Encrypt**.

---

## Objectif

adminnginx permet de :

- Visualiser les vhosts Nginx
- Gérer les certificats SSL
- Ajouter / modifier / supprimer des sites Docker
- Partager les médias Django avec Nginx
- Automatiser la configuration HTTP → HTTPS
- Générer automatiquement les certificats Let's Encrypt
- Lancer des diagnostics réseau (DNS / HTTP / HTTPS / SSL)
- Suivre les opérations en temps réel

---

## Prérequis

### Serveur

- Linux (Debian recommandé)
- Accès SSH
- Docker + Docker Compose installés

---

## Reverse proxy Nginx (OBLIGATOIRE)

`adminnginx` dépend d’un reverse proxy Nginx externe.

👉 Ce proxy doit être installé **avant** et est disponible ici :  
➡️ https://github.com/seah78/nginx_proxy

---

### 📦 Installation du proxy

Le chemin `/opt/nginx_proxy` est obligatoire avec la configuration fournie :
`adminnginx` utilise explicitement ce chemin pour les bind mounts Docker et
les opérations Certbot.

```bash
cd /opt
git clone https://github.com/seah78/nginx_proxy.git
cd /opt/nginx_proxy
docker compose up -d
```

---

### 📁 Structure attendue

Le projet doit être installé dans :

```text
/opt/nginx_proxy/
├── docker-compose.yml
├── nginx-config/
├── letsencrypt/
└── html/
```

Les vhosts placés dans `nginx-config` doivent obligatoirement se terminer par
`.conf`, par exemple :

```text
/opt/nginx_proxy/nginx-config/admin.example.com.conf
```

---

### Rôle du proxy

Ce proxy est utilisé par `adminnginx` pour :

- héberger les fichiers vhost (`nginx-config`)
- gérer les certificats SSL (`letsencrypt`)
- répondre aux challenges Let's Encrypt (`html`)
- router les requêtes vers les conteneurs Docker

---

### Important

- Les volumes doivent être accessibles par `adminnginx`
- Le réseau Docker (`internal_network`) doit être partagé
- Le conteneur doit s’appeler **nginx_proxy**
- Le volume Docker externe `webapps_media` doit exister
- Les commandes Certbot manuelles doivent utiliser les chemins absolus
  `/opt/nginx_proxy/letsencrypt` et `/opt/nginx_proxy/html`

Le proxy doit monter ce volume en lecture seule :

```yaml
services:
  nginx:
    volumes:
      - webapps_media:/srv/webapps-media:ro

volumes:
  webapps_media:
    external: true
```

---

## Installation de adminnginx

### 1. Cloner le projet

```bash
cd /opt
git clone https://github.com/seah78/adminnginx.git
cd adminnginx
```

---

### 2. Créer le fichier .env

Générer une clé secrète Django aléatoire :

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(64))"
```

Copier la valeur obtenue dans `DJANGO_SECRET_KEY`, puis créer le fichier
`.env` :

```env
DJANGO_SECRET_KEY=coller-ici-la-cle-generee
DJANGO_DEBUG=False
DJANGO_ALLOWED_HOSTS=adminnginx.mondomaine.com
CSRF_TRUSTED_ORIGINS=https://adminnginx.mondomaine.com

ADMINNGINX_NGINX_CONTAINER=nginx_proxy
ADMINNGINX_NGINX_CONFIG_DIR=/nginx-config
ADMINNGINX_HOST_OPT_DIR=/host/opt
ADMINNGINX_LETSENCRYPT_DIR=/letsencrypt
ADMINNGINX_OPERATIONS_DIR=/app/data/operations
ADMINNGINX_APPLICATION_START_TIMEOUT=30
ADMINNGINX_DEPLOYMENT_NAME=production-serveur-1
```

---

### 3. Lancer

```bash
docker compose -f docker-compose.prod.yml up -d
```

---

### 4. Collect static

```bash
docker exec adminnginx python manage.py collectstatic --noinput
```

---

### 5. Créer un superuser

```bash
docker exec -it adminnginx python manage.py createsuperuser
```

---

## Provisionnement d'un projet

Lors de l'ajout d'un domaine, `adminnginx` effectue désormais les contrôles
suivants avant de créer le vhost Nginx :

1. création du dossier `/opt/<projet>` et du fichier
   `docker-compose.prod.yml` ;
2. exécution de `docker compose up -d --pull always` sur ce fichier ;
3. téléchargement de l'image GHCR et démarrage du conteneur applicatif ;
4. connexion au réseau externe `internal_network` ;
5. vérification que le conteneur reste actif ;
6. vérification que le port interne saisi répond depuis `adminnginx` ;
7. création et validation du vhost Nginx ;
8. création du certificat puis activation HTTPS.

En cas d'échec, l'écran de progression indique l'image, le conteneur, le
réseau ou le port concerné et affiche les 50 dernières lignes de logs lorsque
le conteneur s'arrête ou ne répond pas.

Les erreurs Docker Compose courantes sont traduites en messages dédiés :

- accès GHCR refusé (`denied` ou `unauthorized`) : image non encore publiée,
  package privé ou authentification `read:packages` absente ;
- image ou tag `latest` introuvable ;
- réseau externe `internal_network` absent ;
- volume externe `webapps_media` absent ;
- nom de conteneur déjà utilisé.

Une erreur de téléchargement ou de démarrage interrompt le provisionnement
avant la création du vhost. Elle ne doit donc pas rendre la configuration
globale de Nginx invalide.

Le délai d'attente du port applicatif est de 30 secondes par défaut. Il peut
être modifié dans `.env` :

```env
ADMINNGINX_APPLICATION_START_TIMEOUT=60
```

Pour une image GHCR privée, le moteur Docker utilisé par `adminnginx` doit
disposer des autorisations nécessaires pour télécharger l'image.

---

## Version déployée

Chaque build GitHub Actions publie trois tags pour la même image :

```text
latest
build-<numero-du-run>
sha-<commit-git-complet>
```

Le déploiement utilise le tag immuable `sha-<commit>` plutôt que `latest`.
Le checkout de `/opt/adminnginx` est également placé sur ce commit avant
l'exécution du Compose. Après le redémarrage, GitHub Actions compare le label OCI
`org.opencontainers.image.revision` du conteneur avec le commit attendu. Le
job échoue si les deux valeurs diffèrent.

La version est visible en bas de l'identité visuelle dans l'interface et via
un endpoint public non mis en cache :

```bash
curl https://adminnginx.mondomaine.com/version/
```

Exemple :

```json
{
  "version": "build-42",
  "git_sha": "abcdef1234567890",
  "short_sha": "abcdef123456",
  "build_date": "2026-07-27T12:00:00Z",
  "build_run": "123456789",
  "deployment": "production-serveur-1"
}
```

La variable suivante doit être différente sur chaque serveur :

```env
# Premier serveur
ADMINNGINX_DEPLOYMENT_NAME=production-serveur-1

# Second serveur
ADMINNGINX_DEPLOYMENT_NAME=production-serveur-2
```

Vérification directe sur un serveur :

```bash
docker inspect adminnginx \
  --format 'Version={{ index .Config.Labels "org.opencontainers.image.version" }} SHA={{ index .Config.Labels "org.opencontainers.image.revision" }} Image={{ .Config.Image }}'
```

Pour déployer automatiquement sur deux serveurs, créer deux environnements
GitHub, par exemple `production-serveur-1` et `production-serveur-2`, avec les
mêmes noms de secrets (`SERVER_HOST`, `SERVER_USER`, `SERVER_PORT` et
`SERVER_SSH_KEY`). Les environnements GitHub conservent un historique séparé
des déploiements et peuvent appliquer leurs propres protections.

Le workflow fourni déploie le serveur référencé par les secrets `SERVER_*`.
Pour deux serveurs, utiliser deux jobs associés à leurs environnements
respectifs ou une matrice de déploiement.

---

## Sécurité

### Double authentification (2FA)

Admin Nginx permet d’activer une double authentification (TOTP) pour sécuriser l’accès au panel.

Après la première connexion :

1. Accéder à la page **Sécurité**
2. Cliquer sur **Activer la double authentification**
3. Scanner le QR code avec une application compatible :
   - Google Authenticator
   - Microsoft Authenticator
   - Authy
4. Valider avec le code à 6 chiffres

Une fois activée :

- Un code sera demandé à chaque connexion
- L’accès au dashboard est bloqué tant que la vérification n’est pas validée

---

### Désactivation

La désactivation nécessite la saisie d’un code valide.

---

### Procédure de secours

En cas de perte de l’application 2FA, il est possible de désactiver la protection depuis le serveur :

```bash
docker exec -it adminnginx python manage.py shell
```

Puis :

```bash
from django_otp.plugins.otp_totp.models import TOTPDevice
TOTPDevice.objects.all().delete()
```

## Notes

- nginx_proxy est obligatoire
- Vérifier les volumes
- Vérifier les permissions /opt

## Médias Django

Lors de la création d’un site, l’option **Partager le dossier media avec
Nginx** est activée par défaut. Elle :

- monte le volume externe `webapps_media` dans `/app/media` dans le conteneur
  applicatif ;
- ajoute un bloc Nginx `location /media/` servi depuis
  `/srv/webapps-media/`.

Le projet Django déployé doit utiliser les réglages suivants :

```python
MEDIA_URL = "/media/"
MEDIA_ROOT = "/app/media"
```

Créer le volume avant le premier déploiement s’il n’existe pas :

```bash
docker volume create webapps_media
```

Si un dossier bind-mounté comme `html`, `letsencrypt` ou `nginx-config` est
supprimé puis recréé pendant que les conteneurs fonctionnent, il faut recréer
les conteneurs pour reconstruire les montages :

```bash
cd /opt/nginx_proxy
docker compose down
docker compose up -d
```

---

# Auteur

[![forthebadge](https://forthebadge.com/images/badges/built-by-developers.svg)](https://forthebadge.com)

**Sébastien HERLANT**
