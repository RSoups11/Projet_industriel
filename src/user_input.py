"""
Gestion des interactions utilisateur (saisie, validation, listes).
"""

from .utils import extraire_items_depuis_texte


def selectionner_propositions(nom_ss, texte_csv, prefixe=None):
    """
    Permet à l'utilisateur de sélectionner parmi les propositions séparées par '/// ou ///'.
    
    - Affiche les propositions numérotées
    - L'utilisateur peut entrer un numéro seul (ex: 1, 2, 3)
    - Si la proposition est "autre", demande un texte personnalisé
    - Retourne le TEXTE COMPLET avec [OPTION] remplacé par la proposition sélectionnée
    """
    print(f"\n{'='*60}")
    nom_display = nom_ss if len(nom_ss) <= 50 else nom_ss[:47] + "..."
    print(f"📋 Sous-section : {nom_display}")
    print(f"{'='*60}")
    
    # Trouver la ligne avec les propositions (contient '/// ou ///')
    lignes = texte_csv.split('\n')
    proposition_line = None
    
    for ligne in lignes:
        if '/// ou ///' in ligne:
            proposition_line = ligne
            break
    
    if not proposition_line:
        print("Aucune proposition trouvée dans le CSV.")
        return None
    
    # Extraire les propositions PROPRES (sans texte avant/après)
    propositions = [p.strip() for p in proposition_line.split('/// ou ///') if p.strip()]
    
    if not propositions:
        print("Aucune proposition trouvée.")
        return None
    
    # Afficher les propositions numérotées
    print("\n🎯 Propositions disponibles:\n")
    for i, prop in enumerate(propositions, 1):
        print(f"   [{i}] {prop}")
    
    print("\n" + "-"*60)
    print("📝 Sélectionnez une option (1, 2, 3, etc.) - Défaut: 1")
    print("-"*60)
    choix = input("> ").strip()
    
    if choix == "":
        choix = "1"
    
    if choix == "0":
        return None
    
    try:
        idx = int(choix)
        if 1 <= idx <= len(propositions):
            proposition_selectionnee = propositions[idx - 1].strip()
            
            # Si la proposition est "autre", demander un texte personnalisé
            if proposition_selectionnee.lower() == "autre":
                texte_personnalise = input("Entrez votre texte personnalisé : ").strip()
                if texte_personnalise:
                    proposition_selectionnee = texte_personnalise
                else:
                    proposition_selectionnee = "autre"
            
            # Remplacer [OPTION] par la proposition sélectionnée et supprimer [PROPOSITIONS]
            texte_final = texte_csv.replace("[OPTION]", proposition_selectionnee)
            texte_final = texte_final.replace("\n[PROPOSITIONS]\n", "")
            texte_final = texte_final.replace("[PROPOSITIONS]\n", "")
            # Supprimer la ligne avec les propositions (/// ou ///)
            lignes_final = []
            for ligne in texte_final.split('\n'):
                if '/// ou ///' not in ligne:
                    lignes_final.append(ligne)
            texte_final = '\n'.join(lignes_final).strip()
            
            return texte_final
        else:
            print(f"   ⚠️  Numéro {idx} invalide")
            return None
    except ValueError:
        print("   ⚠️  Entrée invalide")
        return None


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


def construire_liste_interactive(nom_ss, texte_csv, prefixe=None):
    """
    Construit une liste à puces LaTeX pour une sous-section donnée.
    - texte_csv donne la liste par défaut (transformée en items).
    - L'utilisateur peut garder ou remplacer la liste.
    - Si au final il n'y a aucun item, retourne "" (ss ignorée).
    - prefixe : texte à placer juste avant la liste (optionnel).
    """
    print(f"\n{'='*60}")
    nom_display = nom_ss if len(nom_ss) <= 50 else nom_ss[:47] + "..."
    print(f"📋 Sous-section : {nom_display}")
    print(f"{'='*60}")

    base_items = extraire_items_depuis_texte(texte_csv)

    if base_items:
        print("\n✅ Liste proposée à partir du CSV:\n")
        for i, it in enumerate(base_items, 1):
            print(f"   {i}. {it}")
        print("\n" + "-"*60)
        rep = input("Souhaitez-vous modifier cette liste ? (o/n) [n] : ").strip().lower()
        if rep == "o":
            print("\n✏️  Entrez les éléments (une ligne par élément, vide pour terminer):\n")
            items = []
            while True:
                l = input("   • ").strip()
                if not l:
                    break
                items.append(l)
        else:
            items = base_items
    else:
        print("\n⚠️  Aucune liste prédéfinie dans le CSV.")
        print("\n✏️  Entrez les éléments (une ligne par élément, vide pour terminer):\n")
        items = []
        while True:
            l = input("   • ").strip()
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
    print("\n✏️  Entrez les éléments (une ligne par élément, vide pour terminer):\n")
    items = []
    while True:
        l = input("   • ").strip()
        if not l:
            break
        items.append(l)

    if not items:
        return ""

    itemize = "\\begin{itemize}\n" + "\n".join(f"    \\item {it}" for it in items) + "\n\\end{itemize}"

    if prefixe:
        return prefixe + "\n\n" + itemize
    return itemize


def saisir_infos_projet():
    """
    Demande à l'utilisateur les informations de la page de garde.
    Retourne un dictionnaire avec les infos.
    """
    print("=== Informations de la page de garde ===")
    intitule_operation = input("Intitulé de l'opération : ").strip().upper()
    lot_intitule = (input(
        "Intitulé du lot [CHARPENTE BOIS] : "
    ).strip() or "CHARPENTE BOIS").upper()
    maitre_ouvrage = input("Maître d'ouvrage : ").strip()
    adresse_chantier = input("Adresse du chantier : ").strip()

    return {
        "Intitule_operation": intitule_operation,
        "Lot_Intitule": lot_intitule,
        "Maitre_ouvrage_nom": maitre_ouvrage,
        "Adresse_chantier": adresse_chantier,
    }


def saisir_liste_items(prompt_intro):
    """
    Affiche un prompt et récupère une liste d'items saisis par l'utilisateur.
    Retourne une liste (peut être vide).
    """
    print(prompt_intro)
    items = []
    while True:
        l = input(" - ").strip()
        if not l:
            break
        items.append(l)
    return items


def saisir_chemin_image(description, obligatoire=False):
    """
    Demande à l'utilisateur un chemin vers une image.
    Supporte les formats : jpg, jpeg, png, pdf, svg
    
    Args:
        description: Description de l'image attendue
        obligatoire: Si True, redemande tant que le chemin n'est pas valide
        
    Returns:
        Le chemin de l'image ou None si non fourni
    """
    import os
    
    formats_valides = {'.jpg', '.jpeg', '.png', '.pdf', '.svg'}
    
    while True:
        print(f"\n📷 {description}")
        print("   Formats acceptés : jpg, jpeg, png, pdf, svg")
        print("   (Laisser vide pour ignorer)")
        chemin = input("   Chemin de l'image : ").strip()
        
        if not chemin:
            if obligatoire:
                print("   ⚠️  Cette image est obligatoire.")
                continue
            return None
        
        # Vérifier le format
        ext = os.path.splitext(chemin.lower())[1]
        if ext not in formats_valides:
            print(f"   ❌ Format non supporté : {ext}")
            print(f"      Formats acceptés : {', '.join(formats_valides)}")
            continue
        
        # Vérifier que le fichier existe
        if not os.path.isfile(chemin):
            print(f"   ❌ Fichier non trouvé : {chemin}")
            if obligatoire:
                continue
            reponse = input("   Continuer quand même ? (o/n) : ").strip().lower()
            if reponse != 'o':
                continue
        
        return chemin


def saisir_chemin_image_avec_defaut(description, chemin_defaut):
    """
    Demande à l'utilisateur un chemin vers une image avec une valeur par défaut.
    
    Args:
        description: Description de l'image attendue
        chemin_defaut: Chemin par défaut si l'utilisateur appuie sur Entrée
        
    Returns:
        Le chemin de l'image (défaut si Entrée, None si '0')
    """
    import os
    
    formats_valides = {'.jpg', '.jpeg', '.png', '.pdf', '.svg'}
    
    print(f"\n📷 {description}")
    print(f"   [Défaut: {chemin_defaut}]")
    print("   (Entrée = défaut, 0 = ignorer)")
    chemin = input("   Chemin de l'image : ").strip()
    
    # Si vide, utiliser le défaut
    if not chemin:
        print(f"   ✓ Utilisation de l'image par défaut")
        return chemin_defaut
    
    # Si 0, ignorer
    if chemin == '0':
        print("   ✗ Image ignorée")
        return None
    
    # Vérifier le format
    ext = os.path.splitext(chemin.lower())[1]
    if ext not in formats_valides:
        print(f"   ⚠️ Format non reconnu, utilisation quand même : {chemin}")
    
    return chemin


def saisir_images_projet():
    """
    Demande tous les chemins d'images pour le projet.
    
    Returns:
        Un dictionnaire avec les clés :
        - image_garde : Image pour la page de garde
        - attestation_visite : Attestation de visite
        - plan_emplacement : Plan/image de l'emplacement
        - image_grue : Image de grue pour transport/levage
    """
    print("\n" + "="*60)
    print("           IMAGES DU MÉMOIRE TECHNIQUE")
    print("="*60)
    print("(Appuyez sur Entrée pour utiliser l'image par défaut)")
    
    images = {}
    
    # Chemins par défaut (relatifs depuis output/)
    default_garde = "../images/exemple_pagegarde.jpeg"
    default_attestation = "../images/attestation_visite.png"
    default_plan = "../images/vue_aerienne.png"
    default_grue = "../images/grue.png"
    
    # Image page de garde
    images['image_garde'] = saisir_chemin_image_avec_defaut(
        "Image pour la page de garde",
        default_garde
    )
    
    # Attestation de visite
    images['attestation_visite'] = saisir_chemin_image_avec_defaut(
        "Attestation de visite (après la section Contexte)",
        default_attestation
    )
    
    # Plan d'emplacement
    images['plan_emplacement'] = saisir_chemin_image_avec_defaut(
        "Plan de masse / Vue aérienne de l'emplacement",
        default_plan
    )
    
    # Image grue
    images['image_grue'] = saisir_chemin_image_avec_defaut(
        "Image de grue/levage (pour la section Transport et Levage)",
        default_grue
    )
    
    # Résumé
    nb_images = sum(1 for v in images.values() if v)
    print(f"\n✅ {nb_images} image(s) configurée(s)")
    
    return images


def demander_doc_en_annexe(materiaux):
    """
    Demande à l'utilisateur pour chaque matériau s'il a une documentation en annexe.
    
    Args:
        materiaux: Liste des noms de matériaux
        
    Returns:
        Liste de réponses: 'OUI' ou '-' pour chaque matériau
    """
    print(f"\n{'='*60}")
    print("📋 Fixation et Assemblage - Documentation en Annexe")
    print(f"{'='*60}\n")
    
    reponses = []
    
    for i, materiau in enumerate(materiaux, 1):
        # Limiter le nom pour l'affichage
        nom_affichage = materiau if len(materiau) <= 50 else materiau[:47] + "..."
        
        print(f"{i}. {nom_affichage}")
        
        while True:
            rep = input("   Documentation en annexe? (OUI/NON) : ").strip().upper()
            
            if rep in ("OUI", "NON"):
                # Convertir NON en '-'
                valeur = "OUI" if rep == "OUI" else "-"
                reponses.append(valeur)
                break
            else:
                print("   ⚠️  Réponse invalide. Tapez 'OUI' ou 'NON'")
    
    print(f"\n✅ {len(reponses)} matériau(x) traité(s)\n")
    return reponses