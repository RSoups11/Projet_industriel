#!/usr/bin/env python3
"""
Test pour vérifier les changements :
1. Que les options multiples affichent seulement les sélectionnées
2. Que les couleurs sont appliquées correctement
"""

import sys
import os
import json

# Ajouter le chemin pour importer
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.pages.generation import GenerationPage
from app.core.config import AppConfig

def test_multiple_options():
    """Test pour vérifier que les options multiples filtrées correctement."""
    print("=" * 50)
    print("TEST 1 : Options multiples")
    print("=" * 50)
    
    # Créer une fausse state avec des options
    fake_state = {
        "sections_enabled": {"Méthodologie de construction": True},
        "sections_data": {
            "Méthodologie de construction": {
                "unique_1": {
                    "nom": "Localisation du site",
                    "texte": "Pavillonnaire /// ou /// Zone industrielle /// ou /// Zone artisanale",
                    "type": "multi_check",
                    "selections": {
                        "options": {
                            "Pavillonnaire": True,
                            "Zone industrielle": False,
                            "Zone artisanale": False
                        }
                    },
                    "couleur": "ecoBleu"
                }
            }
        },
        "template_data": {}
    }
    
    # Créer une instance de GenerationPage
    page = GenerationPage()
    page.project_state = fake_state
    
    # Appeler _collect_data_from_state
    data = page._collect_data_from_state()
    
    # Vérifier les résultats
    print(f"\nDonnées collectées :")
    for section in data:
        print(f"\nSection : {section['titre']}")
        for ss in section.get('sous_sections', []):
            print(f"  Sous-section : {ss['nom']}")
            print(f"  Contenu : {ss['contenu']}")
            print(f"  Couleur : {ss.get('couleur', 'N/A')}")
            
            # Vérifier qu'on n'a que les options sélectionnées
            if "Pavillonnaire" in ss['contenu'] and "Zone industrielle" not in ss['contenu'] and "Zone artisanale" not in ss['contenu']:
                print("  ✓ PASS : Seule l'option sélectionnée est présente")
            else:
                print("  ✗ FAIL : Les options non sélectionnées sont présentes")
                return False
    
    return True

def test_colors_in_data():
    """Test pour vérifier que les couleurs sont dans les données."""
    print("\n" + "=" * 50)
    print("TEST 2 : Couleurs dans les données")
    print("=" * 50)
    
    # Créer une fausse state avec différentes couleurs
    fake_state = {
        "sections_enabled": {"Méthodologie de construction": True},
        "sections_data": {
            "Méthodologie de construction": {
                "unique_1": {
                    "nom": "Déroulement des travaux",
                    "texte": "Voici comment on procède...",
                    "type": "text",
                    "couleur": "ecoVert"
                },
                "unique_2": {
                    "nom": "Conception",
                    "texte": "Conception du projet",
                    "type": "text",
                    "couleur": "ecoMarron"
                }
            }
        },
        "template_data": {}
    }
    
    page = GenerationPage()
    page.project_state = fake_state
    
    data = page._collect_data_from_state()
    
    print(f"\nDonnées collectées :")
    for section in data:
        for ss in section.get('sous_sections', []):
            couleur = ss.get('couleur', 'N/A')
            print(f"  {ss['nom']} -> Couleur : {couleur}")
            
            # Vérifier que les couleurs LaTeX sont présentes
            if couleur in ['ecoVert', 'ecoMarron', 'ecoBleu', 'ecoVertFonce', 'traitBleu', 'red!70!black', 'orange', 'purple', 'gray']:
                print(f"    ✓ PASS : Couleur LaTeX valide")
            else:
                print(f"    ✗ FAIL : Couleur LaTeX invalide")
                return False
    
    return True

if __name__ == "__main__":
    try:
        test1_pass = test_multiple_options()
        test2_pass = test_colors_in_data()
        
        print("\n" + "=" * 50)
        print("RÉSUMÉ DES TESTS")
        print("=" * 50)
        print(f"Test 1 (Options multiples) : {'PASS ✓' if test1_pass else 'FAIL ✗'}")
        print(f"Test 2 (Couleurs) : {'PASS ✓' if test2_pass else 'FAIL ✗'}")
        
        if test1_pass and test2_pass:
            print("\nTous les tests sont passés ! ✓")
            sys.exit(0)
        else:
            print("\nCertains tests ont échoué ✗")
            sys.exit(1)
    except Exception as e:
        print(f"\nERREUR : {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
