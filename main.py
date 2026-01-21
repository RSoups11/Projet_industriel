#!/usr/bin/env python3
"""
Générateur de Mémoires Techniques pour Bois & Techniques

Point d'entrée principal pour générer des mémoires techniques LaTeX
à partir de données CSV.

Usage:
    python main.py [--csv FICHIER_CSV] [--output FICHIER_TEX]
"""

import argparse
import sys
import os

# Ajouter le dossier parent au path pour les imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.config import (
    DEFAULT_CSV_FILE,
    DEFAULT_OUTPUT_TEX,
    ensure_directories,
)
from src.csv_handler import charger_donnees_depuis_csv
from src.user_input import saisir_infos_projet, saisir_images_projet
from src.latex_generator import generer_fichier_tex
from src.section_processors import (
    traiter_section_contexte,
    traiter_section_materiaux,
    traiter_section_moyens_humains,
    traiter_section_moyens_materiel,
    traiter_section_methodologie,
    traiter_section_references,
    ajouter_sections_restantes,
)


def main():
    """Fonction principale du générateur."""
    
    # Parser les arguments
    parser = argparse.ArgumentParser(
        description="Génère un mémoire technique LaTeX à partir d'un fichier CSV."
    )
    parser.add_argument(
        "--csv",
        default=DEFAULT_CSV_FILE,
        help=f"Chemin vers le fichier CSV (défaut: {DEFAULT_CSV_FILE})"
    )
    parser.add_argument(
        "--output",
        default=DEFAULT_OUTPUT_TEX,
        help=f"Chemin du fichier LaTeX de sortie (défaut: {DEFAULT_OUTPUT_TEX})"
    )
    args = parser.parse_args()

    # S'assurer que les dossiers existent
    ensure_directories()

    # Lecture du CSV
    print(f"Lecture du fichier CSV : {args.csv}")
    donnees_brutes = charger_donnees_depuis_csv(args.csv)
    if not donnees_brutes:
        print("Aucune donnée trouvée dans le CSV, arrêt.")
        sys.exit(1)

    # Infos de la page de garde
    infos_projet = saisir_infos_projet()

    # Saisie des images du projet
    images_projet = saisir_images_projet()

    # Traitement des sections
    data_finale = []
    titres_a_ignorer = set()

    # Section Contexte du projet
    section_contexte, ignorer_contexte = traiter_section_contexte(donnees_brutes)
    if section_contexte:
        data_finale.append(section_contexte)
    if ignorer_contexte:
        for s in donnees_brutes:
            if "contexte du projet" in s["titre"].lower():
                titres_a_ignorer.add(s["titre"])

    # Section Situation Administrative (SECTION 2)
    for donnee in donnees_brutes:
        if "situation administrative" in donnee["titre"].lower():
            section_situation = {
                "titre": donnee["titre"],
                "contenu": [donnee]
            }
            data_finale.append(section_situation)
            titres_a_ignorer.add(donnee["titre"])
            break

    # Section Moyens humains (SECTION 3)
    section_mh = traiter_section_moyens_humains(donnees_brutes)
    if section_mh:
        data_finale.append(section_mh)

    # Section Moyens matériel (SECTION 3)
    section_mm = traiter_section_moyens_materiel(donnees_brutes)
    if section_mm:
        data_finale.append(section_mm)
        titres_a_ignorer.add("MOYENS MATERIEL AFFECTES AU PROJET")

    # Section Méthodologie
    section_metho = traiter_section_methodologie(donnees_brutes)
    if section_metho:
        data_finale.append(section_metho)

    # Section Chantiers de référence 
    section_chantiers = {
        "titre": "CHANTIERS DE RÉFÉRENCE",
        "contenu": []
    }
    data_finale.append(section_chantiers)

    # Section Materiaux (SECTION 4)
    section_materiaux = traiter_section_materiaux(donnees_brutes)
    if section_materiaux:
        data_finale.append(section_materiaux)
        titres_a_ignorer.add("LISTE DES MATERIAUX MIS EN OEUVRE")
        titres_a_ignorer.add("LISTE DES MATERIAUX MIS EN ŒUVRE")

    # Section Références
    section_ref = traiter_section_references(donnees_brutes)
    if section_ref:
        data_finale.append(section_ref)

    # Ajouter les sections restantes du CSV
    ajouter_sections_restantes(donnees_brutes, data_finale, titres_a_ignorer)

    # Génération du fichier LaTeX
    if not data_finale:
        print("Aucune section à générer (toutes les sous-sections sont vides).")
        sys.exit(1)
    
    success = generer_fichier_tex(
        data_finale,
        infos_projet,
        images=images_projet,
        output_path=args.output
    )
    
    if success:
        print(f"\n✅ Mémoire technique généré avec succès : {args.output}")
        print(f"\nPour compiler en PDF, exécutez :")
        print(f"  cd output && pdflatex resultat.tex")
    else:
        print("\n❌ Erreur lors de la génération.")
        sys.exit(1)


if __name__ == "__main__":
    main()
