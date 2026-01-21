"""
Page de generation de memoires techniques.
Interface principale avec STATE MANAGEMENT pour capturer les modifications utilisateur.
"""

from nicegui import ui, events
from pathlib import Path
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
        }
        
        # DataFrame source
        self.df = None
        
        # Widgets pour mise a jour du state
        self.input_widgets = {}
        self.section_checkboxes = {}
        
        # Sections autorisees depuis config
        self.sections_autorisees = self.config.user_config.get("sections_autorisees", [])
        for section in self.sections_autorisees:
            self.project_state["sections_enabled"][section] = True
    
    def render(self):
        """Rendu principal de la page."""
        with ui.row().classes('w-full h-full gap-0'):
            # Sidebar gauche
            self._render_sidebar()
            
            # Zone principale
            with ui.column().classes('flex-grow p-4 bg-gray-50 overflow-auto'):
                self._render_main_content()
    
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
            
            with ui.scroll_area().classes('h-48'):
                for section in self.sections_autorisees:
                    display_name = section[:30] + '...' if len(section) > 30 else section
                    cb = ui.checkbox(
                        display_name,
                        value=True,
                        on_change=lambda e, s=section: self._toggle_section(s, e.value)
                    ).classes('text-sm')
                    self.section_checkboxes[section] = cb
            
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
                content = e.content.read()
                img_path = self.config.IMAGES_DIR / e.name
                with open(img_path, 'wb') as f:
                    f.write(content)
                self.project_state["images"][k] = str(img_path)
                fl.set_text(e.name[:12] + '...' if len(e.name) > 12 else e.name)
                ui.notify(f'Image {e.name} chargee', type='positive')
            
            ui.upload(
                on_upload=handle_upload,
                auto_upload=True,
                max_files=1
            ).props('accept=".jpg,.jpeg,.png,.pdf" flat dense').classes('w-20')
    
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
            csv_path = self.config.DATA_DIR / "crack_clean.csv"
        
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
        
        with self.sections_container:
            for titre_officiel in self.sections_autorisees:
                titre_norm = normaliser_titre(titre_officiel)
                rows = self.df[self.df['section_norm'] == titre_norm]
                
                if rows.empty:
                    continue
                
                # Initialiser le state pour cette section
                if titre_officiel not in self.project_state["sections_data"]:
                    self.project_state["sections_data"][titre_officiel] = {}
                
                # Card de section (expansion)
                icon = SECTION_ICONS.get(titre_officiel, 'folder')
                
                with ui.expansion(titre_officiel, icon=icon).classes('w-full bg-white shadow rounded-lg').props('default-opened'):
                    self._build_section_content(titre_officiel, rows)
    
    def _build_section_content(self, titre: str, rows: pd.DataFrame):
        """Construit le contenu d'une section."""
        section_state = self.project_state["sections_data"][titre]
        seen_subs = set()
        
        with ui.column().classes('w-full gap-3 p-2'):
            for index, row in rows.iterrows():
                sous_section = nettoyer_str(row.get('sous-section', ''))
                texte_brut = nettoyer_str(row.get('texte', ''))
                image = nettoyer_str(row.get('image', ''))
                
                if not sous_section and not texte_brut and not image:
                    continue
                
                # Eviter doublons
                sub_key = sous_section.lower().strip()
                if sub_key in seen_subs:
                    continue
                seen_subs.add(sub_key)
                
                # Creer la sous-section avec binding au state
                unique_key = f"{index}_{sub_key}"
                self._create_subsection_widget(titre, unique_key, sous_section, texte_brut, image, section_state)
    
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
                
                # Checkboxes pour les noms
                with ui.row().classes('gap-3 flex-wrap'):
                    for opt in options:
                        cb = ui.checkbox(
                            opt,
                            value=True,
                            on_change=lambda e, o=opt: self._toggle_selection(state, 'noms', o, e.value)
                        )
                        state['selections'].setdefault('noms', {})[opt] = True
                
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
                
                with ui.column().classes('gap-1'):
                    for opt in options:
                        cb = ui.checkbox(
                            opt[:60] + '...' if len(opt) > 60 else opt,
                            value=True,
                            on_change=lambda e, o=opt: self._toggle_selection(state, 'options', o, e.value)
                        ).classes('text-sm')
                        state['selections'].setdefault('options', {})[opt] = True
                
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
    
    def _collect_data_from_state(self) -> List[Dict[str, Any]]:
        """Collecte les donnees depuis le state central pour la generation."""
        data_finale = []
        
        for titre in self.sections_autorisees:
            # Verifier si section active
            if not self.project_state["sections_enabled"].get(titre, True):
                continue
            
            section_data = self.project_state["sections_data"].get(titre, {})
            if not section_data:
                continue
            
            sous_sections = []
            
            for key, ss_state in section_data.items():
                nom = ss_state.get('nom', '')
                image = ss_state.get('image', '')
                content = ""
                
                ss_type = ss_state.get('type', 'text')
                
                if ss_type == 'contexte_visite':
                    date_val = ss_state.get('date', '').strip()
                    adr_val = ss_state.get('adresse_visite', '').strip()
                    if date_val:
                        content = f"Nous sommes passes faire la visite sur le site le {date_val}."
                        if adr_val:
                            content += f" Adresse : {adr_val}."
                
                elif ss_type == 'title_options':
                    # Noms selectionnes
                    noms_sel = ss_state.get('selections', {}).get('noms', {})
                    selected_noms = [n for n, v in noms_sel.items() if v]
                    if selected_noms:
                        base_nom = nom.split(':')[0].strip() if ':' in nom else nom
                        nom = f"{base_nom} : {', '.join(selected_noms)}"
                    content = ss_state.get('texte', '')
                
                elif ss_type == 'multi_check':
                    options_sel = ss_state.get('selections', {}).get('options', {})
                    selected = [o for o, v in options_sel.items() if v]
                    if selected:
                        content = "\n".join(f"- {s}" for s in selected)
                
                else:  # text
                    content = ss_state.get('texte', '')
                
                if content or image:
                    # Sanitize title to avoid tcolorbox key parsing issues
                    nom_sanitized = self.latex_service.echapper_latex(nom)
                    # Avoid commas which can conflict in optional args parsing
                    nom_sanitized = nom_sanitized.replace(',', ';')
                    # Echapper LaTeX
                    content_escaped = self.latex_service.echapper_latex(content)
                    
                    # Convertir listes en itemize LaTeX
                    if content.strip().startswith("-"):
                        lines = [l.strip()[1:].strip() for l in content.split("\n") if l.strip().startswith("-")]
                        if lines:
                            items = [f"    \\item {self.latex_service.echapper_latex(l)}" for l in lines]
                            content_escaped = "\\begin{itemize}\n" + "\n".join(items) + "\n\\end{itemize}"
                    
                    sous_sections.append({
                        'nom': nom_sanitized,
                        'contenu': content_escaped,
                        'image': image
                    })
            
            if sous_sections:
                data_finale.append({
                    'titre': titre,
                    'sous_sections': sous_sections
                })
        
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
            
            tex_path = self.latex_service.generer_tex(
                data_finale,
                infos,
                images
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
