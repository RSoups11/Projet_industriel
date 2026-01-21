"""
Traitement des sections spécifiques du mémoire technique.
Chaque fonction traite une section particulière et retourne les sous-sections formatées.
"""

from .utils import normaliser_texte
from .user_input import (
    demander_validation_ou_modif,
    construire_liste_interactive,
    construire_liste_directe,
    saisir_liste_items,
    selectionner_propositions,
    demander_doc_en_annexe,
)
from .table_converters import convertir_fixation_assemblage_en_tableau, convertir_traitement_en_tableau, convertir_produit_en_bloc


def traiter_section_contexte(donnees_brutes):
    """
    Traite la section "Contexte du projet".
    Retourne (section_finale, a_ignorer) où:
    - section_finale: dict avec titre et sous_sections, ou None
    - a_ignorer: True si la section doit être ignorée par le fallback
    """
    print(f"\n{'#'*60}")
    print("# SECTION : Contexte du projet" + " "*29 + "#")
    print(f"{'#'*60}")

    section_contexte = None
    for section in donnees_brutes:
        if normaliser_texte(section["titre"]) == "contexte du projet":
            section_contexte = section
            break

    if section_contexte is None:
        print("Section 'Contexte du projet' introuvable dans le CSV.")
        return None, False

    nouvelles_sous_sections = []

    # Récupérer les contenus bruts du CSV pour les propositions
    contenus_csv = {}
    for ss in section_contexte["sous_sections"]:
        nom_lc = ss["nom"].strip().lower()
        contenus_csv[nom_lc] = ss.get("contenu_brut", "") or ss.get("contenu", "")

    # Inputs utilisateur pour la sous-section Contexte
    date_visite = input(
        "Date de la visite de site (laisser vide pour ne pas afficher) : "
    ).strip()

    # Environnement : sélection parmi les propositions du CSV
    env_csv = contenus_csv.get("environnement", "")
    if "/// ou ///" in env_csv:
        environnement_texte = selectionner_propositions("Environnement", env_csv)
    else:
        environnement_texte = input(
            "Texte pour la sous-section 'Environnement' (laisser vide pour ignorer) : "
        ).strip()

    acces_texte = input(
        "Texte pour la sous-section 'Accès chantier et stationnement' (laisser vide pour ignorer) : "
    ).strip()

    # Levage : sélection parmi les propositions du CSV
    levage_csv = contenus_csv.get("levage", "")
    if "/// ou ///" in levage_csv:
        levage_texte = selectionner_propositions("Levage", levage_csv)
    else:
        levage_texte = input(
            "Texte pour la sous-section 'Levage' (laisser vide pour ignorer) : "
        ).strip()

    # Respect des délais du planning prévisionnel
    respect_delais_csv = contenus_csv.get("respect des délais du planning prévisionnel", "")
    if "/// ou ///" in respect_delais_csv:
        respect_delais_texte = selectionner_propositions("Respect des délais du planning prévisionnel", respect_delais_csv)
    elif respect_delais_csv:
        respect_delais_texte = respect_delais_csv
    else:
        respect_delais_texte = ""

    # Contraintes du chantier : sélection parmi les propositions du CSV
    contraintes_csv = contenus_csv.get("contraintes du chantier", "")
    if "/// ou ///" in contraintes_csv:
        contraintes_texte = selectionner_propositions("Contraintes du chantier", contraintes_csv)
    else:
        contraintes = saisir_liste_items(
            "Liste des contraintes du chantier (une contrainte par ligne, laisser vide pour terminer) :"
        )
        if contraintes:
            contraintes_texte = "\\begin{itemize}\n" + "\n".join(
                f"    \\item {c}" for c in contraintes
            ) + "\n\\end{itemize}"
        else:
            contraintes_texte = ""

    # Extraire contraintes EN PREMIER
    contraintes_item = None
    autres_items = []
    
    for ss in section_contexte["sous_sections"]:
        nom_ss = ss["nom"].strip()
        nom_lc = nom_ss.lower()

        if "contextes, environnement" in nom_lc:
            continue

        if "contraintes du chantier" == nom_lc:
            if contraintes_texte:
                contraintes_item = {
                    "nom": nom_ss,
                    "contenu": contraintes_texte,
                    "image": ss.get("image"),
                }

        elif nom_lc == "contexte" or nom_lc == "contextes":
            if date_visite :
                parties = []
                if date_visite:
                    parties.append(f"Nous sommes rendus sur les lieux {date_visite}.")

                contenu = " ".join(parties)
                autres_items.append({
                    "nom": nom_ss,
                    "contenu": contenu,
                    "image": ss.get("image"),
                })

        elif "environnement" in nom_lc:
            if environnement_texte:
                autres_items.append({
                    "nom": nom_ss,
                    "contenu": environnement_texte,
                    "image": ss.get("image"),
                })

        elif "acces chantier et stationnement" == nom_lc:
            if acces_texte:
                autres_items.append({
                    "nom": nom_ss,
                    "contenu": acces_texte,
                    "image": ss.get("image"),
                })

        elif nom_lc == "levage":
            if levage_texte:
                autres_items.append({
                    "nom": nom_ss,
                    "contenu": levage_texte,
                    "image": ss.get("image"),
                })

        elif "respect des délais" in nom_lc:
            if respect_delais_texte:
                autres_items.append({
                    "nom": nom_ss,
                    "contenu": respect_delais_texte,
                    "image": ss.get("image"),
                })

    # Ajouter contraintes EN PREMIER, puis les autres
    if contraintes_item:
        nouvelles_sous_sections.append(contraintes_item)
    nouvelles_sous_sections.extend(autres_items)

    if nouvelles_sous_sections:
        return {
            "titre": section_contexte["titre"],
            "sous_sections": nouvelles_sous_sections,
        }, False
    else:
        return None, True  # À ignorer par le fallback


def traiter_section_moyens_materiel(donnees_brutes):
    """
    Traite la section "MOYENS MATERIEL AFFECTES AU PROJET".
    Retourne la section formatée ou None.
    """
    print(f"\n{'#'*60}")
    print("# SECTION : Moyens matériel affectés au projet" + " "*14 + "#")
    print(f"{'#'*60}")

    section_materiel = None
    for section in donnees_brutes:
        if "moyens materiel affectes au projet" in normaliser_texte(section["titre"]):
            section_materiel = section
            break

    if section_materiel is None:
        print("Section 'Moyens matériel affectés au projet' introuvable dans le CSV.")
        return None

    # Récupérer toutes les sous-sections
    nouvelles_sous_sections = []
    for ss in section_materiel["sous_sections"]:
        nom_ss = ss["nom"].strip()
        contenu = ss.get("contenu", "").strip()
        image = (ss.get("image") or "").strip()

        if contenu or image:
            nouvelles_sous_sections.append({
                "nom": nom_ss,
                "contenu": contenu,
                "image": image,
            })

    if nouvelles_sous_sections:
        return {
            "titre": section_materiel["titre"],
            "sous_sections": nouvelles_sous_sections,
        }
    else:
        return None


def traiter_section_materiaux(donnees_brutes):
    """
    Traite la section "Liste des materiaux mis en oeuvre".
    """
    print(f"\n{'#'*60}")
    print("# SECTION : Matériaux mis en œuvre" + " "*24 + "#")
    print(f"{'#'*60}")

    section_materiaux = None
    for section in donnees_brutes:
        if "liste des materiaux mis en oeuvre" in normaliser_texte(section["titre"]):
            section_materiaux = section
            break

    if section_materiaux is None:
        print("Section 'Liste des materiaux mis en oeuvre' introuvable dans le CSV.")
        return None

    nouvelles_sous_sections = []

    noms_cibles = {
        "une matiere premiere de qualite certifiee",
        "fixation et assemblage",
        "produit utilise",
        "traitement preventif des bois",
        "traitement curatif des bois",
        "methodologie de traitement",
        "produits proposes par l'intermediaire des fiches technique",
    }

    for ss in section_materiaux["sous_sections"]:
        nom_ss = ss["nom"].strip()
        nom_lc = normaliser_texte(nom_ss)

        image_path = (ss.get("image") or "").strip()
        texte_csv = ss.get("contenu", "").strip()
        texte_brut = ss.get("contenu_brut", "").strip()

        if nom_lc in noms_cibles:
            # Cas spécial : FIXATION et ASSEMBLAGE -> tableau
            if "fixation" in nom_lc and "assemblage" in nom_lc:
                # Extraire la liste des matériaux de la première ligne
                lignes = texte_brut.strip().split('\n')
                materiaux = []
                if lignes:
                    premiere_ligne = lignes[0]
                    if ':' in premiere_ligne:
                        valeurs_str = premiere_ligne.split(':', 1)[1].strip()
                        materiaux = [v.strip() for v in valeurs_str.split(';') if v.strip()]
                
                # Demander à l'utilisateur les réponses
                doc_reponses = None
                if materiaux:
                    doc_reponses = demander_doc_en_annexe(materiaux)
                
                texte_csv = convertir_fixation_assemblage_en_tableau(texte_brut, doc_reponses)
            # Cas spécial : PRODUIT UTILISÉ -> bloc stylisé
            elif "produit utilisé" in nom_lc:
                texte_csv = convertir_produit_en_bloc(texte_brut)
            # Cas spécial : TRAITEMENT PREVENTIF ou CURATIF -> tableau
            elif "traitement preventif" in nom_lc or "traitement curatif" in nom_lc:
                # Demander à l'utilisateur pour Doc en annexe (OUI/NON)
                doc_reponses = ["OUI", "NON"]  # Options disponibles
                reponse_doc = None
                
                # Déterminer le label du traitement
                label = "Traitement Préventif" if "preventif" in nom_lc else "Traitement Curatif"
                
                print(f"\n{'='*60}")
                print(f"📋 {label} - Documentation en Annexe")
                print(f"{'='*60}\n")
                
                while True:
                    rep = input(f"{label} - Documentation en annexe? (OUI/NON) : ").strip().upper()
                    if rep in ("OUI", "NON"):
                        reponse_doc = rep
                        break
                    else:
                        print("   ⚠️  Réponse invalide. Tapez 'OUI' ou 'NON'")
                
                texte_csv = convertir_traitement_en_tableau(texte_brut, reponse_doc)
            
            nouvelles_sous_sections.append({
                "nom": nom_ss,
                "contenu": texte_csv,
                "image": image_path,
            })

    if nouvelles_sous_sections:
        return {
            "titre": section_materiaux["titre"],
            "sous_sections": nouvelles_sous_sections,
        }
    else:
        print("Aucune sous-section trouvée pour 'Liste des materiaux mis en oeuvre'.")
        return None


def traiter_section_moyens_humains(donnees_brutes):
    """
    Traite la section "Moyens humains affectes au projet".
    """
    print(f"\n{'#'*60}")
    print("# SECTION : Moyens humains" + " "*33 + "#")
    print(f"{'#'*60}")

    section_mh = None
    for section in donnees_brutes:
        if normaliser_texte(section["titre"]) == "moyens humains affectes au projet":
            section_mh = section
            break

    if section_mh is None:
        print("Section 'Moyens humains affectes au projet' introuvable dans le CSV.")
        return None

    nouvelles_ss_mh = []

    for ss in section_mh["sous_sections"]:
        nom_ss = ss["nom"].strip()
        nom_lc = normaliser_texte(nom_ss)
        texte_csv = ss.get("contenu", "")

        if nom_lc == "organisation du chantier":
            contenu_ss = _traiter_organisation_chantier()
            if contenu_ss:
                nouvelles_ss_mh.append({
                    "nom": nom_ss,
                    "contenu": contenu_ss,
                    "image": ss.get("image")
                })

        elif nom_lc == "securite et sante sur les chantiers" or \
             "organigramme" in nom_lc:
            if texte_csv or ss.get("image"):
                print(f"  -> Ajout de la sous-section '{nom_ss}' (texte: {bool(texte_csv)}, image: {ss.get('image')})")
                nouvelles_ss_mh.append({
                    "nom": nom_ss,
                    "contenu": texte_csv,
                    "image": ss.get("image"),
                })

        elif nom_lc in {
            "conception et precision",
            "securite",
            "atelier de taille",
            "transport",
            "levage",
            "machine portative",
            "protection/nettoyage du batiment",
            "gestion des dechets",
        }:
            prefixe = None
            if nom_lc == "atelier de taille":
                prefixe = "Opération à effectuer en atelier pour le projet :"

            contenu_liste = construire_liste_interactive(nom_ss, texte_csv, prefixe=prefixe)

            if contenu_liste:
                nouvelles_ss_mh.append({
                    "nom": nom_ss,
                    "contenu": contenu_liste,
                    "image": ss.get("image")
                })

    if nouvelles_ss_mh:
        return {
            "titre": section_mh["titre"],
            "sous_sections": nouvelles_ss_mh,
        }
    return None


def _traiter_organisation_chantier():
    """
    Sous-fonction pour traiter la sous-section 'Organisation du chantier'.
    """
    print("\n📌 Sous-section : Organisation du chantier")
    print("-"*60)

    # Chargé d'affaires
    default_charge_nom = "Frederic Anselm"
    print(f"\n👤 Le chargé d'affaires : {default_charge_nom}")
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

    if charge_nom:
        texte_charge = (
            "Il est l'unique interlocuteur de tous les intervenants du projet, "
            "il participe aux réunions de chantiers, établit la descente de charges, "
            "la note de calculs et les plans en tenant compte des interfaces avec les autres lots. "
            "Il organise les travaux de préparation et de levage en assurant un contrôle qualité "
            "des ouvrages exécutés à tous les stades de la construction."
        )
        texte_charge = demander_validation_ou_modif(f"le chargé d'affaires ({charge_nom})", texte_charge)
        bloc = f"\\textbf{{Le chargé d'affaires :}} {charge_nom}\\\\\n{texte_charge}\n"
        contenu_parts.append(bloc)

    if chef_noms:
        noms_chef = ", ".join(chef_noms)
        texte_chef = (
            "Il dirige les opérations de taille et de levage de la charpente en se basant sur les PAC "
            "et en étroite collaboration avec le chargé d'affaires. "
            "Il applique les consignes de sécurité du PPSPS."
        )
        texte_chef = demander_validation_ou_modif(f"le chef d'équipe ({noms_chef})", texte_chef)
        bloc = f"\\textbf{{Le chef d'équipe :}} {noms_chef}\\\\\n{texte_chef}\n"
        contenu_parts.append(bloc)

    if charp_noms:
        noms_charp = ", ".join(charp_noms)
        texte_charp = (
            "Les charpentiers seront affectés à ce projet en plus du chef d'équipe. "
            "Cet effectif pourra être augmenté selon les contraintes du planning "
            "en phase d'exécution des travaux."
        )
        texte_charp = demander_validation_ou_modif(f"les charpentiers ({noms_charp})", texte_charp)
        bloc = f"\\textbf{{Les charpentiers :}} {noms_charp}\\\\\n{texte_charp}\n"
        contenu_parts.append(bloc)

    if contenu_parts:
        return "\n\n".join(contenu_parts)
    return None


def traiter_section_methodologie(donnees_brutes):
    """
    Traite la section "Méthodologie / Chronologie".
    """
    print(f"\n{'#'*60}")
    print("# SECTION : Méthodologie / Chronologie" + " "*22 + "#")
    print(f"{'#'*60}")

    section_metho = None
    for section in donnees_brutes:
        titre_norm = normaliser_texte(section["titre"])
        if "methodologie" in titre_norm and "chronologie" in titre_norm:
            section_metho = section
            break

    if section_metho is None:
        print("Section 'Méthodologie / Chronologie' introuvable dans le CSV.")
        return None

    nouvelles_ss_metho = []

    for ss in section_metho["sous_sections"]:
        nom_ss = ss["nom"].strip()
        nom_lc = nom_ss.lower()
        texte_csv = ss.get("contenu", "")
        image = ss.get("image")

        if "fabrication/taille en atelier" == nom_lc or "fabrication / taille en atelier" == nom_lc:
            if '/// ou ///' in texte_csv:
                contenu = selectionner_propositions(nom_ss, texte_csv, prefixe="LES OPERATIONS REALISEES POUR CE PROJET :")
            else:
                prefixe = "Opérations à réaliser en atelier :"
                contenu = construire_liste_directe(prefixe=prefixe)
            if contenu:
                nouvelles_ss_metho.append({"nom": nom_ss, "contenu": contenu, "image": image})

        elif nom_lc == "transport et levage":
            if '/// ou ///' in texte_csv:
                # Séparer les propositions des autres contenus
                import re
                # Pattern pour détecter "Ouvrages livrés sur chantier :"
                ouvrages_pattern = r'ouvrages\s+livr[eé]s\s+sur\s+chantier\s*:'
                ouvrages_match = re.search(ouvrages_pattern, texte_csv, re.IGNORECASE)
                
                if ouvrages_match:
                    # Prendre le texte avant "Ouvrages" comme propositions
                    texte_propositions = texte_csv[:ouvrages_match.start()].strip()
                    # Le texte après "Ouvrages..." comme complément
                    ouvrages_texte = texte_csv[ouvrages_match.start():].strip()
                    
                    # Appeler selectionner_propositions avec juste les propositions
                    contenu = selectionner_propositions(nom_ss, texte_propositions)
                    
                    # Ajouter la section "Ouvrages livrés sur chantier" en dessous
                    if contenu and ouvrages_texte:
                        contenu += "\n\n\\vspace{0.3cm}\n\\noindent\n" + ouvrages_texte
                else:
                    # Pas de section "Ouvrages", utiliser tout comme propositions
                    contenu = selectionner_propositions(nom_ss, texte_csv)
            else:
                base = (texte_csv or "").strip()
                prefixe = base + "\n\nOpérations à réaliser pour le projet :" if base else "Opérations à réaliser pour le projet :"
                contenu = construire_liste_directe(prefixe=prefixe)
                if not contenu and base:
                    contenu = base
            if contenu:
                nouvelles_ss_metho.append({"nom": nom_ss, "contenu": contenu, "image": image})

        elif nom_lc == "chantier":
            if '/// ou ///' in texte_csv:
                contenu = selectionner_propositions(nom_ss, texte_csv)
            else:
                base = (texte_csv or "").strip()
                prefixe = base + "\n\nOpérations à réaliser pour le projet :" if base else "Opérations à réaliser pour le projet :"
                contenu = construire_liste_directe(prefixe=prefixe)
                if not contenu and base:
                    contenu = base
            if contenu:
                nouvelles_ss_metho.append({"nom": nom_ss, "contenu": contenu, "image": image})

        elif "protection de l'existant" in nom_lc:
            contenu = construire_liste_interactive(nom_ss, texte_csv)
            if contenu:
                nouvelles_ss_metho.append({"nom": nom_ss, "contenu": contenu, "image": image})

        elif "organisation en matiere d'hygiene et de securite" in nom_lc:
            contenu = construire_liste_interactive(nom_ss, texte_csv)
            if contenu:
                nouvelles_ss_metho.append({"nom": nom_ss, "contenu": contenu, "image": image})

        elif "protection/nettoyage" in nom_lc:
            contenu = construire_liste_interactive(nom_ss, texte_csv)
            if contenu:
                nouvelles_ss_metho.append({"nom": nom_ss, "contenu": contenu, "image": image})

        else:
            if texte_csv or image:
                nouvelles_ss_metho.append({"nom": nom_ss, "contenu": texte_csv, "image": image})

    if nouvelles_ss_metho:
        return {
            "titre": section_metho["titre"],
            "sous_sections": nouvelles_ss_metho,
        }
    return None


def traiter_section_references(donnees_brutes):
    """
    Traite la section "Chantiers références en rapport avec l'opération".
    Utilise le système de propositions avec /// ou ///.
    """
    print(f"\n{'#'*60}")
    print("# SECTION : Chantiers références" + " "*28 + "#")
    print(f"{'#'*60}")

    section_ref = None
    for section in donnees_brutes:
        titre_norm = normaliser_texte(section["titre"])
        if "chantiers references en rapport avec l'operation" in titre_norm:
            section_ref = section
            break

    if section_ref is None:
        print("Section 'Chantiers références en rapport avec l'opération' introuvable dans le CSV.")
        return None

    # Récupérer le texte du CSV (qui contient les propositions)
    texte_csv = ""
    for ss in section_ref["sous_sections"]:
        # Utiliser contenu_brut pour avoir le texte non échappé
        texte_csv = ss.get("contenu_brut", "") or ss.get("contenu", "")
        if texte_csv:
            break

    # Utiliser le système de propositions
    if '/// ou ///' in texte_csv:
        contenu = selectionner_propositions("Chantiers de référence", texte_csv)
    else:
        # Fallback: saisie manuelle
        items = saisir_liste_items(
            "Entrez les chantiers de référence (une ligne par chantier, laisser vide pour terminer) :"
        )
        if items:
            contenu = "\\begin{itemize}\n" + "\n".join(
                f"    \\item {it}" for it in items
            ) + "\n\\end{itemize}"
        else:
            contenu = None

    if contenu:
        return {
            "titre": section_ref["titre"],
            "sous_sections": [{
                "nom": "Références",
                "contenu": contenu,
                "image": None,
            }],
        }
    else:
        print("Aucune référence sélectionnée, section ignorée.")
    
    return None


def ajouter_sections_restantes(donnees_brutes, data_finale, titres_a_ignorer):
    """
    Ajoute toutes les sections non traitées explicitement (texte + image bruts du CSV).
    """
    titres_deja = {section["titre"] for section in data_finale}

    for section in donnees_brutes:
        if section["titre"] in titres_deja:
            continue
        if section["titre"] in titres_a_ignorer:
            continue

        ss_list = []
        for ss in section["sous_sections"]:
            if ss.get("contenu") or ss.get("image"):
                ss_list.append({
                    "nom": ss["nom"],
                    "contenu": ss.get("contenu", ""),
                    "image": ss.get("image"),
                })
        
        if ss_list:
            data_finale.append({
                "titre": section["titre"],
                "sous_sections": ss_list,
            })
