import pypdf
import re
from typing import Dict, Any, List


def extraire_texte_complet(chemin_pdf: str) -> str:
    """
    Extrait tout le texte d'un document PDF.
    """
    try:
        reader = pypdf.PdfReader(chemin_pdf)
        texte_complet = ""
        for page in reader.pages:
            texte_complet += page.extract_text() + "\n\n"
        return texte_complet
    except FileNotFoundError:
        print(f"❌ Erreur : Le fichier PDF '{chemin_pdf}' n'a pas été trouvé.")
        return ""
    except Exception as e:
        print(f"❌ Erreur lors de l'extraction du texte du PDF : {e}")
        return ""


def extraire_donnees(chemin_pdf: str) -> Dict[str, Any]:
    """
    Analyse le texte du PDF pour extraire les données nécessaires au template Jinja2.

    Retourne un dictionnaire prêt à être passé à template.render().
    """
    texte_source = extraire_texte_complet(chemin_pdf)

    if not texte_source:
        return {}  # Retourne un dictionnaire vide en cas d'erreur

    donnees_extraites = {}

    # --- 1. Extraction par expression régulière (RegEx) ou mots-clés ---

    # 📌 Exemple 1: Extraction de l'adresse du chantier
    # On cherche le texte après une phrase clé, jusqu'à un retour à la ligne ou une virgule.
    match_adresse = re.search(r"Adresse du Chantier\s*[:]\s*(.*?)\n", texte_source, re.IGNORECASE)
    if match_adresse:
        donnees_extraites['Adresse_chantier'] = match_adresse.group(1).strip()
    else:
        donnees_extraites['Adresse_chantier'] = "Non spécifiée dans le PDF"

    # 📌 Exemple 2: Extraction de l'intitulé de l'opération
    match_operation = re.search(r"Intitulé de l’opération\s*[:]\s*(.*?)\n", texte_source, re.IGNORECASE)
    if match_operation:
        # On suppose que le lot fait partie de l'intitulé
        full_title = match_operation.group(1).strip()
        donnees_extraites['Intitule_operation'] = full_title
        # Tente de séparer le lot
        match_lot = re.search(r"(Lot\s*[\d\s–-]+.*)", full_title, re.IGNORECASE)
        donnees_extraites['Lot_Intitule'] = match_lot.group(1).strip() if match_lot else "Lot 00 - À définir"
    else:
        donnees_extraites['Intitule_operation'] = "Opération à Renseigner"
        donnees_extraites['Lot_Intitule'] = "Lot 00 - À définir"

    # 📌 Exemple 3: Extraction d'une contrainte simple
    # Ici, nous extrayons des données pour le champ 'Conditions_acces'
    conditions_index = texte_source.find("Conditions d’accès")
    if conditions_index != -1:
        # Tente de lire 100 caractères après la mention, puis nettoie
        snippet = texte_source[conditions_index:conditions_index + 150]
        # Simplifié : on prend le texte après les deux points
        match_conditions = re.search(r"Conditions d’accès.*?[:](.*?)(?:\n|\.)", snippet, re.DOTALL)
        if match_conditions:
            donnees_extraites['Conditions_acces'] = match_conditions.group(1).strip()
        else:
            donnees_extraites['Conditions_acces'] = "À vérifier sur site"

    # --- 2. Extraction des Tableaux (La plus complexe, ici simmulée) ---
    # L'extraction de tableaux nécessite des outils plus robustes comme 'camelot'
    # ou de l'analyse structurelle du PDF. Ici, on simule des données par défaut.

    donnees_extraites['Liste_materiaux'] = [
        {'nature': 'Poutres IPE', 'marque': 'HESS TIMBER GL24h', 'provenance': 'Allemagne',
         'documentation': 'Annexe 1 (BLC)'},
        {'nature': 'Pare-pluie', 'marque': 'DELTA', 'provenance': 'UE', 'documentation': 'Fiche F4'},
    ]

    # --- 3. Ajout des données statiques de l'entreprise (non dans le PDF source) ---
    # Ces infos sont fixes pour Bois & Techniques et ne sont pas dans le PDF de l'appel d'offre.
    donnees_extraites.update({
        'Siret': '123 456 789 00010',
        'TVA': 'FR 98 123456789',
        'Email_contact': 'contact@boisettechniques.fr',
        'Site_web': 'www.boisettechniques.fr',
        'Telephone': '03 83 00 00 00',
        'Conducteur_travaux_nom': 'Frédéric Anselm',  # Fixe
        'Planning_ajustable': True,
        'Plan_photos_joints': False,

        # Données par défaut pour les champs non trouvés
        'Environnement_site': 'Urbain',
        'Marque_visserie': 'BERNER',
        'Liste_produits_DPGF': [],  # Laisser vide si non trouvé
    })

    # Validation pour s'assurer que toutes les clés Jinja sont présentes
    # (même avec une valeur par défaut) pour éviter un crash au rendu.

    return donnees_extraites


# --- Exemple d'utilisation (pour le test) ---
if __name__ == '__main__':
    # ATTENTION : Remplacez 'chemin/vers/votre/document.pdf' par un VRAI chemin de fichier
    # ou créez un fichier PDF test avec du texte contenant les mots-clés ci-dessus.
    CHEMIN_TEST = 'chemin/vers/votre/document_appel_offre.pdf'

    print(f"Tentative d'extraction des données à partir de : {CHEMIN_TEST}")

    # Si vous n'avez pas de PDF, décommentez ceci pour tester la structure
    # print("\n--- Résultat de la structure (sans vrai PDF) ---")
    # print(extraire_donnees(""))

    # Sinon, si vous avez un PDF de test :
    # resultats = extraire_donnees(CHEMIN_TEST)
    # print("\n--- Résultat de l'extraction ---")
    # import json
    # print(json.dumps(resultats, indent=4))