import streamlit as st
import json
import os
from jinja2 import Environment, FileSystemLoader

# --- CONFIGURATION ---
DATA_DIR = "data"
TEMPLATE_DIR = "templates"       # Dossier source des .j2 (reste local)
OUTPUT_DIR = "./output_tex"      # Dossier de génération temporaire (reste local)

# NOUVEAU : Chemin vers le dossier templates principal (à la racine du projet)
# On remonte d'un niveau ("..") pour sortir de "modif_templates"
MAIN_TEMPLATES_DIR = "../templates" 

if not os.path.exists(OUTPUT_DIR):
    os.makedirs(OUTPUT_DIR)

# --- FONCTIONS UTILITAIRES ---
# ... (load_data et safe_get restent inchangés) ...

def load_data(filename):
    path = os.path.join(DATA_DIR, filename)
    if not os.path.exists(path):
        st.error(f"Fichier {filename} non trouvé")
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            if data == {}:
                st.warning(f"Fichier {filename} vide")
                return {}
            return data
    except json.JSONDecodeError as e:
        st.error(f"Erreur de format JSON dans {filename}: {str(e)}")
        return {}
    except Exception as e:
        st.error(f"Erreur lors de la lecture de {filename}: {str(e)}")
        return {}

def safe_get(data, key_path, default=""):
    keys = key_path.split('.')
    current = data
    try:
        for key in keys:
            current = current[key]
        return current
    except (KeyError, TypeError):
        return default

def save_data(filename, data):
    path = os.path.join(DATA_DIR, filename)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

def generate_tex(template_name, data, output_name):
    # Charge les templates depuis le dossier local "templates" (.j2)
    env = Environment(
        loader=FileSystemLoader(TEMPLATE_DIR),
        variable_start_string='{{', variable_end_string='}}',
        block_start_string='{%', block_end_string='%}'
    )
    try:
        template = env.get_template(template_name)
        tex_content = template.render(data)
        
        # 1. Sauvegarde dans output_tex (Local - pour vérification)
        output_path = os.path.join(OUTPUT_DIR, output_name)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(tex_content)
        
        # 2. Sauvegarde dans le dossier templates PRINCIPAL (Racine du projet)
        # MODIFICATION ICI : On utilise MAIN_TEMPLATES_DIR ("../templates")
        sync_path = os.path.join(MAIN_TEMPLATES_DIR, output_name)
        
        # Sécurité : Créer le dossier s'il n'existe pas (optionnel mais recommandé)
        os.makedirs(os.path.dirname(sync_path), exist_ok=True)

        with open(sync_path, "w", encoding="utf-8") as f:
            f.write(tex_content)
            
        return "OK"
    except Exception as e:
        return f"Erreur : {str(e)}"

# --- INTERFACE STREAMLIT ---
st.set_page_config(page_title="Générateur Mémoire Technique", layout="wide")
st.title("🏭 Générateur de Sections Techniques")

# Définition des Onglets
tabs_names = [
    "Administratif", "Moyens Matériel", "Matière Première", 
    "Sécurité & Santé", "Env. Chantiers", "Env. Atelier", 
    "HQE", "Traitement", "Organigramme"
]
tabs = st.tabs(tabs_names)

# --- 1. SITUATION ADMINISTRATIVE ---
with tabs[0]:
    st.header("Situation Administrative")
    data = load_data("situation_administrative.json")
    with st.form("form_admin"):
        st.subheader("Qualifications")
        for i, qualification in enumerate(data["qualifications"]["elements"]):
            data["qualifications"]["elements"][i] = st.text_input(f"Qualification {i+1}", qualification)
        
        st.subheader("Effectif")
        data["effectif"]["number"] = st.number_input("Effectif", value=int(data["effectif"]["number"]))
        data["effectif"]["title"] = st.text_input("Titre effectif", value=data["effectif"]["title"])
        data["effectif"]["label"] = st.text_input("Label effectif", value=data["effectif"]["label"])
        
        st.subheader("Chiffres d'affaires")
        for i, year in enumerate(data["chiffre_affaires"]["years"]):
            c1, c2 = st.columns(2)
            year["year"] = c1.text_input(f"Année {i+1}", year["year"])
            year["amount"] = c2.text_input(f"Montant {i+1}", year["amount"])
            
        if st.form_submit_button("Générer Administratif"):
            save_data("situation_administrative.json", data)
            generate_tex("situation_administrative.tex.j2", data, "situation_administrative_generated.tex")
            st.success("Fichier généré !")

# --- 2. MOYENS MATERIEL ---
with tabs[1]:
    st.header("Moyens Matériel")
    data = load_data("moyen.json")
    with st.form("form_moyens"):
        data["intro"] = st.text_area("Introduction", value=data["intro"])
        
        for section_key, content in data.items():
            if section_key == "intro":
                continue
            st.subheader(f"📦 {content['titre']}")
            text_items = "\n".join(content["elements"])
            new_items = st.text_area(f"Liste ({content['titre']})", value=text_items, height=100)
            data[section_key]["elements"] = [item for item in new_items.split("\n") if item.strip()]
            
        if st.form_submit_button("Générer Moyens"):
            save_data("moyen.json", data)
            generate_tex("moyen_materiel.tex.j2", data, "moyens_materiel_generated.tex")
            st.success("Fichier généré !")

# --- 3. MATIERE PREMIERE ---
with tabs[2]:
    st.header("Matière Première")
    data = load_data("matiere.json")
    with st.form("form_matiere"):
        st.subheader("Label Vert")
        data["certifications"]["label_vert"]["texte"] = st.text_area("Texte Label Vert", value=data["certifications"]["label_vert"]["texte"])
        
        st.subheader("Certifications PEFC/FSC")
        data["certifications"]["certifications"]["texte"] = st.text_area("Texte Certifications", value=data["certifications"]["certifications"]["texte"])
        
        st.subheader("Achats Locaux")
        data["certifications"]["local"]["texte"] = st.text_area("Texte Achats Locaux", value=data["certifications"]["local"]["texte"])
        
        st.subheader("Zone Verte")
        data["certifications"]["zone_verte"]["texte"] = st.text_area("Texte Zone Verte", value=data["certifications"]["zone_verte"]["texte"])
        
        data["sante_env"] = st.text_area("Bloc Santé & Environnement", value=data["sante_env"])
        
        if st.form_submit_button("Générer Matière"):
            save_data("matiere.json", data)
            generate_tex("matiere_premiere.tex.j2", data, "matiere_premiere_generated.tex")
            st.success("Fichier généré !")

# --- 4. SECURITE & SANTE ---
with tabs[3]:
    st.header("Sécurité et Santé")
    data = load_data("securite_sante.json")
    with st.form("form_securite"):
        data["intro"] = st.text_area("Introduction", value=data["intro"])
        data["accident_travail"]["nombre"] = st.text_input("Nombre d'accidents", value=data["accident_travail"]["nombre"])
        data["accident_travail"]["annees_sans_accident"] = st.number_input("Années sans accident", value=int(data["accident_travail"]["annees_sans_accident"]))
        
        st.subheader("Blocs de détails")
        for i, bloc in enumerate(data["blocs"]):
            st.markdown(f"**{bloc['titre']}**")
            if isinstance(bloc["contenu"], list):
                val = "\n".join(bloc["contenu"])
                new_val = st.text_area(f"Liste {bloc['titre']}", val, key=f"bloc_{i}")
                data["blocs"][i]["contenu"] = [item for item in new_val.split("\n") if item.strip()]
            else:
                data["blocs"][i]["contenu"] = st.text_area(f"Texte {bloc['titre']}", bloc["contenu"], key=f"bloc_text_{i}")

        if st.form_submit_button("Générer Sécurité"):
            save_data("securite_sante.json", data)
            # On récupère le résultat de la génération
            resultat = generate_tex("securite_sante.tex.j2", data, "securite_sante_generated.tex")
            
            if resultat == "OK":
                st.success(f"Fichiers générés avec succès dans {OUTPUT_DIR} et {TEMPLATE_DIR} !")
            else:
                # On affiche l'erreur réelle (souvent une erreur Jinja2)
                st.error(resultat)

# --- 5. ENVIRONNEMENT CHANTIERS ---
with tabs[4]:
    st.header("Environnement Chantiers")
    data = load_data("env_chantiers.json")
    if not data:
        st.error("Fichier env_chantiers.json non trouvé ou vide")
        st.stop()
        
    with st.form("form_env_chantier"):
        st.subheader("Introduction")
        data["intro"]["text1"] = st.text_area("Texte intro 1", value=data.get("intro", {}).get("text1", ""))
        data["intro"]["text2"] = st.text_area("Texte intro 2", value=data.get("intro", {}).get("text2", ""))
        data["intro"]["text3"] = st.text_area("Texte intro 3", value=data.get("intro", {}).get("text3", ""))
        
        st.subheader("Cas n°1 - Tri collectif")
        items_text = "\n".join(data["cas1"]["elements"])
        new_items = st.text_area("Items Cas 1", value=items_text, height=150)
        data["cas1"]["elements"] = [item for item in new_items.split("\n") if item.strip()]
        
        st.subheader("Cas n°2 - Gros volume")
        data["cas2"]["condition"] = st.text_input("Condition Cas 2", value=data["cas2"]["condition"])
        items_text = "\n".join(data["cas2"]["elements"])
        new_items = st.text_area("Items Cas 2", value=items_text, height=200)
        data["cas2"]["elements"] = [item for item in new_items.split("\n") if item.strip()]
        
        st.subheader("Cas n°3 - Petit volume")
        data["cas3"]["condition"] = st.text_input("Condition Cas 3", value=data["cas3"]["condition"])
        data["cas3"]["intro"] = st.text_area("Introduction Cas 3", value=data["cas3"]["intro"])
        items_text = "\n".join(data["cas3"]["elements"])
        new_items = st.text_area("Items Cas 3", value=items_text, height=200)
        data["cas3"]["elements"] = [item for item in new_items.split("\n") if item.strip()]

        if st.form_submit_button("Générer Env. Chantiers"):
            save_data("env_chantiers.json", data)
            generate_tex("demarche_env_chantiers.tex.j2", data, "demarche_env_chantiers_generated.tex")
            st.success("Fichier généré !")

# --- 6. ENVIRONNEMENT ATELIER ---
with tabs[5]:
    st.header("Environnement Atelier")
    data = load_data("env_atelier.json")
    if not data:
        st.error("Fichier env_atelier.json non trouvé ou vide")
        st.stop()
        
    with st.form("form_env_atelier"):
        st.subheader("Introduction")
        data["intro"]["text1"] = st.text_area("Texte intro 1", value=data["intro"]["text1"])
        data["intro"]["text2"] = st.text_area("Texte intro 2", value=data["intro"]["text2"])
        
        st.subheader("Actions concrètes")
        items_text = "\n".join(data["actions"]["elements"])
        new_items = st.text_area("Liste actions", value=items_text, height=200)
        data["actions"]["elements"] = [item for item in new_items.split("\n") if item.strip()]
        
        st.subheader("Tri sélectif")
        data["tri"]["intro"] = st.text_area("Introduction tri", value=data["tri"]["intro"])
        items_text = "\n".join(data["tri"]["elements"])
        new_items = st.text_area("Liste tri", value=items_text, height=300)
        data["tri"]["elements"] = [item for item in new_items.split("\n") if item.strip()]
        
        st.subheader("Réduction déchets")
        items_text = "\n".join(data["diminuer"]["elements"])
        new_items = st.text_area("Liste réduction", value=items_text, height=100)
        data["diminuer"]["elements"] = [item for item in new_items.split("\n") if item.strip()]
        
        st.subheader("Sensibilisation")
        data["sensibilisation"]["text1"] = st.text_area("Texte sensibilisation 1", value=data["sensibilisation"]["text1"])
        data["sensibilisation"]["text2"] = st.text_area("Texte sensibilisation 2", value=data["sensibilisation"]["text2"])

        if st.form_submit_button("Générer Env. Atelier"):
            save_data("env_atelier.json", data)
            generate_tex("demarche_env_atelier.tex.j2", data, "demarche_env_atelier_generated.tex")
            st.success("Fichier généré !")

# --- 7. HQE ---
with tabs[6]:
    st.header("Démarche HQE")
    data = load_data("hqe.json")
    if not data:
        st.error("Fichier hqe.json non trouvé ou vide")
        st.stop()
        
    with st.form("form_hqe"):
        data["intro"]["text"] = st.text_area("Introduction Globale", value=data["intro"]["text"])
        
        # ECO-CONSTRUCTION
        with st.expander("🌿 ECO-Construction (F1)"):
            for i, cible in enumerate(data["eco_construction"]["cibles"]):
                st.markdown(f"**{cible['titre']}**")
                for j, section in enumerate(cible["sections"]):
                    section["titre"] = st.text_input(f"Titre {i}.{j}", section["titre"], key=f"eco_f1_t_{i}_{j}")
                    section["contenu"] = st.text_area(f"Contenu {i}.{j}", section["contenu"], key=f"eco_f1_c_{i}_{j}")
        
        # ECO-GESTION
        with st.expander("⚙️ ECO-Gestion (F2)"):
            for i, cible in enumerate(data["eco_gestion"]["cibles"]):
                st.markdown(f"**{cible['titre']}**")
                if "contenu" in cible:
                    cible["contenu"] = st.text_area(f"Contenu cible {i}", cible["contenu"], key=f"eco_f2_main_{i}")
                for j, section in enumerate(cible["sections"]):
                    section["titre"] = st.text_input(f"Titre {i}.{j}", section["titre"], key=f"eco_f2_t_{i}_{j}")
                    section["contenu"] = st.text_area(f"Contenu {i}.{j}", section["contenu"], key=f"eco_f2_c_{i}_{j}")
        
        # CONFORT
        with st.expander("🏠 Confort (F3)"):
            for i, cible in enumerate(data["confort"]["cibles"]):
                st.markdown(f"**{cible['titre']}**")
                for j, section in enumerate(cible["sections"]):
                    section["titre"] = st.text_input(f"Titre {i}.{j}", section["titre"], key=f"conf_t_{i}_{j}")
                    section["contenu"] = st.text_area(f"Contenu {i}.{j}", section["contenu"], key=f"conf_c_{i}_{j}")
        
        # SANTÉ
        with st.expander("❤️ Santé (F4)"):
            for i, cible in enumerate(data["sante"]["cibles"]):
                st.markdown(f"**{cible['titre']}**")
                for j, section in enumerate(cible["sections"]):
                    section["titre"] = st.text_input(f"Titre {i}.{j}", section["titre"], key=f"sante_t_{i}_{j}")
                    section["contenu"] = st.text_area(f"Contenu {i}.{j}", section["contenu"], key=f"sante_c_{i}_{j}")

        if st.form_submit_button("Générer HQE"):
            save_data("hqe.json", data)
            generate_tex("demarche_hqe.tex.j2", data, "demarche_hqe_generated.tex")
            st.success("Fichier généré !")

# --- 8. TRAITEMENT ---
with tabs[7]:
    st.header("Méthodologie Traitement")
    data = load_data("traitement.json")
    if not data:
        st.error("Fichier traitement.json non trouvé ou vide")
        st.stop()
        
    with st.form("form_traitement"):
        data["intro"]["text"] = st.text_area("Introduction", value=data["intro"]["text"])
        
        st.subheader("Préparation")
        items_text = "\n".join(data["preparation"]["elements"])
        new_items = st.text_area("Étapes Préparation", value=items_text, height=100)
        data["preparation"]["elements"] = [item for item in new_items.split("\n") if item.strip()]
        
        c1, c2 = st.columns(2)
        with c1:
            st.subheader("Grosses pièces")
            items_text = "\n".join(data["traitement"]["grosses_pieces"]["elements"])
            new_items = st.text_area("Étapes", value=items_text, height=200)
            data["traitement"]["grosses_pieces"]["elements"] = [item for item in new_items.split("\n") if item.strip()]
        with c2:
            st.subheader("Chevrons")
            items_text = "\n".join(data["traitement"]["chevrons"]["elements"])
            new_items = st.text_area("Étapes", value=items_text, height=200)
            data["traitement"]["chevrons"]["elements"] = [item for item in new_items.split("\n") if item.strip()]

        if st.form_submit_button("Générer Traitement"):
            save_data("traitement.json", data)
            generate_tex("methodologie_traitement.tex.j2", data, "methodologie_traitement_generated.tex")
            st.success("Fichier généré !")

# --- 9. ORGANIGRAMME ---
with tabs[8]:
    st.header("Organigramme (TikZ)")
    data = load_data("organigramme.json")
    if not data:
        st.error("Fichier organigramme.json non trouvé ou vide")
        st.stop()
    
    with st.form("form_orga"):
        st.subheader("Contact")
        c1, c2, c3 = st.columns(3)
        data["contact"]["phone"] = c1.text_input("Téléphone", data["contact"]["phone"])
        data["contact"]["mobile"] = c2.text_input("Mobile", data["contact"]["mobile"])
        data["contact"]["email"] = c3.text_input("Email", data["contact"]["email"])
        
        st.subheader("Directeur")
        c1, c2 = st.columns(2)
        with c1:
            data["manager"]["name"] = st.text_input("Nom", data["manager"]["name"])
            data["manager"]["position"] = st.text_input("Titre", data["manager"]["position"])
        with c2:
            data["manager"]["experience"] = st.text_input("Expérience", data["manager"]["experience"])
            data["manager"]["education"] = st.text_input("Formation", data["manager"]["education"])
            
        st.subheader("Équipe")
        c1, c2 = st.columns(2)
        with c1:
            data["team"]["chef_name"] = st.text_input("Chef d'équipe", data["team"]["chef_name"])
            data["team"]["chef_experience"] = st.text_input("Expérience chef", data["team"]["chef_experience"])
        with c2:
            data["team"]["chef_education"] = st.text_input("Formation chef", data["team"]["chef_education"])
            data["team"]["renforts_name"] = st.text_input("Renforts", data["team"]["renforts_name"])

        st.subheader("Réunion Quotidienne")
        data["processus"]["reunion_items"] = st.text_area("Points abordés", "\n".join(data["processus"]["reunion_items"])).split("\n")

        if st.form_submit_button("Générer Organigramme .tex"):
            save_data("organigramme.json", data)
            generate_tex("organigramme_simple.tex.j2", data, "organigramme.tex")
            st.success("Fichier généré avec inclusion du PDF !")