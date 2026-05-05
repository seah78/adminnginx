# adminnginx

[![forthebadge](/badges/docker-container.svg)](https://forthebadge.com)


Interface graphique Django pour administrer un reverse proxy **Nginx + Docker + Let's Encrypt**.

---

## Objectif

adminnginx permet de :

- Visualiser les vhosts Nginx
- Gérer les certificats SSL
- Ajouter / modifier / supprimer des sites Docker
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

```bash
cd /opt
git clone https://github.com/seah78/nginx_proxy.git
cd nginx_proxy
docker compose up -d
```

---

### 📁 Structure attendue

Le projet doit être installé dans :

/opt/nginx_proxy/
├── docker-compose.yml
├── nginx-config/
├── letsencrypt/
└── html/

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

```env
DJANGO_SECRET_KEY=change-me
DJANGO_DEBUG=False
DJANGO_ALLOWED_HOSTS=adminnginx.mondomaine.com
CSRF_TRUSTED_ORIGINS=https://adminnginx.mondomaine.com

NGINX_PROXY_CONTAINER=nginx_proxy
NGINX_CONFIG_PATH=/nginx-config
NGINX_HTML_PATH=/nginx-html
LETSENCRYPT_PATH=/letsencrypt
```

---

### 3. Lancer

```bash
docker compose up -d
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


---

# Auteur

[![forthebadge](https://forthebadge.com/images/badges/built-by-developers.svg)](https://forthebadge.com)

**Sébastien HERLANT**
