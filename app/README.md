# 📘 Guide d'utilisation - Bois & Techniques v2.0
## Générateur de Mémoires Techniques

> **Guide pour débutants** - Tout ce que vous devez savoir pour utiliser l'application sans casser le LaTeX ! 🛠️

---

## 📋 Table des matières

1. [Démarrage rapide](#-démarrage-rapide)
2. [Page "Nouveau mémoire"](#-page-nouveau-mémoire)
3. [Page "Base de données"](#-page-base-de-données)
4. [Codes et symboles spéciaux LaTeX](#-codes-et-symboles-spéciaux-latex)
5. [Exemples d'utilisation](#-exemples-dutilisation)
6. [Dépannage](#-dépannage)

---

## 🚀 Démarrage rapide

### Installation (une seule fois)

**Étape 1 : Installer Python** (si pas déjà installé)
- Windows : Télécharger sur [python.org](https://python.org) (version 3.9 ou plus)
- Mac/Linux : Python est souvent déjà installé

**Étape 2 : Installer les dépendances**
```bash
cd app
pip install -r requirements.txt
```

**Étape 3 : Installer LaTeX** (pour générer les PDF)
- Windows : [MiKTeX](https://miktex.org/download)
- Mac : `brew install --cask mactex`
- Linux : `sudo apt install texlive-full`

### Lancement de l'application

Double-cliquez sur `run.py` ou ouvrez un terminal :
```bash
python run.py
```

L'application s'ouvre automatiquement dans votre navigateur à l'adresse : `http://localhost:8080`

---

## 📝 Page "Nouveau mémoire"

Cette page permet de créer un nouveau mémoire technique en personnalisant les informations du projet.

### 1️⃣ Panneau latéral gauche

**Informations du projet** (obligatoires)
- **Intitulé de l'opération** : Le nom complet du projet
  - ✅ Exemple : `Réhabilitation du bâtiment A - Résidence Les Érables`
  - ❌ Évitez : Trop de majuscules ou caractères spéciaux

- **Intitulé du lot** : Votre lot d'intervention
  - ✅ Exemple : `Lot N°02 - Charpente bois`
  - 💡 Astuce : Gardez la numérotation cohérente

- **Maître d'ouvrage** : Le client
  - ✅ Exemple : `Ville de Strasbourg - Direction de l'Urbanisme`

- **Adresse du chantier** : Lieu des travaux
  - ✅ Exemple : `12 rue de la Paix, 67000 Strasbourg`

**Images du projet**
- Formats acceptés : `.jpg`, `.png`, `.pdf`
- Taille recommandée : moins de 5 Mo par image
- Types d'images :
  - **Image de garde** : Photo du projet (couverture du mémoire)
  - **Attestation de visite** : Document officiel
  - **Plan d'emplacement** : Carte ou plan de situation
  - **Image grue/levage** : Photo des moyens de levage

💡 **Astuce** : Renommez vos fichiers AVANT de les importer (ex: `photo_facade.jpg` plutôt que `IMG_20240912.jpg`)

**Sections à inclure**
- Cochez les sections que vous voulez dans le mémoire
- Décochez celles qui ne sont pas pertinentes pour votre projet
- ✅ Exemple : Si pas de grue, décochez "Moyens matériel"

### 2️⃣ Zone principale - Remplissage du contenu

Chaque section a des **sous-sections** (cartes blanches). Voici comment les remplir :

#### 📅 Date et adresse de visite
```
Date de la visite : 15/09/2024
Adresse (si différente) : [laissez vide si identique à l'adresse du chantier]
```

#### ✏️ Zones de texte libre

**Ce qu'il faut savoir** :
- Vous pouvez écrire normalement (comme dans Word)
- ⚠️ Certains caractères posent problème au LaTeX

**Caractères à ÉVITER** :
```
❌ & (esperluette)     → Utilisez "et" à la place
❌ % (pourcentage)     → Écrivez "\%" ou "pourcent"
❌ _ (underscore)      → Écrivez "\_" ou évitez
❌ # (dièse)           → Écrivez "\#" ou évitez
❌ $ (dollar)          → Écrivez "\$" ou évitez
❌ { } (accolades)     → Évitez ou utilisez "\{ \}"
```

**Caractères AUTORISÉS** :
```
✅ é, è, à, ù, ç (accents)
✅ - (tiret)
✅ ' (apostrophe)
✅ , . ; : ! ? (ponctuation)
✅ () (parenthèses)
✅ " " (guillemets)
✅ 1 2 3 (chiffres)
```

#### 📊 Listes à puces

Pour faire une liste, il y a 2 méthodes :

**Méthode 1 : Simple (recommandée pour débutants)**
```
Premier point
Deuxième point
Troisième point
```
→ Chaque ligne devient automatiquement une puce

**Méthode 2 : Avancée (pour utilisateurs confirmés)**
```
\begin{itemize}
\item Premier point
\item Deuxième point
\item Troisième point
\end{itemize}
```

#### 🔢 Listes numérotées

**Méthode simple**
```
1. Premier point
2. Deuxième point
3. Troisième point
```

**Méthode avancée**
```
\begin{enumerate}
\item Premier point
\item Deuxième point
\item Troisième point
\end{enumerate}
```

#### ✍️ Texte en gras ou italique

```
\textbf{Texte en gras}
\textit{Texte en italique}
\textbf{\textit{Gras et italique}}
```

### 3️⃣ Génération du PDF

1. Vérifiez que tous les champs obligatoires sont remplis
2. Cliquez sur **"GÉNÉRER LE PDF"** (bouton vert en bas à gauche)
3. Patientez pendant la compilation (peut prendre 30 secondes à 2 minutes)
4. Le PDF s'ouvre automatiquement ou se trouve dans le dossier `output/`

**En cas d'erreur** :
- Vérifiez qu'il n'y a pas de caractères interdits (`&`, `%`, `_`, etc.)
- Assurez-vous que les images existent et sont dans un format valide
- Consultez la section [Dépannage](#-dépannage)

---

## 🗄️ Page "Base de données"

Cette page permet de **modifier les templates** (modèles) de texte utilisés dans les mémoires.

### ⚠️ ATTENTION - Zone réservée aux utilisateurs avancés

Modifier les templates peut **casser la génération des PDF** si mal fait. Suivez ces règles strictement :

### 1️⃣ Structure d'un template

Un template contient :
- Du **texte fixe** (qui apparaît toujours)
- Des **variables** entre `{{ }}` (remplacées par vos données)
- Des **commandes LaTeX** (structure du document)

**Exemple de template** :
```latex
\section{Contexte du projet}

Le projet concerne {{ infos_projet.intitule }}, situé à {{ infos_projet.adresse }}.

Le maître d'ouvrage est {{ infos_projet.moa }}.
```

### 2️⃣ Variables disponibles

```
{{ infos_projet.intitule }}      → Intitulé de l'opération
{{ infos_projet.lot }}           → Intitulé du lot
{{ infos_projet.moa }}           → Maître d'ouvrage
{{ infos_projet.adresse }}       → Adresse du chantier
{{ date_visite }}                → Date de la visite de site
{{ sections.NOM_SECTION }}       → Contenu d'une section
```

### 3️⃣ Règles à respecter ABSOLUMENT

#### ✅ À FAIRE
- Sauvegarder une copie avant modification
- Tester après chaque changement
- Utiliser les caractères spéciaux correctement
- Respecter l'indentation (espaces au début des lignes)
- Garder les balises `\begin{...}` et `\end{...}` appariées

#### ❌ À NE PAS FAIRE
- Supprimer les balises `\begin` sans supprimer le `\end` correspondant
- Utiliser `&` directement (toujours `\&`)
- Modifier les noms de variables (ex : `{{ intitule }}` → `{{ titre }}`)
- Supprimer les `%` de commentaires LaTeX
- Mélanger les accolades `{}` sans respect de la structure

### 4️⃣ Commandes LaTeX courantes

```latex
\section{Titre de section}           → Section principale
\subsection{Titre de sous-section}   → Sous-section
\textbf{Texte en gras}              → Gras
\textit{Texte en italique}          → Italique
\newline                            → Saut de ligne
\vspace{1cm}                        → Espace vertical
\\                                  → Saut de ligne dans tableau

% Ceci est un commentaire           → Invisible dans le PDF
```

### 5️⃣ Tableaux

**Structure d'un tableau simple** :
```latex
\begin{tabular}{|l|c|r|}  % l=gauche, c=centré, r=droite
\hline
Colonne 1 & Colonne 2 & Colonne 3 \\
\hline
Donnée 1  & Donnée 2  & Donnée 3  \\
Donnée 4  & Donnée 5  & Donnée 6  \\
\hline
\end{tabular}
```

⚠️ **Pièges courants** :
- Chaque ligne se termine par `\\`
- Les colonnes sont séparées par `&`
- Le nombre de colonnes dans `{|l|c|r|}` doit correspondre au nombre de `&` + 1

---

## 🔤 Codes et symboles spéciaux LaTeX

### Tableau récapitulatif

| Symbole | Comment l'écrire | Exemple |
|---------|------------------|---------|
| & | `\&` ou "et" | `Dupont \& Fils` |
| % | `\%` | `50\% de réduction` |
| € | `\euro` ou € | `1\,500\euro` |
| ≤ | `$\leq$` | `Température $\leq$ 20°C` |
| ≥ | `$\geq$` | `Charge $\geq$ 100 kg` |
| ² | `$^2$` | `m$^2$` (mètre carré) |
| ³ | `$^3$` | `m$^3$` (mètre cube) |
| ° | `$^\circ$` ou ° | `45$^\circ$` |
| × | `$\times$` | `3 $\times$ 4` |
| → | `$\rightarrow$` | `A $\rightarrow$ B` |
| _ | `\_` | `nom\_fichier` |

### Caractères accentués

**Bonne nouvelle** : Les accents français fonctionnent directement ! ✅
```
✅ é è à ù ç ê ô î â
✅ É È À Ù Ç Ê Ô Î Â
```

### Espaces insécables

Pour éviter qu'un nombre soit séparé de son unité :
```latex
100~kg        → 100 kg (pas de coupure possible)
25~m²         → 25 m² (restent ensemble)
M.~Dupont     → M. Dupont (restent ensemble)
```

---

## 💡 Exemples d'utilisation

### Exemple 1 : Description d'un projet

```latex
Le projet de {{ infos_projet.intitule }} consiste en la réalisation d'une 
charpente bois traditionnelle d'une surface de 250~m². Les travaux seront 
effectués sur une période de 6~semaines, du 15~mars au 30~avril~2024.

\textbf{Caractéristiques principales :}
\begin{itemize}
\item Essence : Douglas classe 2
\item Section des poutres : 200~mm $\times$ 250~mm
\item Traitement : Classe de service 2
\item Charge admissible : 150~kg/m²
\end{itemize}
```

### Exemple 2 : Liste de moyens humains

```latex
\subsection{Équipe affectée au projet}

L'équipe sera composée de :
\begin{enumerate}
\item 1 Chef de chantier - M. Jean MARTIN (15 ans d'expérience)
\item 2 Charpentiers qualifiés - Certificat professionnel
\item 1 Aide-charpentier - En formation CAP
\item 1 Conducteur d'engins - CACES R482 cat. C
\end{enumerate}

\textit{Note : Toute l'équipe dispose des habilitations de sécurité requises.}
```

### Exemple 3 : Tableau de planning

```latex
\begin{tabular}{|l|c|c|}
\hline
\textbf{Phase} & \textbf{Durée} & \textbf{Effectif} \\
\hline
Préparation    & 3 jours        & 2 personnes       \\
Levage         & 5 jours        & 4 personnes       \\
Assemblage     & 10 jours       & 3 personnes       \\
Finitions      & 4 jours        & 2 personnes       \\
\hline
\textbf{TOTAL} & \textbf{22 jours} & -              \\
\hline
\end{tabular}
```

### Exemple 4 : Section matériaux

```latex
\section{Matériaux mis en œuvre}

\textbf{Bois de structure :}
\begin{itemize}
\item Essence : Épicéa du Nord, classe C24
\item Traitement : Autoclave classe 3
\item Provenance : Scierie locale (circuit court)
\item Certification : PEFC
\end{itemize}

\textbf{Quincaillerie :}
\begin{itemize}
\item Boulons HR \O 16~mm, longueur 200~mm
\item Sabots de charpente acier galvanisé
\item Tire-fond \O 12~mm
\end{itemize}

\textit{Tous les matériaux sont conformes aux normes en vigueur (NF, DTU 31.1).}
```

---

## 🔧 Dépannage

### Le PDF ne se génère pas

**Problème** : Message d'erreur lors de la génération

**Solutions** :
1. Vérifiez les caractères spéciaux (`&`, `%`, `_`, etc.)
2. Assurez-vous que LaTeX est bien installé :
   ```bash
   pdflatex --version
   ```
3. Consultez le fichier de log dans `output/` pour voir l'erreur exacte
4. Testez avec un mémoire vide (toutes sections décochées)

### Les accents s'affichent mal

**Problème** : `Ã©` au lieu de `é`

**Solution** : Le fichier CSV doit être encodé en UTF-8
1. Ouvrez le CSV dans un éditeur avancé (Notepad++, VS Code)
2. Vérifiez l'encodage (en bas à droite)
3. Convertissez en UTF-8 si nécessaire
4. Sauvegardez

### L'image ne s'affiche pas

**Problème** : Espace blanc dans le PDF

**Solutions** :
1. Vérifiez que l'image existe bien dans le dossier `images/`
2. Format accepté : JPG, PNG, PDF
3. Évitez les espaces dans le nom du fichier
4. Taille max recommandée : 5 Mo

### Erreur "Undefined control sequence"

**Problème** : Commande LaTeX incorrecte

**Solution** : Vérifiez les `\backslash`
- Chaque commande LaTeX commence par `\`
- Les accolades doivent être appariées `{}`
- Exemple correct : `\textbf{texte}`

### L'application ne démarre pas

**Problème** : Erreur au lancement

**Solutions** :
1. Vérifiez que Python est installé :
   ```bash
   python --version
   ```
2. Réinstallez les dépendances :
   ```bash
   pip install -r requirements.txt --force-reinstall
   ```
3. Vérifiez qu'aucun autre programme n'utilise le port 8080

---

## 📞 Besoin d'aide ?

### Avant de demander de l'aide

1. ✅ Avez-vous vérifié les caractères spéciaux ?
2. ✅ Avez-vous testé avec un exemple simple ?
3. ✅ Avez-vous consulté la section Dépannage ?
4. ✅ Avez-vous le message d'erreur complet ?

### Informations utiles à fournir

- Version de l'application (voir `config.json`)
- Système d'exploitation (Windows, Mac, Linux)
- Message d'erreur exact
- Capture d'écran si possible

---

## 📚 Ressources complémentaires

### Pour aller plus loin avec LaTeX

- [Guide LaTeX pour débutants (français)](https://fr.wikibooks.org/wiki/LaTeX)
- [Documentation officielle LaTeX](https://www.latex-project.org/)
- [Overleaf - Éditeur LaTeX en ligne](https://www.overleaf.com/learn)

### Raccourcis utiles

| Action | Windows | Mac |
|--------|---------|-----|
| Sauvegarder | Ctrl + S | Cmd + S |
| Copier | Ctrl + C | Cmd + C |
| Coller | Ctrl + V | Cmd + V |
| Annuler | Ctrl + Z | Cmd + Z |

---

## 🎯 Checklist avant génération

- [ ] Toutes les informations du projet sont remplies
- [ ] Les images sont importées (si nécessaire)
- [ ] Pas de caractères interdits (`&`, `%`, `_`)
- [ ] Les sections inutiles sont décochées
- [ ] LaTeX est installé sur l'ordinateur
- [ ] Le contenu a été relu

---

**Version du guide** : 2.0  
**Dernière mise à jour** : Janvier 2026

**Bonne génération de mémoires techniques ! 🎉**
