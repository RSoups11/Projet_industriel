import jinja2
import subprocess
import os

# --- Configuration du Fichier et du Compilateur ---
NOM_TEMPLATE = 'memoire_technique.tex.j2'
NOM_FICHIER_TEX_FINAL = 'rapport_final.tex'
COMPILATEUR = 'pdflatex'

# --- 1. Dictionnaire de Données (Exemple) ---
# Ce dictionnaire doit contenir TOUTES les variables et listes
# nécessaires au remplissage de memoire_technique.tex.j2
data_projet = {
    # 1. Page de garde
    'Intitule_operation': 'Réhabilitation du Centre Sportif Ouest',
    'Lot_Intitule': 'Lot 02 - Charpente Bois',
    'Maitre_ouvrage_nom': 'Ville de Nancy, Direction des Sports',
    'Adresse_chantier': 'Avenue du 20ème Corps, 54000 Nancy',
    'Siret': '123 456 789 00010',
    'TVA': 'FR 98 123456789',
    'Email_contact': 'contact@boisettechniques.fr',
    'Site_web': 'www.boisettechniques.fr',
    'Telephone': '03 83 00 00 00',

    # 4. Détails techniques des travaux
    'Environnement_site': 'Périphérie urbaine, site partiellement occupé (accès à la piscine).',
    'Conditions_acces': 'Accès poids-lourds possible, levage par grue automotrice 30T.',
    'Contrainte_hauteur': '12 mètres',
    'Contrainte_delais': '2 mois (phase de charpente)',
    'Contrainte_site_occupe': 'Oui, protection stricte des accès publics.',
    'Plan_photos_joints': True,  # Met à True pour inclure la ligne conditionnelle

    # Données pour les tableaux I.2 et I.5 (Liste de dictionnaires)
    'Liste_materiaux': [
        {'nature': 'Poutres BLC', 'marque': 'HESS TIMBER GL28c', 'provenance': 'Allemagne',
         'documentation': 'Annexe 1 (BLC)'},
        {'nature': 'Panneaux OSB', 'marque': 'EGGER OSB/4 E1', 'provenance': 'France',
         'documentation': 'Annexe 2 (OSB)'},
    ],
    'Marque_visserie': 'HILTI',
    'Liste_produits_DPGF': [
        {'position': '02.01', 'nature': 'Fourniture et pose BLC', 'marque_type': 'GL28c', 'provenance': 'EU',
         'documentation': 'DCE 2.1'},
        {'position': '02.02', 'nature': 'Système de fixation métallique', 'marque_type': 'SIMPSON Strong-Tie',
         'provenance': 'FR', 'documentation': 'DCE 2.2'},
    ],

    # 5. Moyens humains et matériels
    'Conducteur_travaux_nom': 'Frédéric Anselm',
    'Planning_ajustable': True,  # Met à True pour inclure la ligne conditionnelle

    # 7. Annexes
    'Fiche_bois': 'Fiche technique BLC HESS (Annexe 1)',
    'Certificat_traitement': 'Certificat XILIX 3000P (Annexe 3)',
    'CV_chef': 'CV F. Anselm (Annexe 4)',
}


def generer_fichier_tex(data):
    """
    Étape 1: Utilise Jinja2 pour remplir le template et créer le fichier .tex.
    """
    print(f"Étape 1 : Rendu du template '{NOM_TEMPLATE}' en '{NOM_FICHIER_TEX_FINAL}'")

    # 💡 Configuration de l'environnement Jinja2 avec les délimiteurs personnalisés
    latex_jinja_env = jinja2.Environment(
        block_start_string='((%',
        block_end_string='%))',
        variable_start_string='((*',
        variable_end_string='*))',
        loader=jinja2.FileSystemLoader(os.path.abspath('.'))
    )

    try:
        template = latex_jinja_env.get_template(NOM_TEMPLATE)
        latex_output = template.render(data)

        # Écrire le fichier .tex
        with open(NOM_FICHIER_TEX_FINAL, 'w', encoding='utf-8') as f:
            f.write(latex_output)

        print("Rendu terminé. Fichier .tex généré avec succès.")
        return True

    except jinja2.exceptions.TemplateNotFound:
        print(
            f"❌ Erreur : Le template Jinja2 '{NOM_TEMPLATE}' n'a pas été trouvé. Assurez-vous qu'il est dans le répertoire.")
        return False
    except Exception as e:
        print(f"❌ Erreur lors du rendu Jinja2 : {e}")
        return False


def compiler_latex(nom_fichier_tex):
    """
    Étape 2: Compile le fichier .tex en PDF, en exécutant deux passes pour le sommaire.
    """
    print(f"\nÉtape 2 : Double compilation LaTeX pour {nom_fichier_tex} (nécessaire pour le sommaire).")

    # Répertoire pour les fichiers de sortie (le répertoire courant)
    repertoire_sortie = os.path.dirname(os.path.abspath(nom_fichier_tex))

    commande = [
        COMPILATEUR,
        '-interaction=nonstopmode',  # Ne pas s'arrêter pour les erreurs
        '-output-directory=' + repertoire_sortie,
        nom_fichier_tex
    ]

    for i in range(1, 3):
        print(f"-> Exécution de la compilation ({i}/2)...")
        try:
            subprocess.run(
                commande,
                check=True,
                capture_output=True,
                text=True,
                timeout=30
            )
        except subprocess.CalledProcessError as e:
            print(f"\n❌ Erreur de compilation LaTeX à la passe {i}.")
            print(
                f"Vérifiez le fichier de log ({os.path.splitext(nom_fichier_tex)[0]}.log) et le stderr : \n{e.stderr[:500]}...")
            return False
        except FileNotFoundError:
            print(f"\n❌ Erreur : Le compilateur '{COMPILATEUR}' est introuvable. Installez TeX Live/MiKTeX.")
            return False
        except subprocess.TimeoutExpired:
            print(f"\n❌ Erreur : La compilation a pris trop de temps et a été annulée.")
            return False

    print(f"\n✅ Compilation terminée. Le fichier PDF est disponible sous : {os.path.splitext(nom_fichier_tex)[0]}.pdf")
    return True


# --- Programme Principal ---
if __name__ == "__main__":
    if generer_fichier_tex(data_projet):
        compiler_latex(NOM_FICHIER_TEX_FINAL)

        # Optionnel : nettoyer les fichiers temporaires (.aux, .log, .out, etc.)
        # Ne pas le faire ici pour laisser le log en cas d'erreur.