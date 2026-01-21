# Projet Industriel - Bois & Techniques

---

Ce projet Python permet de générer automatiquement un mémoire technique PDF à partir de données CSV pour l'entreprise Bois & Techniques.

Il s'appuie sur un template LaTeX structuré et un système de génération Jinja2 pour personnaliser automatiquement le rendu final.# Projet Industriel - Bois & Technique



---Ce projet Python permet de générer automatiquement un mémoire technique PDF à partir de documents PDF issus d’un Dossier de Consultation des Entreprises (DCE), comme le CCTP, CCAP, CCTC ou DPGF.

Il s’appuie sur un template LaTeX structuré et un système d’extraction de variables basique pour personnaliser automatiquement le rendu final.

## Structure du projet

---

```

pi_bois_techniques/## Prérequis & Installation

├── main.py                   # Point d'entrée principal

├── requirements.txt          # Dépendances Python### Dépendances

├── README.md                 # Ce fichier

│```bash

├── src/                      # Modules Pythonpip install -r requirements.txt

│   ├── __init__.py           # Package init```

│   ├── config.py             # Configuration et chemins

│   ├── utils.py              # Fonctions utilitaires (normalisation, échappement LaTeX)

│   ├── csv_handler.py        # Lecture et parsing des fichiers CSV### Autres outils nécessaires

│   ├── table_converters.py   # Conversion de données en tableaux LaTeX

│   ├── user_input.py         # Gestion des interactions utilisateur* **pdflatex** : LaTeX est installé machine (`texlive`, `pdflatex`, etc.) pour compiler le fichier `.tex` en `.pdf`. Sous Ubuntu :

│   ├── latex_generator.py    # Génération du fichier LaTeX final

│   └── section_processors.py # Traitement des sections spécifiques```bash

│sudo apt install texlive-full

├── templates/                # Templates Jinja2```

│   ├── template.tex.j2       # Template principal du mémoire

│   ├── demarche_hqe.tex.j2   # Template démarche HQE---

│   ├── demarche_env_atelier.tex.j2    # Template démarche environnementale atelier

│   └── demarche_env_chantiers.tex.j2  # Template démarche environnementale chantiers## Structure du projet

│

├── data/                     # Fichiers de données CSV```bash

│   ├── crack.csv             # Base de données principale.     

│   ├── bd_template.csv       # Template CSV vide├── implementer_sousSection.py       

│   └── bd_complete.csv       # Base de données                          

│├── images/                   

├── output/                   # Fichiers générés│   └── entete.png

│   ├── resultat.tex          # Fichier LaTeX généré│   └── traitement_curatif.png

│   ├── resultat.pdf          # PDF compilé│   └── ...

│   └── *_generated.tex       # Sections générées spéciales└── Document DCE (CCAP, CCTP, CCTC, RC, DPGF)

│```

├── images/                   # Images et logos

│   ├── entete.png            # En-tête du document---

│   ├── logo_boisTechniques.png

│   └── ...                   # Autres logos et images## Utilisation

│

└── venv/                     # Environnement virtuel Python```bash

```python3 implementer_sousSection.py

```

---

---

## Prérequis & Installation

### Fonctionnement du script - Sections & Sous-sections

### 1. Environnement Python

Ce script génère automatiquement un **mémoire technique** à partir :

```bash

# Créer un environnement virtuel* du fichier **bd_template.csv** (structure + textes + images),

python3 -m venv venv* du template **LaTeX Jinja**,

* des réponses interactives de l’utilisateur.

# Activer l'environnement

source venv/bin/activate  # Linux/MacChaque **section** et **sous-section** suit une logique décrite ci-dessous.

# ou

venv\Scripts\activate     # Windows---



# Installer les dépendances### Page de garde

pip install -r requirements.txt

```L’utilisateur renseigne :



### 2. LaTeX* **Intitulé de l’opération**

* **Intitulé du lot**

**pdflatex** doit être installé pour compiler le fichier `.tex` en `.pdf`.* **Maître d’ouvrage**

* **Adresse du chantier**

```bash

# Ubuntu/DebianLes éléments fixes (SIRET, email, téléphone, site web) sont intégrés automatiquement.

sudo apt install texlive-full

---

# Arch Linux

sudo pacman -S texlive-most### Préambule



# macOS (via MacTeX)* Texte fixe, non modifiable.

brew install --cask mactex* Directement injecté dans le PDF.

```

---

---

### Contexte du projet

## Utilisation

Sous-sections :

### Génération du mémoire technique

#### Contexte

```bash

# Activer l'environnement virtuelLe texte du CSV contient :

source venv/bin/activate« Nous sommes passés faire la visite sur le site le … »



# Lancer le générateurL’utilisateur saisit une **date**.

python main.py-> Si rien n’est saisi → **la sous-section est ignorée.**

```

---

Le script vous posera des questions interactives pour personnaliser le mémoire :

- Informations de la page de garde (opération, lot, maître d'ouvrage, adresse)#### Environnement

- Contexte du projet (date de visite, environnement, contraintes...)

- Moyens humains (chargé d'affaires, chef d'équipe, charpentiers)L’utilisateur saisit un texte libre.

- Références de chantiers similaires➡ Si vide -> sous-section ignorée.



### Options de ligne de commande---



```bash#### Accès chantier et stationnement

# Utiliser un fichier CSV personnalisé

python main.py --csv data/mon_fichier.csvTexte libre demandé à l’utilisateur.



# Spécifier le fichier de sortie---

python main.py --output output/mon_memoire.tex

```#### Levage



### Compilation du PDFTexte libre demandé à l’utilisateur.



```bash---

cd output

pdflatex resultat.tex#### Contraintes du chantier

pdflatex resultat.tex  # Deuxième passe pour la table des matières

```L’utilisateur saisit une liste.

-> Si aucun élément → sous-section ignorée.

---

---

## Format du fichier CSV

### Liste des matériaux mis en œuvre

Le fichier CSV utilise le point-virgule (`;`) comme séparateur et contient les colonnes :

Section basée **uniquement sur les images du CSV** :

| Colonne | Description |

|---------|-------------|* Matière première de qualité certifiée

| `section` | Nom de la section principale |* Fixation et assemblage

| `sous-section` | Nom de la sous-section |* Traitement préventif des bois

| `texte` | Contenu textuel |* Traitement curatif des bois

| `image` | Chemin vers une image (optionnel) |

Les sous-sections ayant un **chemin d’image** sont affichées.

Exemple :

```csv---

section;sous-section;texte;image

CONTEXTE DU PROJET;Contexte;Nous sommes passés faire la visite sur le site le;### Moyens humains affectés au projet

LISTE DES MATERIAUX MIS EN OEUVRE;UNE MATIERE PREMIERE DE QUALITE CERTIFIEE;Utilisation de bois certifiés...;../images/logo_pefc.png

```#### Organisation du chantier



---Le script demande :



## Modules Python* Nom du chargé d’affaires

* Nom du chef d’équipe

### `src/config.py`* Noms des charpentiers (séparés par virgules)

Configuration des chemins et constantes du projet.

Pour chaque rôle :

### `src/utils.py`

Fonctions utilitaires :1. Le nom proposé peut être validé ou modifié.

- `normaliser_texte()` : Normalise les textes pour comparaison2. Le texte descriptif du CSV peut être accepté ou réécrit.

- `echapper_latex()` : Échappe les caractères spéciaux LaTeX3. Si aucun nom n’est fourni -> rôle ignoré.

- `extraire_items_depuis_texte()` : Parse les listes depuis le texte CSV

---

### `src/csv_handler.py`

- `charger_donnees_depuis_csv()` : Charge et structure les données du CSV#### Sécurité et santé sur les chantiers



### `src/table_converters.py`Texte + image issus du CSV (pas d’interaction).

- `convertir_fixation_assemblage_en_tableau()` : Convertit en tableau LaTeX

- `convertir_traitement_en_tableau()` : Convertit les traitements en tableau---



### `src/user_input.py`#### Organigramme fonctionnel

Gestion des interactions utilisateur (saisie, validation, listes).

Texte + image issus du CSV.

### `src/latex_generator.py`

- `generer_fichier_tex()` : Génère le fichier LaTeX à partir du template Jinja2---



### `src/section_processors.py`#### Conception et précision

Traitement des sections spécifiques :

- Contexte du projetLe CSV donne une liste (ex. laser, CAO…).

- Liste des matériauxL’utilisateur peut :

- Moyens humains

- Méthodologie* accepter la liste,

- Références* supprimer des éléments,

* en ajouter.

---

---

## Personnalisation

#### Sécurité

### Modifier le template LaTeX

Éditez `templates/template.tex.j2` pour modifier la structure du document.Même logique que “Conception et précision”.



### Ajouter de nouvelles sections---

1. Ajoutez les données dans le fichier CSV

2. Si nécessaire, créez un processeur dans `src/section_processors.py`#### Atelier de taille

3. Appelez le processeur dans `main.py`

Affiche le texte :

### Modifier les styles écologiques« Opérations à effectuer en atelier pour le projet : »

Les couleurs sont définies dans le template principal :Puis l’utilisateur saisit une liste.

- `ecoVert` : #27AE60

- `ecoVertFonce` : #1E8449---

- `ecoVertClair` : #A9DFBF

- `ecoBleu` : #3498DB#### Transport

- `ecoMarron` : #795548

Texte du CSV

---

* liste d’opérations ajoutées par l’utilisateur.

## Fichiers hérités (ancienne version)

---

Ces fichiers ne sont plus utilisés mais conservés pour référence :

- `implementer_sousSection.py` : Ancienne version monolithique#### Levage

- `generate_pdf.py` : Ancien générateur PDF

- `pdf_data_extractor.py` : Extracteur de données PDFTexte du CSV

- `replace_sections.py` : Script de remplacement de sections

* actions du projet ajoutées par l’utilisateur.

---

---

## Licence

#### Machines portatives

Projet développé pour Bois & Techniques - 2024/2025

Liste modifiable par l’utilisateur.

---

#### Protection / Nettoyage du bâtiment

Liste modifiable par l’utilisateur.

---

#### Gestion des déchets

Liste modifiable par l’utilisateur.

---

### Moyens matériels affectés au projet

Affiche uniquement **l’image** fournie dans le CSV.

---

### Méthodologie / Chronologie

####  Conception

Texte du CSV.

#### Fabrication / Taille en atelier

Commence par :
« Opérations à réaliser en atelier : »
Puis liste saisie par l’utilisateur.

#### Transport et levage

Texte du CSV + liste d’opérations à saisir.

#### Chantier

Même logique que Transport.

#### Protection de l’existant

Liste du CSV, modifiable par l’utilisateur.

#### Organisation hygiène & sécurité

Liste du CSV, modifiable par l’utilisateur.

#### Protection / Nettoyage

Liste du CSV, modifiable par l’utilisateur.


---

### Chantiers références en rapport avec l’opération

Section interactive :

L’utilisateur saisit **une liste de chantiers**, sous forme de bullet points.

Si aucune saisie -> la section est ignorée.

---

### Sections restantes du CSV

Toute section non traitée explicitement :

* est affichée automatiquement,
* avec ses sous-sections,
* uniquement si du contenu (texte ou image) est présent.

---

## Compilation

```bash
pdflatex resultat.text
```

_N.B : Il est des fois nécessaire de compiler 2 fois afin de tout load dans le rendu pdf (ex : La table des matières)._

## Manque

- Proposer a l'utilisateur d'ajouter une section/sous-section à la main
- Répertorier les modifications et/ou ajout dans le csv
- Revoir les textes affichés dans le csv ("Insérer image", "lien vers..." etc à modifier à terme)
- Propose en avance si l'utilisateur veut tel ou tel section plus tot que attendre des réponses vide
- Auto-compilation du fichier resultat.tex

---

