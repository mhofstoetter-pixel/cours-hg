# Cours d'Histoire-Géo-EMC : site public

Ce site reprend les ressources du parcours Éléa (cours, BEX, méthodologie, QCM, enquêtes) pour les élèves qui n'arrivent pas à se connecter. Il ne demande aucun compte et ne contient rien de nominatif.

Adresse prévue : https://mhofstoetter-pixel.github.io/cours-hg/

## Mettre le site à jour après un changement sur Éléa

1. Sur Éléa, dans le parcours : **Sauvegarde**, sans les utilisateurs. Récupérer le fichier `.mbz`.
2. Le donner à Claude dans ce dossier (« mets à jour le site avec cette sauvegarde de 4e »), ou lancer soi-même :

```bash
python3 scripts/build.py ~/Downloads/sauvegarde.mbz --niveau 4e
```

```bash
python3 -I scripts/fetch_docs.py 4e
```

```bash
python3 scripts/build.py --pages
```

3. Lire le rapport affiché : ce qui est publié, ce qui est écarté, et le **contrôle de vie privée**, qui doit finir par « OK ».
4. Publier (Claude le fait sur demande) : envoi du dossier `docs/` sur GitHub.

## Ce qui n'est jamais publié

Réglé dans `scripts/config.json`, rubrique `exclusions` :

- la section « Fichier de suivi » et tout titre contenant « Suivi », « Groupe », « Appel », « Absences » ;
- tout lien vers un tableur Google Sheets ou un formulaire ;
- les étiquettes, devoirs, forums, badges, et tout ce qui est caché sur Éléa ;
- dans les liens Google, l'identifiant du compte (`ouid=…`) ; dans les documents, les commentaires.

Si un document à exclure passe quand même, le contrôle final bloque la construction.

## Les Google Docs

Pour que le site récupère un document et que le bouton « Ouvrir le Google Doc » fonctionne hors ENT, le document doit être partagé en **« Tous les utilisateurs disposant du lien » · Lecteur**. Chaque document donne sur le site une page web, un PDF et le lien.

## Les rubriques et les chapitres

Les sections d'Éléa sont rangées en rubriques d'après leur titre (`rubriques` dans `config.json`). Le code de chapitre (H1, G1…) est lu dans le titre ; s'il n'y est pas, l'ajouter dans `chapitres`. Pour corriger un titre mal écrit sur Éléa sans toucher à Éléa, l'ajouter dans `titres` (titre Éléa → titre affiché).

## Organisation du dossier

| Dossier | Contenu |
|---|---|
| `scripts/` | construction du site (`build.py`), lecture d'Éléa (`elea.py`), récupération des Google Docs (`fetch_docs.py`), réglages (`config.json`) |
| `data/` | contenu lu dans les sauvegardes, un fichier par niveau |
| `sources/` | PDF et HTML téléchargés depuis Google (non publiés tels quels) |
| `templates/` | gabarits des pages |
| `docs/` | le site publié |
| `CONTRATS.md` | formats techniques partagés entre les parties du site |

## Le mode parent

Chaque page a une bascule **Élève / Parent**. Les pages parent (`docs/parents/<langue>/`) sont générées à partir des textes de `contenus/parents/` (français, arabe, turc, anglais, espagnol, portugais). Quand un nouveau chapitre arrive, le rapport de construction l'indique dans « Textes parents à rédiger » : Claude rédige le texte en français, vous le relisez, puis il est traduit. Le format est décrit dans `CONTRATS.md` §8.
