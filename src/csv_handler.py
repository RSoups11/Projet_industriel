"""
Gestion de la lecture et du parsing des fichiers CSV.
"""

import csv
from collections import defaultdict

from .utils import echapper_latex, normaliser_texte


def charger_donnees_depuis_csv(chemin_csv):
    """
    Lit un CSV plat (section;sous-section;texte;image) et le transforme en structure hiérarchique :
    [
      {
        'titre': 'Nom de la section',
        'sous_sections': [
            {'nom': 'Nom de ss', 'contenu': '...', 'image': '...'},
            ...
        ]
      },
      ...
    ]
    """
    sections = defaultdict(list)

    try:
        with open(chemin_csv, mode="r", encoding="utf-8") as f:
            reader = csv.DictReader(f, delimiter=";")
            for row in reader:
                section_nom = (row.get("section") or "").strip()
                sous_section_nom = (row.get("sous-section") or "").strip()
                texte_brut = (row.get("texte") or "").strip()
                texte = echapper_latex(texte_brut)
                image = (row.get("image") or "").strip() or None

                if not sous_section_nom:
                    titre_norm = normaliser_texte(section_nom)

                    # Cas spécial : Chantiers références en rapport avec l'opération
                    if "chantiers references en rapport avec l'operation" in titre_norm:
                        sous_section_nom = "Références"   # nom factice interne
                    else:
                        continue

                sections[section_nom].append(
                    {
                        "nom": sous_section_nom,
                        "contenu": texte,
                        "contenu_brut": texte_brut,
                        "image": image,
                    }
                )

        donnees = []
        for titre, sous_secs in sections.items():
            donnees.append({"titre": titre, "sous_sections": sous_secs})

        return donnees

    except Exception as e:
        print(f"Erreur lors de la lecture du CSV '{chemin_csv}' : {e}")
        return []
