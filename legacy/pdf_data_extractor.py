import pypdf
import re
from typing import Dict, Any, List
import json, sys
from collections import defaultdict

def extraire_texte_complet(chemin_pdf: str) -> str:
    try:
        reader = pypdf.PdfReader(chemin_pdf)
        texte_complet = ""
        for page in reader.pages:
            texte = page.extract_text()
            if texte:
                texte_complet += texte + "\n\n"
        return texte_complet
    except Exception as e:
        print(f"Erreur d'extraction dans {chemin_pdf}: {e}")
        return ""

def extraire_donnees_texte(texte_source: str, chemin_pdf: str) -> Dict[str, Any]:
    donnees_extraites = {}

    # Intitulé opération
    match_titre = re.search(r"(?:Travaux|Rénovation|Réhabilitation|Construction|Aménagement)[^\n]{5,100}", texte_source, re.IGNORECASE)
    if match_titre:
        donnees_extraites["Intitule_operation"] = match_titre.group(0).strip()

    # Lot
    match_lot = re.search(r"Lot\s*0*2\s*[-:]?\s*(.*)", texte_source, re.IGNORECASE)
    if match_lot:
        donnees_extraites["Lot_Intitule"] = f"Lot 02 - {match_lot.group(1).strip()}"

    # Maître d’ouvrage
    match_mo = re.search(r"Ma[îi]tre d['’]?ouvrage\s*[:\-]?\s*(.+)", texte_source, re.IGNORECASE)
    if match_mo:
        donnees_extraites["Maitre_ouvrage_nom"] = match_mo.group(1).strip()

    # Adresse chantier (heuristique)
    match_adresse = re.search(r"\d{1,3} ?(rue|avenue|boulevard|place)[^\n]{5,80}", texte_source, re.IGNORECASE)
    if match_adresse:
        donnees_extraites["Adresse_chantier"] = match_adresse.group(0).strip()

    # Contraintes
    if "occupé" in texte_source.lower():
        donnees_extraites["Contrainte_site_occupe"] = "Oui"
    if re.search(r"échafaudage|hauteur", texte_source, re.IGNORECASE):
        donnees_extraites["Contrainte_hauteur"] = "Travail en hauteur prévu"
    match_delai = re.search(r"délai.*?(?:\d+\s*(?:jours|mois))", texte_source, re.IGNORECASE)
    if match_delai:
        donnees_extraites["Contrainte_delais"] = match_delai.group(0).split(":")[-1].strip()

    # Conditions accès
    match_acces = re.search(r"(conditions d['’]accès[^:]*[:\-]?\s*)([^\n\.]{10,150})", texte_source, re.IGNORECASE)
    if match_acces:
        donnees_extraites["Conditions_acces"] = match_acces.group(2).strip()

    # DPGF (produits)
    if "DPGF" in chemin_pdf.upper():
        lignes = re.findall(r"^\s*([0-9]+(?:\.[0-9]+)+)\s+(.+)$", texte_source, re.MULTILINE)
        produits = []
        for code, desc in lignes:
            desc = re.sub(r"\d+[\d\s,\.]*€.*", "", desc).strip()
            produits.append({
                "position": code,
                "nature": desc,
                "marque_type": "",
                "provenance": "",
                "documentation": f"DCE {code}"
            })
        if produits:
            donnees_extraites["Liste_produits_DPGF"] = produits

    return donnees_extraites

def fusionner_donnees(liste_dicts: List[Dict[str, Any]]) -> Dict[str, Any]:
    result = {}
    for d in liste_dicts:
        result.update(d)  # le dernier écrase les précédents en cas de doublon
    return result

def valeurs_par_defaut() -> Dict[str, Any]:
    return {
        'Siret': '893 822 841 00027',
        'Email_contact': 'bois-techniques@orange.fr',
        'Telephone': '03 89 53 36 58',
        'Site_web': 'www.bois-techniques.fr',
        'Conducteur_travaux_nom': 'Frédéric Anselm',
        'Planning_ajustable': True,
        'Plan_photos_joints': False,
        'Environnement_site': 'À définir',
        'Adresse_chantier': 'À compléter',
        'Intitule_operation': 'À compléter',
        'Lot_Intitule': 'Lot 02 - Charpente Bois',
        'Maitre_ouvrage_nom': 'Non spécifié',
        'Conditions_acces': 'Non spécifiées',
        'Contrainte_site_occupe': 'Non déterminé',
        'Contrainte_hauteur': 'Non précisée',
        'Contrainte_delais': 'Non précisé',
        'Marque_visserie': 'BERNER',
        'Liste_materiaux': [
            {'nature': 'Poutres BLC', 'marque': 'HESS TIMBER GL24h', 'provenance': 'Allemagne', 'documentation': 'Annexe 1'},
            {'nature': 'Pare-pluie', 'marque': 'DELTA', 'provenance': 'UE', 'documentation': 'Fiche F4'}
        ],
        'Liste_produits_DPGF': [],
        'Fiche_bois': 'Non fourni',
        'Certificat_traitement': 'Non fourni',
        'CV_chef': 'Non fourni'
    }

def extraire_depuis_plusieurs_pdfs(chemins: List[str]) -> Dict[str, Any]:
    donnees_list = []
    for chemin in chemins:
        texte = extraire_texte_complet(chemin)
        d = extraire_donnees_texte(texte, chemin)
        donnees_list.append(d)
    fusion = fusionner_donnees(donnees_list)
    fusion_complete = {**valeurs_par_defaut(), **fusion}  # Ajoute valeurs par défaut si manquantes
    return fusion_complete

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python pdf_data_extractor.py fichier1.pdf fichier2.pdf ...")
        sys.exit(1)
    chemins = sys.argv[1:]
    donnees = extraire_depuis_plusieurs_pdfs(chemins)
    print(json.dumps(donnees, indent=4, ensure_ascii=False))
