"""
Fonctions utilitaires pour la normalisation de texte et l'échappement LaTeX.
"""

import re
import unicodedata


import sys
import os

def normaliser_texte(s: str) -> str:
    """
    Normalise un titre pour comparaison :
    - remplace les retours à la ligne par des espaces
    - remplace les apostrophes courbes par des apostrophes simples
    - enlève les accents
    - compresse les espaces multiples
    - passe en minuscules
    """
    if s is None:
        return ""
    s = s.replace("\n", " ")
    # Remplacer les apostrophes courbes (U+2019, U+2018) par apostrophe simple (U+0027)
    s = s.replace("\u2019", "'").replace("\u2018", "'")
    s = s.strip().lower()
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = re.sub(r"\s+", " ", s)
    return s

def resource_path(relative_path):
    """
    Retourne le chemin absolu d'une ressource, compatible PyInstaller.
    """
    try:
        # PyInstaller crée un dossier temporaire et y place le bundle
        base_path = sys._MEIPASS
    except AttributeError:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

def echapper_latex_simple(texte):
    """
    Échappe les caractères spéciaux LaTeX (version simple sans gestion des images).
    """
    if not texte:
        return texte
    
    replacements = [
        ('\\', r'\textbackslash{}'),
        ('&', r'\&'),
        ('%', r'\%'),
        ('$', r'\$'),
        ('#', r'\#'),
        ('_', r'\_'),
        ('{', r'\{'),
        ('}', r'\}'),
        ('~', r'\textasciitilde{}'),
        ('^', r'\textasciicircum{}'),
    ]
    
    for old, new in replacements:
        texte = texte.replace(old, new)
    
    return texte


def echapper_latex(texte):
    """
    Échappe les caractères spéciaux LaTeX pour éviter les erreurs de compilation.
    Les caractères comme _, &, %, $, #, {, }, ~, ^ sont interprétés par LaTeX.
    Convertit aussi les patterns "img : chemin" en inclusion d'image LaTeX.
    """
    if not texte:
        return texte
    
    # Pattern plus souple pour capturer les chemins d'images
    img_pattern = re.compile(r'img\s*:\s*([^\n]+?)(?:\n|$)', re.IGNORECASE)
    
    images_trouvees = []
    def remplacer_img(match):
        chemin = match.group(1).strip()
        # Ajouter .png si pas d'extension
        if not chemin.lower().endswith(('.png', '.jpg', '.jpeg', '.pdf')):
            chemin = chemin + '.png'
        idx = len(images_trouvees)
        images_trouvees.append(chemin)
        return f"%%IMG_PLACEHOLDER_{idx}%%\n"
    
    texte = img_pattern.sub(remplacer_img, texte)
    
    # Ordre important : d'abord le backslash, puis les autres
    replacements = [
        ('\\', r'\textbackslash{}'),
        ('&', r'\&'),
        ('%', r'\%'),
        ('$', r'\$'),
        ('#', r'\#'),
        ('_', r'\_'),
        ('{', r'\{'),
        ('}', r'\}'),
        ('~', r'\textasciitilde{}'),
        ('^', r'\textasciicircum{}'),
    ]
    
    for old, new in replacements:
        texte = texte.replace(old, new)
    
    # Maintenant on remet les images avec le code LaTeX approprié
    for idx, chemin in enumerate(images_trouvees):
        latex_img = f"""

\\begin{{center}}
    \\includegraphics[width=0.9\\textwidth]{{{chemin}}}
\\end{{center}}

"""
        # Le placeholder a été échappé (% -> \%), donc on cherche la version échappée
        placeholder_escaped = f"\\%\\%IMG\\_PLACEHOLDER\\_{idx}\\%\\%"
        texte = texte.replace(placeholder_escaped, latex_img)
    
    return texte


def extraire_items_depuis_texte(texte):
    """
    Transforme un texte du CSV en liste d'items.
    - Si le texte contient des '-', on coupe dessus.
    - Sinon, si ';' est présent, on coupe dessus.
    - Sinon, un seul item avec le texte complet.
    """
    texte = (texte or "").strip()
    if not texte:
        return []

    if "-" in texte:
        bruts = texte.split("-")
    elif ";" in texte:
        bruts = texte.split(";")
    else:
        return [texte]

    items = []
    for b in bruts:
        t = b.strip(" \n\r\t-")
        if t:
            items.append(t)
    return items
