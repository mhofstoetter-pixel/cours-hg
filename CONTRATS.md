# Contrats entre les parties du site

Ce fichier fixe les formats que partagent le script de construction (`scripts/build.py`), le design (`docs/assets/hg.css`, `templates/`) et le moteur de QCM (`docs/assets/qcm.js`). Chaque partie peut avancer seule tant qu'elle respecte ces formats. Toute modification de ce fichier se décide dans la session principale.

## 1. Arborescence publiée (`docs/`, servie par GitHub Pages)

```
docs/
  index.html                      accueil : choix du niveau + bouton « Mon suivi BEX »
  4e/index.html                   page du niveau : 5 rubriques
  4e/<slug>/index.html            page d'une ressource (cours, BEX, méthodo, enquête)
  4e/<slug>/<slug>.pdf            copie PDF
  4e/qcm/<slug>/index.html        page d'entraînement d'un QCM
  4e/qcm/<slug>/qcm.json          données du QCM (format §2)
  5e/…                            même structure
  assets/hg.css                   design (session « Design »)
  assets/qcm.js                   moteur QCM (session « Moteur QCM »)
  assets/qcm.css                  styles propres au QCM (session « Moteur QCM »), s'appuie sur les variables de hg.css
```

Liens toujours **relatifs** (le site vit sous `/cours-hg/`, jamais de chemin commençant par `/`).

## 2. Format d'un QCM (`qcm.json`)

```json
{
  "id": "qcm-01-revisions-5e",
  "titre": "QCM 1 - Révisions 5e",
  "niveau": "4e",
  "chapitre": "H1",
  "discipline": "histoire",
  "intro": "<p>HTML facultatif</p>",
  "tirage": null,
  "questions": [ … ]
}
```

- `discipline` : `"histoire" | "geographie" | "emc" | null`.
- `tirage` : `null` = toutes les questions ; un entier N = tirer N questions au hasard à chaque essai (cas des QCM Éléa à questions aléatoires).
- Tout champ `*Html` contient du HTML déjà nettoyé par `build.py` (balises autorisées : `p br strong em u sup sub ul ol li span a img table thead tbody tr th td`). Le moteur l'insère tel quel.

Chaque question a `id`, `type`, `enonceHtml`, `feedbackHtml` (explication générale, peut être `""`), et selon le type :

### `choix` (QCM à une ou plusieurs bonnes réponses, et vrai/faux)
```json
{ "id": "16165", "type": "choix", "enonceHtml": "Quel est le projet de Christophe Colomb en 1492 ?",
  "multiple": false, "melanger": true,
  "reponses": [
    { "texteHtml": "Atteindre l'Asie en naviguant vers l'ouest", "fraction": 1, "feedbackHtml": "Oui. Colomb cherche une nouvelle route vers l'Asie." },
    { "texteHtml": "Conquérir l'empire aztèque", "fraction": 0, "feedbackHtml": "" }
  ],
  "feedbackHtml": "Colomb veut rejoindre l'Asie par l'ouest…" }
```
`fraction` entre -1 et 1 (Moodle). `multiple: true` → cases à cocher ; une réponse est juste si la somme des fractions cochées vaut 1 et qu'aucune fraction négative n'est cochée. Le vrai/faux est un `choix` à deux réponses « Vrai » / « Faux ».

### `association` (appariement)
```json
{ "id": "16169", "type": "association", "enonceHtml": "Relie chaque terme à sa définition.",
  "paires": [ { "gaucheHtml": "Tenochtitlan", "droite": "Capitale de l'empire aztèque" } ],
  "distracteurs": [],
  "feedbackHtml": "…" }
```
`droite` est du texte brut (liste déroulante). `distracteurs` : réponses de droite supplémentaires sans paire.

### `trous` (texte à trous Moodle, `{1:MULTICHOICE_S:…}`)
```json
{ "id": "17150", "type": "trous",
  "enonceHtml": "Dans les colonies, les colons possèdent des {{1}}. Aux Antilles, on dit des « {{2}} ».",
  "trous": {
    "1": { "mode": "liste", "options": [ { "texte": "plantations", "fraction": 1, "feedback": "" }, { "texte": "usines", "fraction": 0, "feedback": "" } ] },
    "2": { "mode": "liste", "options": [ … ] }
  },
  "feedbackHtml": "" }
```
`mode` : `"liste"` (MULTICHOICE, MULTICHOICE_S → menu déroulant), `"boutons"` (MULTICHOICE_V/H → boutons radio), `"texte"` (SHORTANSWER → champ libre, comparaison sans casse ni espaces superflus ; `options` = réponses acceptées). Le marqueur `{{n}}` est remplacé par le moteur.

## 3. Comportement attendu du moteur (`qcm.js`)

- Chargement : la page QCM contient `<div id="qcm" data-src="qcm.json"></div>` et `<script src="../../../assets/qcm.js" defer></script>`. Le moteur lit `data-src`, récupère le JSON et construit tout dans `#qcm`.
- Une question à la fois, barre de progression « Question 3 sur 10 ».
- Bouton « Vérifier » → correction immédiate (juste / partiellement juste / à revoir), feedback de la réponse choisie puis `feedbackHtml`. Puis « Question suivante ».
- Fin : score « 7 sur 10 », liste des questions à revoir, boutons « Recommencer » (nouvel ordre, nouveau tirage) et « Retour au niveau ».
- Rien n'est envoyé ni enregistré hors du navigateur (au plus `localStorage` pour le meilleur score, dans un try/catch).
- Accessible au clavier, cibles tactiles ≥ 44 px, fonctionne sur téléphone (375 px), `prefers-reduced-motion` respecté.
- Sans dépendance externe, ES2017, fichier unique.

## 4. Gabarits (`templates/`, session « Design »)

Gabarits HTML complets remplis par `build.py` avec `string.Template` de Python : variables `$nom` ou `${nom}`, `$$` pour un dollar littéral. Variables fournies :

| Gabarit | Variables |
|---|---|
| tous | `$titre_page`, `$racine` (chemin relatif vers `docs/`, ex. `../../`), `$fil_ariane` (HTML), `$annee` |
| `accueil.html` | `$niveaux` (HTML : une carte par niveau), `$lien_bex` (URL) |
| `niveau.html` | `$niveau` (« 4e »), `$rubriques` (HTML : sections `.hg-rubrique` contenant des cartes `.hg-carte`) |
| `ressource.html` | `$titre`, `$code` (« H1 », peut être vide), `$discipline` (`histoire`/`geographie`/`emc`/`methode`), `$contenu` (HTML du document), `$lien_pdf`, `$lien_gdoc`, `$retour` |
| `qcm.html` | `$titre`, `$code`, `$discipline`, `$intro`, `$retour` |

Classes que `build.py` utilise dans le HTML qu'il injecte (à styler dans `hg.css`) :
`.hg-carte` (lien-carte), `.hg-carte__code`, `.hg-carte__titre`, `.hg-carte__type`, `.hg-rubrique`, `.hg-rubrique__titre`, `.hg-pastille--histoire|--geographie|--emc|--methode`, `.hg-doc` (conteneur du contenu d'un Google Doc : titres, paragraphes, listes, tableaux, images), `.hg-vide` (rubrique vide : « Bientôt disponible »).

## 5. Variables CSS exposées par `hg.css` (utilisables par `qcm.css`)

Couleurs : `--outline --ink-900 --ink-500 --ink-300 --paper --paper-muted --jaune --rose --cyan --violet --bleu --vert --orange` et leurs `-soft`, `--vert-profond --vert-neon`, `--focus-ring`, `--juste`, `--faux`.
Typo : `--font-display --font-body --font-mono`. Espacements `--sp-1` … `--sp-10`. Rayons `--r-0 --r-sm --r-md --r-lg --r-pill`. Bordures `--bw --bw-bold --border`. Animation `--dur --ease`.
Valeurs : celles du design system « Cours HG-EMC Hofstoetter » (artefact claude.ai `86mLV7XHZjRHWW2gZXAEfz`, fichier `project/tokens.json` et `project/README.md`). `--juste` et `--faux` : choisir dans la palette, contraste AA avec du texte noir, distinguables autrement que par la couleur (icône + mot).

## 6. Exemple

`data/exemple-qcm.json` : un QCM réel de 4 questions, une de chaque type, au format §2.

## 7. Pages BEX interactives (`scripts/bex.py`, `docs/assets/bex.css`, `docs/assets/bex.js`)

Pour les rubriques « Les BEX » et « Méthodologie », `build.py` passe le HTML nettoyé du Google Doc à `bex.structurer()`. S'il reconnaît une BEX (titres « Exercice modèle », « Banque d'exercices », « Corrections »…), la page reçoit :

- `div.bex` > `nav.bex-sommaire` (liens vers les parties + `p.bex-progression[data-total]`) puis des `section.bex-partie#{comprendre|methode|exemple|entrainement|corrections|plus-loin}` ;
- `div.bex-cartes` > `li.bex-carte` > `button.bex-carte__face[aria-controls]` + `div.bex-carte__dos` : une carte par lettre de la méthode (C — Contexte…) ;
- `fieldset.bex-criteres` : critères de réussite à cocher ;
- `ol.bex-pas` > `li.bex-pas__etape` : modelage corrigé, étape par étape ;
- `article.bex-exercice` > titre `h3.bex-exercice__titre`, contenu, `details.bex-corrige` (fermé) et `p.bex-fait` (case « J'ai fait cet exercice »).

Les exemplaires à imprimer (blocs répétés, section « Exemplaires à imprimer ») sont retirés de la page : le PDF les garde. Sans JavaScript, tout reste visible et lisible. La progression et les cases cochées restent dans le navigateur de l'élève (`localStorage`), rien n'est envoyé.

Les liens vers `assets/*.css|js` reçoivent `?v=<empreinte>` à chaque construction pour forcer la mise à jour dans les navigateurs.

## 8. Mode parent (`scripts/parents.py`, `contenus/parents/`, `docs/assets/parents.css`, `docs/assets/mode.js`)

- Pages : `docs/parents/<langue>/index.html`, `<niveau>/index.html`, `<niveau>/<code>/index.html` (h1, g1…), `<niveau>/outils/index.html`. Langues : `fr ar tr en es pt` ; `ar` est en `dir="rtl"` avec la police Noto Sans Arabic.
- Textes : `contenus/parents/<langue>.json`, même structure dans chaque langue : `accueil{titre, intro[], comment_utiliser[]}`, `pratique[{question, reponse}]`, `aide_generale[]`, `outils[{cle, titre, texte[]}]`, `methodes.<niveau>.<slug de la BEX>{savoir_faire, nom, lettres[{lettre, mot, explication}], faire_reciter}`, `chapitres.<niveau>.<code>{titre, resume[], mots[{mot, definition}], reperes[], questions[{question, reponse}], evalue}`. Un champ `a_confirmer` signale une question au professeur : il n'est jamais affiché, et le rapport de construction le liste.
- Libellés de l'interface : `contenus/parents/interface.json`.
- Texte absent dans une langue : le français est affiché, entouré de `lang="fr" dir="ltr"`, avec la mention « pas encore traduit ». Chapitre sans texte : la page affiche les conseils généraux, le rapport le liste « à rédiger ».
- Bascule `nav.hg-bascule` (Élève / Parent) dans l'en-tête de toutes les pages ; `mode.js` retient la langue choisie (localStorage) et l'applique au lien « Parent » des pages élèves.
- « En ce moment » = code du dernier cours publié du niveau (ordre d'Éléa).
