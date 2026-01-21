# Package src - Modules pour la génération de mémoires techniques
"""
Ce package contient les modules pour générer des mémoires techniques LaTeX
à partir de données CSV pour l'entreprise Bois & Techniques.

Modules:
- config: Configuration et chemins
- utils: Fonctions utilitaires (normalisation, échappement LaTeX)
- csv_handler: Lecture et parsing des fichiers CSV
- table_converters: Conversion de données en tableaux LaTeX
- user_input: Gestion des interactions utilisateur
- latex_generator: Génération du fichier LaTeX final
- section_processors: Traitement des sections spécifiques du mémoire
"""

from .config import *
from .utils import normaliser_texte, echapper_latex, echapper_latex_simple
from .csv_handler import charger_donnees_depuis_csv
from .table_converters import convertir_fixation_assemblage_en_tableau, convertir_traitement_en_tableau
from .user_input import demander_validation_ou_modif, construire_liste_interactive, construire_liste_directe
from .latex_generator import generer_fichier_tex
