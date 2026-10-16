# Veille des avis stores

Récupère les avis publics de l'App Store et de Google Play (sans accès propriétaire), les analyse (par mots-clés
et par note, ou avec Claude si une clé API est fournie) et envoie :

- un **email chaque matin à 9 h** (heure de Paris) sur l'activité de la veille ;
- des **alertes par email** quand un seuil est franchi (volume, note, sujet, gravité).

Chaque matin, les 14 derniers jours sont revérifiés pour rattraper les avis arrivés en retard.
Une configuration par événement : `config/tour-de-france.yml` (copier pour le Dakar ou la Vuelta).

## Mise en route

1. Dans **Settings → Secrets and variables → Actions**, ajouter :

   | Secret | Contenu |
   |---|---|
   | `ANTHROPIC_API_KEY` | **facultatif** : clé API Claude (payante). Sans elle, l'analyse se fait par mots-clés et par note, gratuitement |
   | `SMTP_HOST`, `SMTP_PORT` | serveur d'envoi (ex. `smtp.gmail.com`, `587`) |
   | `SMTP_USER`, `SMTP_PASSWORD` | identifiants de la boîte d'envoi (mot de passe d'application) |
   | `MAIL_FROM` | adresse expéditrice (optionnel, sinon `SMTP_USER`) |

2. **Actions → Rapport quotidien → Run workflow** : renseigner un destinataire de test. Le premier lancement
   collecte l'historique récent (il sert de base, il n'est pas compté comme « nouveau »).
3. Pour activer l'envoi automatique, renseigner `active_from` et `active_to` dans le fichier de config.

## Tester sans rien envoyer ni accéder au réseau

```bash
pip install -r requirements.txt
python -m avis_watch.main daily --demo --dry-run --no-llm --data-dir .demo-data
python -m avis_watch.main alert --demo --dry-run --no-llm --data-dir .demo-data
```

Les emails sont écrits dans `out/`.

## Rejeu d'une journée passée (test avec de vraies données)

Dans **Actions → Rapport quotidien → Run workflow**, renseigner `as_of` (ex. `2026-07-05T09:00`) : le rapport est
calculé comme si on était à cette date (les avis publiés après sont ignorés). Les données de rejeu sont
stockées à part, dans `data-replay/`. Pour enchaîner deux jours, lancer d'abord le 05/07 puis le 06/07.
Les logs indiquent, pour chaque pays, combien d'avis ont été retrouvés et jusqu'à quelle date.

## Limites connues

- Sources publiques : Apple (flux RSS, environ 500 avis récents par pays) et Play Store (par pays et langue).
  Une source qui ne répond pas est signalée en bas de l'email plutôt que passée sous silence.
- Les avis n'apparaissent pas toujours immédiatement dans les stores : d'où la revérification quotidienne.
- Les notes sans commentaire ne sont pas visibles dans les flux publics.

## Coût

Gratuit avec : GitHub Actions (dépôt privé : 2 000 minutes par mois offertes), une adresse Gmail dédiée,
les flux publics des stores. Seule l'analyse par Claude (clé API) est payante, et elle est facultative.
