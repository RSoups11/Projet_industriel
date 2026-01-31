"""
Page de gestion des donnees CSV (base de donnees du memoire).
Interface simplifiee SANS code LaTeX visible.
Permet de modifier les textes et options du memoire de maniere intuitive.
"""

from nicegui import ui
from pathlib import Path
import pandas as pd
import json
from datetime import datetime
from typing import Dict, List, Any, Optional

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.config import AppConfig
from app.core.csv_service import CSVService


class TemplatesPage:
    """Page de gestion des donnees/templates du memoire."""
    
    def __init__(self):
        self.config = AppConfig()
        self.csv_service = CSVService()
        self.df = None
        self.current_section = None
        self.edit_widgets = {}
        # Sections autorisees (memes que dans "Nouveau memoire")
        self.authorized_sections = self.config.user_config.get("sections_autorisees", [])
    
    def render(self):
        """Rendu principal de la page."""
        with ui.column().classes('w-full h-full p-6'):
            ui.label('Base de donnees du memoire').classes('text-2xl font-bold text-blue-900 mb-2')
            ui.label('Modifiez ici les textes et options par defaut qui apparaitront dans vos memoires.').classes('text-gray-600 mb-4')
            
            with ui.row().classes('w-full gap-4 flex-grow'):
                # Panneau gauche : liste des sections
                self._render_sections_list()
                
                # Panneau droit : edition de la section selectionnee
                self._render_editor_panel()
        
        # Charger les donnees au demarrage
        ui.timer(0.3, self._load_data, once=True)
    
    def _render_sections_list(self):
        """Liste des sections du CSV."""
        with ui.card().classes('w-80 p-4'):
            ui.label('Sections').classes('text-lg font-bold text-blue-800 mb-3')
            
            with ui.row().classes('gap-2 mb-3'):
                ui.button('Recharger', on_click=self._load_data, icon='refresh').props('flat size=sm')
                ui.button('Sauvegarder', on_click=self._save_all, icon='save').props('size=sm').classes('bg-green-600 text-white')
            
            self.sections_container = ui.scroll_area().classes('h-96')
    
    def _render_editor_panel(self):
        """Panneau d'edition."""
        with ui.card().classes('flex-grow p-4'):
            self.editor_title = ui.label('Selectionnez une section').classes('text-lg font-bold text-blue-800 mb-3')
            self.editor_container = ui.column().classes('w-full gap-3')
    
    async def _load_data(self):
        """Charge les donnees du CSV."""
        csv_path = self.config.DEFAULT_CSV_FILE
        
        if not csv_path.exists():
            # Essayer bd_interface.csv
            csv_path = self.config.DATA_DIR / "bd_interface.csv"
        
        if not csv_path.exists():
            ui.notify('Fichier CSV introuvable', type='negative')
            return
        
        try:
            # Essayer differents encodages
            encodings = ['utf-8', 'latin-1', 'iso-8859-1', 'cp1252']
            self.df = None
            
            for encoding in encodings:
                try:
                    self.df = pd.read_csv(csv_path, sep=";", dtype=str, encoding=encoding, on_bad_lines='skip')
                    break
                except UnicodeDecodeError:
                    continue
            
            if self.df is None:
                raise ValueError("Impossible de lire le fichier avec les encodages disponibles")
            
            self.df = self.df.fillna("")
            self.df.columns = self.df.columns.str.strip().str.lower()
            
            # Afficher les sections
            await self._display_sections()
            
            ui.notify(f'Donnees chargees: {len(self.df)} lignes', type='positive')
        
        except Exception as ex:
            ui.notify(f'Erreur: {str(ex)}', type='negative')
    
    async def _display_sections(self):
        """Affiche la liste des sections valides (autorisees et non vides)."""
        if self.df is None:
            return
        
        self.sections_container.clear()
        
        # Grouper par section et filtrer
        sections = self.df['section'].unique()
        
        with self.sections_container:
            for section in sorted(sections):
                if not section.strip():
                    continue
                
                # Filtrer: ne montrer que les sections autorisees
                if self.authorized_sections and section not in self.authorized_sections:
                    continue
                
                # Filtrer: ne montrer que les sections avec au moins une ligne valide
                section_rows = self.df[self.df['section'] == section]
                valid_rows = section_rows[
                    (section_rows['sous-section'].str.strip() != '') | 
                    (section_rows['texte'].str.strip() != '')
                ]
                
                if valid_rows.empty:
                    continue  # Sauter les sections completement vides
                
                count = len(valid_rows)
                
                with ui.card().classes('w-full p-3 cursor-pointer hover:bg-blue-50').on('click', lambda s=section: self._select_section(s)):
                    ui.label(section[:40] + '...' if len(section) > 40 else section).classes('font-semibold text-sm')
                    ui.label(f'{count} elements').classes('text-xs text-gray-500')
    
    async def _select_section(self, section: str):
        """Selectionne une section pour l'editer."""
        self.current_section = section
        self.editor_title.set_text(f'Edition: {section}')
        self.edit_widgets = {}
        
        self.editor_container.clear()
        
        # Filtrer les lignes de cette section
        rows = self.df[self.df['section'] == section]
        
        with self.editor_container:
            for idx, row in rows.iterrows():
                sous_section = str(row.get('sous-section', '')).strip()
                texte = str(row.get('texte', '')).strip()
                image = str(row.get('image', '')).strip()
                
                if not sous_section and not texte:
                    continue
                
                with ui.card().classes('w-full p-4'):
                    # Nom de la sous-section (editable)
                    ui.label('Titre de la sous-section:').classes('text-xs text-gray-500')
                    ss_input = ui.input(value=sous_section).classes('w-full mb-2')
                    
                    # Contenu (editable)
                    ui.label('Contenu:').classes('text-xs text-gray-500')
                    
                    # Detecter si c'est un choix multiple
                    if "/// ou ///" in texte:
                        ui.label('(Options separees par "/// ou ///")').classes('text-xs text-orange-500')
                    
                    rows_count = max(2, min(8, len(texte) // 60 + 1))
                    texte_input = ui.textarea(value=texte).classes('w-full').props(f'rows={rows_count}')
                    
                    # Image (optionnelle)
                    with ui.row().classes('items-center gap-2 mt-2'):
                        ui.label('Image:').classes('text-xs text-gray-500')
                        image_input = ui.input(value=image, placeholder='Chemin de l\'image (optionnel)').classes('flex-grow')
                    
                    # Stocker les widgets pour la sauvegarde
                    self.edit_widgets[idx] = {
                        'sous_section': ss_input,
                        'texte': texte_input,
                        'image': image_input
                    }
            
            # Bouton ajouter une nouvelle sous-section
            with ui.row().classes('w-full justify-center mt-4'):
                ui.button('Ajouter une sous-section', on_click=lambda: self._add_subsection(section), icon='add').props('outline')
    
    async def _add_subsection(self, section: str):
        """Ajoute une nouvelle sous-section."""
        # Ajouter une ligne au DataFrame
        new_row = pd.DataFrame([{
            'section': section,
            'sous-section': 'Nouvelle sous-section',
            'texte': '',
            'image': ''
        }])
        self.df = pd.concat([self.df, new_row], ignore_index=True)
        
        # Rafraichir l'affichage
        await self._select_section(section)
        ui.notify('Sous-section ajoutee', type='positive')
    
    async def _save_all(self):
        """Sauvegarde toutes les modifications."""
        if self.df is None:
            ui.notify('Aucune donnee a sauvegarder', type='warning')
            return
        
        # Appliquer les modifications des widgets
        for idx, widgets in self.edit_widgets.items():
            if idx in self.df.index:
                self.df.at[idx, 'sous-section'] = widgets['sous_section'].value
                self.df.at[idx, 'texte'] = widgets['texte'].value
                self.df.at[idx, 'image'] = widgets['image'].value
        
        # Sauvegarder le CSV
        csv_path = self.config.DEFAULT_CSV_FILE
        
        try:
            # Backup avant sauvegarde
            backup_path = csv_path.with_suffix('.csv.bak')
            if csv_path.exists():
                import shutil
                shutil.copy(csv_path, backup_path)
            
            # Sauvegarder
            self.df.to_csv(csv_path, sep=";", index=False, encoding='utf-8')
            
            ui.notify(f'Donnees sauvegardees dans {csv_path.name}', type='positive')
        
        except Exception as ex:
            ui.notify(f'Erreur de sauvegarde: {str(ex)}', type='negative')


def render():
    """Point d'entree pour le rendu de la page."""
    page = TemplatesPage()
    page.render()
