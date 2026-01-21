"""
Génération du fichier LaTeX à partir du template Jinja2. 
"""

import os
import re
import jinja2

from .config import DEFAULT_TEMPLATE, DEFAULT_OUTPUT_TEX, TEMPLATES_DIR


def markdown_to_latex(texte: str) -> str:
    """Convertit les patterns markdown en LaTeX: **texte** -> \\textbf{texte}"""
    if not texte:
        return texte
    # Remplacer **texte** par \textbf{texte}
    texte = re.sub(r'\*\*([^*]+)\*\*', r'\\textbf{\1}', texte)
    return texte


def generer_fichier_tex(data, infos_projet, images=None, template_path=None, output_path=None):
    """
    Génère le .tex à partir du template Jinja et des données déjà préparées :
    - data : liste de sections hiérarchiques (venant du CSV + interactions utilisateur)
    - infos_projet : dict avec les infos de page de garde
    - images : dict avec les chemins des images (optionnel)
    - template_path : chemin du template (optionnel, défaut: DEFAULT_TEMPLATE)
    - output_path : chemin du fichier de sortie (optionnel, défaut: DEFAULT_OUTPUT_TEX)
    """
    if template_path is None:
        template_path = DEFAULT_TEMPLATE
    if output_path is None:
        output_path = DEFAULT_OUTPUT_TEX
    if images is None:
        images = {}
    
    try:
        dossier_template = os.path.dirname(template_path) or TEMPLATES_DIR
        nom_template = os.path.basename(template_path)

        env = jinja2.Environment(
            loader=jinja2.FileSystemLoader(dossier_template),
            autoescape=False,
        )
        # Registrar o filtro markdown_to_latex
        env.filters['markdown_to_latex'] = markdown_to_latex
        
        template = env.get_template(nom_template)

        contexte = {
            "data": data,
            "Intitule_operation": infos_projet.get("Intitule_operation", ""),
            "Lot_Intitule": infos_projet.get("Lot_Intitule", ""),
            "Maitre_ouvrage_nom": infos_projet.get("Maitre_ouvrage_nom", ""),
            "Adresse_chantier": infos_projet.get("Adresse_chantier", ""),
            # Images du projet
            "image_garde": images.get("image_garde", ""),
            "attestation_visite": images.get("attestation_visite", ""),
            "plan_emplacement": images.get("plan_emplacement", ""),
            "image_grue": images.get("image_grue", ""),
        }
        
        print("DEBUG Intitule_operation =", repr(infos_projet.get("Intitule_operation")))
        resultat_tex = template.render(**contexte)

        # S'assurer que le dossier de sortie existe
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        with open(output_path, "w", encoding="utf-8") as f_out:
            f_out.write(resultat_tex)

        print(f"Fichier LaTeX généré : {output_path}")
        return True

    except Exception as e:
        print(f"Erreur lors de la génération du fichier LaTeX : {e}")
        return False