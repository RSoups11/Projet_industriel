# Application Bois & Techniques v2.0

## Nouvelle interface unifiée

Cette nouvelle version utilise **NiceGUI** pour offrir une interface moderne, scalable et facile à maintenir.

### Fonctionnalités

1. **Génération de mémoires** - Interface principale pour créer des PDF
2. **Gestion des templates** - Éditeur de templates LaTeX/Jinja2
3. **Paramètres** - Configuration de l'application

### Installation

```bash
cd app
pip install -r requirements.txt
```

### Lancement

```bash
# Méthode 1 : Script de lancement
python run.py

# Méthode 2 : Directement
python main.py
```

### Prérequis

- Python 3.9+
- pdflatex (TexLive) pour la compilation PDF

```bash
# Ubuntu/Debian
sudo apt install texlive-full

# macOS
brew install --cask mactex
```

### Architecture

```
app/
├── main.py              # Point d'entrée
├── run.py               # Script de lancement
├── requirements.txt     # Dépendances
├── config.json          # Configuration utilisateur
├── core/                # Services métier
│   ├── config.py        # Configuration
│   ├── csv_service.py   # Gestion CSV
│   ├── latex_service.py # Génération LaTeX/PDF
│   └── template_service.py  # Gestion templates
└── pages/               # Pages de l'interface
    ├── generation.py    # Page principale
    ├── templates.py     # Gestion templates
    └── parametres.py    # Paramètres
```

### Avantages de NiceGUI

- Interface web moderne (HTML/CSS/JS) sans besoin de JavaScript
- Fonctionne en mode natif (sans navigateur visible)
- Pas besoin d'accès internet après installation
- Scalable et maintenable
- Composants réutilisables
- Hot reload en développement
