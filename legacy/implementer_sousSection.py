import csv
import os
import jinja2
from collections import defaultdict
import unicodedata 
import re

# CONFIGURATION 
FICHIER_CSV = "bd_interface.csv"
NOM_TEMPLATE = "template.tex.j2"
NOM_FICHIER_TEX_FINAL = "resultat.tex"


def echapper_latex(texte):
    """
    Échappe les caractères spéciaux LaTeX pour éviter les erreurs de compilation.
    Les caractères comme _, &, %, $, #, {, }, ~, ^ sont interprétés par LaTeX.
    Convertit aussi les patterns "img : chemin" en inclusion d'image LaTeX.
    """
    if not texte:
        return texte
    
    # D'abord, on extrait et protège les patterns "img : chemin" avant l'échappement
    # On les remplace temporairement par des marqueurs
    import re
    import os
    
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

                    # Cas spécial : Chantiers références en rapport avec l’opération
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


def generer_fichier_tex(data, infos_projet):
    """
    Génère le .tex à partir du template Jinja et des données déjà préparées :
    - data : liste de sections hiérarchiques (venant du CSV + interactions utilisateur)
    - infos_projet : dict avec les infos de page de garde
    """
    try:
        dossier_template = os.path.dirname(NOM_TEMPLATE) or "."
        nom_template = os.path.basename(NOM_TEMPLATE)

        env = jinja2.Environment(
            loader=jinja2.FileSystemLoader(dossier_template),
            autoescape=False,
        )
        # Registrar filtro markdown_to_latex
        def markdown_to_latex(texte: str) -> str:
            if not texte:
                return texte
            return re.sub(r'\*\*([^*]+)\*\*', r'\\textbf{\1}', texte)
        env.filters['markdown_to_latex'] = markdown_to_latex
        
        template = env.get_template(nom_template)

        contexte = {
            "data": data,
            "Intitule_operation": infos_projet.get("Intitule_operation", ""),
            "Lot_Intitule": infos_projet.get("Lot_Intitule", ""),
            "Maitre_ouvrage_nom": infos_projet.get("Maitre_ouvrage_nom", ""),
            "Adresse_chantier": infos_projet.get("Adresse_chantier", ""),
        }
        print("DEBUG Intitule_operation =", repr(infos_projet.get("Intitule_operation")))
        resultat_tex = template.render(**contexte)

        with open(NOM_FICHIER_TEX_FINAL, "w", encoding="utf-8") as f_out:
            f_out.write(resultat_tex)

        print(f"Fichier LaTeX généré : {NOM_FICHIER_TEX_FINAL}")
        return True

    except Exception as e:
        print(f"Erreur lors de la génération du fichier LaTeX : {e}")
        return False


def demander_validation_ou_modif(label, texte_default):
    """
    Affiche un texte proposé et laisse l'utilisateur le valider ou le remplacer.
    """
    print(f"\nTexte proposé pour {label} :\n")
    print(texte_default)
    rep = input("\nValider ce texte ? (o/n) [o] : ").strip().lower()
    if rep in ("", "o"):
        return texte_default

    nouveau = input("Entrez le texte souhaité (une seule ligne, LaTeX autorisé) : ").strip()
    if nouveau:
        return nouveau
    return texte_default


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


def construire_liste_interactive(nom_ss, texte_csv, prefixe=None):
    """
    Construit une liste à puces LaTeX pour une sous-section donnée.
    - texte_csv donne la liste par défaut (transformée en items).
    - L'utilisateur peut garder ou remplacer la liste.
    - Si au final il n'y a aucun item, retourne "" (ss ignorée).
    - prefixe : texte à placer juste avant la liste (optionnel).
    """
    print(f"\n=== Sous-section : {nom_ss} ===")

    base_items = extraire_items_depuis_texte(texte_csv)

    if base_items:
        print("Liste proposée à partir du CSV :")
        for it in base_items:
            print(f" - {it}")
        rep = input("Souhaitez-vous modifier cette liste ? (o/n) [n] : ").strip().lower()
        if rep == "o":
            print("Entrez les éléments de la liste (une ligne par élément, laisser vide pour terminer) :")
            items = []
            while True:
                l = input(" - ").strip()
                if not l:
                    break
                items.append(l)
        else:
            items = base_items
    else:
        print("Aucune liste prédéfinie dans le CSV.")
        print("Entrez les éléments de la liste (une ligne par élément, laisser vide pour terminer) :")
        items = []
        while True:
            l = input(" - ").strip()
            if not l:
                break
            items.append(l)

    if not items:
        return ""

    itemize = "\\begin{itemize}\n" + "\n".join(f"    \\item {it}" for it in items) + "\n\\end{itemize}"

    if prefixe:
        return prefixe + "\n\n" + itemize
    return itemize


def construire_liste_directe(prefixe=None):
    """
    Construit une liste à puces uniquement à partir de la saisie utilisateur.
    Si aucun item saisi, renvoie "".
    """
    print("Entrez les éléments de la liste (une ligne par élément, laisser vide pour terminer) :")
    items = []
    while True:
        l = input(" - ").strip()
        if not l:
            break
        items.append(l)

    if not items:
        return ""

    itemize = "\\begin{itemize}\n" + "\n".join(f"    \\item {it}" for it in items) + "\n\\end{itemize}"

    if prefixe:
        return prefixe + "\n\n" + itemize
    return itemize


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


def convertir_fixation_assemblage_en_tableau(texte):
    """
    Convertit le texte de FIXATION et ASSEMBLAGE en tableau LaTeX.
    Le texte contient plusieurs lignes (Nature, Marque, Provenance, Documentation)
    où chaque ligne a des valeurs séparées par ;
    On transpose pour que chaque ligne originale devienne une colonne.
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
    
    if not colonnes:
        return texte
    
    # Nombre de lignes du tableau = max des valeurs
    nb_lignes = max(len(col[1]) for col in colonnes)
    nb_colonnes = len(colonnes)
    
    # Construire le tableau LaTeX avec largeurs personnalisées
    # Colonne 1 (Nature) plus large, colonne 4 (Documentation) plus petite
    if nb_colonnes == 4:
        format_cols = "|p{5cm}|p{4cm}|p{3cm}|p{2cm}|"
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


def convertir_traitement_en_tableau(texte):
    """
    Convertit le texte de TRAITEMENT PREVENTIF/CURATIF en tableau LaTeX.
    Format : chaque ligne est "Légende : valeur"
    On crée un tableau à 4 colonnes (Nature, Marque, Provenance, Doc) avec 1 ligne de données.
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
        if key in donnees:
            valeurs.append(donnees[key][1])
        else:
            valeurs.append("")
    
    tableau += " & ".join(headers) + " \\\\\n\\hline\n"
    tableau += " & ".join(valeurs) + " \\\\\n\\hline\n"
    tableau += "\\end{tabular}"
    
    return tableau


# EXÉCUTION
if __name__ == "__main__":
    # Lecture du CSV
    donnees_brutes = charger_donnees_depuis_csv(FICHIER_CSV)
    if not donnees_brutes:
        print("Aucune donnée trouvée dans le CSV, arrêt.")
        exit(1)

    # Infos de la page de garde
    print("=== Informations de la page de garde ===")
    intitule_operation = input("Intitulé de l'opération : ").strip()
    lot_intitule = input(
        "Intitulé du lot [Lot N°02 - Charpente bois] : "
    ).strip() or "Lot N°02 - Charpente bois"
    maitre_ouvrage = input("Maître d'ouvrage : ").strip()
    adresse_chantier = input("Adresse du chantier : ").strip()

    infos_projet = {
        "Intitule_operation": intitule_operation,
        "Lot_Intitule": lot_intitule,
        "Maitre_ouvrage_nom": maitre_ouvrage,
        "Adresse_chantier": adresse_chantier,
    }

    data_finale = []
    titres_a_ignorer = set()

    # -----------------------------
    # Section "Contexte du projet"
    # -----------------------------
    print("\n=== Section : Contexte du projet ===")

    section_contexte = None
    for section in donnees_brutes:
        if normaliser_texte(section["titre"]) == "contexte du projet":
            section_contexte = section
            break

    if section_contexte is not None:
        nouvelles_sous_sections = []

        # Inputs utilisateur
        date_visite = input(
            "Date de la visite de site (laisser vide pour ne pas afficher la sous-section 'Contexte') : "
        ).strip()

        environnement_texte = input(
            "Texte pour la sous-section 'Environnement' (laisser vide pour ignorer) : "
        ).strip()

        acces_texte = input(
            "Texte pour la sous-section 'Accès chantier et stationnement' (laisser vide pour ignorer) : "
        ).strip()

        levage_texte = input(
            "Texte pour la sous-section 'Levage' (laisser vide pour ignorer) : "
        ).strip()

        print(
            "Liste des contraintes du chantier (une contrainte par ligne, laisser vide pour terminer) :"
        )
        contraintes = []
        while True:
            ligne = input(" - ").strip()
            if not ligne:
                break
            contraintes.append(ligne)

        if contraintes:
            contraintes_texte = "\\begin{itemize}\n" + "\n".join(
                f"    \\item {c}" for c in contraintes
            ) + "\n\\end{itemize}"
        else:
            contraintes_texte = ""

        # Construction des sous-sections
        for ss in section_contexte["sous_sections"]:
            nom_ss = ss["nom"].strip()
            nom_lc = nom_ss.lower()

            # Sous-section "Contexte"
            if nom_lc == "contexte" or nom_lc == "contextes":
                if date_visite:
                    base = ss.get("contenu", "").strip()
                    if not base:
                        base = "Nous sommes passés faire la visite sur le site le"
                    contenu = f"{base} {date_visite}."
                    nouvelles_sous_sections.append(
                        {"nom": nom_ss, "contenu": contenu, "image": ss.get("image")}
                    )

            # Sous-section "Environnement"
            elif "environnement" in nom_lc:
                if environnement_texte:
                    nouvelles_sous_sections.append(
                        {
                            "nom": nom_ss,
                            "contenu": environnement_texte,
                            "image": ss.get("image"),
                        }
                    )

            # Sous-section "Accès chantier et stationnement"
            elif "acces chantier et stationnement" == nom_lc:
                if acces_texte:
                    nouvelles_sous_sections.append(
                        {
                            "nom": nom_ss,
                            "contenu": acces_texte,
                            "image": ss.get("image"),
                        }
                    )

            # Sous-section "Levage"
            elif nom_lc == "levage":
                if levage_texte:
                    nouvelles_sous_sections.append(
                        {
                            "nom": nom_ss,
                            "contenu": levage_texte,
                            "image": ss.get("image"),
                        }
                    )

            # Sous-section "Contraintes du chantier"
            elif "contraintes du chantier" == nom_lc:
                if contraintes_texte:
                    nouvelles_sous_sections.append(
                        {
                            "nom": nom_ss,
                            "contenu": contraintes_texte,
                            "image": ss.get("image"),
                        }
                    )

            else:
                continue
        
        if nouvelles_sous_sections:
            # L'utilisateur a rempli au moins une sous-section -> on garde
            data_finale.append(
                {
                    "titre": section_contexte["titre"],
                    "sous_sections": nouvelles_sous_sections,
                }
            )
        else:
            # L'utilisateur n'a rien mis -> on ne veut PAS que le fallback récupère cette section
            titres_a_ignorer.add(section_contexte["titre"])

    else:
        print("Section 'Contexte du projet' introuvable dans le CSV.")

    # ------------------------------------------
    # Section "Liste des materiaux mis en oeuvre"
    # ------------------------------------------
    print("\n=== Section : Liste des materiaux mis en oeuvre ===")

    section_materiaux = None
    for section in donnees_brutes:
        if "liste des materiaux mis en oeuvre" in normaliser_texte(section["titre"]):
            section_materiaux = section
            break

    if section_materiaux is not None:
        nouvelles_sous_sections_mat = []

        # on garde les 5 SS prévues, et seulement si une image est définie
        noms_cibles = {
            "une matiere premiere de qualite certifiee",
            "fixation et assemblage",
            "traitement preventif des bois",
            "traitement curatif des bois",
            "methodologie de traitement",
        }

        for ss in section_materiaux["sous_sections"]:
            nom_ss = ss["nom"].strip()
            nom_lc = nom_ss.lower()

            # Récupération des données du CSV
            image_path = (ss.get("image") or "").strip()
            texte_csv = ss.get("contenu", "").strip()
            texte_brut = ss.get("contenu_brut", "").strip()

            # On vérifie si c'est une section cible
            if nom_lc in noms_cibles:
                # Cas spécial : FIXATION et ASSEMBLAGE -> tableau
                if "fixation" in nom_lc and "assemblage" in nom_lc:
                    texte_csv = convertir_fixation_assemblage_en_tableau(texte_brut)
                # Cas spécial : TRAITEMENT PREVENTIF ou CURATIF -> tableau
                elif "traitement preventif" in nom_lc or "traitement curatif" in nom_lc:
                    texte_csv = convertir_traitement_en_tableau(texte_brut)
                
                nouvelles_sous_sections_mat.append(
                    {
                        "nom": nom_ss,
                        "contenu": texte_csv,
                        "image": image_path,
                    }
                )

        if nouvelles_sous_sections_mat:
            data_finale.append(
                {
                    "titre": section_materiaux["titre"],
                    "sous_sections": nouvelles_sous_sections_mat,
                }
            )
        else:
            print("Aucune sous-section avec image trouvée pour 'Liste des materiaux mis en oeuvre'.")
    else:
        print("Section 'Liste des materiaux mis en oeuvre' introuvable dans le CSV.")

    # ------------------------------------------
    # Section "Moyens humains affectes au projet"
    # ------------------------------------------
    print("\n=== Section : Moyens humains affectes au projet ===")

    section_mh = None
    for section in donnees_brutes:
        if normaliser_texte(section["titre"]) == "moyens humains affectes au projet":
            section_mh = section
            break

    if section_mh is not None:
        nouvelles_ss_mh = []

        for ss in section_mh["sous_sections"]:
            nom_ss = ss["nom"].strip()
            nom_lc = normaliser_texte(nom_ss)  # Utiliser normaliser_texte pour gérer les apostrophes
            texte_csv = ss.get("contenu", "")

            # Organisation du chantier
            if nom_lc == "organisation du chantier":
                print("\nSous-section 'Organisation du chantier'")

                # Chargé d'affaires
                default_charge_nom = "Frederic Anselm"
                print(f"\nLe chargé d'affaires : {default_charge_nom}")
                rep = input("Valider ce nom ? (o/n) [o] : ").strip().lower()
                if rep in ("", "o"):
                    charge_nom = default_charge_nom
                else:
                    charge_nom = input("Entrez le nom du chargé d'affaires (laisser vide pour ignorer) : ").strip()

                # Chef d'équipe
                chef_noms_str = input(
                    "Entrez le(s) nom(s) du chef d'équipe (séparés par des virgules, laisser vide pour ignorer) : "
                ).strip()
                chef_noms = [n.strip() for n in chef_noms_str.split(",") if n.strip()]

                # Charpentiers
                charp_noms_str = input(
                    "Entrez le(s) nom(s) des charpentiers (séparés par des virgules, laisser vide pour ignorer) : "
                ).strip()
                charp_noms = [n.strip() for n in charp_noms_str.split(",") if n.strip()]

                contenu_parts = []

                # Textes par défaut (découpés à partir du csv)
                if charge_nom:
                    texte_charge = (
                        "Il est l’unique interlocuteur de tous les intervenants du projet, "
                        "il participe aux réunions de chantiers, établit la descente de charges, "
                        "la note de calculs et les plans en tenant compte des interfaces avec les autres lots. "
                        "Il organise les travaux de préparation et de levage en assurant un contrôle qualité "
                        "des ouvrages exécutés à tous les stades de la construction."
                    )
                    texte_charge = demander_validation_ou_modif(
                        f"le chargé d'affaires ({charge_nom})", texte_charge
                    )
                    bloc = (
                        f"\\textbf{{Le chargé d'affaires :}} {charge_nom}\\\\\n"
                        f"{texte_charge}\n"
                    )
                    contenu_parts.append(bloc)

                if chef_noms:
                    noms_chef = ", ".join(chef_noms)
                    texte_chef = (
                        "Il dirige les opérations de taille et de levage de la charpente en se basant sur les PAC "
                        "et en étroite collaboration avec le chargé d’affaires. "
                        "Il applique les consignes de sécurité du PPSPS."
                    )
                    texte_chef = demander_validation_ou_modif(
                        f"le chef d'équipe ({noms_chef})", texte_chef
                    )
                    bloc = (
                        f"\\textbf{{Le chef d'équipe :}} {noms_chef}\\\\\n"
                        f"{texte_chef}\n"
                    )
                    contenu_parts.append(bloc)

                if charp_noms:
                    noms_charp = ", ".join(charp_noms)
                    texte_charp = (
                        "Les charpentiers seront affectés à ce projet en plus du chef d’équipe. "
                        "Cet effectif pourra être augmenté selon les contraintes du planning "
                        "en phase d’exécution des travaux."
                    )
                    texte_charp = demander_validation_ou_modif(
                        f"les charpentiers ({noms_charp})", texte_charp
                    )
                    bloc = (
                        f"\\textbf{{Les charpentiers :}} {noms_charp}\\\\\n"
                        f"{texte_charp}\n"
                    )
                    contenu_parts.append(bloc)

                if contenu_parts:
                    contenu_ss = "\n\n".join(contenu_parts)
                    nouvelles_ss_mh.append(
                        {"nom": nom_ss, "contenu": contenu_ss, "image": ss.get("image")}
                    )

            # Sécurité et santé sur les chantiers / Organigramme fonctionnel...
            elif nom_lc == "securite et sante sur les chantiers" or \
                 nom_lc == "organigramme fonctionnel de l'equipe affectee aux projets":
                # On reprend texte + image du CSV sans interaction
                if texte_csv or ss.get("image"):
                    print(f"  -> Ajout de la sous-section '{nom_ss}' (texte: {bool(texte_csv)}, image: {ss.get('image')})")
                    nouvelles_ss_mh.append(
                        {
                            "nom": nom_ss,
                            "contenu": texte_csv,
                            "image": ss.get("image"),
                        }
                    )

            # Sous-sections gérées comme listes modifiables
            elif nom_lc in {
                "conception et precision",
                "securite",
                "atelier de taille",
                "transport",
                "levage",
                "machine portative",
                "protection/nettoyage du batiment",
                "gestion des déchets",
                "gestion des dechets",  # au cas où sans accent
            }:
                prefixe = None
                if nom_lc == "atelier de taille":
                    prefixe = "Opération à effectuer en atelier pour le projet :"

                contenu_liste = construire_liste_interactive(nom_ss, texte_csv, prefixe=prefixe)

                if contenu_liste:
                    nouvelles_ss_mh.append(
                        {"nom": nom_ss, "contenu": contenu_liste, "image": ss.get("image")}
                    )

            else:
                continue

        if nouvelles_ss_mh:
            data_finale.append(
                {
                    "titre": section_mh["titre"],
                    "sous_sections": nouvelles_ss_mh,
                }
            )
    else:
        print("Section 'Moyens humains affectes au projet' introuvable dans le CSV.")

    # ------------------------------------------
    # Section "Méthodologie / Chronologie"
    # ------------------------------------------
    print("\n=== Section : Méthodologie / Chronologie ===")

    section_metho = None
    for section in donnees_brutes:
        if "methodologie/chronologie" in normaliser_texte(section["titre"]):
            section_metho = section
            break

    if section_metho is not None:
        nouvelles_ss_metho = []

        for ss in section_metho["sous_sections"]:
            nom_ss = ss["nom"].strip()
            nom_lc = nom_ss.lower()
            texte_csv = ss.get("contenu", "")
            image = ss.get("image")

            # Fabrication/Taille en atelier
            if "fabrication/taille en atelier" == nom_lc or \
               "fabrication / taille en atelier" == nom_lc:
                print("\nSous-section 'Fabrication/Taille en atelier'")
                prefixe = "Opérations à réaliser en atelier :"
                contenu = construire_liste_directe(prefixe=prefixe)
                if contenu:
                    nouvelles_ss_metho.append(
                        {"nom": nom_ss, "contenu": contenu, "image": image}
                    )

            # Transport et levage
            elif nom_lc == "transport et levage":
                print("\nSous-section 'Transport et levage'")
                base = (texte_csv or "").strip()
                prefixe = base + "\n\nOpérations à réaliser pour le projet :" if base else "Opérations à réaliser pour le projet :"
                contenu_liste = construire_liste_directe(prefixe=prefixe)
                if contenu_liste:
                    nouvelles_ss_metho.append(
                        {"nom": nom_ss, "contenu": contenu_liste, "image": image}
                    )
                elif base:
                    nouvelles_ss_metho.append(
                        {"nom": nom_ss, "contenu": base, "image": image}
                    )

            # Chantier
            elif nom_lc == "chantier":
                print("\nSous-section 'Chantier'")
                base = (texte_csv or "").strip()
                prefixe = base + "\n\nOpérations à réaliser pour le projet :" if base else "Opérations à réaliser pour le projet :"
                contenu_liste = construire_liste_directe(prefixe=prefixe)
                if contenu_liste:
                    nouvelles_ss_metho.append(
                        {"nom": nom_ss, "contenu": contenu_liste, "image": image}
                    )
                elif base:
                    nouvelles_ss_metho.append(
                        {"nom": nom_ss, "contenu": base, "image": image}
                    )

            # Protection de l’existant ou ses ouvrages pour ce projet
            elif "protection de l'existant" in nom_lc or \
                 "protection de l’existant" in nom_lc:
                contenu = construire_liste_interactive(nom_ss, texte_csv)
                if contenu:
                    nouvelles_ss_metho.append(
                        {"nom": nom_ss, "contenu": contenu, "image": image}
                    )

            # Organisation en matière d’hygiène et de sécurité
            elif "organisation en matiere d'hygiene et de securite" in nom_lc or \
                 "organisation en matière d’hygiène et de sécurité" in nom_lc:
                contenu = construire_liste_interactive(nom_ss, texte_csv)
                if contenu:
                    nouvelles_ss_metho.append(
                        {"nom": nom_ss, "contenu": contenu, "image": image}
                    )

            # Protection/Nettoyage
            elif "protection/nettoyage" in nom_lc:
                contenu = construire_liste_interactive(nom_ss, texte_csv)
                if contenu:
                    nouvelles_ss_metho.append(
                        {"nom": nom_ss, "contenu": contenu, "image": image}
                    )

            # Autres SS : texte CSV simple
            else:
                if texte_csv or image:
                    print("lalalalalalal" +nom_ss)
                    nouvelles_ss_metho.append(
                        {"nom": nom_ss, "contenu": texte_csv, "image": image}
                    )

        if nouvelles_ss_metho:
            data_finale.append(
                {
                    "titre": section_metho["titre"],
                    "sous_sections": nouvelles_ss_metho,
                }
            )
    else:
        print("Section 'Méthodologie / Chronologie' introuvable dans le CSV.")

    # ------------------------------------------
    # Section "Chantiers références en rapport avec l’opération :"
    # ------------------------------------------
    print("\n=== Section : Chantiers références en rapport avec l’opération ===")

    section_ref = None
    for section in donnees_brutes:
        titre_norm = normaliser_texte(section["titre"])
        if "chantiers references en rapport avec l'operation" in titre_norm:
            section_ref = section
            break

    if section_ref is not None:
        print("Entrez les chantiers de référence (une ligne par chantier, laisser vide pour terminer) :")
        items = []
        while True:
            l = input(" - ").strip()
            if not l:
                break
            items.append(l)

        if items:
            contenu_liste = "\\begin{itemize}\n" + "\n".join(
                f"    \\item {it}" for it in items
            ) + "\n\\end{itemize}"

            nouvelles_ss_ref = []
            for ss in section_ref["sous_sections"]:
                nouvelles_ss_ref.append(
                    {
                        "nom": ss["nom"],
                        "contenu": contenu_liste,
                        "image": ss.get("image"),
                    }
                )

            if nouvelles_ss_ref:
                data_finale.append(
                    {
                        "titre": section_ref["titre"],
                        "sous_sections": nouvelles_ss_ref,
                    }
                )
        else:
            print("Aucune référence saisie, section ignorée.")
    else:
        print("Section 'Chantiers références en rapport avec l’opération' introuvable dans le CSV.")

    # ------------------------------------------
    # Ajout de TOUTES les autres sections non traitées explicitement
    # (texte + image bruts du CSV)
    # ------------------------------------------
    titres_deja = {section["titre"] for section in data_finale}

    for section in donnees_brutes:
        # on saute ce qui est déjà ajouté
        if section["titre"] in titres_deja:
            continue
        # on saute aussi ce qu'on a explicitement décidé d'ignorer
        if section["titre"] in titres_a_ignorer:
            continue

        ss_list = []
        for ss in section["sous_sections"]:
            if ss.get("contenu") or ss.get("image"):
                ss_list.append(
                    {
                        "nom": ss["nom"],
                        "contenu": ss.get("contenu", ""),
                        "image": ss.get("image"),
                    }
                )
        if ss_list:
            data_finale.append(
                {
                    "titre": section["titre"],
                    "sous_sections": ss_list,
                }
            )

    # -----------------------------
    # Génération du .tex
    # -----------------------------
    if not data_finale:
        print("Aucune section à générer (toutes les sous-sections sont vides).")
    else:
        generer_fichier_tex(data_finale, infos_projet)
