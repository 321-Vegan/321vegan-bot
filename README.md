# Bot Discord de validation produit 321Vegan

MVP de la commande
`/valider-produit ean:<EAN> resultat:<vegan|non-vegan> capture:<fichier> [raison:<choix>]`.
Le bot agit comme un contributeur normal
via les routes existantes de l’API 321Vegan :

- `POST /auth/login`
- `GET /products/ean/{ean}`
- `PUT /products/{id}`

Il ne possède ni accès PostgreSQL, ni clé `ApiClient`, ni compte administrateur.
Les messages publics du salon `réponses-marques` constituent l’historique des
validations.

## Fonctionnement et sécurité

La commande est autorisée uniquement dans le salon `1350813080476581918` et
pour les membres possédant le rôle `1350810248256159805`. Les contrôles utilisent
exclusivement les IDs Discord.

Après l’aperçu, le bot publie une confirmation avec **Confirmer** et **Annuler**.
Seule la personne ayant lancé la commande peut agir. Avant toute modification,
le bot désactive les boutons, affiche « validation en cours », recharge le
produit et compare `status`, `state` et `updated_at`. Si l’un de ces champs a
changé — ou si `problem_description` a changé — aucun PUT n’est envoyé.

L’option `capture` est une pièce jointe Discord obligatoire qui rappelle à la
personne contributrice d’inclure la capture d’écran de la réponse de la marque.
Le message de confirmation affiche cette capture directement depuis son URL CDN
Discord. Le bot ne télécharge pas, n’inspecte pas, ne stocke pas et ne transmet
pas le fichier à l’API. L’image reste visible dans le même message lorsque celui-ci
devient le journal final de la validation.

L’option `raison` est requise par le bot lorsque le résultat est `non-vegan` et
refusée lorsque le résultat est `vegan`. Discord ne permet pas de masquer
conditionnellement une option de commande : elle reste donc visible mais facultative
dans le formulaire. Les choix autorisés sont :

- `ARÔMES`
- `ARÔMES NATURELS`
- `VITAMINE D`
- `CLARIFIÉ AVEC DES PRODUITS D'ORIGINE ANIMALE`

Pour une validation `non-vegan`, le PUT contient uniquement :

```json
{
  "ean": "0123456789012",
  "status": "NON_VEGAN",
  "state": "WAITING_PUBLISH",
  "problem_description": "ARÔMES (réponse de la marque)"
}
```

La valeur sélectionnée remplace `problem_description`. Pour une validation
`vegan`, le champ `problem_description` est omis du PUT et reste donc inchangé.

Un produit déjà dans le statut demandé et dans `WAITING_PUBLISH` ne déclenche
pas de PUT inutile si sa raison non végane correspond aussi, le cas échéant.
Une raison différente est remplacée. Si seul le statut correspond, le bot peut
encore déplacer le produit vers `WAITING_PUBLISH`.

Les **Checkings ne sont volontairement pas modifiés dans ce MVP**. Leur
traitement sera évalué séparément. Aucun historique ou undo automatisé n’est
créé.

## Compte contributeur dédié

Créer, via l’outil d’administration habituel, un compte 321Vegan réservé au bot :

1. utiliser une adresse e-mail technique contrôlée par l’équipe ;
2. attribuer exactement le rôle `contributor` ;
3. activer le compte ;
4. générer un mot de passe long et unique ;
5. stocker le mot de passe dans le gestionnaire de secrets du déploiement.

Ne pas réutiliser les identifiants personnels d’un membre de l’équipe : les
actions deviendraient impossibles à distinguer et le départ de cette personne
pourrait casser le bot. Ne pas utiliser un compte administrateur : le bot n’a
besoin que des droits normaux de contribution et une compromission aurait sinon
un impact inutilement large.

## Installation locale

Prérequis : Python 3.11 ou plus récent.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
cp .env.example .env
```

Configurer `.env` sans jamais le committer :

```dotenv
DISCORD_BOT_TOKEN=
DISCORD_APPLICATION_ID=
DISCORD_GUILD_ID=
DISCORD_REQUIRED_ROLE_ID=1350810248256159805
DISCORD_ALLOWED_CHANNEL_ID=1350813080476581918
DISCORD_SYNC_COMMANDS=false

VEGAN_API_BASE_URL=https://api.example.invalid
VEGAN_API_EMAIL=discord-bot@example.invalid
VEGAN_API_PASSWORD=
```

Puis lancer :

```bash
python -m vegan_discord_bot
```

Le jeton d’accès API est obtenu par formulaire OAuth2, conservé uniquement en
mémoire et renouvelé une seule fois après un HTTP 401. Le mot de passe et les
jetons ne sont jamais journalisés.

## Discord Developer Portal

1. Créer une application et son bot dans le
   [Developer Portal](https://discord.com/developers/applications).
2. Copier l’Application ID et conserver le token Discord dans un gestionnaire de
   secrets.
3. Dans **OAuth2 > URL Generator**, sélectionner `bot` et
   `applications.commands`.
4. Accorder au minimum **View Channel**, **Send Messages**, **Read Message
   History** et **Use Application Commands** dans `réponses-marques`.
5. Activer le mode développeur Discord et vérifier les IDs du salon, du rôle et
   de la guilde.

Aucun intent **Message Content** n’est nécessaire : ce MVP ne parse pas les
messages libres.

### Synchronisation dans une guilde de développement

Définir `DISCORD_GUILD_ID`, passer temporairement
`DISCORD_SYNC_COMMANDS=true`, lancer le bot une fois, puis remettre la variable à
`false`. Les commandes de guilde apparaissent rapidement.

### Enregistrement en production

Après validation dans une guilde de développement, laisser `DISCORD_GUILD_ID`
vide et lancer explicitement une fois avec `DISCORD_SYNC_COMMANDS=true`. Remettre
ensuite la variable à `false`. La propagation d’une commande globale peut
prendre du temps. Cette procédure n’est pas exécutée automatiquement pendant les
tests ou la construction de l’image.

## Rotation des secrets

Mot de passe du compte 321Vegan :

1. modifier le mot de passe via le flux sécurisé existant ;
2. mettre à jour `VEGAN_API_PASSWORD` dans le gestionnaire de secrets ;
3. redémarrer le bot ;
4. révoquer toute ancienne valeur encore stockée ailleurs.

Token Discord :

1. régénérer le token dans le Developer Portal ;
2. mettre à jour `DISCORD_BOT_TOKEN` dans le gestionnaire de secrets ;
3. redémarrer le bot immédiatement ;
4. vérifier que l’ancien token ne fonctionne plus.

## Tests

```bash
pytest
```

Les tests utilisent des transports HTTP et interactions Discord simulés. Ils ne
contactent pas l’API réelle et ne modifient aucune donnée.

## Docker

Le bot n’écoute sur aucun port entrant. Il ouvre uniquement des connexions
sortantes vers Discord et l’API 321Vegan.

### Construction et lancement direct

```bash
docker build -t 321vegan-discord-bot .
docker run --rm --env-file .env 321vegan-discord-bot
```

### Lancement avec Docker Compose

Créer le fichier `.env`, puis lancer le service en arrière-plan :

```bash
cp .env.example .env
chmod 600 .env
docker compose up -d --build
docker compose logs -f bot
```

Les mêmes opérations sont disponibles via le `Makefile` :

```bash
make up
make logs
make ps
make restart
make down
```

Le service redémarre automatiquement après un crash ou un redémarrage du VPS.
Le conteneur utilise un utilisateur non privilégié, un système de fichiers en
lecture seule, un `/tmp` temporaire et des journaux Docker limités en taille.

Commandes d’exploitation courantes :

```bash
docker compose ps
docker compose restart bot
docker compose logs --tail=100 bot
docker compose down
```

### Adresse de l’API depuis le conteneur

`localhost` dans `.env` désigne le conteneur du bot, pas le VPS. Configurer
`VEGAN_API_BASE_URL` selon le déploiement :

- URL HTTPS publique : `https://api.example.com`
- API publiée sur le port 8000 du VPS : `http://host.docker.internal:8000`
- API sur le même réseau Docker : utiliser son nom de service, par exemple
  `http://321veganapi:8000`, et rattacher les deux services au même réseau

Le mapping `host.docker.internal:host-gateway` de `compose.yaml` rend la deuxième
option compatible avec un hôte Linux.

### Déploiement et mises à jour sur le VPS

Après avoir copié ou cloné le projet sur le VPS et créé son `.env` :

```bash
docker compose up -d --build
```

Pour publier une nouvelle version du code :

```bash
git pull
docker compose up -d --build
```

Ne jamais copier `.env` dans l’image ni le committer. Pour synchroniser une
nouvelle version de la commande Discord :

```bash
make sync
make up
```

`make sync` force la synchronisation pour cette exécution uniquement, puis le
conteneur temporaire s’arrête. Il ne modifie pas `.env` : `DISCORD_SYNC_COMMANDS`
peut rester à `false`. Si `DISCORD_GUILD_ID` est renseigné, la commande est
synchronisée uniquement dans cette guilde de développement ; s’il est vide, la
commande globale est synchronisée.

L’image s’exécute avec un utilisateur non privilégié. Aucun compte, déploiement,
enregistrement de commande ou changement de données de production n’est créé par
ce projet.
