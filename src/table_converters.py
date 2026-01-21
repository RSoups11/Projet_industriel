"""
Fonctions de conversion de données en tableaux LaTeX.
"""

from .utils import echapper_latex_simple


def convertir_fixation_assemblage_en_tableau(texte, doc_en_annexe=None):
    """
    Convertit le texte de FIXATION et ASSEMBLAGE en tableau LaTeX.
    Le texte contient plusieurs lignes (Nature, Marque, Provenance, Documentation)
    où chaque ligne a des valeurs séparées par ;
    On transpose pour que chaque ligne originale devienne une colonne.
    
    Args:
        texte: Le texte brut à convertir
        doc_en_annexe: Liste optionnelle de réponses OUI/- pour chaque matériau
    """
    if not texte:
        return texte
    
    lignes = texte.strip().split('\n')
    
    # Parser chaque ligne : "Légende : val1 ; val2 ; val3..."
    colonnes = []
    for ligne in lignes:
        ligne = ligne.strip()
        if not ligne:
            continue
        if ':' in ligne:
            parts = ligne.split(':', 1)
            header = parts[0].strip()
            valeurs_str = parts[1].strip() if len(parts) > 1 else ""
        else:
            header = ""
            valeurs_str = ligne
        
        # Échapper les caractères LaTeX dans les valeurs
        valeurs = [echapper_latex_simple(v.strip()) for v in valeurs_str.split(';')]
        header = echapper_latex_simple(header)
        colonnes.append((header, valeurs))
    
    # Si des réponses doc_en_annexe sont fournies, remplacer la dernière colonne
    if doc_en_annexe and len(colonnes) > 0:
        # Chercher la colonne "Doc en annexe" ou la remplacer
        colonne_trouvee = False
        for i, (header, vals) in enumerate(colonnes):
            if "doc" in header.lower() and "annexe" in header.lower():
                colonnes[i] = (header, doc_en_annexe)
                colonne_trouvee = True
                break
        
        # Si pas trouvée, ajouter comme nouvelle colonne
        if not colonne_trouvee:
            colonnes.append(("Doc en annexe", doc_en_annexe))
    
    if not colonnes:
        return texte
    
    # Nombre de lignes du tableau = max des valeurs
    nb_lignes = max(len(col[1]) for col in colonnes)
    nb_colonnes = len(colonnes)
    
    # Construire le tableau LaTeX avec largeurs personnalisées
    # Colonne 1 (Nature) plus large, colonne 4 (Documentation) plus petite
    if nb_colonnes == 4:
        format_cols = "|p{5cm}|p{4cm}|p{3cm}|p{2cm}|"
    elif nb_colonnes == 5:
        format_cols = "|p{4.5cm}|p{3.5cm}|p{3cm}|p{2cm}|p{1.5cm}|"
    else:
        largeur = f"{14 // nb_colonnes:.1f}cm"
        format_cols = "|" + "|".join([f"p{{{largeur}}}"] * nb_colonnes) + "|"
    
    tableau = f"\\begin{{tabular}}{{{format_cols}}}\n\\hline\n"
    
    # Ligne d'en-tête avec les légendes
    headers = [f"\\textbf{{{col[0]}}}" for col in colonnes]
    tableau += " & ".join(headers) + " \\\\\n\\hline\n"
    
    # Lignes de données
    for i in range(nb_lignes):
        row_vals = []
        for col in colonnes:
            if i < len(col[1]):
                row_vals.append(col[1][i])
            else:
                row_vals.append("")
        tableau += " & ".join(row_vals) + " \\\\\n\\hline\n"
    
    tableau += "\\end{tabular}"
    
    return tableau


def convertir_traitement_en_tableau(texte, reponse_doc=None):
    """
    Convertit le texte de TRAITEMENT PREVENTIF/CURATIF en tableau LaTeX.
    Format : chaque ligne est "Légende : valeur"
    On crée un tableau à 4 colonnes (Nature, Marque, Provenance, Doc) avec 1 ligne de données.
    
    Args:
        texte: Texte brut du traitement
        reponse_doc: Réponse de l'utilisateur pour "Doc en annexe" ('OUI' ou 'NON')
    """
    if not texte:
        return texte
    
    lignes = texte.strip().split('\n')
    
    # Parser chaque ligne : "Légende : valeur"
    donnees = {}
    for ligne in lignes:
        ligne = ligne.strip()
        if not ligne or ':' not in ligne:
            continue
        parts = ligne.split(':', 1)
        header = parts[0].strip()
        valeur = parts[1].strip() if len(parts) > 1 else ""
        donnees[header.lower()] = (header, echapper_latex_simple(valeur))
    
    if not donnees:
        return texte
    
    # Ordre des colonnes
    ordre = [
        ("nature des éléments", "Nature des éléments"),
        ("marque, type, performance", "Marque, type, performance"),
        ("provenance", "Provenance"),
        ("documentation jointe en annexe", "Doc en annexe"),
    ]
    
    # Construire le tableau LaTeX
    format_cols = "|p{4cm}|p{6cm}|p{2.5cm}|p{1.5cm}|"
    tableau = f"\\begin{{tabular}}{{{format_cols}}}\n\\hline\n"
    
    # Ligne d'en-tête
    headers = []
    valeurs = []
    for key, display in ordre:
        headers.append(f"\\textbf{{{display}}}")
        if key == "documentation jointe en annexe" and reponse_doc:
            # Utiliser la réponse fournie par l'utilisateur
            valeurs.append(reponse_doc)
        elif key in donnees:
            valeurs.append(donnees[key][1])
        else:
            valeurs.append("")
    
    tableau += " & ".join(headers) + " \\\\\n\\hline\n"
    tableau += " & ".join(valeurs) + " \\\\\n\\hline\n"
    tableau += "\\end{tabular}"
    
    return tableau

def convertir_produit_en_bloc(texte):
    """
    Convertit le texte de PRODUIT UTILISÉ en bloc LaTeX stylisé.
    """
    if not texte:
        return texte
    
    texte_clean = texte.strip()
    texte_clean = echapper_latex_simple(texte_clean)
    
    # Créer un bloc tcolorbox stylisé pour le produit
    bloc = f"""\\begin{{tcolorbox}}[
    enhanced,
    colback=ecoFond,
    colframe=ecoBleu,
    fonttitle=\\bfseries,
    coltitle=white,
    title={{\\faIcon{{leaf}}\\hspace{{0.2em}}Produit utilisé}},
    colbacktitle=ecoBleu,
    rounded corners,
    boxrule=1pt,
    left=6pt, right=6pt, top=4pt, bottom=4pt
]
\\textbf{{{texte_clean}}}
\\end{{tcolorbox}}"""
    
    return bloc