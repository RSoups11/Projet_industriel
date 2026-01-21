import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox
import pandas as pd
import os
import re
import threading
import time
from src.utils import echapper_latex
from src.latex_generator import generer_fichier_tex
from src.table_converters import convertir_fixation_assemblage_en_tableau, convertir_traitement_en_tableau

# --- CONFIGURATION ---
ctk.set_appearance_mode("System")
ctk.set_default_color_theme("blue")

# VALEURS PAR DÉFAUT
DEFAUTS = {
    "intitule": "",
    "lot": "Lot N°02 - Charpente bois",
    "moa": "",
    "adresse": ""
}

# LABELS PROPRES POUR LA SIDEBAR
SIDEBAR_LABELS = {
    "intitule": "Intitulé Opération",
    "lot": "Intitulé Lot",
    "moa": "Maître d'Ouvrage",
    "adresse": "Adresse Chantier"
}

# ORDRE STRICT DES SECTIONS
SECTIONS_AUTORISEES = [
    "SITUATION ADMINISTRATIVE DE L'ENTREPRISE",
    "CONTEXTE DU PROJET",
    "LISTE DES MATERIAUX MIS EN OEUVRE",
    "MOYENS HUMAINS AFFECTES AU PROJET",
    "MOYENS MATERIEL AFFECTES AU PROJET",
    "Méthodologie / Chronologie",
    "Chantiers références en rapport avec l'opération",
    "Planning",
    "Annexes"
]

def nettoyer_str(valeur):
    if pd.isna(valeur): return ""
    s = str(valeur).strip()
    return "" if s.lower() == "nan" else s

def normaliser_titre(titre):
    s = nettoyer_str(titre)
    if not s: return ""
    s = s.replace('Œ', 'OE').replace('œ', 'oe')
    return re.sub(r'[^a-zA-Z0-9]', '', s).upper()

class LoadingWindow(ctk.CTkToplevel):
    def __init__(self, master, message="Chargement..."):
        super().__init__(master)
        self.title("")
        self.geometry("300x120")
        self.resizable(False, False)
        
        # Centrer la fenêtre par rapport au master
        self.transient(master)
        
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        
        self.label = ctk.CTkLabel(self, text=message, font=("Arial", 14))
        self.label.grid(row=0, column=0, pady=(20, 10))
        
        self.progressbar = ctk.CTkProgressBar(self, orientation="horizontal", mode="indeterminate")
        self.progressbar.grid(row=1, column=0, pady=(0, 20), padx=20, sticky="ew")
        self.progressbar.start()

        # Centrage écran et focus
        try:
            # Force la mise à jour pour avoir les dimensions correctes
            self.update_idletasks() 
            x = master.winfo_x() + (master.winfo_width() // 2) - 150
            y = master.winfo_y() + (master.winfo_height() // 2) - 60
            self.geometry(f"+{x}+{y}")
            
            # CRUCIAL : Attendre que la fenêtre soit visible avant de grab
            # Sinon "grab failed: window not viewable"
            self.wait_visibility() 
            self.grab_set()
            self.focus_force()
        except:
            # Fallback si erreur (ex: fenêtre fermée trop vite)
            pass

    def close(self):
        try:
            self.grab_release()
            self.destroy()
        except:
            pass

class ScrollableSectionFrame(ctk.CTkScrollableFrame):
    def __init__(self, master, title, data_rows):
        super().__init__(master, label_text=title)
        self.widgets = {} 
        self.seen_subs = set() 
        
        for index, row in data_rows.iterrows():
            sous_section = nettoyer_str(row.get('sous-section', ''))
            texte_brut = nettoyer_str(row.get('texte', ''))
            image = nettoyer_str(row.get('image', ''))

            if not sous_section and not texte_brut and not image: continue

            sub_lower = sous_section.lower().strip()

            # --- FILTRES SPECIFIQUES ---
            if "chargé d'affaires" in sub_lower and "chef d'équipe" in sub_lower and "charpentiers" in sub_lower:
                continue
            
            # Gestion doublons et Contexte Unique
            is_contexte = ("contexte" == sub_lower or "contextes" == sub_lower) and "projet" in title.lower()
            if is_contexte:
                if "contexte_unique_marker" in self.seen_subs: continue
                self.seen_subs.add("contexte_unique_marker")
            elif sub_lower:
                if sub_lower in self.seen_subs: continue
                self.seen_subs.add(sub_lower)

            # --- DÉTECTION DU TYPE DE WIDGET ---

            # CAS 1 : Section Contexte (Date & Adresse)
            if is_contexte:
                frame_ctx = ctk.CTkFrame(self, fg_color="transparent")
                frame_ctx.pack(fill="x", pady=5)
                ctk.CTkLabel(frame_ctx, text="Date de visite :", width=100, anchor="w").pack(side="left")
                date_var = ctk.StringVar()
                ctk.CTkEntry(frame_ctx, textvariable=date_var, placeholder_text="ex: 12/09/2024").pack(side="left", fill="x", expand=True, padx=5)
                
                frame_adr = ctk.CTkFrame(self, fg_color="transparent")
                frame_adr.pack(fill="x", pady=5)
                ctk.CTkLabel(frame_adr, text="Adresse visite :", width=100, anchor="w").pack(side="left")
                adr_var = ctk.StringVar()
                ctk.CTkEntry(frame_adr, textvariable=adr_var, placeholder_text="(Laisser vide si idem chantier)").pack(side="left", fill="x", expand=True, padx=5)

                self.widgets[index] = {
                    "type": "smart_contexte", 
                    "date_var": date_var, 
                    "adr_var": adr_var, 
                    "row": row, 
                    "nom": sous_section
                }

            # CAS 2 : Sections avec options dans le TITRE (Chef d'équipe, Charpentiers...)
            elif "/// ou ///" in sous_section:
                # 1. Parsing du Titre (Noms)
                parts_titre = sous_section.split(":")
                prefix_titre = parts_titre[0].strip() + " :"
                options_noms = []
                if len(parts_titre) > 1:
                    options_noms = [o.strip() for o in parts_titre[1].split("/// ou ///") if o.strip()]

                ctk.CTkLabel(self, text=prefix_titre, anchor="w", font=("Arial", 12, "bold")).pack(fill="x", pady=(15, 2))

                frame_noms = ctk.CTkFrame(self, fg_color="transparent")
                frame_noms.pack(fill="x", padx=10)
                vars_noms = []
                for nom in options_noms:
                    v = ctk.StringVar(value=nom) # Coché par défaut
                    cb = ctk.CTkCheckBox(frame_noms, text=nom, variable=v, onvalue=nom, offvalue="")
                    cb.select()
                    cb.pack(anchor="w", pady=2)
                    vars_noms.append(v)

                # 2. Parsing du Texte (Description / Quantité)
                vars_text = None
                text_widget = None

                if "/// ou ///" in texte_brut:
                    # Cas spécial Charpentiers "1 à 2" vs "3..."
                    options_text = [o.strip() for o in texte_brut.split("/// ou ///") if o.strip()]
                    
                    if any(o.startswith("1") for o in options_text) and any(o.startswith("3") for o in options_text):
                        ctk.CTkLabel(self, text="Effectif :", anchor="w", font=("Arial", 11, "italic")).pack(fill="x", padx=10, pady=(5, 0))
                        
                        frame_rb = ctk.CTkFrame(self, fg_color="transparent")
                        frame_rb.pack(fill="x", padx=10)
                        
                        var_choix = ctk.StringVar(value="3") # 3 par défaut
                        
                        opt1 = next((o for o in options_text if o.startswith("1")), "1 à 2")
                        ctk.CTkRadioButton(frame_rb, text=opt1, variable=var_choix, value="1").pack(anchor="w", pady=2)
                        
                        opt3_full = next((o for o in options_text if o.startswith("3")), "3")
                        ctk.CTkRadioButton(frame_rb, text="3", variable=var_choix, value="3").pack(anchor="w", pady=2)
                        
                        ctk.CTkLabel(self, text="Détails (pour l'option 3) :", anchor="w", font=("Arial", 10)).pack(fill="x", padx=25, pady=(2, 0))
                        text_box_3 = ctk.CTkTextbox(self, height=60)
                        text_box_3.insert("0.0", opt3_full)
                        text_box_3.pack(fill="x", padx=25, pady=(0, 10))
                        
                        vars_text = {"type": "special_radio", "var": var_choix, "opt1_val": opt1, "text_box": text_box_3}

                    else:
                        # Cas standard choix multiples texte
                        frame_txt_opts = ctk.CTkFrame(self, fg_color="transparent")
                        frame_txt_opts.pack(fill="x", padx=10)
                        vars_text_list = []
                        for txt in options_text:
                            v = ctk.StringVar(value=txt)
                            cb = ctk.CTkCheckBox(frame_txt_opts, text=txt, variable=v, onvalue=txt, offvalue="")
                            cb.select()
                            cb.pack(anchor="w", pady=2)
                            vars_text_list.append(v)
                        vars_text = {"type": "checkboxes", "vars": vars_text_list}
                
                else:
                    h = 60 if len(texte_brut) > 60 else 30
                    text_widget = ctk.CTkTextbox(self, height=h)
                    text_widget.insert("0.0", texte_brut)
                    text_widget.pack(fill="x", padx=10, pady=5)

                self.widgets[index] = {
                    "type": "title_options_section",
                    "prefix_titre": prefix_titre,
                    "vars_noms": vars_noms,
                    "vars_text": vars_text,
                    "text_widget": text_widget,
                    "row": row,
                    "nom": sous_section 
                }

            # CAS 3 : Choix Multiples simples dans le TEXTE
            elif "/// ou ///" in texte_brut:
                ctk.CTkLabel(self, text=sous_section, anchor="w", font=("Arial", 12, "bold")).pack(fill="x", pady=(15, 5))

                lignes = texte_brut.split('\n')
                prefixe_lines = []
                options = []
                
                for ligne in lignes:
                    if "/// ou ///" in ligne:
                        opts = [opt.strip() for opt in ligne.split("/// ou ///") if opt.strip()]
                        options.extend(opts)
                    else:
                        if ligne.strip(): prefixe_lines.append(ligne.strip())
                
                prefixe_text = "\n".join(prefixe_lines)
                if prefixe_text:
                    ctk.CTkLabel(self, text=prefixe_text, anchor="w", justify="left").pack(fill="x", pady=(2, 5))

                checkboxes = []
                frame_checks = ctk.CTkFrame(self, fg_color="transparent")
                frame_checks.pack(fill="x", pady=2, padx=10)
                
                for opt in options:
                    var = ctk.StringVar(value=opt) 
                    cb = ctk.CTkCheckBox(frame_checks, text=opt, variable=var, onvalue=opt, offvalue="")
                    cb.select()
                    cb.pack(anchor="w", pady=2)
                    checkboxes.append(var)

                self.widgets[index] = {
                    "type": "multi_check", 
                    "prefix": prefixe_text,
                    "vars": checkboxes, 
                    "row": row, 
                    "nom": sous_section
                }

            # CAS 4 : Texte libre standard
            else:
                ctk.CTkLabel(self, text=sous_section, anchor="w", font=("Arial", 12, "bold")).pack(fill="x", pady=(15, 5))
                
                texte_clean = texte_brut.replace('"date?"', "").replace('"adresse?"', "").replace("inserer plan de masse et vue aerienne", "")
                texte_clean = texte_clean.replace(", ,", ".").strip()
                if texte_clean.startswith(","): texte_clean = texte_clean[1:].strip()

                h = 60 if len(texte_clean) > 60 else 30
                textbox = ctk.CTkTextbox(self, height=h)
                textbox.insert("0.0", texte_clean)
                textbox.pack(fill="x", pady=5)
                self.widgets[index] = {"type": "text", "widget": textbox, "row": row, "nom": sous_section}

    def get_data(self):
        processed_subs = []
        for idx, item in self.widgets.items():
            nom_section = item["nom"]
            content = ""
            is_latex_formatted = False
            
            if item["type"] == "smart_contexte":
                d = item["date_var"].get().strip()
                a = item["adr_var"].get().strip()
                if d:
                    content = f"Nous sommes passés faire la visite sur le site le {d}."
                    if a: content += f" Adresse : {a}."
            
            elif item["type"] == "title_options_section":
                noms_sel = [v.get() for v in item["vars_noms"] if v.get()]
                if noms_sel:
                    nom_section = f"{item['prefix_titre']} {', '.join(noms_sel)}"
                
                if item["vars_text"]:
                    vt = item["vars_text"]
                    if vt["type"] == "special_radio": 
                        choix = vt["var"].get()
                        if choix == "1":
                            content = vt["opt1_val"]
                        else:
                            content = vt["text_box"].get("0.0", "end").strip()
                    elif vt["type"] == "checkboxes":
                        sel_txt = [v.get() for v in vt["vars"] if v.get()]
                        if sel_txt:
                            items_latex = [f"    \\item {echapper_latex(t)}" for t in sel_txt]
                            content = "\\begin{itemize}\n" + "\n".join(items_latex) + "\n\\end{itemize}"
                            is_latex_formatted = True
                elif item["text_widget"]:
                    content = item["text_widget"].get("0.0", "end").strip()

            elif item["type"] == "multi_check":
                selected = [v.get() for v in item["vars"] if v.get()]
                if selected:
                    items_latex = [f"    \\item {echapper_latex(it)}" for it in selected]
                    list_block = "\\begin{itemize}\n" + "\n".join(items_latex) + "\n\\end{itemize}"
                    prefix = item["prefix"]
                    content = f"{echapper_latex(prefix)}\n\n{list_block}" if prefix else list_block
                    is_latex_formatted = True
            
            elif item["type"] == "text":
                content = item["widget"].get("0.0", "end").strip()

            image = nettoyer_str(item["row"].get('image', ''))
            
            if content or image:
                if not is_latex_formatted:
                    nom_lower = nom_section.lower()
                    if "fixation" in nom_lower and "assemblage" in nom_lower:
                        content = convert_to_table_wrapper(content, "fixation")
                        is_latex_formatted = True
                    elif "traitement" in nom_lower and ("preventif" in nom_lower or "curatif" in nom_lower):
                        content = convert_to_table_wrapper(content, "traitement")
                        is_latex_formatted = True
                    else:
                        content = echapper_latex(content)
                
                final_content = content 

                processed_subs.append({
                    "nom": nom_section,
                    "contenu": final_content,
                    "contenu_brut": content,
                    "image": image if image else None
                })
        return processed_subs

def convert_to_table_wrapper(text, type_table):
    if not text: return ""
    try:
        if type_table == "fixation":
            return convertir_fixation_assemblage_en_tableau(text)
        elif type_table == "traitement":
            return convertir_traitement_en_tableau(text)
    except Exception as e:
        print(f"Erreur conversion tableau {type_table}: {e}")
        return echapper_latex(text)
    return echapper_latex(text)

class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Générateur Mémoire - Bois & Techniques")
        self.geometry("1100x800")
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.sidebar = ctk.CTkFrame(self, width=250, corner_radius=0)
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        
        ctk.CTkLabel(self.sidebar, text="BOIS & TECHNIQUES", font=("Arial", 20, "bold")).pack(pady=20)

        self.inputs = {}
        for key, default_val in DEFAUTS.items():
            label_text = SIDEBAR_LABELS.get(key, key)
            ctk.CTkLabel(self.sidebar, text=label_text, anchor="w").pack(fill="x", padx=20, pady=(10, 0))
            entry = ctk.CTkEntry(self.sidebar)
            entry.insert(0, default_val)
            entry.pack(fill="x", padx=20, pady=(0, 10))
            self.inputs[key] = entry

        ctk.CTkLabel(self.sidebar, text="Sections à inclure :", anchor="w", font=("Arial", 14, "bold")).pack(fill="x", padx=20, pady=(20, 0))
        self.section_vars = {}
        scroll_sections = ctk.CTkScrollableFrame(self.sidebar, fg_color="transparent")
        scroll_sections.pack(fill="both", expand=True, padx=10, pady=10)

        for section in SECTIONS_AUTORISEES:
            var = tk.BooleanVar(value=True)
            cb = ctk.CTkCheckBox(scroll_sections, text=section, variable=var, font=("Arial", 11))
            cb.pack(anchor="w", padx=5, pady=2)
            self.section_vars[section] = var

        ctk.CTkButton(self.sidebar, text="GÉNÉRER PDF", fg_color="#27AE60", hover_color="#1E8449", height=50, command=self.generate).pack(pady=20, padx=20, side="bottom")

        self.tabview = ctk.CTkTabview(self)
        self.tabview.grid(row=0, column=1, padx=20, pady=20, sticky="nsew")

        # Lancement du chargement
        self.after(200, self.start_loading_data)

    def start_loading_data(self):
        # Affichage du loader
        self.loader_csv = LoadingWindow(self, "Chargement des données CSV...")
        self.update() 
        
        # Lancement du thread de lecture
        threading.Thread(target=self._thread_read_csv).start()

    def _thread_read_csv(self):
        try:
            csv_files = ["data/crack.csv", "data/bd_complete.csv", "crack.csv"]
            csv_path = next((f for f in csv_files if os.path.exists(f)), None)
            
            if not csv_path:
                self.after(0, lambda: messagebox.showerror("Erreur", "Fichier CSV introuvable"))
                self.after(0, self.loader_csv.close)
                return

            # Lecture du CSV (IO bound)
            df = pd.read_csv(csv_path, sep=";", dtype=str, encoding='utf-8', on_bad_lines='skip')
            df = df.fillna("")
            df.columns = df.columns.str.strip().str.lower()
            df['section_norm'] = df['section'].apply(normaliser_titre)
            
            # On passe la main au thread principal pour la construction de l'UI
            self.after(0, lambda: self._init_ui_build(df))
            
        except Exception as e:
            self.after(0, lambda: messagebox.showerror("Erreur", f"Erreur de chargement : {e}"))
            self.after(0, self.loader_csv.close)

    def _init_ui_build(self, df):
        # Préparation de la liste des sections à créer
        self.sections_to_build = []
        for titre_officiel in SECTIONS_AUTORISEES:
            titre_clean = normaliser_titre(titre_officiel)
            rows = df[df['section_norm'] == titre_clean]
            
            if not rows.empty:
                self.sections_to_build.append((titre_officiel, rows))
        
        self.section_frames = []
        # Lancer la construction séquentielle pour ne pas figer l'UI
        self._build_next_section(0)

    def _build_next_section(self, index):
        if index >= len(self.sections_to_build):
            # Fini
            self.loader_csv.close()
            return

        titre_officiel, rows = self.sections_to_build[index]
        
        # Création de l'onglet et du frame (Bloquant mais court pour une seule section)
        try:
            tab_name = (titre_officiel[:20] + "..") if len(titre_officiel) > 20 else titre_officiel
            base = tab_name
            c = 1
            existing_tabs = [x['tab'] for x in self.section_frames]
            while tab_name in existing_tabs:
                c += 1
                tab_name = f"{base} ({c})"

            self.tabview.add(tab_name)
            frame = ScrollableSectionFrame(self.tabview.tab(tab_name), title=titre_officiel, data_rows=rows)
            frame.pack(fill="both", expand=True)
            
            self.section_frames.append({
                "titre_final": titre_officiel,
                "tab": tab_name,
                "frame": frame
            })
        except Exception as e:
            print(f"Erreur construction section {titre_officiel}: {e}")

        # Force l'update de l'UI pour que la barre bouge
        self.update_idletasks()
        
        # Planifie la prochaine section
        self.after(10, lambda: self._build_next_section(index + 1))

    def generate(self):
        # 1. Création du Loader (Thread Principal)
        self.loader = LoadingWindow(self, "Génération du PDF en cours...\nVeuillez patienter.")
        self.update() # Force l'affichage
        
        # 2. Lancement du travail lourd dans un thread
        threading.Thread(target=self._process_generation).start()

    def _process_generation(self):
        try:
            infos = {
                "Intitule_operation": self.inputs["intitule"].get(),
                "Lot_Intitule": self.inputs["lot"].get(),
                "Maitre_ouvrage_nom": self.inputs["moa"].get(),
                "Adresse_chantier": self.inputs["adresse"].get()
            }

            # RE-STRUCTURATION pour Thread-Safety
            pass

        except:
            pass
            
        # Pour faire simple et robuste : je rappelle le main thread pour collecter
        self.after(0, self._collect_and_compile)

    def _collect_and_compile(self):
        # Cette méthode tourne dans le thread principal, donc accès sûr aux widgets
        try:
            data_collected = []
            for item in self.section_frames:
                titre = item["titre_final"]
                if self.section_vars.get(titre, tk.BooleanVar(value=True)).get():
                    sous_sections = item["frame"].get_data()
                    if sous_sections:
                        data_collected.append({
                            "titre": titre,
                            "sous_sections": sous_sections
                        })
            
            infos = {
                "Intitule_operation": self.inputs["intitule"].get(),
                "Lot_Intitule": self.inputs["lot"].get(),
                "Maitre_ouvrage_nom": self.inputs["moa"].get(),
                "Adresse_chantier": self.inputs["adresse"].get()
            }
            
            # Maintenant on lance le thread lourd avec les données DÉJÀ collectées
            threading.Thread(target=self._run_latex_compilation, args=(data_collected, infos)).start()
            
        except Exception as e:
            self.loader.close()
            messagebox.showerror("Erreur Données", str(e))

    def _run_latex_compilation(self, data_finale, infos):
        images = {
            "image_garde": "../images/exemple_pagegarde.jpeg",
            "attestation_visite": "../images/attestation_visite.png",
            "plan_emplacement": "../images/vue_aerienne.png",
            "image_grue": "../images/grue.png"
        }

        output_dir = "output"
        if not os.path.exists(output_dir): os.makedirs(output_dir)
        output_path = os.path.join(output_dir, "resultat.tex")
        
        success = False
        err_msg = ""
        
        try:
            if generer_fichier_tex(data_finale, infos, images, output_path=output_path):
                cwd = os.getcwd()
                os.chdir(output_dir)
                os.system("pdflatex -interaction=nonstopmode resultat.tex > nul 2>&1")
                os.system("pdflatex -interaction=nonstopmode resultat.tex > nul 2>&1")
                os.chdir(cwd)
                success = True
            else:
                err_msg = "Échec génération .tex"
        except Exception as e:
            err_msg = str(e)
            
        # Retour au thread principal pour l'UI
        self.after(0, lambda: self._generation_finished(success, err_msg, output_dir))

    def _generation_finished(self, success, err_msg, output_dir):
        if self.loader:
            self.loader.close()
        if success:
            messagebox.showinfo("Succès", f"PDF généré avec succès dans {output_dir}/resultat.pdf")
        else:
            messagebox.showerror("Erreur", f"Erreur : {err_msg}")

if __name__ == "__main__":
    app = App()
    app.mainloop()