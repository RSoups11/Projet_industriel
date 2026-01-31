"""
Page de generation de memoires techniques.
Interface principale avec STATE MANAGEMENT pour capturer les modifications utilisateur.
"""

from nicegui import ui, events
from pathlib import Path
from datetime import datetime
import asyncio
import pandas as pd
import re
from typing import Dict, List, Any, Optional

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.config import AppConfig, FIELD_LABELS, SECTION_ICONS
from app.core.csv_service import CSVService
from app.core.latex_service import LaTeXService

# Couleurs LaTeX disponibles avec leur équivalent CSS
# Couleurs disponibles - TOUTES définies dans template_v2.tex.j2
LATEX_COLORS = {
    'ecoBleu': {'latex': 'ecoBleu', 'css': '#3498DB', 'nom': 'Bleu'},
    'ecoVert': {'latex': 'ecoVert', 'css': '#27AE60', 'nom': 'Vert'},
    'ecoVertFonce': {'latex': 'ecoVertFonce', 'css': '#1E8449', 'nom': 'Vert foncé'},
    'ecoMarron': {'latex': 'ecoMarron', 'css': '#795548', 'nom': 'Marron'},
    'ecoRouge': {'latex': 'ecoRouge', 'css': '#C0392B', 'nom': 'Rouge'},
    'ecoViolet': {'latex': 'ecoViolet', 'css': '#8E44AD', 'nom': 'Violet'},
    'ecoOrange': {'latex': 'ecoOrange', 'css': '#E67E22', 'nom': 'Orange'},
    'ecoJaune': {'latex': 'ecoJaune', 'css': '#F1C40F', 'nom': 'Jaune'},
}


def valider_couleur(couleur: str) -> str:
    """Valide une couleur et retourne une couleur valide.
    Si la couleur n'est pas dans LATEX_COLORS, retourne 'ecoBleu' par défaut."""
    if couleur in LATEX_COLORS:
        return couleur
    # Essayer de mapper les anciennes couleurs vers les nouvelles
    mapping = {
        'red': 'ecoRouge',
        'red!70!black': 'ecoRouge',
        'orange': 'ecoOrange',
        'purple': 'ecoViolet',
        'gray': 'ecoBleu',
        'grey': 'ecoBleu',
        'blue': 'ecoBleu',
        'green': 'ecoVert',
        'brown': 'ecoMarron',
        'traitBleu': 'ecoBleu',
        'ecoGris': 'ecoBleu',
    }
    return mapping.get(couleur, 'ecoBleu')


def nettoyer_str(valeur) -> str:
    """Nettoie une valeur string."""
    if pd.isna(valeur):
        return ""
    s = str(valeur).strip()
    return "" if s.lower() == "nan" else s


def normaliser_titre(titre: str) -> str:
    """Normalise un titre pour comparaison."""
    s = nettoyer_str(titre)
    if not s:
        return ""
    s = s.replace('OE', 'OE').replace('oe', 'oe')
    return re.sub(r'[^a-zA-Z0-9]', '', s).upper()


class GenerationPage:
    """Composant de la page de generation avec state management."""
    
    def __init__(self):
        self.config = AppConfig()
        self.csv_service = CSVService()
        self.latex_service = LaTeXService(
            self.config.TEMPLATES_DIR,
            self.config.OUTPUT_DIR
        )
        
        # Charger les données de templates modifiables
        self.template_data = self._load_template_data()
        
        # ========== STATE CENTRAL ==========
        # Toutes les donnees modifiees par l'utilisateur sont stockees ici
        self.project_state: Dict[str, Any] = {
            "infos_projet": {
                "intitule": "",
                "lot": "Lot N02 - Charpente bois",
                "moa": "",
                "adresse": "",
            },
            "images": {
                "image_garde": "",
                "attestation_visite": "",
                "plan_emplacement": "",
                "image_grue": "",
            },
            "sections_enabled": {},  # section_name -> bool
            "sections_data": {},     # section_name -> {sous_section_key -> data}
            "template_data": self.template_data.copy(),  # Données des templates modifiables
        }
        
        # DataFrame source
        self.df = None
        
        # Widgets pour mise a jour du state
        self.input_widgets = {}
        self.section_checkboxes = {}
        
        # Sections autorisees depuis config
        self.sections_autorisees = self.config.user_config.get("sections_autorisees", [])
        for section in self.sections_autorisees:
            # Toutes les sections cochées par défaut
            self.project_state["sections_enabled"][section] = True
    
    def _load_template_data(self) -> Dict[str, Any]:
        """Charge les données de templates depuis template_data.json."""
        import json
        template_data_path = self.config.BASE_DIR / "app" / "template_data.json"
        if template_data_path.exists():
            with open(template_data_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}
    
    def render(self):
        """Rendu principal de la page."""
        # Recharger les données de templates à chaque rendu (pour sync avec Base de données)
        self._refresh_template_data()
        
        with ui.row().classes('w-full h-full gap-0'):
            # Sidebar gauche
            self._render_sidebar()
            
            # Zone principale
            with ui.column().classes('flex-grow p-4 bg-gray-50 overflow-auto'):
                self._render_main_content()
    
    def _refresh_template_data(self):
        """Recharge les données template depuis le fichier (sync avec Base de données)."""
        import copy
        fresh_data = self._load_template_data()
        self.template_data = fresh_data
        # Mettre aussi à jour dans le project_state
        self.project_state["template_data"] = fresh_data
        
        # Rafraîchir les données des tableaux dans sections_data si elles existent
        # pour que les nouvelles données de template_data soient utilisées
        for section_key, section_data in self.project_state.get("sections_data", {}).items():
            if isinstance(section_data, dict):
                # Forcer le rechargement des tableaux en supprimant les anciennes données
                keys_to_refresh = [k for k in section_data.keys() 
                                   if k.startswith('fixation_') or k.startswith('traitement_')]
                for k in keys_to_refresh:
                    if 'table_data' in section_data[k]:
                        # Recharger depuis les données fraîches
                        if 'fixation' in k:
                            section_data[k]['table_data'] = copy.deepcopy(
                                fresh_data.get('table_fixation_assemblage', []))
                        elif 'preventif' in k:
                            section_data[k]['table_data'] = copy.deepcopy(
                                fresh_data.get('table_traitement_preventif', []))
                        elif 'curatif' in k:
                            section_data[k]['table_data'] = copy.deepcopy(
                                fresh_data.get('table_traitement_curatif', []))
    
    def _render_sidebar(self):
        """Barre laterale avec infos projet et controles."""
        with ui.column().classes('w-80 bg-white shadow-lg p-4 gap-2 h-full overflow-auto'):
            ui.label('Informations du projet').classes('text-lg font-bold text-blue-900 mb-2')
            
            # Champs projet avec binding au state
            for key, label in [
                ('intitule', 'Intitule de l\'operation'),
                ('lot', 'Intitule du lot'),
                ('moa', 'Maitre d\'ouvrage'),
                ('adresse', 'Adresse du chantier'),
            ]:
                ui.label(label).classes('text-sm text-gray-600 mt-2')
                inp = ui.input(
                    value=self.project_state["infos_projet"].get(key, ""),
                    on_change=lambda e, k=key: self._update_state_info(k, e.value)
                ).classes('w-full')
                self.input_widgets[key] = inp
            
            ui.separator().classes('my-4')
            
            # Préambule éditable
            ui.label('Préambule du mémoire').classes('text-lg font-bold text-blue-900 mb-2')
            preambule_data = self.project_state.get("template_data", {}).get("preambule", {})
            preambule_default = preambule_data.get("texte", "")
            
            if 'preambule' not in self.project_state:
                self.project_state['preambule'] = preambule_default
            
            def update_preambule(e):
                self.project_state['preambule'] = e.value
            
            ui.textarea(
                value=self.project_state.get('preambule', preambule_default),
                on_change=update_preambule
            ).classes('w-full').props('rows=5 outlined')
            
            ui.separator().classes('my-4')
            
            # Section Images
            ui.label('Images du projet').classes('text-lg font-bold text-blue-900 mb-2')
            
            for key, label in [
                ('image_garde', 'Image de garde'),
                ('attestation_visite', 'Attestation de visite'),
                ('plan_emplacement', 'Plan d\'emplacement'),
                ('image_grue', 'Image grue/levage'),
            ]:
                self._render_image_upload(key, label)
            
            ui.separator().classes('my-4')
            
            # Sections a inclure
            ui.label('Sections a inclure').classes('text-lg font-bold text-blue-900 mb-2')
            
            # Container pour les checkboxes de sections
            self.sections_scroll = ui.scroll_area().classes('h-48')
            
            with self.sections_scroll:
                for section in self.sections_autorisees:
                    display_name = section[:30] + '...' if len(section) > 30 else section
                    # Toutes les sections cochées par défaut
                    cb = ui.checkbox(
                        display_name,
                        value=True,
                        on_change=lambda e, s=section: self._toggle_section(s, e.value)
                    ).classes('text-sm')
                    # Initialiser le state pour cette section
                    self.project_state["sections_enabled"][section] = True
                    self.section_checkboxes[section] = cb
            
            # Bouton pour ajouter une section personnalisée
            ui.button('+ Ajouter section', on_click=self._show_add_section_dialog).props('flat color=blue size=sm').classes('mt-2')
            
            ui.space()
            
            # Bouton generation
            ui.button(
                'GENERER LE PDF',
                on_click=self._generate_pdf,
            ).classes('w-full bg-green-600 hover:bg-green-700 text-white font-bold py-4 text-lg')
    
    def _render_image_upload(self, key: str, label: str):
        """Upload d'image avec binding au state."""
        with ui.row().classes('w-full items-center gap-2'):
            ui.label(label).classes('text-sm text-gray-600 flex-grow')
            file_label = ui.label('Aucun fichier').classes('text-xs text-gray-400 truncate max-w-24')
            
            async def handle_upload(e: events.UploadEventArguments, k=key, fl=file_label):
                with open(self.config.IMAGES_DIR / e.file.name, 'wb') as f:
                    f.write(await e.file.read())
                self.project_state["images"][k] = str(self.config.IMAGES_DIR / e.file.name)
                fl.set_text(e.file.name[:12] + '...' if len(e.file.name) > 12 else e.file.name)
                ui.notify(f'Image {e.file.name} chargee', type='positive')

            ui.upload(
                on_upload=handle_upload,
                auto_upload=True,
                max_files=1
            ).props('accept=".jpg,.jpeg,.png,.pdf" flat dense').classes('w-20')
    
    def _show_add_section_dialog(self):
        """Dialog pour ajouter une nouvelle section."""
        with ui.dialog() as dialog, ui.card().classes('w-96'):
            ui.label('Ajouter une section').classes('text-lg font-bold mb-4')
            
            section_input = ui.input(
                label='Nom de la section',
                placeholder='Ex: NOUVELLES REFERENCES'
            ).classes('w-full')
            
            with ui.row().classes('justify-end gap-2 mt-4'):
                ui.button('Annuler', on_click=dialog.close).props('flat')
                
                def add_section():
                    new_section = section_input.value.strip().upper()
                    if new_section and new_section not in self.sections_autorisees:
                        # Ajouter à la liste
                        self.sections_autorisees.append(new_section)
                        
                        # Ajouter le checkbox
                        with self.sections_scroll:
                            cb = ui.checkbox(
                                new_section[:30] + '...' if len(new_section) > 30 else new_section,
                                value=True,
                                on_change=lambda e, s=new_section: self._toggle_section(s, e.value)
                            ).classes('text-sm')
                            self.section_checkboxes[new_section] = cb
                        
                        # Activer dans le state
                        self.project_state["sections_enabled"][new_section] = True
                        self.project_state["sections_data"][new_section] = {}
                        
                        # Sauvegarder dans la config
                        self.config.user_config["sections_autorisees"] = self.sections_autorisees
                        self.config.save_user_config(self.config.user_config)
                        
                        ui.notify(f'Section "{new_section}" ajoutée', type='positive')
                        dialog.close()
                    else:
                        ui.notify('Section déjà existante ou nom invalide', type='warning')
                
                ui.button('Ajouter', on_click=add_section).props('color=blue')
        
        dialog.open()
    
    def _update_state_info(self, key: str, value: str):
        """Met a jour le state des infos projet."""
        self.project_state["infos_projet"][key] = value
    
    def _toggle_section(self, section: str, enabled: bool):
        """Active/desactive une section dans le state."""
        self.project_state["sections_enabled"][section] = enabled
    
    def _render_main_content(self):
        """Zone principale avec les sections."""
        ui.label('Contenu du memoire technique').classes('text-2xl font-bold text-blue-900 mb-4')
        
        # Container pour les sections (grille uniforme)
        self.sections_container = ui.column().classes('w-full gap-4')
        
        # Charger les donnees au demarrage
        ui.timer(0.3, self._load_data, once=True)
    
    async def _load_data(self):
        """Charge les donnees du CSV."""
        csv_path = self.config.DEFAULT_CSV_FILE
        
        if not csv_path.exists():
            csv_path = self.config.DATA_DIR / "bd_interface.csv"
        
        if not csv_path.exists():
            ui.notify('Fichier CSV introuvable', type='negative')
            return
        
        try:
            # Charger avec gestion multi-encodage
            encodings = ['utf-8', 'latin-1', 'iso-8859-1', 'cp1252']
            self.df = None
            
            for encoding in encodings:
                try:
                    self.df = pd.read_csv(csv_path, sep=";", dtype=str, encoding=encoding, on_bad_lines='skip')
                    break
                except UnicodeDecodeError:
                    continue
            
            if self.df is None:
                raise ValueError("Impossible de lire le fichier CSV")
            
            self.df = self.df.fillna("")
            self.df.columns = self.df.columns.str.strip().str.lower()
            self.df['section_norm'] = self.df['section'].apply(normaliser_titre)
            
            # Construire les sections
            await self._build_sections()
            
            ui.notify(f'Donnees chargees depuis {csv_path.name}', type='positive')
        
        except Exception as ex:
            ui.notify(f'Erreur: {str(ex)}', type='negative')
    
    async def _build_sections(self):
        """Construit toutes les sections dans un layout uniforme."""
        self.sections_container.clear()
        
        # Texte par défaut pour le planning (fallback si pas dans CSV)
        default_planning_text = self.config.user_config.get("defaults", {}).get("planning_texte", 
            "Lors de l'étude du planning transmis dans le cadre du dossier de consultation, nous avons porté une attention particulière à la durée prévue par le planning pour la phase de montage. Au regard des caractéristiques techniques du projet, du volume des éléments à assembler, des conditions d'accès au site, ainsi que de nos retours d'expérience sur des opérations similaires, cette durée apparaît ........... pour garantir une exécution conforme aux exigences de qualité, de sécurité et de coordination des intervenants. Nos prévisions internes, fondées sur une simulation détaillée estiment le besoin réel à ...... semaines. Nous recommandons donc d'ajuster le planning initial sur cette base afin d'assurer une exécution réaliste fluide et sans tension sur les ressources.")
        
        with self.sections_container:
            for titre_officiel in self.sections_autorisees:
                titre_norm = normaliser_titre(titre_officiel)
                rows = self.df[self.df['section_norm'] == titre_norm]
                
                # Initialiser le state pour cette section
                if titre_officiel not in self.project_state["sections_data"]:
                    self.project_state["sections_data"][titre_officiel] = {}
                
                # Card de section (expansion)
                icon = SECTION_ICONS.get(titre_officiel, 'folder')
                
                # Cas spéciaux pour sections sans données CSV
                if 'PLANNING' in titre_officiel.upper():
                    # Charger le texte depuis CSV si disponible, sinon fallback
                    planning_text = default_planning_text
                    planning_couleur = 'ecoBleu'
                    if not rows.empty:
                        # Chercher une ligne avec "Respect des délais" ou texte d'analyse
                        for _, row in rows.iterrows():
                            texte = nettoyer_str(row.get('texte', ''))
                            if texte and len(texte) > 100:  # Texte long = analyse du planning
                                planning_text = texte
                                planning_couleur = valider_couleur(nettoyer_str(row.get('couleur', 'ecoBleu')))
                                break
                    with ui.expansion(titre_officiel, icon='calendar_today').classes('w-full bg-white shadow rounded-lg').props('default-opened'):
                        self._build_planning_section(titre_officiel, planning_text, planning_couleur, rows)
                    continue
                
                if 'QSE' in titre_officiel.upper() or 'HYGIENE' in titre_officiel.upper() or 'QUALITE ENVIRONNEMENT' in titre_officiel.upper() or 'HQE' in titre_officiel.upper():
                    with ui.expansion(titre_officiel, icon='eco').classes('w-full bg-white shadow rounded-lg').props('default-opened'):
                        self._build_hqe_section(titre_officiel)
                    continue
                
                if 'ANNEXES' in titre_officiel.upper():
                    with ui.expansion(titre_officiel, icon='attachment').classes('w-full bg-white shadow rounded-lg').props('default-opened'):
                        self._build_annexes_section(titre_officiel)
                    continue
                
                if 'SITUATION ADMINISTRATIVE' in titre_officiel.upper():
                    with ui.expansion(titre_officiel, icon='business').classes('w-full bg-white shadow rounded-lg').props('default-opened'):
                        self._build_situation_admin_section(titre_officiel)
                    continue
                
                if 'CHANTIER' in titre_officiel.upper() and 'REFERENCE' in titre_officiel.upper():
                    with ui.expansion(titre_officiel, icon='work').classes('w-full bg-white shadow rounded-lg').props('default-opened'):
                        self._build_chantiers_references_section(titre_officiel, rows)
                    continue
                
                if 'MOYENS MATERIEL' in titre_officiel.upper():
                    with ui.expansion(titre_officiel, icon='build').classes('w-full bg-white shadow rounded-lg').props('default-opened'):
                        self._build_moyens_materiel_section(titre_officiel, rows)
                    continue
                
                if 'MOYENS HUMAINS' in titre_officiel.upper():
                    with ui.expansion(titre_officiel, icon='people').classes('w-full bg-white shadow rounded-lg').props('default-opened'):
                        self._build_moyens_humains_section(titre_officiel, rows)
                    continue
                
                # Section CONTEXTE DU PROJET
                if 'CONTEXTE' in titre_officiel.upper() and 'PROJET' in titre_officiel.upper():
                    with ui.expansion(titre_officiel, icon='location_on').classes('w-full bg-white shadow rounded-lg').props('default-opened'):
                        self._build_contexte_projet_section(titre_officiel, rows)
                    continue
                
                if rows.empty:
                    continue
                
                with ui.expansion(titre_officiel, icon=icon).classes('w-full bg-white shadow rounded-lg').props('default-opened'):
                    self._build_section_content(titre_officiel, rows)
    
    def _build_planning_section(self, titre: str, default_text: str, couleur: str = 'ecoBleu', rows=None):
        """Construit la section Planning avec texte modifiable, couleur et sous-sections depuis CSV."""
        section_state = self.project_state["sections_data"][titre]
        
        # Initialiser si pas encore fait
        if 'planning_main' not in section_state:
            section_state['planning_main'] = {
                'nom': 'Analyse du planning',
                'texte': default_text,
                'image': '',
                'type': 'planning',
                'couleur': couleur
            }
        
        state = section_state['planning_main']
        # Mettre à jour la couleur si elle vient du CSV
        state['couleur'] = couleur
        
        with ui.column().classes('w-full gap-3 p-2'):
            # Sélecteur de couleur
            couleur_css = LATEX_COLORS.get(couleur, LATEX_COLORS['ecoBleu'])['css']
            with ui.card().classes('w-full p-4').style(f'border-left: 4px solid {couleur_css};'):
                with ui.row().classes('w-full justify-between items-center mb-3'):
                    ui.label('Analyse du planning').classes('font-bold text-blue-700')
                    
                    color_options = {k: f"{v['nom']}" for k, v in LATEX_COLORS.items()}
                    def update_color(e, st=state):
                        st['couleur'] = e.value
                    
                    with ui.row().classes('items-center gap-1'):
                        ui.icon('palette', size='xs').classes('text-gray-400')
                        ui.select(
                            options=color_options,
                            value=state.get('couleur', 'ecoBleu'),
                            on_change=update_color
                        ).props('dense outlined').classes('w-28')
                
                ui.label('Ce texte sera affiché dans la section Planning du mémoire.').classes('text-sm text-gray-600 mb-2')
                
                ui.textarea(
                    value=state['texte'],
                    on_change=lambda e: self._update_subsection_state(state, 'texte', e.value)
                ).classes('w-full').props('rows=8')
                
                ui.separator().classes('my-3')
                
                # Upload d'image pour planning (optionnel)
                ui.label('Image/document pour le planning (optionnel)').classes('text-sm text-gray-600')
                
                with ui.row().classes('items-center gap-2'):
                    file_label = ui.label('Aucun fichier').classes('text-xs text-gray-400')
                    
                    async def handle_planning_upload(e: events.UploadEventArguments, st=state, fl=file_label):
                        with open(self.config.IMAGES_DIR / e.file.name, 'wb') as f:
                            f.write(await e.file.read())
                        st['image'] = str(self.config.IMAGES_DIR / e.file.name)
                        fl.set_text(e.file.name[:20] + '...' if len(e.file.name) > 20 else e.file.name)
                        ui.notify(f'Image {e.file.name} chargée pour le planning', type='positive')

                    ui.upload(
                        on_upload=handle_planning_upload,
                        auto_upload=True,
                        max_files=1
                    ).props('accept=".jpg,.jpeg,.png,.pdf" flat dense').classes('w-32')
    
    def _build_contexte_projet_section(self, titre: str, rows: pd.DataFrame):
        """Construit la section CONTEXTE DU PROJET avec cartes réordonnables."""
        section_state = self.project_state["sections_data"][titre]
        template_data = self.project_state.get("template_data", {})
        contexte_data = template_data.get('contexte_projet', {})
        
        # Charger données depuis crack.csv si rows est vide
        crack_data = {}
        if rows.empty:
            crack_csv = self.config.DATA_DIR / "crack.csv"
            if crack_csv.exists():
                try:
                    for encoding in ['utf-8', 'latin-1', 'iso-8859-1', 'cp1252']:
                        try:
                            crack_df = pd.read_csv(crack_csv, sep=";", dtype=str, encoding=encoding, on_bad_lines='skip')
                            crack_df = crack_df.fillna("")
                            crack_df.columns = crack_df.columns.str.strip().str.lower()
                            crack_df_ctx = crack_df[crack_df['section'].str.upper().str.contains('CONTEXTE', na=False)]
                            
                            for _, row in crack_df_ctx.iterrows():
                                ss = nettoyer_str(row.get('sous-section', '')).lower()
                                texte = nettoyer_str(row.get('texte', ''))
                                if 'environnement' in ss:
                                    crack_data['environnement'] = texte
                                elif 'acces' in ss or 'accès' in ss:
                                    crack_data['acces'] = texte
                                elif ss == 'levage':
                                    crack_data['levage'] = texte
                                elif 'contrainte' in ss:
                                    crack_data['contraintes'] = texte
                                elif 'contexte' in ss:
                                    crack_data['intro_visite'] = texte
                            break
                        except UnicodeDecodeError:
                            continue
                except Exception:
                    pass
        else:
            for _, row in rows.iterrows():
                ss = nettoyer_str(row.get('sous-section', '')).lower()
                texte = nettoyer_str(row.get('texte', ''))
                if 'environnement' in ss:
                    crack_data['environnement'] = texte
                elif 'acces' in ss or 'accès' in ss:
                    crack_data['acces'] = texte
                elif ss == 'levage':
                    crack_data['levage'] = texte
                elif 'contrainte' in ss:
                    crack_data['contraintes'] = texte
        
        # Helper pour initialiser selections avec première option cochée
        def init_selections_first_checked(options_str):
            """Retourne un dict de selections avec la première option cochée."""
            options = [o.strip() for o in options_str.split('/// ou ///') if o.strip()]
            if options:
                return {options[0]: True}
            return {}
        
        # Initialiser la liste ordonnée des sous-sections contexte
        order_key = '_contexte_order_'
        if order_key not in section_state:
            env_options = crack_data.get('environnement', 'Pavillonnaire /// ou /// Zone industrielle /// ou /// Zone artisanale /// ou /// Centre-ville /// ou /// Campagne')
            levage_options = crack_data.get('levage', 'Grue automotrice /// ou /// Camion grue')
            contraintes_options = crack_data.get('contraintes', 'Travaux hauteur /// ou /// Chute de hauteur /// ou /// Contraintes temporelles')
            
            section_state[order_key] = [
                {
                    'key': 'visite',
                    'nom': 'Visite de site',
                    'type': 'visite',
                    'date_visite': contexte_data.get('date_visite_defaut', ''),
                    'intro_visite': contexte_data.get('intro_visite', 'Nous nous sommes rendus sur les lieux le'),
                    'adresse': self.project_state["infos_projet"].get('adresse', ''),
                    'couleur': 'ecoBleu'
                },
                {
                    'key': 'environnement',
                    'nom': 'Localisation / Environnement',
                    'type': 'checkbox',
                    'options': env_options,
                    'selections': init_selections_first_checked(env_options),
                    'couleur': 'ecoVert'
                },
                {
                    'key': 'acces',
                    'nom': 'Accès chantier et stationnement',
                    'type': 'text',
                    'contenu': contexte_data.get('acces_chantier', '') or crack_data.get('acces', 'Selon PGC délivrée à l\'entreprise retenue'),
                    'couleur': 'ecoOrange'
                },
                {
                    'key': 'levage',
                    'nom': 'Levage',
                    'type': 'checkbox',
                    'options': levage_options,
                    'selections': init_selections_first_checked(levage_options),
                    'couleur': 'ecoMarron'
                },
                {
                    'key': 'contraintes',
                    'nom': 'Contraintes du chantier',
                    'type': 'checkbox',
                    'options': contraintes_options,
                    'selections': init_selections_first_checked(contraintes_options),
                    'couleur': 'ecoRouge'
                },
            ]
        
        items = section_state[order_key]
        main_container = ui.column().classes('w-full gap-3 p-2')
        
        def rebuild_contexte():
            """Reconstruit l'affichage de la section contexte."""
            main_container.clear()
            with main_container:
                for i in range(len(items)):
                    self._build_contexte_card(items, i, rebuild_contexte, section_state)
                
                # Bouton ajouter une sous-section
                def add_new_subsection():
                    new_item = {
                        'key': f'custom_{len(items)}_{datetime.now().timestamp()}',
                        'nom': 'Nouvelle sous-section',
                        'type': 'text',
                        'contenu': '',
                        'couleur': 'ecoBleu'
                    }
                    items.append(new_item)
                    rebuild_contexte()
                    ui.notify('Sous-section ajoutée', type='positive')
                
                ui.button('+ Ajouter une sous-section', on_click=add_new_subsection, icon='add').props('outline color=blue').classes('mt-2')
        
        rebuild_contexte()
    
    def _build_contexte_card(self, items: list, index: int, rebuild_fn, section_state: dict):
        """Construit une carte de contexte avec contrôles de réordonnancement et couleur."""
        item = items[index]
        item['couleur'] = valider_couleur(item.get('couleur', 'ecoBleu'))
        couleur_css = LATEX_COLORS.get(item['couleur'], LATEX_COLORS['ecoBleu'])['css']
        
        with ui.card().classes('w-full p-4').style(f'border-left: 4px solid {couleur_css};'):
            # Barre de contrôle en haut
            with ui.row().classes('w-full justify-between items-center mb-3'):
                with ui.row().classes('items-center gap-1'):
                    ui.label(f'#{index + 1}').classes('text-xs text-gray-400 font-mono')
                    
                    def move_up(idx=index):
                        if idx > 0:
                            items[idx], items[idx-1] = items[idx-1], items[idx]
                            rebuild_fn()
                    
                    def move_down(idx=index):
                        if idx < len(items) - 1:
                            items[idx], items[idx+1] = items[idx+1], items[idx]
                            rebuild_fn()
                    
                    ui.button(icon='arrow_upward', on_click=move_up).props('flat dense size=sm').classes('text-gray-500').tooltip('Monter')
                    ui.button(icon='arrow_downward', on_click=move_down).props('flat dense size=sm').classes('text-gray-500').tooltip('Descendre')
                
                with ui.row().classes('items-center gap-2'):
                    # Bouton supprimer
                    def delete_item(idx=index):
                        if len(items) > 1:
                            items.pop(idx)
                            rebuild_fn()
                            ui.notify('Sous-section supprimée', type='info')
                    
                    ui.button(icon='delete', on_click=delete_item).props('flat dense size=sm color=red').tooltip('Supprimer')
                    
                    # Sélecteur de couleur
                    color_options = {k: f"{v['nom']}" for k, v in LATEX_COLORS.items()}
                    def update_color(e, it=item):
                        it['couleur'] = e.value
                        rebuild_fn()
                    
                    ui.icon('palette', size='xs').classes('text-gray-400')
                    ui.select(options=color_options, value=item.get('couleur', 'ecoBleu'), on_change=update_color).props('dense outlined').classes('w-28')
            
            # Titre éditable
            ui.label('Titre :').classes('text-xs text-gray-500')
            def update_nom(e, it=item):
                it['nom'] = e.value
            ui.input(value=item.get('nom', ''), on_change=update_nom).props('outlined dense').classes('w-full mb-2 font-bold')
            
            # Contenu selon le type
            item_type = item.get('type', 'text')
            
            if item_type == 'visite':
                # Champs date + adresse + intro
                with ui.row().classes('w-full gap-4'):
                    with ui.column().classes('flex-1'):
                        ui.label('Date de visite').classes('text-xs text-gray-500')
                        def update_date(e, it=item):
                            it['date_visite'] = e.value
                        ui.input(value=item.get('date_visite', ''), placeholder='Ex: 15 janvier 2026', on_change=update_date).classes('w-full')
                    
                    with ui.column().classes('flex-1'):
                        ui.label('Adresse du chantier').classes('text-xs text-gray-500')
                        def update_adresse(e, it=item):
                            it['adresse'] = e.value
                        ui.input(value=item.get('adresse', ''), placeholder='Adresse complète', on_change=update_adresse).classes('w-full')
                
                ui.label('Texte d\'introduction').classes('text-xs text-gray-500 mt-2')
                def update_intro(e, it=item):
                    it['intro_visite'] = e.value
                ui.textarea(value=item.get('intro_visite', ''), on_change=update_intro).classes('w-full').props('rows=2 outlined')
            
            elif item_type == 'checkbox':
                # Checkboxes avec tout cocher/décocher et ajouter option
                options_str = item.get('options', '')
                options = [o.strip() for o in options_str.split('/// ou ///') if o.strip()]
                selections = item.get('selections', {})
                
                if not isinstance(selections, dict):
                    selections = {}
                    item['selections'] = selections
                
                # Container pour les checkboxes
                checkbox_container = ui.column().classes('w-full gap-1')
                checkbox_widgets = []
                
                def rebuild_checkboxes():
                    checkbox_container.clear()
                    checkbox_widgets.clear()
                    with checkbox_container:
                        current_options = [o.strip() for o in item.get('options', '').split('/// ou ///') if o.strip()]
                        for opt in current_options:
                            def make_handler(option, sel=selections):
                                def handler(e):
                                    sel[option] = e.value
                                return handler
                            
                            cb = ui.checkbox(opt, value=selections.get(opt, False), on_change=make_handler(opt)).classes('text-sm')
                            checkbox_widgets.append((opt, cb))
                
                rebuild_checkboxes()
                
                # Boutons d'action
                with ui.row().classes('gap-2 mt-2'):
                    def check_all():
                        for opt, cb in checkbox_widgets:
                            cb.set_value(True)
                            selections[opt] = True
                    
                    def uncheck_all():
                        for opt, cb in checkbox_widgets:
                            cb.set_value(False)
                            selections[opt] = False
                    
                    ui.button('✓ Tout cocher', on_click=check_all).props('flat color=green size=sm')
                    ui.button('✗ Tout décocher', on_click=uncheck_all).props('flat color=red size=sm')
                    
                    # Ajouter une option
                    def add_option():
                        async def do_add():
                            with ui.dialog() as dialog, ui.card():
                                ui.label('Ajouter une option').classes('font-bold mb-2')
                                new_opt_input = ui.input(placeholder='Nouvelle option').classes('w-full')
                                with ui.row().classes('gap-2 mt-2'):
                                    ui.button('Annuler', on_click=dialog.close).props('flat')
                                    def confirm():
                                        new_val = new_opt_input.value.strip()
                                        if new_val:
                                            current = item.get('options', '')
                                            if current:
                                                item['options'] = current + ' /// ou /// ' + new_val
                                            else:
                                                item['options'] = new_val
                                            rebuild_checkboxes()
                                            ui.notify(f'Option "{new_val}" ajoutée', type='positive')
                                        dialog.close()
                                    ui.button('Ajouter', on_click=confirm).props('color=blue')
                            dialog.open()
                        ui.timer(0.1, do_add, once=True)
                    
                    ui.button('+ Option', on_click=add_option).props('flat color=blue size=sm')
            
            else:  # type == 'text'
                # Textarea simple
                ui.label('Contenu :').classes('text-xs text-gray-500')
                def update_contenu(e, it=item):
                    it['contenu'] = e.value
                ui.textarea(value=item.get('contenu', ''), on_change=update_contenu).classes('w-full').props('rows=3 outlined')
    
    def _build_hqe_section(self, titre: str):
        """Construit la section Hygiène Qualité Environnement avec TOUS les champs modifiables."""
        section_state = self.project_state["sections_data"][titre]
        template_data = self.project_state.get("template_data", {})
        
        # Charger les données depuis template_data
        demarche_hqe = template_data.get("demarche_hqe", {})
        demarche_env_atelier = template_data.get("demarche_env_atelier", {})
        demarche_env_chantiers = template_data.get("demarche_env_chantiers", {})
        
        if 'hqe_main' not in section_state:
            section_state['hqe_main'] = {
                'nom': 'Hygiène Qualité Environnement',
                'texte': '',
                'image': '',
                'type': 'template_include'
            }
        
        with ui.column().classes('w-full gap-3 p-2'):
            
            # ========== INTRODUCTION HQE ==========
            with ui.expansion('Introduction HQE', icon='info').classes('w-full bg-green-50').props('default-opened'):
                with ui.card().classes('w-full p-3'):
                    ui.label('Introduction générale').classes('font-bold text-green-700 mb-2')
                    ui.textarea(
                        value=demarche_hqe.get('intro', ''),
                        on_change=lambda e: demarche_hqe.update({'intro': e.value})
                    ).classes('w-full').props('rows=5')
            
            # ========== ÉCO-CONSTRUCTION ==========
            with ui.expansion('Éco-construction', icon='build').classes('w-full bg-green-50'):
                eco_construction = demarche_hqe.get('eco_construction', {})
                
                # Cible 02
                cible_02 = eco_construction.get('cible_02', {})
                with ui.card().classes('w-full p-3 mb-2'):
                    ui.label('Cible n°02 - Choix intégré des procédés et produits').classes('font-bold text-green-700 mb-2')
                    
                    ui.label('Durabilité et adaptabilité').classes('text-sm text-gray-600 mt-2')
                    ui.textarea(
                        value=cible_02.get('durabilite', ''),
                        on_change=lambda e: cible_02.update({'durabilite': e.value})
                    ).classes('w-full').props('rows=3')
                    
                    ui.label('Choix des procédés constructifs').classes('text-sm text-gray-600 mt-2')
                    ui.textarea(
                        value=cible_02.get('procedes', ''),
                        on_change=lambda e: cible_02.update({'procedes': e.value})
                    ).classes('w-full').props('rows=3')
                    
                    ui.label('Choix des produits de construction').classes('text-sm text-gray-600 mt-2')
                    ui.textarea(
                        value=cible_02.get('produits', ''),
                        on_change=lambda e: cible_02.update({'produits': e.value})
                    ).classes('w-full').props('rows=3')
                
                # Cible 03
                cible_03 = eco_construction.get('cible_03', {})
                with ui.card().classes('w-full p-3'):
                    ui.label('Cible n°03 - Chantier à faibles nuisances').classes('font-bold text-green-700 mb-2')
                    
                    ui.label('Gestion des déchets').classes('text-sm text-gray-600 mt-2')
                    ui.input(
                        value=cible_03.get('gestion_dechets', ''),
                        on_change=lambda e: cible_03.update({'gestion_dechets': e.value})
                    ).classes('w-full').props('dense')
                    
                    ui.label('Réduction des pollutions').classes('text-sm text-gray-600 mt-2')
                    ui.textarea(
                        value=cible_03.get('reduction_pollution', ''),
                        on_change=lambda e: cible_03.update({'reduction_pollution': e.value})
                    ).classes('w-full').props('rows=3')
            
            # ========== ÉCO-GESTION ==========
            with ui.expansion('Éco-gestion', icon='settings').classes('w-full bg-blue-50'):
                eco_gestion = demarche_hqe.get('eco_gestion', {})
                
                # Cible 04
                cible_04 = eco_gestion.get('cible_04', {})
                with ui.card().classes('w-full p-3 mb-2'):
                    ui.label('Cible n°04 - Gestion de l\'énergie').classes('font-bold text-blue-700 mb-2')
                    ui.textarea(
                        value=cible_04.get('reduction', ''),
                        on_change=lambda e: cible_04.update({'reduction': e.value})
                    ).classes('w-full').props('rows=2')
                
                # Cible 06
                cible_06 = eco_gestion.get('cible_06', {})
                with ui.card().classes('w-full p-3'):
                    ui.label('Cible n°06 - Gestion des déchets d\'activités').classes('font-bold text-blue-700 mb-2')
                    
                    ui.label('Gestion').classes('text-sm text-gray-600 mt-2')
                    ui.input(
                        value=cible_06.get('gestion', ''),
                        on_change=lambda e: cible_06.update({'gestion': e.value})
                    ).classes('w-full').props('dense')
                    
                    ui.label('Réduction').classes('text-sm text-gray-600 mt-2')
                    ui.textarea(
                        value=cible_06.get('reduction', ''),
                        on_change=lambda e: cible_06.update({'reduction': e.value})
                    ).classes('w-full').props('rows=2')
            
            # ========== DÉMARCHE ENV ATELIER ==========
            with ui.expansion('Démarche environnementale - Atelier & Bureaux', icon='factory').classes('w-full bg-purple-50'):
                with ui.column().classes('w-full gap-2'):
                    # Introduction
                    with ui.card().classes('w-full p-3'):
                        ui.label('Introduction').classes('font-bold text-purple-700 mb-2')
                        ui.textarea(
                            value=demarche_env_atelier.get('intro', ''),
                            on_change=lambda e: demarche_env_atelier.update({'intro': e.value})
                        ).classes('w-full').props('rows=4')
                    
                    # Actions concrètes
                    with ui.card().classes('w-full p-3'):
                        ui.label('Actions concrètes').classes('font-bold text-purple-700 mb-2')
                        actions = demarche_env_atelier.get('actions_concretes', [])
                        for i, action in enumerate(actions):
                            def update_action(e, idx=i, data=demarche_env_atelier, lst=actions):
                                if 'actions_concretes' not in data:
                                    data['actions_concretes'] = lst.copy()
                                if idx < len(data['actions_concretes']):
                                    data['actions_concretes'][idx] = e.value
                            ui.input(value=action, on_change=update_action).classes('w-full').props('dense')
                    
                    # Tri sélectif
                    with ui.card().classes('w-full p-3'):
                        ui.label('Tri sélectif - Introduction').classes('font-bold text-purple-700 mb-2')
                        ui.textarea(
                            value=demarche_env_atelier.get('tri_selectif_intro', ''),
                            on_change=lambda e: demarche_env_atelier.update({'tri_selectif_intro': e.value})
                        ).classes('w-full').props('rows=2')
                        
                        ui.label('Tri sélectif - Détails').classes('font-bold text-purple-700 mt-3 mb-2')
                        tri_items = demarche_env_atelier.get('tri_selectif_items', [])
                        for i, item in enumerate(tri_items):
                            def update_tri(e, idx=i, data=demarche_env_atelier, lst=tri_items):
                                if 'tri_selectif_items' not in data:
                                    data['tri_selectif_items'] = lst.copy()
                                if idx < len(data['tri_selectif_items']):
                                    data['tri_selectif_items'][idx] = e.value
                            ui.input(value=item[:80] + '...' if len(item) > 80 else item, on_change=update_tri).classes('w-full').props('dense')
                    
                    # Diminuer déchets
                    with ui.card().classes('w-full p-3'):
                        ui.label('Diminuer les déchets').classes('font-bold text-purple-700 mb-2')
                        diminuer = demarche_env_atelier.get('diminuer_dechets', [])
                        for i, item in enumerate(diminuer):
                            def update_dim(e, idx=i, data=demarche_env_atelier, lst=diminuer):
                                if 'diminuer_dechets' not in data:
                                    data['diminuer_dechets'] = lst.copy()
                                if idx < len(data['diminuer_dechets']):
                                    data['diminuer_dechets'][idx] = e.value
                            ui.input(value=item, on_change=update_dim).classes('w-full').props('dense')
            
            # ========== DÉMARCHE ENV CHANTIERS ==========
            with ui.expansion('Démarche environnementale - Chantiers', icon='construction').classes('w-full bg-orange-50'):
                with ui.column().classes('w-full gap-2'):
                    # Introduction
                    with ui.card().classes('w-full p-3'):
                        ui.label('Introduction').classes('font-bold text-orange-700 mb-2')
                        ui.textarea(
                            value=demarche_env_chantiers.get('intro', ''),
                            on_change=lambda e: demarche_env_chantiers.update({'intro': e.value})
                        ).classes('w-full').props('rows=4')
                    
                    # Cas 1
                    with ui.card().classes('w-full p-3'):
                        ui.label(demarche_env_chantiers.get('cas_1_titre', 'Cas n°1')).classes('font-bold text-orange-700 mb-2')
                        cas1_items = demarche_env_chantiers.get('cas_1_items', [])
                        for i, item in enumerate(cas1_items):
                            def update_cas1(e, idx=i, data=demarche_env_chantiers, lst=cas1_items):
                                if 'cas_1_items' not in data:
                                    data['cas_1_items'] = lst.copy()
                                if idx < len(data['cas_1_items']):
                                    data['cas_1_items'][idx] = e.value
                            ui.textarea(value=item, on_change=update_cas1).classes('w-full').props('rows=2')
                    
                    # Cas 2
                    with ui.card().classes('w-full p-3'):
                        ui.label(demarche_env_chantiers.get('cas_2_titre', 'Cas n°2')).classes('font-bold text-orange-700 mb-2')
                        ui.input(
                            value=demarche_env_chantiers.get('cas_2_condition', ''),
                            on_change=lambda e: demarche_env_chantiers.update({'cas_2_condition': e.value})
                        ).classes('w-full text-sm').props('dense')
                        
                        cas2_items = demarche_env_chantiers.get('cas_2_items', [])
                        for i, item in enumerate(cas2_items):
                            def update_cas2(e, idx=i, data=demarche_env_chantiers, lst=cas2_items):
                                if 'cas_2_items' not in data:
                                    data['cas_2_items'] = lst.copy()
                                if idx < len(data['cas_2_items']):
                                    data['cas_2_items'][idx] = e.value
                            ui.textarea(value=item, on_change=update_cas2).classes('w-full').props('rows=2')
                    
                    # Proscrit
                    with ui.card().classes('w-full p-3'):
                        ui.label('Il est strictement proscrit de :').classes('font-bold text-red-700 mb-2')
                        proscrit = demarche_env_chantiers.get('proscrit', [])
                        for i, item in enumerate(proscrit):
                            def update_proscrit(e, idx=i, data=demarche_env_chantiers, lst=proscrit):
                                if 'proscrit' not in data:
                                    data['proscrit'] = lst.copy()
                                if idx < len(data['proscrit']):
                                    data['proscrit'][idx] = e.value
                            ui.input(value=item, on_change=update_proscrit).classes('w-full').props('dense')
                    
                    # Cas 3
                    with ui.card().classes('w-full p-3'):
                        ui.label(demarche_env_chantiers.get('cas_3_titre', 'Cas n°3')).classes('font-bold text-orange-700 mb-2')
                        ui.input(
                            value=demarche_env_chantiers.get('cas_3_condition', ''),
                            on_change=lambda e: demarche_env_chantiers.update({'cas_3_condition': e.value})
                        ).classes('w-full text-sm').props('dense')
                        
                        cas3_items = demarche_env_chantiers.get('cas_3_items', [])
                        for i, item in enumerate(cas3_items):
                            def update_cas3(e, idx=i, data=demarche_env_chantiers, lst=cas3_items):
                                if 'cas_3_items' not in data:
                                    data['cas_3_items'] = lst.copy()
                                if idx < len(data['cas_3_items']):
                                    data['cas_3_items'][idx] = e.value
                            ui.input(value=item, on_change=update_cas3).classes('w-full').props('dense')
    
    def _build_annexes_section(self, titre: str):
        """Construit la section Annexes."""
        section_state = self.project_state["sections_data"][titre]
        
        if 'annexes_main' not in section_state:
            section_state['annexes_main'] = {
                'nom': 'Documents annexes',
                'texte': '',
                'image': '',
                'type': 'annexes'
            }
        
        state = section_state['annexes_main']
        
        with ui.column().classes('w-full gap-3 p-2'):
            with ui.card().classes('w-full p-4'):
                ui.label('Documents annexes').classes('font-bold text-blue-700 mb-2')
                ui.label('Ajoutez des documents ou images en annexe').classes('text-sm text-gray-600 mb-2')
                
                # Upload multiple pour annexes
                with ui.row().classes('items-center gap-2'):
                    file_label = ui.label('Aucun fichier').classes('text-xs text-gray-400')
                    
                    async def handle_annexe_upload(e: events.UploadEventArguments, st=state, fl=file_label):
                        with open(self.config.IMAGES_DIR / e.file.name, 'wb') as f:
                            f.write(await e.file.read())
                        st['image'] = str(self.config.IMAGES_DIR / e.file.name)
                        fl.set_text(e.file.name[:20] + '...' if len(e.file.name) > 20 else e.file.name)
                        ui.notify(f'Document {e.file.name} ajouté aux annexes', type='positive')

                    ui.upload(
                        on_upload=handle_annexe_upload,
                        auto_upload=True,
                        max_files=1
                    ).props('accept=".jpg,.jpeg,.png,.pdf" flat dense').classes('w-32')

    def _build_chantiers_references_section(self, titre: str, rows):
        """Construit la section Chantiers Références avec des cadres séparés par sous-section.
        
        Chaque sous-section du CSV devient un cadre:
        - Si le texte contient "/// ou ///", affiche des checkboxes
        - Sinon, affiche un texte éditable
        
        Les nouvelles sous-sections ajoutées dans Base de données apparaissent comme nouveaux cadres.
        """
        section_state = self.project_state["sections_data"][titre]
        
        # Initialiser la liste ordonnée des sous-sections
        order_key = f'_subsection_order_{titre}'
        if order_key not in section_state:
            items = []
            seen_subs = set()
            
            for index, row in rows.iterrows():
                sous_section = nettoyer_str(row.get('sous-section', ''))
                texte_brut = nettoyer_str(row.get('texte', ''))
                image = nettoyer_str(row.get('image', ''))
                couleur = valider_couleur(nettoyer_str(row.get('couleur', 'ecoBleu')))
                
                if not sous_section and not texte_brut and not image:
                    continue
                
                # Eviter doublons
                sub_key = sous_section.lower().strip()
                if sub_key in seen_subs:
                    continue
                seen_subs.add(sub_key)
                
                items.append({
                    'index': index,
                    'sous_section': sous_section,
                    'texte': texte_brut,
                    'image': image,
                    'couleur': couleur,
                    'unique_key': f"ref_{index}_{sub_key}"
                })
            
            section_state[order_key] = items
        
        items = section_state[order_key]
        
        # Container principal
        main_container = ui.column().classes('w-full gap-3 p-2')
        
        def rebuild_section():
            """Reconstruit l'affichage de la section."""
            main_container.clear()
            with main_container:
                for i, item in enumerate(items):
                    self._build_reference_card(items, i, rebuild_section, titre, section_state)
                
                # Bouton ajouter
                def add_new():
                    new_item = {
                        'index': -1,
                        'sous_section': 'Nouvelle référence',
                        'texte': '',
                        'image': '',
                        'couleur': 'ecoBleu',
                        'unique_key': f"ref_new_{len(items)}_{datetime.now().timestamp()}",
                        'is_new': True
                    }
                    items.append(new_item)
                    rebuild_section()
                    ui.notify('Référence ajoutée', type='positive')
                
                ui.button('+ Ajouter une référence', on_click=add_new, icon='add').props('outline color=blue')
        
        rebuild_section()
    
    def _build_reference_card(self, items: list, index: int, rebuild_fn, titre: str, section_state: Dict):
        """Construit une carte de référence chantier avec support pour checkboxes ou texte."""
        item = items[index]
        unique_key = item.get('unique_key', f"ref_{index}")
        
        # Valider et corriger la couleur
        item['couleur'] = valider_couleur(item.get('couleur', 'ecoBleu'))
        couleur_css = LATEX_COLORS.get(item['couleur'], LATEX_COLORS['ecoBleu'])['css']
        
        # Initialiser le state pour cette sous-section si nécessaire
        if unique_key not in section_state:
            section_state[unique_key] = {
                "nom": item['sous_section'],
                "texte": item['texte'],
                "image": item['image'],
                "couleur": item['couleur'],
                "selections": {}
            }
        
        state = section_state[unique_key]
        state['couleur'] = item['couleur']
        
        with ui.card().classes('w-full p-4').style(f'border-left: 4px solid {couleur_css};'):
            # Barre de contrôle en haut
            with ui.row().classes('w-full justify-between items-center mb-3'):
                with ui.row().classes('items-center gap-1'):
                    ui.label(f'#{index + 1}').classes('text-xs text-gray-400 font-mono')
                    
                    def move_up(idx=index):
                        if idx > 0:
                            items[idx], items[idx-1] = items[idx-1], items[idx]
                            rebuild_fn()
                    
                    def move_down(idx=index):
                        if idx < len(items) - 1:
                            items[idx], items[idx+1] = items[idx+1], items[idx]
                            rebuild_fn()
                    
                    ui.button(icon='arrow_upward', on_click=move_up).props('flat dense size=sm').classes('text-gray-500').tooltip('Monter')
                    ui.button(icon='arrow_downward', on_click=move_down).props('flat dense size=sm').classes('text-gray-500').tooltip('Descendre')
                
                def delete_item(idx=index, uk=unique_key):
                    if len(items) > 0:
                        items.pop(idx)
                        if uk in section_state:
                            del section_state[uk]
                        rebuild_fn()
                        ui.notify('Référence supprimée', type='info')
                
                ui.button(icon='delete', on_click=delete_item).props('flat dense size=sm color=red').tooltip('Supprimer')
                
                # Sélecteur de couleur
                color_options = {k: f"{v['nom']}" for k, v in LATEX_COLORS.items()}
                def update_color(e, it=item, st=state):
                    it['couleur'] = e.value
                    st['couleur'] = e.value
                    rebuild_fn()
                
                with ui.row().classes('items-center gap-1 ml-2'):
                    ui.icon('palette', size='xs').classes('text-gray-400')
                    ui.select(options=color_options, value=item.get('couleur', 'ecoBleu'), on_change=update_color).props('dense outlined').classes('w-28').style(f'background-color: {couleur_css}20;')
            
            # Titre éditable
            ui.label('Titre de la sous-section:').classes('text-xs text-gray-500')
            def update_nom(e, st=state, it=item):
                st['nom'] = e.value
                it['sous_section'] = e.value
            ui.input(value=state.get('nom', item['sous_section']), on_change=update_nom).classes('w-full mb-2')
            
            # Contenu : checkboxes si "/// ou ///" sinon textarea
            texte = item.get('texte', '')
            
            if "/// ou ///" in texte:
                # Options multiples avec checkboxes (premier coché par défaut)
                ui.label('Références disponibles (cochez celles à inclure):').classes('text-xs text-gray-500')
                options = [o.strip() for o in texte.split("/// ou ///") if o.strip()]
                
                if 'options' not in state['selections']:
                    state['selections']['options'] = {opt: (i == 0) for i, opt in enumerate(options)}
                
                checkbox_container = ui.column().classes('gap-1')
                checkbox_widgets = []
                
                with checkbox_container:
                    for opt in options:
                        is_checked = state['selections']['options'].get(opt, False)
                        def update_opt(e, o=opt, st=state):
                            st['selections']['options'][o] = e.value
                        cb = ui.checkbox(opt, value=is_checked, on_change=update_opt).classes('text-sm')
                        checkbox_widgets.append((opt, cb))
                
                # Boutons Tout cocher / Tout décocher
                with ui.row().classes('gap-2 mt-2'):
                    def check_all(widgets=checkbox_widgets, st=state):
                        for opt_name, cb_widget in widgets:
                            cb_widget.set_value(True)
                            st['selections']['options'][opt_name] = True
                    
                    def uncheck_all(widgets=checkbox_widgets, st=state):
                        for opt_name, cb_widget in widgets:
                            cb_widget.set_value(False)
                            st['selections']['options'][opt_name] = False
                    
                    ui.button('✓ Tout cocher', on_click=check_all).props('flat color=green size=sm')
                    ui.button('✗ Tout décocher', on_click=uncheck_all).props('flat color=red size=sm')
            else:
                # Texte simple éditable
                ui.label('Contenu:').classes('text-xs text-gray-500')
                current_texte = state.get('texte', texte)
                def update_texte(e, st=state, it=item):
                    st['texte'] = e.value
                    it['texte'] = e.value
                ui.textarea(value=current_texte, on_change=update_texte).classes('w-full').props('rows=3 outlined')

    def _build_moyens_materiel_section(self, titre: str, rows):
        """Construit la section Moyens Matériel avec intro éditable + sous-sections CSV."""
        section_state = self.project_state["sections_data"][titre]
        template_data = self.project_state.get("template_data", {})
        if not isinstance(template_data, dict):
            template_data = {}
        moyens_materiel = template_data.get("moyens_materiel", {})
        if not isinstance(moyens_materiel, dict):
            moyens_materiel = {}
        
        # Initialiser la liste ordonnée si pas encore fait
        order_key = f'_subsection_order_{titre}'
        if order_key not in section_state:
            items = []
            seen_subs = set()
            
            # Ajouter le cadre "Un parc machines" en premier
            default_intro = "L'entreprise Bois & Techniques dispose d'un parc matériel complet et régulièrement entretenu, permettant d'assurer la qualité et la sécurité de nos interventions."
            intro_text = moyens_materiel.get('intro', default_intro) if isinstance(moyens_materiel, dict) else default_intro
            
            items.append({
                'index': -1,
                'sous_section': 'Un parc machines récent, certifié et entretenu',
                'texte': intro_text,
                'image': '',
                'couleur': 'ecoBleu',
                'unique_key': 'intro_parc_machines'
            })
            seen_subs.add('un parc machines récent, certifié et entretenu')
            
            # Ajouter les autres sous-sections depuis le CSV
            for index, row in rows.iterrows():
                sous_section = nettoyer_str(row.get('sous-section', ''))
                texte_brut = nettoyer_str(row.get('texte', ''))
                image = nettoyer_str(row.get('image', ''))
                couleur = valider_couleur(nettoyer_str(row.get('couleur', 'ecoBleu')))
                
                if not sous_section and not texte_brut and not image:
                    continue
                
                # Eviter doublons
                sub_key = sous_section.lower().strip()
                if sub_key in seen_subs:
                    continue
                seen_subs.add(sub_key)
                
                items.append({
                    'index': index,
                    'sous_section': sous_section,
                    'texte': texte_brut,
                    'image': image,
                    'couleur': couleur,
                    'unique_key': f"{index}_{sub_key}"
                })
            
            section_state[order_key] = items
        
        items = section_state[order_key]
        
        # Container principal
        main_container = ui.column().classes('w-full gap-3 p-2')
        
        def rebuild_section():
            """Reconstruit l'affichage de la section."""
            main_container.clear()
            with main_container:
                for i, item in enumerate(items):
                    self._build_subsection_card_generation(items, i, rebuild_section, titre, section_state)
                
                # Bouton ajouter
                def add_new():
                    new_item = {
                        'index': -1,
                        'sous_section': 'Nouvelle sous-section',
                        'texte': '',
                        'image': '',
                        'couleur': 'ecoBleu',
                        'unique_key': f"new_{len(items)}_{datetime.now().timestamp()}",
                        'is_new': True
                    }
                    items.append(new_item)
                    rebuild_section()
                    ui.notify('Sous-section ajoutée', type='positive')
                
                ui.button('+ Ajouter une sous-section', on_click=add_new, icon='add').props('outline color=blue')
        
        rebuild_section()

    def _build_moyens_humains_section(self, titre: str, rows):
        """Construit la section Moyens Humains avec équipe réorganisable + sécurité/santé."""
        section_state = self.project_state["sections_data"][titre]
        template_data = self.project_state.get("template_data", {})
        if not isinstance(template_data, dict):
            template_data = {}
        
        securite_sante = template_data.get("securite_sante", {})
        moyens_humains = template_data.get("moyens_humains", {})
        
        # ===== Créer la liste ordonnée pour L'ÉQUIPE =====
        order_key = f'_equipe_order_{titre}'
        if order_key not in section_state:
            items = []
            seen_subs = set()
            
            # D'abord essayer de charger depuis le CSV
            for index, row in rows.iterrows():
                sous_section = row.get('sous-section', '') if not pd.isna(row.get('sous-section', '')) else ''
                texte_brut = row.get('texte', '') if not pd.isna(row.get('texte', '')) else ''
                image = row.get('image', '') if not pd.isna(row.get('image', '')) else ''
                couleur = valider_couleur(row.get('couleur', 'ecoBleu') if not pd.isna(row.get('couleur', '')) else 'ecoBleu')
                
                if not sous_section:
                    continue
                
                ss_lower = sous_section.lower()
                
                # Ignorer sécurité/santé et organigramme - on les gère séparément
                if ('sécurité' in ss_lower and 'santé' in ss_lower) or 'organigramme' in ss_lower:
                    continue
                
                # Eviter doublons
                sub_key = sous_section.lower().strip()
                if sub_key in seen_subs:
                    continue
                seen_subs.add(sub_key)
                
                items.append({
                    'index': index,
                    'sous_section': sous_section,
                    'texte': texte_brut,
                    'image': image,
                    'couleur': couleur,
                    'unique_key': f"equipe_{index}_{sub_key}"
                })
            
            # FALLBACK: Si pas de données dans CSV, charger depuis template_data
            if not items and moyens_humains:
                idx = 0
                
                # Chargé d'affaires
                ca = moyens_humains.get('charge_affaires', {})
                ca_nom = ca.get('nom', 'Frédéric ANSELM')
                ca_desc = ca.get('description', '')
                if ca_nom or ca_desc:
                    items.append({
                        'index': idx,
                        'sous_section': f'Chargé d\'affaires : {ca_nom}',
                        'texte': ca_desc,
                        'image': '',
                        'couleur': 'ecoBleu',
                        'unique_key': f"equipe_{idx}_charge_affaires"
                    })
                    idx += 1
                
                # Chefs d'équipe
                chefs = moyens_humains.get('chefs_equipe', {})
                chefs_noms = chefs.get('noms', [])
                chefs_desc = chefs.get('description', '')
                if chefs_noms:
                    noms_str = ' /// ou /// '.join(chefs_noms) if isinstance(chefs_noms, list) else chefs_noms
                    items.append({
                        'index': idx,
                        'sous_section': f'Chef d\'équipe : {noms_str}',
                        'texte': chefs_desc,
                        'image': '',
                        'couleur': 'ecoVert',
                        'unique_key': f"equipe_{idx}_chef_equipe"
                    })
                    idx += 1
                
                # Charpentiers
                charp = moyens_humains.get('charpentiers', {})
                charp_noms = charp.get('noms', [])
                charp_desc = charp.get('description', '')
                if charp_noms or charp_desc:
                    noms_str = ' /// ou /// '.join(charp_noms) if isinstance(charp_noms, list) else (charp_noms or 'Équipe charpentiers')
                    items.append({
                        'index': idx,
                        'sous_section': f'Charpentiers : {noms_str}',
                        'texte': charp_desc,
                        'image': '',
                        'couleur': 'ecoOrange',
                        'unique_key': f"equipe_{idx}_charpentiers"
                    })
                    idx += 1
            
            section_state[order_key] = items
        
        equipe_items = section_state[order_key]
        
        # Initialiser sécurité/santé depuis template_data
        if 'securite_sante_data' not in section_state:
            # Charger les couleurs sauvegardées depuis template_data
            couleurs_sauvees = securite_sante.get('couleurs', {})
            noms_sauves = securite_sante.get('noms', {})
            
            section_state['securite_sante_data'] = {
                'organisation_production': securite_sante.get('organisation_production', ''),
                'confort_travail': securite_sante.get('confort_travail', ''),
                'accueil_nouveaux': securite_sante.get('accueil_nouveaux', ''),
                'securite_generale': securite_sante.get('securite_generale', ''),
                'concretement': securite_sante.get('concretement', []),
                'habilitations': securite_sante.get('habilitations', []),
                'controle_annuel': securite_sante.get('controle_annuel', ''),
                'couleurs': couleurs_sauvees if couleurs_sauvees else {
                    'organisation_production': 'ecoBleu',
                    'confort_travail': 'ecoVert',
                    'accueil_nouveaux': 'ecoOrange',
                    'securite_generale': 'ecoRouge',
                    'concretement': 'ecoMarron',
                    'habilitations': 'ecoViolet',
                    'controle_annuel': 'ecoJaune',
                },
                'noms': noms_sauves if noms_sauves else {
                    'organisation_production': 'Organisation de production',
                    'confort_travail': 'Confort de travail',
                    'accueil_nouveaux': 'Accueil des nouveaux salariés',
                    'securite_generale': 'Sécurité et santé sur les chantiers',
                    'concretement': 'Concrètement',
                    'habilitations': 'Habilitations',
                    'controle_annuel': 'Contrôle annuel',
                },
            }
        
        ss_state = section_state['securite_sante_data']
        
        # Assurer que les couleurs et noms existent
        if 'couleurs' not in ss_state:
            ss_state['couleurs'] = securite_sante.get('couleurs', {
                'organisation_production': 'ecoBleu',
                'confort_travail': 'ecoVert',
                'accueil_nouveaux': 'ecoOrange',
                'securite_generale': 'ecoRouge',
                'concretement': 'ecoMarron',
                'habilitations': 'ecoViolet',
                'controle_annuel': 'ecoJaune',
            })
        if 'noms' not in ss_state:
            ss_state['noms'] = securite_sante.get('noms', {})
        
        with ui.column().classes('w-full gap-3 p-2'):
            # ===== SECTION 1: L'ÉQUIPE (réorganisable) =====
            ui.label('L\'ÉQUIPE').classes('text-lg font-bold text-blue-900 mt-2 mb-2 border-b-2 border-blue-200 pb-2')
            
            equipe_container = ui.column().classes('w-full gap-3')
            
            def rebuild_equipe():
                """Reconstruit l'affichage de l'équipe."""
                equipe_container.clear()
                with equipe_container:
                    for i, item in enumerate(equipe_items):
                        self._build_equipe_card(equipe_items, i, rebuild_equipe, titre, section_state)
                    
                    # Bouton ajouter
                    def add_new_equipe():
                        new_item = {
                            'index': -1,
                            'sous_section': 'Nouveau membre',
                            'texte': '',
                            'image': '',
                            'couleur': 'ecoBleu',
                            'unique_key': f"equipe_new_{len(equipe_items)}_{datetime.now().timestamp()}"
                        }
                        equipe_items.append(new_item)
                        rebuild_equipe()
                        ui.notify('Membre ajouté', type='positive')
                    
                    ui.button('+ Ajouter un membre', on_click=add_new_equipe, icon='add').props('outline color=blue')
            
            with equipe_container:
                rebuild_equipe()
            
            # ===== SECTION 2: SÉCURITÉ ET SANTÉ SUR LES CHANTIERS (liste ordonnée) =====
            ui.label('SÉCURITÉ ET SANTÉ SUR LES CHANTIERS').classes('text-lg font-bold text-blue-900 mt-6 mb-2 border-b-2 border-blue-200 pb-2')
            
            # Créer la liste ordonnée pour sécurité/santé
            ss_order_key = '_securite_order_'
            if ss_order_key not in section_state:
                # Définir l'ordre des clés (peut être personnalisé depuis template_data)
                ordre_sauve = securite_sante.get('_order', [
                    'organisation_production', 'confort_travail', 'accueil_nouveaux',
                    'securite_generale', 'concretement', 'habilitations', 'controle_annuel'
                ])
                noms_sauves = ss_state.get('noms', {})
                couleurs = ss_state.get('couleurs', {})
                
                # Types par clé
                types_map = {
                    'organisation_production': 'text', 'confort_travail': 'text', 
                    'accueil_nouveaux': 'text', 'securite_generale': 'text',
                    'concretement': 'list', 'habilitations': 'list', 'controle_annuel': 'text'
                }
                
                # Noms par défaut
                noms_defaut = {
                    'organisation_production': 'Organisation de production',
                    'confort_travail': 'Confort de travail',
                    'accueil_nouveaux': 'Accueil des nouveaux salariés',
                    'securite_generale': 'Sécurité et santé sur les chantiers',
                    'concretement': 'Concrètement',
                    'habilitations': 'Habilitations',
                    'controle_annuel': 'Contrôle annuel',
                }
                
                # Construire la liste ordonnée
                section_state[ss_order_key] = []
                for key in ordre_sauve:
                    section_state[ss_order_key].append({
                        'key': key,
                        'nom': noms_sauves.get(key, noms_defaut.get(key, key)),
                        'type': types_map.get(key, 'text'),
                        'contenu': ss_state.get(key, [] if types_map.get(key) == 'list' else ''),
                        'couleur': couleurs.get(key, 'ecoBleu'),
                    })
            
            ss_items = section_state[ss_order_key]
            ss_container = ui.column().classes('w-full gap-3')
            
            def rebuild_ss():
                """Reconstruit l'affichage de sécurité/santé."""
                ss_container.clear()
                with ss_container:
                    for i, item in enumerate(ss_items):
                        self._build_securite_card(ss_items, i, rebuild_ss, section_state, ss_state)
                    
                    # Bouton pour ajouter un nouveau cadre
                    def add_new_ss():
                        new_key = f'custom_ss_{len(ss_items)}_{datetime.now().timestamp()}'
                        new_item = {
                            'key': new_key,
                            'nom': 'Nouveau cadre',
                            'type': 'text',
                            'contenu': '',
                            'couleur': 'ecoBleu',
                        }
                        ss_items.append(new_item)
                        rebuild_ss()
                        ui.notify('Cadre ajouté', type='positive')
                    
                    ui.button('+ Ajouter un cadre', on_click=add_new_ss, icon='add').props('outline color=blue')
            
            with ss_container:
                rebuild_ss()
            
            # ===== SECTION 3: ORGANIGRAMME =====
            ui.label('ORGANIGRAMME').classes('text-lg font-bold text-blue-900 mt-6 mb-2 border-b-2 border-blue-200 pb-2')
            
            org_image = ''
            for idx, row in rows.iterrows():
                ss = row.get('sous-section', '') if not pd.isna(row.get('sous-section', '')) else ''
                if 'organigramme' in ss.lower():
                    org_image = row.get('image', '') if not pd.isna(row.get('image', '')) else ''
                    break
            
            if 'organigramme' not in section_state:
                section_state['organigramme'] = {'image': org_image or '../images/organigramme.png', 'type': 'organigramme'}
            
            with ui.card().classes('w-full p-4'):
                ui.label('Image de l\'organigramme').classes('text-xs text-gray-500 mb-2')
                org_state = section_state['organigramme']
                with ui.row().classes('items-center gap-4 w-full'):
                    def update_org_path(e):
                        org_state['image'] = e.value
                    ui.input(value=org_state['image'], on_change=update_org_path).classes('flex-grow')
                    async def handle_org_upload(e: events.UploadEventArguments):
                        with open(self.config.IMAGES_DIR / e.file.name, 'wb') as f:
                            f.write(await e.file.read())
                        org_state['image'] = str(self.config.IMAGES_DIR / e.file.name)
                        ui.notify(f'Organigramme {e.file.name} chargé', type='positive')
                    ui.upload(on_upload=handle_org_upload, auto_upload=True, max_files=1).props('accept=".jpg,.jpeg,.png,.pdf" flat dense').classes('w-32')

    def _build_equipe_card(self, items: list, index: int, rebuild_fn, titre: str, section_state: Dict):
        """Construit une carte de membre d'équipe avec contrôles de réordonnancement."""
        item = items[index]
        unique_key = item.get('unique_key', f"equipe_{index}")
        
        # Valider et corriger la couleur
        item['couleur'] = valider_couleur(item.get('couleur', 'ecoBleu'))
        
        couleur_css = LATEX_COLORS.get(item['couleur'], LATEX_COLORS['ecoBleu'])['css']
        
        with ui.card().classes('w-full p-4').style(f'border-left: 4px solid {couleur_css};'):
            with ui.row().classes('w-full justify-between items-center mb-3'):
                with ui.row().classes('items-center gap-1'):
                    ui.label(f'#{index + 1}').classes('text-xs text-gray-400 font-mono')
                    
                    def move_up(idx=index):
                        if idx > 0:
                            items[idx], items[idx-1] = items[idx-1], items[idx]
                            rebuild_fn()
                    
                    def move_down(idx=index):
                        if idx < len(items) - 1:
                            items[idx], items[idx+1] = items[idx+1], items[idx]
                            rebuild_fn()
                    
                    ui.button(icon='arrow_upward', on_click=move_up).props('flat dense size=sm').classes('text-gray-500').tooltip('Monter')
                    ui.button(icon='arrow_downward', on_click=move_down).props('flat dense size=sm').classes('text-gray-500').tooltip('Descendre')
                
                def delete_item(idx=index, uk=unique_key):
                    if len(items) > 0:
                        items.pop(idx)
                        rebuild_fn()
                        ui.notify('Membre supprimé', type='info')
                
                ui.button(icon='delete', on_click=delete_item).props('flat dense size=sm color=red').tooltip('Supprimer')
                
                color_options = {k: f"{v['nom']}" for k, v in LATEX_COLORS.items()}
                def update_color(e, it=item):
                    it['couleur'] = e.value
                    rebuild_fn()
                
                with ui.row().classes('items-center gap-1 ml-2'):
                    ui.icon('palette', size='xs').classes('text-gray-400')
                    ui.select(options=color_options, value=item.get('couleur', 'ecoBleu'), on_change=update_color).props('dense outlined').classes('w-28').style(f'background-color: {couleur_css}20;')
            
            # Contenu
            sous_section = item['sous_section']
            
            if "/// ou ///" in sous_section:
                parts = sous_section.split(":")
                prefix = parts[0].strip()
                options_str = parts[1] if len(parts) > 1 else sous_section
                options = [o.strip() for o in options_str.split("/// ou ///") if o.strip()]
                
                ui.label(prefix).classes('font-bold text-blue-700 mb-2')
                
                if 'selections' not in item:
                    item['selections'] = {'noms': {}}
                    for i, opt in enumerate(options):
                        item['selections']['noms'][opt] = (i == 0)
                
                with ui.row().classes('gap-3 flex-wrap'):
                    for opt in options:
                        is_checked = item['selections']['noms'].get(opt, False)
                        def update_selection(e, o=opt, it=item):
                            it['selections']['noms'][o] = e.value
                        ui.checkbox(opt, value=is_checked, on_change=update_selection)
            else:
                ui.label('Titre:').classes('text-xs text-gray-500')
                def update_nom(e, it=item):
                    it['sous_section'] = e.value
                ui.input(value=sous_section, on_change=update_nom).classes('w-full mb-2')
            
            ui.label('Description :').classes('text-xs text-gray-500 mt-2')
            def update_texte(e, it=item):
                it['texte'] = e.value
            ui.textarea(value=item.get('texte', ''), on_change=update_texte).classes('w-full').props('rows=4 outlined')

    def _build_securite_card(self, items: list, index: int, rebuild_fn, section_state: Dict, ss_state: Dict):
        """Construit une carte de sécurité/santé avec contrôles de réordonnancement."""
        item = items[index]
        
        # Valider et corriger la couleur
        item['couleur'] = valider_couleur(item.get('couleur', 'ecoBleu'))
        
        couleur_css = LATEX_COLORS.get(item['couleur'], LATEX_COLORS['ecoBleu'])['css']
        
        with ui.card().classes('w-full p-4').style(f'border-left: 4px solid {couleur_css};'):
            with ui.row().classes('w-full justify-between items-center mb-3'):
                with ui.row().classes('items-center gap-1'):
                    ui.label(f'#{index + 1}').classes('text-xs text-gray-400 font-mono')
                    
                    def move_up(idx=index):
                        if idx > 0:
                            items[idx], items[idx-1] = items[idx-1], items[idx]
                            rebuild_fn()
                    
                    def move_down(idx=index):
                        if idx < len(items) - 1:
                            items[idx], items[idx+1] = items[idx+1], items[idx]
                            rebuild_fn()
                    
                    ui.button(icon='arrow_upward', on_click=move_up).props('flat dense size=sm').classes('text-gray-500').tooltip('Monter')
                    ui.button(icon='arrow_downward', on_click=move_down).props('flat dense size=sm').classes('text-gray-500').tooltip('Descendre')
                
                with ui.row().classes('items-center gap-2'):
                    # Bouton supprimer
                    def delete_item(idx=index):
                        if len(items) > 1:  # Garder au moins un cadre
                            items.pop(idx)
                            rebuild_fn()
                            ui.notify('Cadre supprimé', type='info')
                        else:
                            ui.notify('Impossible de supprimer le dernier cadre', type='warning')
                    
                    ui.button(icon='delete', on_click=delete_item).props('flat dense size=sm color=red').tooltip('Supprimer ce cadre')
                    
                    # Sélecteur de couleur
                    color_options = {k: f"{v['nom']}" for k, v in LATEX_COLORS.items()}
                    def update_color(e, it=item, key=item.get('key', '')):
                        it['couleur'] = e.value
                        # Synchroniser avec ss_state
                        if key and 'couleurs' in ss_state:
                            ss_state['couleurs'][key] = e.value
                        rebuild_fn()
                    
                    ui.icon('palette', size='xs').classes('text-gray-400')
                    ui.select(options=color_options, value=item.get('couleur', 'ecoBleu'), on_change=update_color).props('dense outlined').classes('w-28').style(f'background-color: {couleur_css}20;')
            
            # Titre du cadre (éditable)
            ui.label('Titre :').classes('text-xs text-gray-500')
            def update_nom(e, it=item, k=item.get('key', '')):
                it['nom'] = e.value
                # Synchroniser avec ss_state
                if k and 'noms' in ss_state:
                    ss_state['noms'][k] = e.value
            ui.input(value=item.get('nom', 'Cadre'), on_change=update_nom).props('outlined').classes('font-bold text-blue-700 mb-2 w-full')
            
            # Contenu selon le type
            item_type = item.get('type', 'text')
            key = item.get('key', '')
            
            if item_type == 'list':
                # Pour les listes (concretement, habilitations)
                contenu = item.get('contenu', [])
                if isinstance(contenu, list):
                    contenu_str = '\n'.join(contenu)
                else:
                    contenu_str = str(contenu)
                
                ui.label('(un élément par ligne)').classes('text-xs text-gray-400 italic mb-1')
                
                def update_list_content(e, it=item, k=key):
                    lines = [l.strip() for l in e.value.split('\n') if l.strip()]
                    it['contenu'] = lines
                    # Synchroniser avec ss_state
                    if k:
                        ss_state[k] = lines
                
                ui.textarea(value=contenu_str, on_change=update_list_content).classes('w-full').props('rows=6 outlined')
            else:
                # Pour les textes
                contenu = item.get('contenu', '')
                
                def update_text_content(e, it=item, k=key):
                    it['contenu'] = e.value
                    # Synchroniser avec ss_state
                    if k:
                        ss_state[k] = e.value
                
                ui.textarea(value=contenu, on_change=update_text_content).classes('w-full').props('rows=4 outlined')

    def _build_transport_levage_section(self, titre: str, section_state: Dict):
        """Construit la sous-section Transport et Levage avec cartes réordonnables."""
        template_data = self.project_state.get("template_data", {})
        transport_levage = template_data.get("transport_levage", {})
        
        # Initialiser la liste ordonnée des cartes transport/levage
        tl_order_key = '_transport_levage_order_'
        if tl_order_key not in section_state:
            # Définir les cartes par défaut
            couleurs = transport_levage.get('couleurs', {})
            noms = transport_levage.get('noms', {})
            
            section_state[tl_order_key] = [
                {'key': 'intro', 'nom': noms.get('intro', 'Introduction'), 'type': 'text',
                 'contenu': transport_levage.get('intro', ''), 'couleur': couleurs.get('intro', 'ecoBleu')},
                {'key': 'livraison', 'nom': noms.get('livraison', 'Livraison'), 'type': 'checklist',
                 'contenu': transport_levage.get('livraison_options', []), 'couleur': couleurs.get('livraison', 'ecoVert')},
                {'key': 'levage', 'nom': noms.get('levage', 'Levage'), 'type': 'checklist',
                 'contenu': transport_levage.get('levage_options', []), 'couleur': couleurs.get('levage', 'ecoOrange')},
                {'key': 'ouvrages_livres', 'nom': noms.get('ouvrages_livres', 'Stockage des ouvrages livrés'), 'type': 'text',
                 'contenu': transport_levage.get('ouvrages_livres', ''), 'couleur': couleurs.get('ouvrages_livres', 'ecoMarron')},
                {'key': 'encadrement', 'nom': noms.get('encadrement', 'Encadrement'), 'type': 'text',
                 'contenu': transport_levage.get('encadrement', ''), 'couleur': couleurs.get('encadrement', 'ecoViolet')},
                {'key': 'sous_traitance', 'nom': noms.get('sous_traitance', 'Sous-traitance'), 'type': 'text',
                 'contenu': transport_levage.get('sous_traitance', ''), 'couleur': couleurs.get('sous_traitance', 'ecoJaune')},
            ]
            
            # Initialiser les sélections pour checklists avec le premier item coché par défaut
            livraison_options = transport_levage.get('livraison_options', [])
            levage_options = transport_levage.get('levage_options', [])
            
            section_state['_tl_selections_'] = {
                'livraison': {opt: (i == 0) for i, opt in enumerate(livraison_options)},
                'levage': {opt: (i == 0) for i, opt in enumerate(levage_options)}
            }
        
        tl_items = section_state[tl_order_key]
        tl_selections = section_state.get('_tl_selections_', {'livraison': {}, 'levage': {}})
        
        tl_container = ui.column().classes('w-full gap-3')
        
        def rebuild_tl():
            """Reconstruit l'affichage des cartes transport/levage."""
            tl_container.clear()
            with tl_container:
                for i in range(len(tl_items)):
                    self._build_transport_levage_card(tl_items, i, rebuild_tl, section_state, tl_selections)
                
                # Bouton pour ajouter une nouvelle carte
                def add_card():
                    new_item = {
                        'key': f'custom_{len(tl_items)}',
                        'nom': 'Nouvelle section',
                        'type': 'text',
                        'contenu': '',
                        'couleur': 'ecoBleu'
                    }
                    tl_items.append(new_item)
                    rebuild_tl()
                    ui.notify('Section ajoutée', type='positive')
                
                ui.button('+ Ajouter une section', on_click=add_card, icon='add').props('outline color=blue').classes('mt-2')
        
        with tl_container:
            rebuild_tl()

    def _build_transport_levage_card(self, items: list, index: int, rebuild_fn, section_state: Dict, tl_selections: Dict):
        """Construit une carte de transport/levage avec contrôles de réordonnancement."""
        item = items[index]
        
        # Valider et corriger la couleur
        item['couleur'] = valider_couleur(item.get('couleur', 'ecoBleu'))
        
        couleur_css = LATEX_COLORS.get(item['couleur'], LATEX_COLORS['ecoBleu'])['css']
        
        with ui.card().classes('w-full p-4').style(f'border-left: 4px solid {couleur_css};'):
            with ui.row().classes('w-full justify-between items-center mb-3'):
                with ui.row().classes('items-center gap-1'):
                    ui.label(f'#{index + 1}').classes('text-xs text-gray-400 font-mono')
                    
                    def move_up(idx=index):
                        if idx > 0:
                            items[idx], items[idx-1] = items[idx-1], items[idx]
                            rebuild_fn()
                    
                    def move_down(idx=index):
                        if idx < len(items) - 1:
                            items[idx], items[idx+1] = items[idx+1], items[idx]
                            rebuild_fn()
                    
                    ui.button(icon='arrow_upward', on_click=move_up).props('flat dense size=sm').classes('text-gray-500').tooltip('Monter')
                    ui.button(icon='arrow_downward', on_click=move_down).props('flat dense size=sm').classes('text-gray-500').tooltip('Descendre')
                
                with ui.row().classes('items-center gap-2'):
                    # Bouton supprimer
                    def delete_item(idx=index):
                        if len(items) > 1:
                            items.pop(idx)
                            rebuild_fn()
                            ui.notify('Section supprimée', type='info')
                    
                    ui.button(icon='delete', on_click=delete_item).props('flat dense size=sm color=red').tooltip('Supprimer cette section')
                    
                    # Sélecteur de couleur
                    color_options = {k: f"{v['nom']}" for k, v in LATEX_COLORS.items()}
                    def update_color(e, it=item):
                        it['couleur'] = e.value
                        rebuild_fn()
                    
                    ui.icon('palette', size='xs').classes('text-gray-400')
                    ui.select(options=color_options, value=item.get('couleur', 'ecoBleu'), on_change=update_color).props('dense outlined').classes('w-28').style(f'background-color: {couleur_css}20;')
            
            # Titre du cadre (éditable)
            ui.label('Titre :').classes('text-xs text-gray-500')
            def update_nom(e, it=item):
                it['nom'] = e.value
            ui.input(value=item.get('nom', 'Section'), on_change=update_nom).props('outlined').classes('font-bold text-blue-700 mb-2 w-full')
            
            # Contenu selon le type
            item_type = item.get('type', 'text')
            key = item.get('key', '')
            
            if item_type == 'checklist':
                # Pour les listes avec checkboxes (livraison, levage)
                options = item.get('contenu', [])
                if not isinstance(options, list):
                    options = []
                
                ui.label('Options disponibles (cochez celles à inclure)').classes('text-xs text-gray-400 italic mb-1')
                
                # Container pour checkboxes
                checkbox_container = ui.column().classes('w-full gap-1')
                checkbox_widgets = []
                
                # Initialiser les sélections si nécessaire - premier coché par défaut
                if key not in tl_selections:
                    tl_selections[key] = {opt: (i == 0) for i, opt in enumerate(options)}
                elif not tl_selections[key]:
                    # Si les sélections sont vides, initialiser avec le premier coché
                    tl_selections[key] = {opt: (i == 0) for i, opt in enumerate(options)}
                
                def rebuild_checkboxes():
                    checkbox_container.clear()
                    checkbox_widgets.clear()
                    with checkbox_container:
                        for i, opt in enumerate(options):
                            is_checked = tl_selections[key].get(opt, (i == 0))
                            def update_sel(e, o=opt, k=key):
                                tl_selections[k][o] = e.value
                            cb = ui.checkbox(opt, value=is_checked, on_change=update_sel).classes('text-sm')
                            checkbox_widgets.append((opt, cb))
                
                with checkbox_container:
                    rebuild_checkboxes()
                
                # Boutons tout cocher/décocher et ajouter
                with ui.row().classes('gap-2 mt-2 flex-wrap'):
                    def check_all(k=key):
                        for opt in options:
                            tl_selections[k][opt] = True
                        rebuild_checkboxes()
                    
                    def uncheck_all(k=key):
                        for opt in options:
                            tl_selections[k][opt] = False
                        rebuild_checkboxes()
                    
                    ui.button('✓ Tout', on_click=check_all).props('flat color=green size=sm')
                    ui.button('✗ Aucun', on_click=uncheck_all).props('flat color=red size=sm')
                    
                    # Ajouter une option
                    new_opt_input = ui.input(placeholder='Nouvelle option...').props('dense outlined').classes('w-40')
                    def add_option(it=item, k=key):
                        val = new_opt_input.value.strip()
                        if val and val not in it['contenu']:
                            it['contenu'].append(val)
                            tl_selections[k][val] = True
                            new_opt_input.value = ''
                            rebuild_checkboxes()
                    ui.button('+', on_click=add_option).props('dense size=sm color=blue')
                    
            else:
                # Pour les textes
                contenu = item.get('contenu', '')
                
                def update_text_content(e, it=item):
                    it['contenu'] = e.value
                
                ui.textarea(value=contenu, on_change=update_text_content).classes('w-full').props('rows=4 outlined')

    def _build_situation_admin_section(self, titre: str):
        """Construit la section Situation Administrative avec champs modifiables."""
        template_data = self.project_state.get("template_data", {})
        situation_admin = template_data.get("situation_administrative", {})
        
        with ui.column().classes('w-full gap-3 p-2'):
            # Qualifications
            with ui.card().classes('w-full p-4'):
                ui.label('Qualifications RGE QUALIBAT').classes('font-bold text-blue-700 mb-2')
                
                # S'assurer que qualifications est une liste dans situation_admin
                if 'qualifications' not in situation_admin:
                    situation_admin['qualifications'] = []
                qualifs = situation_admin['qualifications']
                
                # Container pour les qualifications
                qualifs_container = ui.column().classes('w-full gap-2')
                
                def update_qualif(idx, value):
                    if idx < len(situation_admin['qualifications']):
                        situation_admin['qualifications'][idx] = value
                
                def remove_qualif(idx, container):
                    if idx < len(situation_admin['qualifications']):
                        situation_admin['qualifications'].pop(idx)
                        # Rafraîchir l'affichage
                        container.clear()
                        with container:
                            for i, q in enumerate(situation_admin['qualifications']):
                                with ui.row().classes('w-full items-center gap-2'):
                                    ui.input(
                                        value=q,
                                        on_change=lambda e, idx=i: update_qualif(idx, e.value)
                                    ).classes('flex-1').props('dense')
                                    ui.button(icon='delete', on_click=lambda idx=i: remove_qualif(idx, container)).props('flat dense color=red size=sm')
                
                def add_qualif(container):
                    new_qualif = "Nouvelle qualification"
                    situation_admin['qualifications'].append(new_qualif)
                    idx = len(situation_admin['qualifications']) - 1
                    with container:
                        with ui.row().classes('w-full items-center gap-2'):
                            ui.input(
                                value=new_qualif,
                                on_change=lambda e, idx=idx: update_qualif(idx, e.value)
                            ).classes('flex-1').props('dense')
                            ui.button(icon='delete', on_click=lambda idx=idx: remove_qualif(idx, container)).props('flat dense color=red size=sm')
                
                with qualifs_container:
                    for i, q in enumerate(qualifs):
                        with ui.row().classes('w-full items-center gap-2'):
                            ui.input(
                                value=q,
                                on_change=lambda e, idx=i: update_qualif(idx, e.value)
                            ).classes('flex-1').props('dense')
                            ui.button(icon='delete', on_click=lambda idx=i: remove_qualif(idx, qualifs_container)).props('flat dense color=red size=sm')
                
                # Bouton pour ajouter une qualification
                ui.button('+ Ajouter une qualification', on_click=lambda: add_qualif(qualifs_container)).props('flat color=blue size=sm').classes('mt-2')
            
            # Effectifs
            with ui.card().classes('w-full p-4'):
                ui.label('Effectifs').classes('font-bold text-blue-700 mb-2')
                with ui.row().classes('w-full gap-4'):
                    ui.input(
                        'Date',
                        value=situation_admin.get('effectif_date', '01/01/2025'),
                        on_change=lambda e: situation_admin.update({'effectif_date': e.value})
                    ).classes('w-48')
                    ui.input(
                        'Nombre de salariés',
                        value=situation_admin.get('effectif_nombre', '12'),
                        on_change=lambda e: situation_admin.update({'effectif_nombre': e.value})
                    ).classes('w-32')
            
            # Chiffre d'affaires
            with ui.card().classes('w-full p-4'):
                ui.label('Chiffre d\'affaires').classes('font-bold text-blue-700 mb-2')
                ca_data = situation_admin.get('chiffre_affaires', [])
                
                with ui.row().classes('w-full gap-4 bg-gray-100 p-2 rounded font-bold text-sm'):
                    ui.label('Année').classes('w-24')
                    ui.label('Montant').classes('flex-1')
                
                def update_ca(idx, field, value):
                    if 'chiffre_affaires' not in situation_admin:
                        situation_admin['chiffre_affaires'] = [c.copy() for c in ca_data]
                    if idx < len(situation_admin['chiffre_affaires']):
                        situation_admin['chiffre_affaires'][idx][field] = value
                
                for i, ca in enumerate(ca_data):
                    with ui.row().classes('w-full gap-4 items-center'):
                        ui.input(
                            value=ca.get('annee', ''),
                            on_change=lambda e, idx=i: update_ca(idx, 'annee', e.value)
                        ).classes('w-24').props('dense')
                        ui.input(
                            value=ca.get('montant', ''),
                            on_change=lambda e, idx=i: update_ca(idx, 'montant', e.value)
                        ).classes('flex-1').props('dense')
                
                # Tendance
                ui.input(
                    'Tendance',
                    value=situation_admin.get('tendance_ca', 'Croissance continue'),
                    on_change=lambda e: situation_admin.update({'tendance_ca': e.value})
                ).classes('w-full mt-2')

    def _build_section_content(self, titre: str, rows: pd.DataFrame):
        """Construit le contenu d'une section avec réordonnancement."""
        section_state = self.project_state["sections_data"][titre]
        
        # Sous-sections à exclure de Méthodologie (déplacées vers QSE)
        excluded_in_methodologie = [
            'demarche hqe', 'démarche hqe', 'demarche environnementale', 'démarche environnementale',
            'hygiene qualite', 'hygiène qualité', 'environnementale atelier', 'environnementale chantier'
        ]
        is_methodologie = 'METHODOLOGIE' in titre.upper()
        
        # Initialiser la liste ordonnée si pas encore fait
        order_key = f'_subsection_order_{titre}'
        if order_key not in section_state:
            items = []
            seen_subs = set()
            
            for index, row in rows.iterrows():
                sous_section = nettoyer_str(row.get('sous-section', ''))
                texte_brut = nettoyer_str(row.get('texte', ''))
                image = nettoyer_str(row.get('image', ''))
                couleur = valider_couleur(nettoyer_str(row.get('couleur', 'ecoBleu')))
                
                if not sous_section and not texte_brut and not image:
                    continue
                
                # Filtrer les sous-sections HQE/environnementales dans Méthodologie
                if is_methodologie:
                    ss_lower = sous_section.lower()
                    if any(excl in ss_lower for excl in excluded_in_methodologie):
                        continue
                
                # Eviter doublons
                sub_key = sous_section.lower().strip()
                if sub_key in seen_subs:
                    continue
                seen_subs.add(sub_key)
                
                items.append({
                    'index': index,
                    'sous_section': sous_section,
                    'texte': texte_brut,
                    'image': image,
                    'couleur': couleur,
                    'unique_key': f"{index}_{sub_key}"
                })
            
            section_state[order_key] = items
        
        items = section_state[order_key]
        
        # Ajouter Transport et Levage à Méthodologie si pas présent (même si state existe déjà)
        if is_methodologie:
            has_tl = any('transport' in it.get('sous_section', '').lower() and 'levage' in it.get('sous_section', '').lower() for it in items)
            if not has_tl:
                items.append({
                    'index': -1,
                    'sous_section': 'Transport et levage',
                    'texte': '',
                    'image': '',
                    'couleur': 'ecoBleu',
                    'unique_key': 'transport_levage_special'
                })
        
        # Container principal
        main_container = ui.column().classes('w-full gap-3 p-2')
        
        def rebuild_section():
            """Reconstruit l'affichage de la section."""
            main_container.clear()
            with main_container:
                for i, item in enumerate(items):
                    # Traitement spécial pour Transport et levage dans Méthodologie
                    if is_methodologie and 'transport' in item['sous_section'].lower() and 'levage' in item['sous_section'].lower():
                        self._build_transport_levage_section(titre, section_state)
                        continue
                    
                    self._build_subsection_card_generation(items, i, rebuild_section, titre, section_state)
                
                # Bouton ajouter
                def add_new():
                    new_item = {
                        'index': -1,
                        'sous_section': 'Nouvelle sous-section',
                        'texte': '',
                        'image': '',
                        'couleur': 'ecoBleu',
                        'unique_key': f"new_{len(items)}_{datetime.now().timestamp()}",
                        'is_new': True
                    }
                    items.append(new_item)
                    rebuild_section()
                    ui.notify('Sous-section ajoutée', type='positive')
                
                ui.button('+ Ajouter une sous-section', on_click=add_new, icon='add').props('outline color=blue')
                
                # ===== TABLEAUX SPECIAUX POUR LISTE DES MATERIAUX =====
                # Vérifier si les tableaux Fixation/Traitement ont été créés via le CSV
                # Sinon, les ajouter explicitement
                if 'LISTE DES MATERIAUX' in titre.upper() or 'MATERIAUX' in titre.upper():
                    # Vérifier si les tableaux existent dans les items
                    has_fixation = any('fixation' in it.get('sous_section', '').lower() and 'assemblage' in it.get('sous_section', '').lower() for it in items)
                    has_traitement_prev = any('traitement' in it.get('sous_section', '').lower() and ('préventif' in it.get('sous_section', '').lower() or 'preventif' in it.get('sous_section', '').lower()) for it in items)
                    has_traitement_cur = any('traitement' in it.get('sous_section', '').lower() and 'curatif' in it.get('sous_section', '').lower() for it in items)
                    
                    ui.separator().classes('my-4')
                    ui.label('Tableaux de données').classes('text-lg font-bold text-blue-900 mb-2')
                    
                    # Forcer l'affichage des tableaux s'ils ne sont pas dans les items
                    if not has_fixation:
                        with ui.card().classes('w-full p-4 mb-3'):
                            fixation_key = 'fixation_table_forced'
                            if fixation_key not in section_state:
                                section_state[fixation_key] = {'nom': 'Fixation et assemblage', 'couleur': 'ecoMarron'}
                            self._build_fixation_table_content(section_state[fixation_key], fixation_key)
                    
                    if not has_traitement_prev:
                        with ui.card().classes('w-full p-4 mb-3'):
                            prev_key = 'traitement_preventif_forced'
                            if prev_key not in section_state:
                                section_state[prev_key] = {'nom': 'Traitement préventif', 'couleur': 'ecoVert'}
                            self._build_traitement_table_content(section_state[prev_key], 'preventif')
                    
                    if not has_traitement_cur:
                        with ui.card().classes('w-full p-4 mb-3'):
                            cur_key = 'traitement_curatif_forced'
                            if cur_key not in section_state:
                                section_state[cur_key] = {'nom': 'Traitement curatif', 'couleur': 'ecoVert'}
                            self._build_traitement_table_content(section_state[cur_key], 'curatif')
        
        rebuild_section()
    
    def _build_subsection_card_generation(self, items: list, index: int, rebuild_fn, titre: str, section_state: Dict):
        """Construit une carte de sous-section avec contrôles de réordonnancement pour Nouveau mémoire."""
        item = items[index]
        unique_key = item.get('unique_key', f"{index}")
        
        # Valider et corriger la couleur
        item['couleur'] = valider_couleur(item.get('couleur', 'ecoBleu'))
        
        couleur_css = LATEX_COLORS.get(item['couleur'], LATEX_COLORS['ecoBleu'])['css']
        
        # Initialiser le state pour cette sous-section si nécessaire
        if unique_key not in section_state:
            section_state[unique_key] = {
                "nom": item['sous_section'],
                "texte": item['texte'],
                "image": item['image'],
                "couleur": item['couleur'],
                "selections": {}
            }
        
        state = section_state[unique_key]
        # Synchroniser la couleur
        state['couleur'] = item['couleur']
        
        with ui.card().classes('w-full p-4').style(f'border-left: 4px solid {couleur_css};'):
            # Barre de contrôle en haut
            with ui.row().classes('w-full justify-between items-center mb-3'):
                with ui.row().classes('items-center gap-1'):
                    ui.label(f'#{index + 1}').classes('text-xs text-gray-400 font-mono')
                    
                    # Boutons de déplacement
                    def move_up(idx=index):
                        if idx > 0:
                            items[idx], items[idx-1] = items[idx-1], items[idx]
                            rebuild_fn()
                    
                    def move_down(idx=index):
                        if idx < len(items) - 1:
                            items[idx], items[idx+1] = items[idx+1], items[idx]
                            rebuild_fn()
                    
                    ui.button(icon='arrow_upward', on_click=move_up).props('flat dense size=sm').classes('text-gray-500').tooltip('Monter')
                    ui.button(icon='arrow_downward', on_click=move_down).props('flat dense size=sm').classes('text-gray-500').tooltip('Descendre')
                
                # Bouton supprimer
                def delete_item(idx=index, uk=unique_key):
                    if len(items) > 0:
                        items.pop(idx)
                        # Supprimer aussi du state
                        if uk in section_state:
                            del section_state[uk]
                        rebuild_fn()
                        ui.notify('Sous-section supprimée', type='info')
                
                ui.button(icon='delete', on_click=delete_item).props('flat dense size=sm color=red').tooltip('Supprimer')
                
                # Sélecteur de couleur
                color_options = {k: f"{v['nom']}" for k, v in LATEX_COLORS.items()}
                def update_color(e, it=item, st=state):
                    it['couleur'] = e.value
                    st['couleur'] = e.value
                    rebuild_fn()
                
                with ui.row().classes('items-center gap-1 ml-2'):
                    ui.icon('palette', size='xs').classes('text-gray-400')
                    ui.select(
                        options=color_options,
                        value=item.get('couleur', 'ecoBleu'),
                        on_change=update_color
                    ).props('dense outlined').classes('w-28').style(f'background-color: {couleur_css}20;')
            
            # Contenu de la sous-section (selon le type)
            sous_section = item['sous_section']
            texte = item['texte']
            
            # CAS SPECIAL : Fixation et assemblage - Tableau éditable
            if 'fixation' in sous_section.lower() and 'assemblage' in sous_section.lower():
                self._build_fixation_table_content(state, unique_key)
                return
            
            # CAS SPECIAL : Traitement Préventif (avec ou sans accent)
            if 'traitement' in sous_section.lower() and ('préventif' in sous_section.lower() or 'preventif' in sous_section.lower()):
                self._build_traitement_table_content(state, 'preventif')
                return
            
            # CAS SPECIAL : Traitement Curatif
            if 'traitement' in sous_section.lower() and 'curatif' in sous_section.lower():
                self._build_traitement_table_content(state, 'curatif')
                return
            
            # Cas standard : édition du titre et contenu
            # Contenu selon le type
            if "/// ou ///" in sous_section or "/// ou ///" in texte:
                # Options multiples avec checkboxes
                self._build_options_content(state, sous_section, texte, item)
            else:
                # Titre éditable pour texte simple
                ui.label('Titre:').classes('text-xs text-gray-500')
                # Utiliser la valeur du state si disponible, sinon celle de l'item
                current_nom = state.get('nom', sous_section)
                def update_nom(e, st=state, it=item):
                    st['nom'] = e.value
                    it['sous_section'] = e.value
                ui.input(value=current_nom, on_change=update_nom).classes('w-full mb-2')
                
                # Texte simple - utiliser la valeur du state si disponible
                ui.label('Contenu:').classes('text-xs text-gray-500')
                current_texte = state.get('texte', texte)
                rows_count = max(3, min(10, len(current_texte) // 50 + 1)) if current_texte else 3
                def update_texte(e, st=state, it=item):
                    st['texte'] = e.value
                    it['texte'] = e.value
                ui.textarea(value=current_texte, on_change=update_texte).classes('w-full').props(f'rows={rows_count} outlined')
            
            # Image
            if item.get('image'):
                with ui.row().classes('items-center gap-2 mt-2'):
                    ui.label('Image:').classes('text-xs text-gray-500')
                    def update_img(e, st=state, it=item):
                        st['image'] = e.value
                        it['image'] = e.value
                    ui.input(value=item.get('image', ''), on_change=update_img).classes('flex-grow')
    
    def _build_options_content(self, state: Dict, sous_section: str, texte: str, item: dict):
        """Construit le contenu avec options multiples (checkboxes)."""
        # Déterminer si les options sont dans le titre ou le texte
        if "/// ou ///" in sous_section:
            parts = sous_section.split(":")
            prefix = parts[0].strip()
            options_str = parts[1] if len(parts) > 1 else sous_section
            options = [o.strip() for o in options_str.split("/// ou ///") if o.strip()]
            
            ui.label(prefix).classes('font-bold text-blue-700 mb-2')
            
            # Initialiser les sélections
            if 'selections' not in state:
                state['selections'] = {'noms': {}}
            if 'noms' not in state['selections']:
                state['selections']['noms'] = {}
            
            for i, opt in enumerate(options):
                if opt not in state['selections']['noms']:
                    state['selections']['noms'][opt] = (i == 0)  # Premier coché par défaut
            
            # Container et widgets pour les checkboxes
            checkbox_container = ui.row().classes('gap-3 flex-wrap')
            checkbox_widgets = []
            
            with checkbox_container:
                for opt in options:
                    is_checked = state['selections']['noms'].get(opt, False)
                    def update_sel(e, o=opt, st=state):
                        st['selections']['noms'][o] = e.value
                    cb = ui.checkbox(opt, value=is_checked, on_change=update_sel)
                    checkbox_widgets.append((opt, cb))
            
            # Boutons Tout cocher / Tout décocher
            with ui.row().classes('gap-2 mt-2'):
                def check_all_noms(widgets=checkbox_widgets, st=state):
                    for opt_name, cb_widget in widgets:
                        cb_widget.set_value(True)
                        st['selections']['noms'][opt_name] = True
                
                def uncheck_all_noms(widgets=checkbox_widgets, st=state):
                    for opt_name, cb_widget in widgets:
                        cb_widget.set_value(False)
                        st['selections']['noms'][opt_name] = False
                
                ui.button('✓ Tout cocher', on_click=check_all_noms).props('flat color=green size=sm')
                ui.button('✗ Tout décocher', on_click=uncheck_all_noms).props('flat color=red size=sm')
            
            # Texte de description si présent
            if texte:
                ui.label('Description:').classes('text-xs text-gray-500 mt-2')
                def update_texte(e, st=state, it=item):
                    st['texte'] = e.value
                    it['texte'] = e.value
                ui.textarea(value=texte, on_change=update_texte).classes('w-full').props('rows=3 outlined')
        
        elif "/// ou ///" in texte:
            # Options dans le texte
            ui.label(sous_section).classes('font-bold text-blue-700 mb-2')
            options = [o.strip() for o in texte.split("/// ou ///") if o.strip()]
            
            if 'selections' not in state:
                state['selections'] = {'options': {}}
            if 'options' not in state['selections']:
                state['selections']['options'] = {}
            
            for i, opt in enumerate(options):
                if opt not in state['selections']['options']:
                    state['selections']['options'][opt] = (i == 0)
            
            # Container et widgets pour les checkboxes
            checkbox_container = ui.column().classes('gap-2')
            checkbox_widgets = []
            
            with checkbox_container:
                for opt in options:
                    is_checked = state['selections']['options'].get(opt, False)
                    def update_opt(e, o=opt, st=state):
                        st['selections']['options'][o] = e.value
                    cb = ui.checkbox(opt, value=is_checked, on_change=update_opt)
                    checkbox_widgets.append((opt, cb))
            
            # Boutons Tout cocher / Tout décocher
            with ui.row().classes('gap-2 mt-2'):
                def check_all_opts(widgets=checkbox_widgets, st=state):
                    for opt_name, cb_widget in widgets:
                        cb_widget.set_value(True)
                        st['selections']['options'][opt_name] = True
                
                def uncheck_all_opts(widgets=checkbox_widgets, st=state):
                    for opt_name, cb_widget in widgets:
                        cb_widget.set_value(False)
                        st['selections']['options'][opt_name] = False
                
                ui.button('✓ Tout cocher', on_click=check_all_opts).props('flat color=green size=sm')
                ui.button('✗ Tout décocher', on_click=uncheck_all_opts).props('flat color=red size=sm')
    
    def _build_fixation_table_content(self, state: Dict, unique_key: str):
        """Construit le contenu tableau pour Fixation et Assemblage."""
        ui.label('Fixation et Assemblage').classes('font-bold text-blue-700 mb-2')
        
        # Données depuis template_data
        template_data = self.project_state.get("template_data", {})
        default_data = template_data.get('table_fixation_assemblage', [])
        
        import copy
        if 'table_data' not in state:
            state['table_data'] = copy.deepcopy(default_data) if default_data else []
        
        table_data = state['table_data']
        state['type'] = 'table_fixation'
        
        # Container pour rebuild
        table_container = ui.column().classes('w-full gap-1')
        
        def rebuild_table():
            table_container.clear()
            with table_container:
                # Headers
                with ui.row().classes('w-full gap-2 bg-gray-100 p-2 rounded font-bold text-xs'):
                    ui.label('Nature').classes('flex-1')
                    ui.label('Marque').classes('flex-1')
                    ui.label('Provenance').classes('w-28')
                    ui.label('Doc').classes('w-14')
                    ui.label('').classes('w-8')  # Pour le bouton supprimer
                
                # Lignes
                for idx, row in enumerate(table_data):
                    with ui.row().classes('w-full gap-2 items-center'):
                        ui.input(value=row.get('nature', ''), on_change=lambda e, i=idx: self._update_table_cell(state, i, 'nature', e.value)).classes('flex-1').props('dense')
                        ui.input(value=row.get('marque', ''), on_change=lambda e, i=idx: self._update_table_cell(state, i, 'marque', e.value)).classes('flex-1').props('dense')
                        ui.input(value=row.get('provenance', ''), on_change=lambda e, i=idx: self._update_table_cell(state, i, 'provenance', e.value)).classes('w-28').props('dense')
                        ui.select(['OUI', 'NON'], value=row.get('doc', 'OUI'), on_change=lambda e, i=idx: self._update_table_cell(state, i, 'doc', e.value)).classes('w-14').props('dense')
                        
                        def delete_row(i=idx):
                            if len(table_data) > 1:
                                table_data.pop(i)
                                rebuild_table()
                                ui.notify('Ligne supprimée', type='info')
                            else:
                                ui.notify('Impossible de supprimer la dernière ligne', type='warning')
                        ui.button(icon='delete', on_click=delete_row).props('flat dense size=sm color=red').classes('w-8')
                
                # Bouton ajouter ligne
                def add_row():
                    table_data.append({'nature': '', 'marque': '', 'provenance': '', 'doc': 'OUI'})
                    rebuild_table()
                ui.button('+ Ajouter ligne', on_click=add_row, icon='add').props('flat size=sm color=blue').classes('mt-2')
        
        rebuild_table()
    
    def _build_traitement_table_content(self, state: Dict, traitement_type: str):
        """Construit le contenu tableau pour Traitement Préventif/Curatif."""
        label = 'Traitement Préventif' if traitement_type == 'preventif' else 'Traitement Curatif'
        ui.label(label).classes('font-bold text-blue-700 mb-2')
        
        template_data = self.project_state.get("template_data", {})
        key = f'table_traitement_{traitement_type}'
        default_data = template_data.get(key, [])
        
        import copy
        if 'table_data' not in state:
            state['table_data'] = copy.deepcopy(default_data) if default_data else []
        
        table_data = state['table_data']
        state['type'] = 'table_fixation'
        
        # Container pour rebuild
        table_container = ui.column().classes('w-full gap-1')
        
        def rebuild_table():
            table_container.clear()
            with table_container:
                # Headers
                with ui.row().classes('w-full gap-2 bg-gray-100 p-2 rounded font-bold text-xs'):
                    ui.label('Nature').classes('flex-1')
                    ui.label('Marque').classes('flex-1')
                    ui.label('Provenance').classes('w-28')
                    ui.label('Doc').classes('w-14')
                    ui.label('').classes('w-8')
                
                # Lignes
                for idx, row in enumerate(table_data):
                    with ui.row().classes('w-full gap-2 items-center'):
                        ui.input(value=row.get('nature', ''), on_change=lambda e, i=idx: self._update_table_cell(state, i, 'nature', e.value)).classes('flex-1').props('dense')
                        ui.input(value=row.get('marque', ''), on_change=lambda e, i=idx: self._update_table_cell(state, i, 'marque', e.value)).classes('flex-1').props('dense')
                        ui.input(value=row.get('provenance', ''), on_change=lambda e, i=idx: self._update_table_cell(state, i, 'provenance', e.value)).classes('w-28').props('dense')
                        ui.select(['OUI', 'NON'], value=row.get('doc', 'OUI'), on_change=lambda e, i=idx: self._update_table_cell(state, i, 'doc', e.value)).classes('w-14').props('dense')
                        
                        def delete_row(i=idx):
                            if len(table_data) > 1:
                                table_data.pop(i)
                                rebuild_table()
                                ui.notify('Ligne supprimée', type='info')
                            else:
                                ui.notify('Impossible de supprimer la dernière ligne', type='warning')
                        ui.button(icon='delete', on_click=delete_row).props('flat dense size=sm color=red').classes('w-8')
                
                # Bouton ajouter ligne
                def add_row():
                    table_data.append({'nature': '', 'marque': '', 'provenance': '', 'doc': 'OUI'})
                    rebuild_table()
                ui.button('+ Ajouter ligne', on_click=add_row, icon='add').props('flat size=sm color=blue').classes('mt-2')
        
        rebuild_table()
    
    def _update_table_cell(self, state: Dict, row_idx: int, col: str, value: str):
        """Met à jour une cellule du tableau dans le state."""
        if 'table_data' in state and row_idx < len(state['table_data']):
            state['table_data'][row_idx][col] = value
    
    def _create_subsection_widget(self, section: str, key: str, sous_section: str, texte: str, image: str, section_state: Dict):
        """Cree un widget de sous-section avec binding au state."""
        
        # Initialiser le state pour cette sous-section
        if key not in section_state:
            section_state[key] = {
                "nom": sous_section,
                "texte": texte,
                "image": image,
                "selections": {}
            }
        
        state = section_state[key]
        
        with ui.card().classes('w-full p-4'):
            # CAS SPECIAL : Fixation et assemblage - Tableau éditable
            if 'fixation' in sous_section.lower() and 'assemblage' in sous_section.lower():
                ui.label('Fixation et Assemblage').classes('font-bold text-blue-700 mb-2')
                ui.label('Tableau des éléments de fixation').classes('text-sm text-gray-600 mb-2')
                
                # Données depuis template_data.json (modifiable dans Base de données)
                template_data = self.project_state.get("template_data", {})
                default_data = template_data.get('table_fixation_assemblage', [
                    {"nature": "Boulons galvanisés à chaud Ø16 et Ø20", "marque": "Classe 6.8. Filetage partiel", "provenance": "France", "doc": "OUI"},
                    {"nature": "Visserie électrozinguée", "marque": "BERNER", "provenance": "France", "doc": "OUI"},
                    {"nature": "Vis Ø8", "marque": "EUROTEC", "provenance": "Allemagne", "doc": "OUI"},
                    {"nature": "Équerres de fixation et sabots galvanisés BEA", "marque": "BEA", "provenance": "France", "doc": "OUI"},
                    {"nature": "Pointes d'ancrage crantées", "marque": "BEA 4/50", "provenance": "France", "doc": "OUI"},
                    {"nature": "Ferrures mécano-soudées", "marque": "MTR", "provenance": "France - Alsace", "doc": "OUI"},
                    {"nature": "Vis anti-fendage", "marque": "SFS - EUROTEC", "provenance": "France - Allemagne", "doc": "OUI"},
                    {"nature": "Pointes brutes", "marque": "GUNEBO", "provenance": "Suède", "doc": "OUI"},
                    {"nature": "Pointes galvanisées à chaud", "marque": "GUNEBO", "provenance": "France", "doc": "OUI"},
                    {"nature": "Chevilles maçonnerie", "marque": "HILTI HRD UGT Ø 10 Ø 14", "provenance": "France", "doc": "OUI"},
                    {"nature": "Goujons d'ancrage", "marque": "HILTI HSAK Ø 12 Ø 16", "provenance": "France", "doc": "OUI"},
                    {"nature": "Vis inox", "marque": "BERNER A2 torx", "provenance": "Allemagne", "doc": "OUI"},
                    {"nature": "Vis inox", "marque": "EUROTEC A4 torx", "provenance": "France", "doc": "OUI"},
                    {"nature": "Boulons TRCC 8 - Ø 10 - Ø 12", "marque": "SCHMERBER", "provenance": "", "doc": "OUI"},
                ])
                
                # Copier pour ne pas modifier l'original
                import copy
                default_data = copy.deepcopy(default_data)
                
                # Initialiser les données dans le state si pas encore fait
                if 'table_data' not in state:
                    state['table_data'] = default_data
                
                # Créer le tableau
                table_data = state['table_data']
                
                # Headers
                with ui.row().classes('w-full gap-2 bg-gray-100 p-2 rounded font-bold text-sm'):
                    ui.label('Nature des éléments').classes('flex-1')
                    ui.label('Marque, type, performance').classes('flex-1')
                    ui.label('Provenance').classes('w-32')
                    ui.label('Doc').classes('w-16')
                    ui.label('').classes('w-8')  # Pour bouton suppr
                
                # Container pour les lignes
                rows_container = ui.column().classes('w-full gap-1')
                
                def rebuild_table(container, st=state):
                    """Reconstruit le tableau après suppression."""
                    container.clear()
                    with container:
                        for idx, row in enumerate(st['table_data']):
                            create_row_with_delete(idx, row, container, st)
                
                def create_row_with_delete(row_idx, row_data, container, st=state):
                    row_element = ui.row().classes('w-full gap-2 items-center')
                    with row_element:
                        ui.input(value=row_data.get('nature', ''),
                            on_change=lambda e, i=row_idx: self._update_table_cell(st, i, 'nature', e.value)
                        ).classes('flex-1').props('dense')
                        ui.input(value=row_data.get('marque', ''),
                            on_change=lambda e, i=row_idx: self._update_table_cell(st, i, 'marque', e.value)
                        ).classes('flex-1').props('dense')
                        ui.input(value=row_data.get('provenance', ''),
                            on_change=lambda e, i=row_idx: self._update_table_cell(st, i, 'provenance', e.value)
                        ).classes('w-32').props('dense')
                        ui.select(['OUI', 'NON'], value=row_data.get('doc', 'OUI'),
                            on_change=lambda e, i=row_idx: self._update_table_cell(st, i, 'doc', e.value)
                        ).classes('w-16').props('dense')
                        
                        def delete_row(idx=row_idx, cont=container, s=st):
                            if len(s['table_data']) > 1:
                                s['table_data'].pop(idx)
                                rebuild_table(cont, s)
                                ui.notify('Ligne supprimée', type='info')
                            else:
                                ui.notify('Impossible de supprimer la dernière ligne', type='warning')
                        
                        ui.button(icon='delete', on_click=delete_row).props('flat dense color=red size=sm').classes('w-8')
                
                with rows_container:
                    for idx, row in enumerate(table_data):
                        create_row_with_delete(idx, row, rows_container, state)
                
                # Bouton ajouter ligne
                def add_row(cont=rows_container, st=state):
                    new_row = {"nature": "", "marque": "", "provenance": "", "doc": "OUI"}
                    st['table_data'].append(new_row)
                    rebuild_table(cont, st)
                    ui.notify('Ligne ajoutée', type='positive')
                
                ui.button('+ Ajouter une ligne', on_click=add_row).props('flat color=blue size=sm').classes('mt-2')
                
                state['type'] = 'table_fixation'
                return
            
            # CAS SPECIAL : Traitement préventif ou curatif des bois - Tableau éditable
            if 'traitement' in sous_section.lower() and ('préventif' in sous_section.lower() or 'preventif' in sous_section.lower() or 'curatif' in sous_section.lower()):
                is_preventif = 'préventif' in sous_section.lower() or 'preventif' in sous_section.lower()
                titre_type = "préventif" if is_preventif else "curatif"
                
                ui.label(f'Traitement {titre_type} des bois').classes('font-bold text-blue-700 mb-2')
                ui.label('Tableau des produits de traitement').classes('text-sm text-gray-600 mb-2')
                
                # Données depuis template_data.json (modifiable dans Base de données)
                template_data = self.project_state.get("template_data", {})
                table_key = 'table_traitement_preventif' if is_preventif else 'table_traitement_curatif'
                
                fallback_preventif = [
                    {"nature": "Traitement SARPECO 850", "marque": "SARPECO", "provenance": "France", "doc": "OUI"},
                    {"nature": "Traitement classe 2 (label vert)", "marque": "SARPECO 850", "provenance": "France", "doc": "OUI"},
                ]
                fallback_curatif = [
                    {"nature": "Traitement XILIX 3000P", "marque": "XILIX", "provenance": "France", "doc": "OUI"},
                    {"nature": "Traitement curatif par injection", "marque": "XILIX", "provenance": "France", "doc": "OUI"},
                ]
                
                default_data = template_data.get(table_key, fallback_preventif if is_preventif else fallback_curatif)
                
                # Copier pour ne pas modifier l'original
                import copy
                default_data = copy.deepcopy(default_data)
                
                # Initialiser les données dans le state si pas encore fait
                if 'table_data' not in state:
                    state['table_data'] = default_data
                
                # Créer le tableau
                table_data = state['table_data']
                
                # Headers
                with ui.row().classes('w-full gap-2 bg-gray-100 p-2 rounded font-bold text-sm'):
                    ui.label('Nature des éléments').classes('flex-1')
                    ui.label('Marque, type, performance').classes('flex-1')
                    ui.label('Provenance').classes('w-32')
                    ui.label('Doc').classes('w-16')
                
                # Container pour les lignes
                rows_container = ui.column().classes('w-full gap-1')
                
                def create_row_traitement(row_idx, row_data, container=rows_container):
                    with ui.row().classes('w-full gap-2 items-center'):
                        ui.input(value=row_data.get('nature', ''),
                            on_change=lambda e, i=row_idx: self._update_table_cell(state, i, 'nature', e.value)
                        ).classes('flex-1').props('dense')
                        ui.input(value=row_data.get('marque', ''),
                            on_change=lambda e, i=row_idx: self._update_table_cell(state, i, 'marque', e.value)
                        ).classes('flex-1').props('dense')
                        ui.input(value=row_data.get('provenance', ''),
                            on_change=lambda e, i=row_idx: self._update_table_cell(state, i, 'provenance', e.value)
                        ).classes('w-32').props('dense')
                        ui.select(['OUI', 'NON'], value=row_data.get('doc', 'OUI'),
                            on_change=lambda e, i=row_idx: self._update_table_cell(state, i, 'doc', e.value)
                        ).classes('w-16').props('dense')
                
                with rows_container:
                    for idx, row in enumerate(table_data):
                        create_row_traitement(idx, row)
                
                # Bouton ajouter ligne
                def add_row_traitement():
                    new_row = {"nature": "", "marque": "", "provenance": "", "doc": "OUI"}
                    state['table_data'].append(new_row)
                    with rows_container:
                        create_row_traitement(len(state['table_data']) - 1, new_row)
                    ui.notify('Ligne ajoutée', type='positive')
                
                ui.button('+ Ajouter une ligne', on_click=add_row_traitement).props('flat color=blue size=sm').classes('mt-2')
                
                state['type'] = 'table_fixation'  # Réutilise le même type de génération LaTeX
                return
            
            # CAS 1 : Contexte visite (date + adresse)
            if 'contexte visite' in sous_section.lower() or ('"date?"' in texte.lower() and '"adresse?"' in texte.lower()):
                ui.label('Visite de site').classes('font-bold text-blue-700 mb-2')
                
                with ui.row().classes('w-full gap-4'):
                    with ui.column().classes('flex-grow'):
                        ui.label('Date de la visite').classes('text-sm text-gray-600')
                        date_input = ui.input(
                            placeholder='Ex: 12/09/2024',
                            on_change=lambda e: self._update_subsection_state(state, 'date', e.value)
                        ).classes('w-full')
                    
                    with ui.column().classes('flex-grow'):
                        ui.label('Adresse (si differente)').classes('text-sm text-gray-600')
                        adr_input = ui.input(
                            placeholder='Laisser vide si identique',
                            on_change=lambda e: self._update_subsection_state(state, 'adresse_visite', e.value)
                        ).classes('w-full')
                
                state['type'] = 'contexte_visite'
                return
            
            # CAS 2 : Options multiples avec "/// ou ///"
            if "/// ou ///" in sous_section:
                parts = sous_section.split(":")
                prefix = parts[0].strip()
                options_str = parts[1] if len(parts) > 1 else sous_section
                options = [o.strip() for o in options_str.split("/// ou ///") if o.strip()]
                
                # Titre editable
                ui.label(prefix).classes('font-bold text-blue-700 mb-2')
                
                # Container pour les checkboxes (pour mise à jour dynamique)
                checkbox_container = ui.row().classes('gap-3 flex-wrap')
                checkbox_widgets = []  # Pour stocker les widgets
                
                # Checkboxes pour les noms - UN SEUL COCHÉ PAR DÉFAUT
                with checkbox_container:
                    for idx, opt in enumerate(options):
                        # Seul le premier est coché par défaut
                        is_checked = (idx == 0)
                        cb = ui.checkbox(
                            opt,
                            value=is_checked,
                            on_change=lambda e, o=opt: self._toggle_selection(state, 'noms', o, e.value)
                        )
                        checkbox_widgets.append((opt, cb))
                        state['selections'].setdefault('noms', {})[opt] = is_checked
                
                # Boutons d'action
                with ui.row().classes('gap-2 mt-1'):
                    # Bouton Tout cocher
                    def check_all(widgets=checkbox_widgets, st=state, cat='noms'):
                        for opt_name, cb_widget in widgets:
                            cb_widget.set_value(True)
                            st['selections'].setdefault(cat, {})[opt_name] = True
                    
                    ui.button('✓ Tout cocher', on_click=check_all).props('flat color=green size=sm')
                    
                    # Bouton Tout décocher
                    def uncheck_all(widgets=checkbox_widgets, st=state, cat='noms'):
                        for opt_name, cb_widget in widgets:
                            cb_widget.set_value(False)
                            st['selections'].setdefault(cat, {})[opt_name] = False
                    
                    ui.button('✗ Tout décocher', on_click=uncheck_all).props('flat color=red size=sm')
                    
                    # Bouton pour ajouter une option
                    def add_option_dialog(container=checkbox_container, st=state, cat='noms', widgets=checkbox_widgets):
                        with ui.dialog() as dialog, ui.card().classes('w-80'):
                            ui.label('Ajouter une option').classes('text-lg font-bold mb-4')
                            new_opt_input = ui.input(label='Nouvelle option', placeholder='Ex: Nouveau nom').classes('w-full')
                            with ui.row().classes('justify-end gap-2 mt-4'):
                                ui.button('Annuler', on_click=dialog.close).props('flat')
                                def do_add():
                                    new_val = new_opt_input.value.strip()
                                    if new_val:
                                        with container:
                                            new_cb = ui.checkbox(new_val, value=True, 
                                                on_change=lambda e, o=new_val: self._toggle_selection(st, cat, o, e.value))
                                            widgets.append((new_val, new_cb))
                                        st['selections'].setdefault(cat, {})[new_val] = True
                                        ui.notify(f'Option "{new_val}" ajoutée', type='positive')
                                    dialog.close()
                                ui.button('Ajouter', on_click=do_add).props('color=blue')
                        dialog.open()
                    
                    ui.button('+ Ajouter', on_click=add_option_dialog).props('flat color=blue size=sm')
                
                # Texte si present
                if texte and "/// ou ///" not in texte:
                    ui.label('Description:').classes('text-sm text-gray-600 mt-2')
                    ui.textarea(
                        value=texte,
                        on_change=lambda e: self._update_subsection_state(state, 'texte', e.value)
                    ).classes('w-full').props('rows=2')
                
                state['type'] = 'title_options'
                return
            
            # CAS 3 : Choix multiples dans le texte
            if "/// ou ///" in texte:
                ui.label(sous_section).classes('font-bold text-blue-700 mb-2')
                
                # Parser les options
                options = [o.strip() for o in texte.split("/// ou ///") if o.strip()]
                
                # Vérifier si le premier élément est un texte d'intro (long texte sans être une option courte)
                # Un texte d'intro contient généralement plus de 100 caractères et des phrases complètes
                intro_text = ""
                if options and len(options[0]) > 80 and '.' in options[0]:
                    # Le premier élément est probablement un texte d'intro
                    intro_text = options[0]
                    options = options[1:]  # Retirer l'intro des options
                    
                    # Afficher le texte d'intro comme textarea modifiable
                    ui.label('Introduction:').classes('text-sm text-gray-600 mt-1')
                    ui.textarea(
                        value=intro_text,
                        on_change=lambda e: self._update_subsection_state(state, 'intro_text', e.value)
                    ).classes('w-full').props('rows=3')
                    state['intro_text'] = intro_text
                    
                    ui.label('Options:').classes('text-sm text-gray-600 mt-2')
                
                # Container pour les checkboxes (pour mise à jour dynamique)
                checkbox_container = ui.column().classes('gap-1')
                checkbox_widgets_multi = []  # Pour stocker les widgets
                
                with checkbox_container:
                    for idx, opt in enumerate(options):
                        # Seul le premier est coché par défaut
                        is_checked = (idx == 0)
                        # Afficher le texte COMPLET, pas tronqué
                        cb = ui.checkbox(
                            opt,
                            value=is_checked,
                            on_change=lambda e, o=opt: self._toggle_selection(state, 'options', o, e.value)
                        ).classes('text-sm')
                        checkbox_widgets_multi.append((opt, cb))
                        state['selections'].setdefault('options', {})[opt] = is_checked
                
                # Boutons d'action
                with ui.row().classes('gap-2 mt-1'):
                    # Bouton Tout cocher
                    def check_all_multi(widgets=checkbox_widgets_multi, st=state, cat='options'):
                        for opt_name, cb_widget in widgets:
                            cb_widget.set_value(True)
                            st['selections'].setdefault(cat, {})[opt_name] = True
                    
                    ui.button('✓ Tout cocher', on_click=check_all_multi).props('flat color=green size=sm')
                    
                    # Bouton Tout décocher
                    def uncheck_all_multi(widgets=checkbox_widgets_multi, st=state, cat='options'):
                        for opt_name, cb_widget in widgets:
                            cb_widget.set_value(False)
                            st['selections'].setdefault(cat, {})[opt_name] = False
                    
                    ui.button('✗ Tout décocher', on_click=uncheck_all_multi).props('flat color=red size=sm')
                    
                    # Bouton pour ajouter une option
                    def add_option_dialog_multi(container=checkbox_container, st=state, cat='options', widgets=checkbox_widgets_multi):
                        with ui.dialog() as dialog, ui.card().classes('w-80'):
                            ui.label('Ajouter une option').classes('text-lg font-bold mb-4')
                            new_opt_input = ui.input(label='Nouvelle option', placeholder='Ex: Nouvelle option').classes('w-full')
                            with ui.row().classes('justify-end gap-2 mt-4'):
                                ui.button('Annuler', on_click=dialog.close).props('flat')
                                def do_add():
                                    new_val = new_opt_input.value.strip()
                                    if new_val:
                                        with container:
                                            new_cb = ui.checkbox(new_val, value=True, 
                                                on_change=lambda e, o=new_val: self._toggle_selection(st, cat, o, e.value)).classes('text-sm')
                                            widgets.append((new_val, new_cb))
                                        st['selections'].setdefault(cat, {})[new_val] = True
                                        ui.notify(f'Option "{new_val}" ajoutée', type='positive')
                                    dialog.close()
                                ui.button('Ajouter', on_click=do_add).props('color=blue')
                        dialog.open()
                    
                    ui.button('+ Ajouter', on_click=add_option_dialog_multi).props('flat color=blue size=sm')
                
                state['type'] = 'multi_check'
                return
            
            # CAS 4 : Texte libre
            # Titre de sous-section editable
            title_input = ui.input(
                value=sous_section,
                on_change=lambda e: self._update_subsection_state(state, 'nom', e.value)
            ).classes('w-full font-bold text-blue-700 mb-2').props('borderless dense')
            
            # Nettoyer le texte
            texte_clean = texte.replace('"date?"', "").replace('"adresse?"', "").strip()
            
            if texte_clean:
                rows_count = max(2, min(8, len(texte_clean) // 80 + 1))
                ui.textarea(
                    value=texte_clean,
                    on_change=lambda e: self._update_subsection_state(state, 'texte', e.value)
                ).classes('w-full').props(f'rows={rows_count}')
            
            # Image si presente
            if image:
                with ui.row().classes('items-center gap-2 mt-2 text-sm text-gray-500'):
                    ui.icon('image', size='xs')
                    ui.label(f'Image: {image}')
            
            state['type'] = 'text'
    
    def _update_subsection_state(self, state: Dict, key: str, value: str):
        """Met a jour une valeur dans le state d'une sous-section."""
        state[key] = value
    
    def _toggle_selection(self, state: Dict, category: str, option: str, enabled: bool):
        """Toggle une selection dans le state."""
        if category not in state['selections']:
            state['selections'][category] = {}
        state['selections'][category][option] = enabled
    
    def _process_item_for_pdf(self, item: Dict, section_state: Dict) -> Dict:
        """Traite un item de sous-section pour le PDF (générique comme L'équipe)."""
        nom = item.get('sous_section', item.get('nom', ''))
        texte = item.get('texte', item.get('contenu', ''))
        image = item.get('image', '')
        couleur = item.get('couleur', 'ecoBleu')
        unique_key = item.get('unique_key', '')
        item_type = item.get('type', 'text')
        
        # Récupérer le state associé pour les valeurs modifiées
        ss_state = section_state.get(unique_key, {})
        if isinstance(ss_state, dict):
            nom = ss_state.get('nom', nom)
            texte = ss_state.get('texte', texte)
            image = ss_state.get('image', image)
            couleur = ss_state.get('couleur', couleur)
        
        # Gérer les options "/// ou ///" dans le nom
        if "/// ou ///" in nom:
            noms_sel = {}
            if isinstance(ss_state, dict):
                noms_sel = ss_state.get('selections', {}).get('noms', {})
            elif 'selections' in item:
                noms_sel = item.get('selections', {}).get('noms', {})
            
            selected_noms = [n for n, v in noms_sel.items() if v]
            
            if selected_noms:
                base_nom = nom.split(':')[0].strip() if ':' in nom else nom.split('/// ou ///')[0].strip()
                nom = f"{base_nom} : {', '.join(selected_noms)}"
            else:
                if ':' in nom:
                    options_str = nom.split(':', 1)[1]
                    options = [o.strip() for o in options_str.split("/// ou ///") if o.strip()]
                    if options:
                        base_nom = nom.split(':')[0].strip()
                        nom = f"{base_nom} : {options[0]}"
                else:
                    options = [o.strip() for o in nom.split("/// ou ///") if o.strip()]
                    if options:
                        nom = options[0]
        
        # Gérer les options "/// ou ///" dans le texte
        if texte and "/// ou ///" in texte:
            options_sel = {}
            if isinstance(ss_state, dict):
                options_sel = ss_state.get('selections', {}).get('options', {})
            elif 'selections' in item:
                options_sel = item.get('selections', {}).get('options', {})
            
            selected = [o for o, v in options_sel.items() if v]
            if selected:
                texte = "\n".join(f"- {s}" for s in selected)
            else:
                options = [o.strip() for o in texte.split("/// ou ///") if o.strip()]
                texte = "\n".join(f"- {o}" for o in options)
        
        # Traiter le type tableau
        if item_type == 'table_fixation' or (isinstance(ss_state, dict) and ss_state.get('type') == 'table_fixation'):
            table_data = []
            if isinstance(ss_state, dict):
                table_data = ss_state.get('table_data', [])
            if not table_data:
                table_data = item.get('table_data', [])
            
            if table_data:
                lines = []
                lines.append("\\begin{tabular}{|p{5cm}|p{4.5cm}|p{3cm}|p{1.5cm}|}")
                lines.append("\\hline")
                lines.append("\\textbf{Nature} & \\textbf{Marque/Type} & \\textbf{Provenance} & \\textbf{Doc} \\\\")
                lines.append("\\hline")
                for row in table_data:
                    nature = self.latex_service.echapper_latex(row.get('nature', ''))
                    marque = self.latex_service.echapper_latex(row.get('marque', ''))
                    provenance = self.latex_service.echapper_latex(row.get('provenance', ''))
                    doc = row.get('doc', 'OUI')
                    lines.append(f"{nature} & {marque} & {provenance} & {doc} \\\\")
                    lines.append("\\hline")
                lines.append("\\end{tabular}")
                texte = "\n".join(lines)
        
        # Sanitizer le nom pour LaTeX
        nom_sanitized = nom.replace(',', '{,}')
        for char, escaped in [('&', r'\&'), ('%', r'\%'), ('_', r'\_'), ('#', r'\#')]:
            nom_sanitized = nom_sanitized.replace(char, escaped)
        
        # Échapper le contenu si nécessaire
        content_escaped = texte
        if texte and not any(cmd in texte for cmd in ['\\begin{', '\\end{', '\\item', '\\textbf', '\\hline']):
            # Vérifier si le texte contient des tirets de liste
            lines_with_dash = [l.strip() for l in texte.split("\n") if l.strip().startswith("-")]
            lines_without_dash = [l.strip() for l in texte.split("\n") if l.strip() and not l.strip().startswith("-")]
            
            if lines_with_dash and not lines_without_dash:
                # Uniquement des tirets -> convertir en itemize
                items_tex = [f"    \\item {self.latex_service.echapper_latex(l[1:].strip())}" for l in lines_with_dash]
                content_escaped = "\\begin{itemize}\n" + "\n".join(items_tex) + "\n\\end{itemize}"
            elif lines_with_dash and lines_without_dash:
                # Mixte: tirets ET texte sans tiret -> garder le texte brut échappé
                content_escaped = self.latex_service.echapper_latex(texte)
            else:
                # Pas de tirets du tout -> échapper le texte normalement
                content_escaped = self.latex_service.echapper_latex(texte)
        
        couleur_latex = LATEX_COLORS.get(couleur, LATEX_COLORS['ecoBleu'])['latex']
        
        return {
            'nom': nom_sanitized,
            'contenu': content_escaped,
            'image': image,
            'couleur': couleur_latex
        }
    
    def _collect_data_from_state(self) -> List[Dict[str, Any]]:
        """Collecte les donnees depuis le state central pour la generation - VERSION GÉNÉRIQUE."""
        data_finale = []
        
        for titre in self.sections_autorisees:
            # Verifier si section active
            if not self.project_state["sections_enabled"].get(titre, True):
                continue
            
            titre_upper = titre.upper()
            section_data = self.project_state["sections_data"].get(titre, {})
            
            # ===== SECTIONS SPÉCIALES AVEC TEMPLATES INCLUS =====
            is_template_section = (
                'SITUATION ADMINISTRATIVE' in titre_upper or
                'QSE' in titre_upper or
                'HYGIENE' in titre_upper or
                'HQE' in titre_upper
            )
            
            if is_template_section:
                data_finale.append({
                    'titre': titre,
                    'sous_sections': [{'nom': '', 'contenu': '', 'image': ''}]
                })
                continue
            
            # ===== CHANTIERS RÉFÉRENCES =====
            if 'CHANTIER' in titre_upper and 'REFERENCE' in titre_upper:
                sous_sections = []
                order_key = f'_subsection_order_{titre}'
                
                if order_key in section_data and isinstance(section_data[order_key], list):
                    for item in section_data[order_key]:
                        unique_key = item.get('unique_key', '')
                        nom = item.get('sous_section', '')
                        couleur = item.get('couleur', 'ecoBleu')
                        
                        # Récupérer le state de cet item
                        item_state = section_data.get(unique_key, {})
                        
                        # Le nom peut avoir été édité
                        nom = item_state.get('nom', nom)
                        couleur = item_state.get('couleur', couleur)
                        
                        # Sanitizer le nom
                        nom_sanitized = nom.replace(',', '{,}')
                        for char, escaped in [('&', r'\&'), ('%', r'\%'), ('_', r'\_'), ('#', r'\#')]:
                            nom_sanitized = nom_sanitized.replace(char, escaped)
                        
                        couleur_latex = LATEX_COLORS.get(couleur, LATEX_COLORS['ecoBleu'])['latex']
                        
                        # Vérifier le type de contenu (checkboxes ou texte)
                        selections = item_state.get('selections', {})
                        options_sel = selections.get('options', {})
                        
                        content_final = ''
                        if options_sel:
                            # C'est une liste de checkboxes
                            checked_opts = [opt for opt, is_checked in options_sel.items() if is_checked]
                            if checked_opts:
                                items_tex = [f"    \\item {self.latex_service.echapper_latex(opt)}" for opt in checked_opts]
                                content_final = "\\begin{itemize}\n" + "\n".join(items_tex) + "\n\\end{itemize}"
                        else:
                            # C'est un texte simple
                            texte = item_state.get('texte', item.get('texte', ''))
                            if texte:
                                content_final = self.latex_service.echapper_latex(texte)
                        
                        image = item_state.get('image', item.get('image', ''))
                        
                        if content_final or nom_sanitized or image:
                            sous_sections.append({
                                'nom': nom_sanitized,
                                'contenu': content_final,
                                'image': image,
                                'couleur': couleur_latex
                            })
                
                if sous_sections:
                    data_finale.append({'titre': titre, 'sous_sections': sous_sections})
                else:
                    data_finale.append({
                        'titre': titre,
                        'sous_sections': [{'nom': '', 'contenu': '', 'image': ''}]
                    })
                continue
            
            # ===== ANNEXES =====
            if 'ANNEXES' in titre_upper:
                annexes_state = section_data.get('annexes_main', {})
                image = annexes_state.get('image', '')
                texte = annexes_state.get('texte', 'Les documents suivants sont joints en annexe.')
                data_finale.append({
                    'titre': titre,
                    'sous_sections': [{'nom': 'Documents joints', 'contenu': texte, 'image': image}]
                })
                continue
            
            # ===== MOYENS HUMAINS - L'ÉQUIPE + SÉCURITÉ/SANTÉ + ORGANIGRAMME =====
            if 'MOYENS HUMAINS' in titre_upper:
                sous_sections = []
                
                # 1. L'ÉQUIPE (depuis _equipe_order_)
                for key in section_data.keys():
                    if key.startswith('_equipe_order_'):
                        equipe_items = section_data[key]
                        if isinstance(equipe_items, list):
                            for item in equipe_items:
                                result = self._process_item_for_pdf(item, section_data)
                                if result['nom'] or result['contenu'] or result['image']:
                                    sous_sections.append(result)
                        break
                
                # 2. SÉCURITÉ/SANTÉ (depuis _securite_order_)
                if '_securite_order_' in section_data:
                    ss_items = section_data['_securite_order_']
                    if isinstance(ss_items, list):
                        for item in ss_items:
                            nom = item.get('nom', '')
                            contenu = item.get('contenu', '')
                            couleur = item.get('couleur', 'ecoBleu')
                            
                            # Pour les listes, convertir en texte
                            if isinstance(contenu, list):
                                contenu = '\n'.join(f"- {c}" for c in contenu)
                            
                            # Sanitizer et échapper
                            nom_sanitized = nom.replace(',', '{,}')
                            for char, escaped in [('&', r'\&'), ('%', r'\%'), ('_', r'\_'), ('#', r'\#')]:
                                nom_sanitized = nom_sanitized.replace(char, escaped)
                            
                            # Traitement du contenu avec gestion des tirets
                            if contenu:
                                lines_with_dash = [l.strip() for l in contenu.split("\n") if l.strip().startswith("-")]
                                lines_without_dash = [l.strip() for l in contenu.split("\n") if l.strip() and not l.strip().startswith("-")]
                                
                                if lines_with_dash and not lines_without_dash:
                                    # Uniquement des tirets -> convertir en itemize
                                    items_tex = [f"    \\item {self.latex_service.echapper_latex(l[1:].strip())}" for l in lines_with_dash]
                                    content_escaped = "\\begin{itemize}\n" + "\n".join(items_tex) + "\n\\end{itemize}"
                                else:
                                    # Mixte ou pas de tirets -> échapper le texte normalement
                                    content_escaped = self.latex_service.echapper_latex(contenu)
                            else:
                                content_escaped = ''
                            
                            couleur_latex = LATEX_COLORS.get(couleur, LATEX_COLORS['ecoBleu'])['latex']
                            
                            sous_sections.append({
                                'nom': nom_sanitized,
                                'contenu': content_escaped,
                                'image': '',
                                'couleur': couleur_latex
                            })
                
                # 3. ORGANIGRAMME
                if 'organigramme' in section_data:
                    org_state = section_data['organigramme']
                    sous_sections.append({
                        'nom': 'Organigramme',
                        'contenu': '',
                        'image': org_state.get('image', '../images/organigramme.png'),
                        'couleur': LATEX_COLORS['ecoBleu']['latex']
                    })
                
                if sous_sections:
                    data_finale.append({'titre': titre, 'sous_sections': sous_sections})
                continue
            
            # ===== CONTEXTE DU PROJET =====
            if 'CONTEXTE' in titre_upper and 'PROJET' in titre_upper:
                sous_sections = []
                
                # Lire depuis _contexte_order_
                if '_contexte_order_' in section_data:
                    for item in section_data['_contexte_order_']:
                        nom = item.get('nom', '')
                        item_type = item.get('type', 'text')
                        couleur = item.get('couleur', 'ecoBleu')
                        couleur_latex = LATEX_COLORS.get(couleur, LATEX_COLORS['ecoBleu'])['latex']
                        
                        contenu = ''
                        
                        if item_type == 'visite':
                            # Visite de site
                            date_visite = item.get('date_visite', '')
                            adresse = item.get('adresse', '') or self.project_state["infos_projet"].get('adresse', '')
                            intro = item.get('intro_visite', 'Nous nous sommes rendus sur les lieux le')
                            
                            if date_visite or adresse:
                                contenu = f"{intro} {date_visite}"
                                if adresse:
                                    contenu += f", {adresse}"
                                contenu += "."
                        
                        elif item_type == 'checkbox':
                            # Sélections multiples
                            selections = item.get('selections', {})
                            selected_items = [k for k, v in selections.items() if v]
                            
                            if selected_items:
                                items_tex = [f"    \\item {self.latex_service.echapper_latex(c)}" for c in selected_items]
                                contenu = "\\begin{itemize}\n" + "\n".join(items_tex) + "\n\\end{itemize}"
                        
                        else:  # type == 'text'
                            contenu = item.get('contenu', '')
                        
                        if contenu:
                            sous_sections.append({
                                'nom': self.latex_service.echapper_latex(nom),
                                'contenu': contenu if item_type == 'checkbox' else self.latex_service.echapper_latex(contenu),
                                'image': '',
                                'couleur': couleur_latex
                            })
                
                if sous_sections:
                    data_finale.append({'titre': titre, 'sous_sections': sous_sections})
                continue
            
            # ===== SECTIONS GÉNÉRIQUES (MOYENS MATÉRIEL, MÉTHODOLOGIE, etc.) =====
            sous_sections = []
            
            # Chercher la liste ordonnée principale
            order_key = f'_subsection_order_{titre}'
            if order_key in section_data and isinstance(section_data[order_key], list):
                items = section_data[order_key]
                
                for item in items:
                    nom = item.get('sous_section', '')
                    
                    # CAS SPÉCIAL: Transport et Levage (cartes réordonnables)
                    if 'transport' in nom.lower() and 'levage' in nom.lower():
                        # Collecter depuis _transport_levage_order_
                        if '_transport_levage_order_' in section_data:
                            tl_items = section_data['_transport_levage_order_']
                            tl_selections = section_data.get('_tl_selections_', {'livraison': {}, 'levage': {}})
                            
                            for tl_item in tl_items:
                                tl_nom = tl_item.get('nom', '')
                                tl_type = tl_item.get('type', 'text')
                                tl_key = tl_item.get('key', '')
                                tl_contenu = tl_item.get('contenu', '')
                                tl_couleur = tl_item.get('couleur', 'ecoBleu')
                                
                                content_final = ''
                                
                                if tl_type == 'checklist':
                                    selections = tl_selections.get(tl_key, {})
                                    checked_opts = [opt for opt, is_checked in selections.items() if is_checked]
                                    if checked_opts:
                                        items_tex = [f"    \\item {self.latex_service.echapper_latex(opt)}" for opt in checked_opts]
                                        content_final = "\\begin{itemize}\n" + "\n".join(items_tex) + "\n\\end{itemize}"
                                else:
                                    if tl_contenu:
                                        content_final = self.latex_service.echapper_latex(tl_contenu)
                                
                                if content_final or tl_nom:
                                    tl_nom_san = tl_nom.replace(',', '{,}')
                                    for char, escaped in [('&', r'\&'), ('%', r'\%'), ('_', r'\_'), ('#', r'\#')]:
                                        tl_nom_san = tl_nom_san.replace(char, escaped)
                                    
                                    sous_sections.append({
                                        'nom': tl_nom_san,
                                        'contenu': content_final,
                                        'image': '',
                                        'couleur': LATEX_COLORS.get(tl_couleur, LATEX_COLORS['ecoBleu'])['latex']
                                    })
                        continue
                    
                    # Traitement générique
                    result = self._process_item_for_pdf(item, section_data)
                    if result['nom'] or result['contenu'] or result['image']:
                        sous_sections.append(result)
            
            # PLANNING - traitement spécial
            if 'PLANNING' in titre_upper and 'planning_main' in section_data:
                state = section_data['planning_main']
                nom = state.get('nom', 'Planning')
                texte = state.get('texte', '')
                couleur = state.get('couleur', 'ecoBleu')
                image = state.get('image', '')

                nom_sanitized = nom.replace(',', '{,}')
                for char, escaped in [('&', r'\&'), ('%', r'\%'), ('_', r'\_'), ('#', r'\#')]:
                    nom_sanitized = nom_sanitized.replace(char, escaped)
                
                content_escaped = self.latex_service.echapper_latex(texte) if texte else ''
                couleur_latex = LATEX_COLORS.get(couleur, LATEX_COLORS['ecoBleu'])['latex']
                
                sous_sections.insert(0, {
                    'nom': nom_sanitized,
                    'contenu': content_escaped,
                    'image': image,
                    'couleur': couleur_latex
                })
            
            # LISTE DES MATERIAUX - Ajouter les tableaux forcés (Fixation, Traitement préventif, Traitement curatif)
            if 'LISTE DES MATERIAUX' in titre_upper or 'MATERIAUX' in titre_upper:
                # Vérifier si les tableaux existent déjà dans les sous_sections
                has_fixation = any('fixation' in ss.get('nom', '').lower() and 'assemblage' in ss.get('nom', '').lower() for ss in sous_sections)
                has_traitement_prev = any('traitement' in ss.get('nom', '').lower() and ('préventif' in ss.get('nom', '').lower() or 'preventif' in ss.get('nom', '').lower()) for ss in sous_sections)
                has_traitement_cur = any('traitement' in ss.get('nom', '').lower() and 'curatif' in ss.get('nom', '').lower() for ss in sous_sections)
                
                # Tableau Fixation et assemblage
                if not has_fixation:
                    fix_state = section_data.get('fixation_table_forced', {})
                    if not fix_state:
                        # Chercher aussi dans les autres clés potentielles
                        for key in section_data:
                            if isinstance(section_data[key], dict) and section_data[key].get('type') == 'table_fixation':
                                if 'fixation' in key.lower():
                                    fix_state = section_data[key]
                                    break
                    
                    table_data = fix_state.get('table_data', [])
                    if not table_data:
                        # Charger depuis template_data
                        template_data = self.project_state.get("template_data", {})
                        table_data = template_data.get('table_fixation_assemblage', [])
                    
                    if table_data:
                        lines = []
                        lines.append("\\begin{tabular}{|p{5cm}|p{4.5cm}|p{3cm}|p{1.5cm}|}")
                        lines.append("\\hline")
                        lines.append("\\textbf{Nature} & \\textbf{Marque/Type} & \\textbf{Provenance} & \\textbf{Doc} \\\\")
                        lines.append("\\hline")
                        for row in table_data:
                            nature = self.latex_service.echapper_latex(row.get('nature', ''))
                            marque = self.latex_service.echapper_latex(row.get('marque', ''))
                            provenance = self.latex_service.echapper_latex(row.get('provenance', ''))
                            doc = row.get('doc', 'OUI')
                            lines.append(f"{nature} & {marque} & {provenance} & {doc} \\\\")
                            lines.append("\\hline")
                        lines.append("\\end{tabular}")
                        
                        fix_couleur = fix_state.get('couleur', 'ecoMarron')
                        sous_sections.append({
                            'nom': 'Fixation et assemblage',
                            'contenu': "\n".join(lines),
                            'image': '',
                            'couleur': LATEX_COLORS.get(fix_couleur, LATEX_COLORS['ecoMarron'])['latex']
                        })
                
                # Tableau Traitement préventif
                if not has_traitement_prev:
                    prev_state = section_data.get('traitement_preventif_forced', {})
                    table_data = prev_state.get('table_data', [])
                    if not table_data:
                        template_data = self.project_state.get("template_data", {})
                        table_data = template_data.get('table_traitement_preventif', [])
                    
                    if table_data:
                        lines = []
                        lines.append("\\begin{tabular}{|p{5cm}|p{4.5cm}|p{3cm}|p{1.5cm}|}")
                        lines.append("\\hline")
                        lines.append("\\textbf{Nature} & \\textbf{Marque/Type} & \\textbf{Provenance} & \\textbf{Doc} \\\\")
                        lines.append("\\hline")
                        for row in table_data:
                            nature = self.latex_service.echapper_latex(row.get('nature', ''))
                            marque = self.latex_service.echapper_latex(row.get('marque', ''))
                            provenance = self.latex_service.echapper_latex(row.get('provenance', ''))
                            doc = row.get('doc', 'OUI')
                            lines.append(f"{nature} & {marque} & {provenance} & {doc} \\\\")
                            lines.append("\\hline")
                        lines.append("\\end{tabular}")
                        
                        prev_couleur = prev_state.get('couleur', 'ecoVert')
                        sous_sections.append({
                            'nom': 'Traitement préventif',
                            'contenu': "\n".join(lines),
                            'image': '',
                            'couleur': LATEX_COLORS.get(prev_couleur, LATEX_COLORS['ecoVert'])['latex']
                        })
                
                # Tableau Traitement curatif
                if not has_traitement_cur:
                    cur_state = section_data.get('traitement_curatif_forced', {})
                    table_data = cur_state.get('table_data', [])
                    if not table_data:
                        template_data = self.project_state.get("template_data", {})
                        table_data = template_data.get('table_traitement_curatif', [])
                    
                    if table_data:
                        lines = []
                        lines.append("\\begin{tabular}{|p{5cm}|p{4.5cm}|p{3cm}|p{1.5cm}|}")
                        lines.append("\\hline")
                        lines.append("\\textbf{Nature} & \\textbf{Marque/Type} & \\textbf{Provenance} & \\textbf{Doc} \\\\")
                        lines.append("\\hline")
                        for row in table_data:
                            nature = self.latex_service.echapper_latex(row.get('nature', ''))
                            marque = self.latex_service.echapper_latex(row.get('marque', ''))
                            provenance = self.latex_service.echapper_latex(row.get('provenance', ''))
                            doc = row.get('doc', 'OUI')
                            lines.append(f"{nature} & {marque} & {provenance} & {doc} \\\\")
                            lines.append("\\hline")
                        lines.append("\\end{tabular}")
                        
                        cur_couleur = cur_state.get('couleur', 'ecoVert')
                        sous_sections.append({
                            'nom': 'Traitement curatif',
                            'contenu': "\n".join(lines),
                            'image': '',
                            'couleur': LATEX_COLORS.get(cur_couleur, LATEX_COLORS['ecoVert'])['latex']
                        })
            
            if sous_sections:
                data_finale.append({'titre': titre, 'sous_sections': sous_sections})
        
        return data_finale
    
    async def _generate_pdf(self):
        """Genere le PDF a partir du state."""
        # Infos projet depuis le state
        infos = {
            "Intitule_operation": self.project_state["infos_projet"]["intitule"],
            "Lot_Intitule": self.project_state["infos_projet"]["lot"],
            "Maitre_ouvrage_nom": self.project_state["infos_projet"]["moa"],
            "Adresse_chantier": self.project_state["infos_projet"]["adresse"],
        }
        
        # Dialog de progression
        with ui.dialog() as dialog, ui.card().classes('p-6 items-center'):
            ui.spinner(size='lg')
            status_label = ui.label('Collecte des donnees...').classes('mt-4')
        
        dialog.open()
        await asyncio.sleep(0.1)
        
        try:
            # Collecter depuis le state
            data_finale = self._collect_data_from_state()
            
            if not data_finale:
                dialog.close()
                ui.notify('Aucune donnee a generer. Remplissez au moins une section.', type='warning')
                return
            
            # Images
            images = {}
            for key, path in self.project_state["images"].items():
                if path:
                    images[key] = path
                else:
                    default_images = {
                        "image_garde": "../images/exemple_pagegarde.jpeg",
                        "attestation_visite": "../images/attestation_visite.png",
                        "plan_emplacement": "../images/vue_aerienne.png",
                        "image_grue": "../images/grue.png",
                    }
                    images[key] = default_images.get(key, "")
            
            # Generer .tex
            status_label.set_text('Generation du fichier LaTeX...')
            await asyncio.sleep(0.1)
            
            # Récupérer les données de templates modifiables depuis le state
            template_data = self.project_state.get("template_data", {})
            
            # PRÉAMBULE: utiliser la valeur modifiée depuis l'UI
            if 'preambule' in self.project_state and self.project_state['preambule']:
                template_data['preambule'] = self.project_state['preambule']
            
            # Mettre à jour securite_sante depuis les modifications faites dans Moyens Humains
            for titre, section_data in self.project_state["sections_data"].items():
                if 'MOYENS HUMAINS' in titre.upper():
                    # D'abord synchroniser depuis _securite_order_ si présent
                    if '_securite_order_' in section_data:
                        ss_items = section_data['_securite_order_']
                        if 'securite_sante_data' not in section_data:
                            section_data['securite_sante_data'] = {}
                        ss_data = section_data['securite_sante_data']
                        
                        for item in ss_items:
                            key = item.get('key', '')
                            if key:
                                ss_data[key] = item.get('contenu', '')
                                if 'couleurs' not in ss_data:
                                    ss_data['couleurs'] = {}
                                ss_data['couleurs'][key] = item.get('couleur', 'ecoBleu')
                    
                    if 'securite_sante_data' in section_data:
                        ss_data = section_data['securite_sante_data']
                        
                        # Mettre à jour template_data avec les nouvelles valeurs
                        if 'securite_sante' not in template_data:
                            template_data['securite_sante'] = {}
                        
                        # Copier les champs modifiés
                        for key in ['organisation_production', 'confort_travail', 'accueil_nouveaux', 
                                    'securite_generale', 'controle_annuel', 'concretement', 'habilitations']:
                            if key in ss_data:
                                template_data['securite_sante'][key] = ss_data[key]
                        
                        # IMPORTANT: Copier les couleurs individuelles par cadre
                        if 'couleurs' in ss_data:
                            template_data['securite_sante']['couleurs'] = ss_data['couleurs']
                    
                    break
            
            # Mettre à jour moyens_materiel avec les couleurs individuelles
            for titre, section_data in self.project_state["sections_data"].items():
                if 'MOYENS MATERIEL' in titre.upper():
                    if 'moyens_materiel' not in template_data:
                        template_data['moyens_materiel'] = {}
                    
                    # Récupérer les couleurs depuis les sous-sections
                    order_key = f'_subsection_order_{titre}'
                    if order_key in section_data:
                        items = section_data[order_key]
                        couleurs_mm = {}
                        
                        for item in items:
                            ss_name = item.get('sous_section', '').lower()
                            couleur = item.get('couleur', 'ecoBleu')
                            
                            # Mapper les noms de sous-sections vers les clés du template
                            if 'intro' in ss_name or 'parc' in ss_name:
                                couleurs_mm['intro'] = couleur
                            elif 'conception' in ss_name or 'précision' in ss_name:
                                couleurs_mm['conception'] = couleur
                            elif 'sécurité' in ss_name or 'securite' in ss_name:
                                couleurs_mm['securite'] = couleur
                            elif 'atelier' in ss_name:
                                couleurs_mm['atelier'] = couleur
                            elif 'levage' in ss_name:
                                couleurs_mm['levage'] = couleur
                            elif 'transport' in ss_name:
                                couleurs_mm['transport'] = couleur
                            elif 'portative' in ss_name or 'machine' in ss_name:
                                couleurs_mm['machine_portative'] = couleur
                            elif 'protection' in ss_name or 'nettoyage' in ss_name:
                                couleurs_mm['protection_nettoyage'] = couleur
                            elif 'déchet' in ss_name or 'dechet' in ss_name or 'gestion' in ss_name:
                                couleurs_mm['gestion_dechet'] = couleur
                        
                        if couleurs_mm:
                            template_data['moyens_materiel']['couleurs'] = couleurs_mm
                    
                    break
            
            # Collecter les couleurs de chaque section depuis le state
            couleurs_sections = {}
            for titre, section_data in self.project_state["sections_data"].items():
                titre_upper = titre.upper()
                # Chercher la couleur principale de la section
                couleur = 'ecoBleu'  # Défaut
                
                # Pour planning, la couleur est dans planning_main
                if 'PLANNING' in titre_upper and 'planning_main' in section_data:
                    couleur = section_data['planning_main'].get('couleur', 'ecoBleu')
                # Pour moyens humains, prendre aussi la couleur de sécurité/santé
                elif 'MOYENS HUMAINS' in titre_upper:
                    # Couleur de la section équipe
                    for key, ss_state in section_data.items():
                        if isinstance(ss_state, dict) and 'couleur' in ss_state and key != 'securite_sante_data':
                            couleur = ss_state['couleur']
                            break
                    # Couleur spécifique pour sécurité/santé
                    if 'securite_sante_data' in section_data:
                        ss_data = section_data['securite_sante_data']
                        if isinstance(ss_data, dict) and 'couleur' in ss_data:
                            couleurs_sections['SECURITE_SANTE'] = ss_data['couleur']
                # Pour les autres sections, chercher dans _section_couleur, _subsection_order_ ou les sous-sections
                else:
                    # D'abord chercher la couleur globale de section si définie
                    if '_section_couleur' in section_data:
                        couleur = section_data['_section_couleur']
                    # Sinon chercher dans la liste ordonnée des sous-sections
                    elif f'_subsection_order_{titre}' in section_data:
                        order_key = f'_subsection_order_{titre}'
                        items = section_data[order_key]
                        if isinstance(items, list) and items and len(items) > 0:
                            # Prendre la couleur du premier item
                            couleur = items[0].get('couleur', 'ecoBleu')
                    else:
                        # Sinon chercher dans les sous-sections classiques
                        for key, ss_state in section_data.items():
                            if isinstance(ss_state, dict) and 'couleur' in ss_state:
                                couleur = ss_state['couleur']
                                break
                
                # Normaliser le nom pour la correspondance
                if 'SITUATION ADMINISTRATIVE' in titre_upper:
                    couleurs_sections['SITUATION ADMINISTRATIVE'] = couleur
                elif 'MOYENS HUMAINS' in titre_upper:
                    couleurs_sections['MOYENS HUMAINS'] = couleur
                elif 'MOYENS MATERIEL' in titre_upper:
                    # Pour MOYENS MATERIEL, on utilise les couleurs par cadre (pas de couleur globale)
                    couleurs_sections['MOYENS MATERIEL'] = couleur
                elif 'PLANNING' in titre_upper:
                    couleurs_sections['PLANNING'] = couleur
            
            # S'assurer que SECURITE_SANTE existe
            if 'SECURITE_SANTE' not in couleurs_sections:
                # Chercher dans MOYENS HUMAINS -> securite_sante_data
                for titre, section_data in self.project_state["sections_data"].items():
                    if 'MOYENS HUMAINS' in titre.upper():
                        if 'securite_sante_data' in section_data:
                            ss_data = section_data['securite_sante_data']
                            if isinstance(ss_data, dict) and 'couleur' in ss_data:
                                couleurs_sections['SECURITE_SANTE'] = ss_data['couleur']
                        break
            
            tex_path = self.latex_service.generer_tex(
                data_finale,
                infos,
                images,
                template_data=template_data,
                couleurs_sections=couleurs_sections
            )
            
            # Compiler PDF
            status_label.set_text('Compilation PDF avec pdflatex...')
            await asyncio.sleep(0.1)
            
            success, message = self.latex_service.compiler_pdf(tex_path)
            
            dialog.close()
            
            if success:
                pdf_path = Path(message)
                print(f"\nPDF genere avec succes!")
                print(f"Fichier PDF : {pdf_path}")
                print(f"Dossier     : {pdf_path.parent.absolute()}\n")
                
                with ui.dialog() as success_dialog, ui.card().classes('p-6'):
                    ui.label('PDF genere avec succes!').classes('text-xl font-bold text-green-600 mb-4')
                    
                    with ui.column().classes('gap-2 bg-green-50 p-4 rounded'):
                        with ui.row().classes('items-center gap-2'):
                            ui.icon('picture_as_pdf', size='sm').classes('text-red-600')
                            ui.label(f'{pdf_path.name}').classes('font-semibold')
                        
                        ui.label(f'Dossier: {pdf_path.parent}').classes('text-sm text-gray-600 break-all')
                    
                    ui.button('Fermer', on_click=success_dialog.close).classes('mt-4')
                
                success_dialog.open()
            else:
                ui.notify(f'Erreur: {message}', type='negative', timeout=10000)
        
        except Exception as ex:
            dialog.close()
            ui.notify(f'Erreur inattendue: {str(ex)}', type='negative')


def render():
    """Point d'entree pour le rendu de la page."""
    page = GenerationPage()
    page.render()
