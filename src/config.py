"""
Configuration et chemins pour le générateur de mémoires techniques.
"""

import os

# Chemin de base du projet (dossier parent de src/)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Dossiers
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")
DATA_DIR = os.path.join(BASE_DIR, "data")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
IMAGES_DIR = os.path.join(BASE_DIR, "images")

# Fichiers par défaut
DEFAULT_CSV_FILE = os.path.join(DATA_DIR, "crack.csv")
DEFAULT_TEMPLATE = os.path.join(TEMPLATES_DIR, "template.tex.j2")
DEFAULT_OUTPUT_TEX = os.path.join(OUTPUT_DIR, "resultat.tex")

# Templates spéciaux pour sections écologiques
TEMPLATE_DEMARCHE_HQE = os.path.join(TEMPLATES_DIR, "demarche_hqe.tex.j2")
TEMPLATE_DEMARCHE_ENV_ATELIER = os.path.join(TEMPLATES_DIR, "demarche_env_atelier.tex.j2")
TEMPLATE_DEMARCHE_ENV_CHANTIERS = os.path.join(TEMPLATES_DIR, "demarche_env_chantiers.tex.j2")

# Fichiers générés pour sections spéciales (dans output/)
GENERATED_DEMARCHE_HQE = os.path.join(OUTPUT_DIR, "demarche_hqe_generated.tex")
GENERATED_DEMARCHE_ENV_ATELIER = os.path.join(OUTPUT_DIR, "demarche_env_atelier_generated.tex")
GENERATED_DEMARCHE_ENV_CHANTIERS = os.path.join(OUTPUT_DIR, "demarche_env_chantiers_generated.tex")
GENERATED_MATIERE_PREMIERE = os.path.join(OUTPUT_DIR, "matiere_premiere_generated.tex")


def get_relative_path(absolute_path, from_dir=None):
    """
    Retourne le chemin relatif depuis from_dir (par défaut OUTPUT_DIR).
    Utile pour les chemins dans les fichiers LaTeX.
    """
    if from_dir is None:
        from_dir = OUTPUT_DIR
    return os.path.relpath(absolute_path, from_dir)


def ensure_directories():
    """
    Crée les dossiers nécessaires s'ils n'existent pas.
    """
    for directory in [TEMPLATES_DIR, DATA_DIR, OUTPUT_DIR]:
        os.makedirs(directory, exist_ok=True)
