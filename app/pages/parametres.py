"""
Page des paramètres de l'application.
Configuration, préférences et gestion des données.
"""

from nicegui import ui
from pathlib import Path
import json
from typing import Dict, Any

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.config import AppConfig, FIELD_LABELS


class ParametresPage:
    """Composant de la page des paramètres."""
    
    def __init__(self):
        self.config = AppConfig()
    
    def render(self):
        """Rendu principal de la page."""
        with ui.column().classes('w-full max-w-4xl mx-auto p-6'):
            ui.label('Paramètres').classes('text-3xl font-bold text-blue-900 mb-6')
            
            # Section valeurs par défaut
            self._render_defaults_section()
            
            ui.separator().classes('my-6')
            
            # Section chemins
            self._render_paths_section()
            
            ui.separator().classes('my-6')
            
            # Section sections autorisées
            self._render_sections_section()
            
            ui.separator().classes('my-6')
            
            # Section actions
            self._render_actions_section()
    
    def _render_defaults_section(self):
        """Section des valeurs par défaut."""
        with ui.card().classes('w-full p-6'):
            ui.label('Valeurs par défaut').classes('text-xl font-bold text-blue-900 mb-4')
            ui.label('Ces valeurs seront pré-remplies lors de la création d\'un nouveau mémoire.').classes('text-sm text-gray-600 mb-4')
            
            defaults = self.config.user_config.get("defaults", {})
            self.default_inputs = {}
            
            with ui.grid(columns=2).classes('w-full gap-4'):
                for key, label in FIELD_LABELS.items():
                    with ui.column().classes('gap-1'):
                        ui.label(label).classes('text-sm font-semibold text-gray-700')
                        self.default_inputs[key] = ui.input(
                            value=defaults.get(key, "")
                        ).classes('w-full')
            
            ui.button(
                'Sauvegarder les valeurs par défaut',
                on_click=self._save_defaults,
                icon='save'
            ).classes('mt-4 bg-green-600 text-white')
    
    def _render_paths_section(self):
        """Section des chemins de fichiers."""
        with ui.card().classes('w-full p-6'):
            ui.label('Chemins de fichiers').classes('text-xl font-bold text-blue-900 mb-4')
            
            paths = [
                ('Dossier de base', self.config.BASE_DIR),
                ('Templates', self.config.TEMPLATES_DIR),
                ('Données (CSV)', self.config.DATA_DIR),
                ('Sortie (PDF)', self.config.OUTPUT_DIR),
                ('Images', self.config.IMAGES_DIR),
            ]
            
            with ui.grid(columns=2).classes('w-full gap-4'):
                for label, path in paths:
                    with ui.row().classes('items-center gap-2'):
                        ui.icon('folder', size='sm').classes('text-blue-600')
                        ui.label(label).classes('font-semibold w-32')
                        ui.label(str(path)).classes('text-sm text-gray-600 font-mono bg-gray-100 px-2 py-1 rounded')
            
            ui.separator().classes('my-4')
            
            ui.label('Commande pdflatex').classes('font-semibold text-gray-700')
            self.pdflatex_input = ui.input(
                value=self.config.user_config.get("pdflatex_path", "pdflatex")
            ).classes('w-full')
            ui.label('Laissez "pdflatex" si installé globalement, sinon spécifiez le chemin complet.').classes('text-xs text-gray-500')
    
    def _render_sections_section(self):
        """Section des sections autorisées."""
        with ui.card().classes('w-full p-6'):
            ui.label('Sections du mémoire').classes('text-xl font-bold text-blue-900 mb-4')
            ui.label('Gérez les sections qui apparaîtront dans les mémoires techniques.').classes('text-sm text-gray-600 mb-4')
            
            sections = self.config.user_config.get("sections_autorisees", [])
            
            self.sections_container = ui.column().classes('w-full gap-2')
            
            for i, section in enumerate(sections):
                self._render_section_item(i, section)
            
            with ui.row().classes('mt-4 gap-2'):
                self.new_section_input = ui.input(placeholder='Nouvelle section...').classes('flex-grow')
                ui.button(
                    'Ajouter',
                    on_click=self._add_section,
                    icon='add'
                ).classes('bg-green-600 text-white')
    
    def _render_section_item(self, index: int, section: str):
        """Affiche un item de section."""
        with self.sections_container:
            with ui.card().classes('w-full p-3'):
                with ui.row().classes('items-center justify-between'):
                    with ui.row().classes('items-center gap-2'):
                        ui.icon('drag_indicator', size='sm').classes('text-gray-400 cursor-move')
                        ui.label(f'{index + 1}.').classes('font-semibold text-gray-500 w-8')
                        ui.label(section).classes('flex-grow')
                    
                    with ui.row().classes('gap-1'):
                        if index > 0:
                            ui.button(icon='arrow_upward', on_click=lambda i=index: self._move_section(i, -1)).props('flat size=sm')
                        if index < len(self.config.user_config.get("sections_autorisees", [])) - 1:
                            ui.button(icon='arrow_downward', on_click=lambda i=index: self._move_section(i, 1)).props('flat size=sm')
                        ui.button(icon='delete', on_click=lambda i=index: self._remove_section(i)).props('flat size=sm color=red')
    
    def _render_actions_section(self):
        """Section des actions."""
        with ui.card().classes('w-full p-6'):
            ui.label('Actions').classes('text-xl font-bold text-blue-900 mb-4')
            
            with ui.row().classes('gap-4'):
                ui.button(
                    'Exporter la configuration',
                    on_click=self._export_config,
                    icon='download'
                ).classes('bg-blue-600 text-white')
                
                ui.button(
                    'Réinitialiser',
                    on_click=self._reset_config,
                    icon='restart_alt'
                ).classes('bg-orange-600 text-white')
                
                ui.button(
                    'Nettoyer les fichiers temporaires',
                    on_click=self._cleanup_temp,
                    icon='cleaning_services'
                ).classes('bg-gray-600 text-white')
            
            ui.separator().classes('my-4')
            
            # Informations système
            ui.label('Informations système').classes('font-semibold text-gray-700 mb-2')
            
            with ui.grid(columns=2).classes('gap-2 text-sm'):
                ui.label('Version de l\'application:')
                ui.label('2.0.0').classes('font-mono')
                
                ui.label('Python:')
                import sys
                ui.label(sys.version.split()[0]).classes('font-mono')
                
                ui.label('NiceGUI:')
                try:
                    import nicegui
                    ui.label(nicegui.__version__).classes('font-mono')
                except:
                    ui.label('N/A').classes('font-mono')
    
    async def _save_defaults(self):
        """Sauvegarde les valeurs par défaut."""
        defaults = {key: inp.value for key, inp in self.default_inputs.items()}
        
        config = self.config.user_config
        config["defaults"] = defaults
        config["pdflatex_path"] = self.pdflatex_input.value
        
        self.config.save_user_config(config)
        ui.notify('Configuration sauvegardée', type='positive')
    
    async def _add_section(self):
        """Ajoute une nouvelle section."""
        new_section = self.new_section_input.value.strip()
        if not new_section:
            ui.notify('Veuillez entrer un nom de section', type='warning')
            return
        
        sections = self.config.user_config.get("sections_autorisees", [])
        sections.append(new_section)
        
        config = self.config.user_config
        config["sections_autorisees"] = sections
        self.config.save_user_config(config)
        
        self.new_section_input.set_value('')
        ui.notify(f'Section "{new_section}" ajoutée', type='positive')
        
        # Recharger la page
        ui.navigate.to('/parametres')
    
    async def _remove_section(self, index: int):
        """Supprime une section."""
        sections = self.config.user_config.get("sections_autorisees", [])
        if 0 <= index < len(sections):
            removed = sections.pop(index)
            
            config = self.config.user_config
            config["sections_autorisees"] = sections
            self.config.save_user_config(config)
            
            ui.notify(f'Section "{removed}" supprimée', type='positive')
            ui.navigate.to('/parametres')
    
    async def _move_section(self, index: int, direction: int):
        """Déplace une section vers le haut ou le bas."""
        sections = self.config.user_config.get("sections_autorisees", [])
        new_index = index + direction
        
        if 0 <= new_index < len(sections):
            sections[index], sections[new_index] = sections[new_index], sections[index]
            
            config = self.config.user_config
            config["sections_autorisees"] = sections
            self.config.save_user_config(config)
            
            ui.navigate.to('/parametres')
    
    async def _export_config(self):
        """Exporte la configuration en JSON."""
        config_json = json.dumps(self.config.user_config, indent=2, ensure_ascii=False)
        
        with ui.dialog() as dialog:
            with ui.card().classes('p-6 w-96'):
                ui.label('Configuration exportée').classes('text-lg font-bold')
                ui.codemirror(value=config_json, language='json').classes('w-full h-64')
                ui.button('Fermer', on_click=dialog.close)
        
        dialog.open()
    
    async def _reset_config(self):
        """Réinitialise la configuration."""
        with ui.dialog() as dialog:
            with ui.card().classes('p-6'):
                ui.label('Confirmer la réinitialisation').classes('text-lg font-bold text-orange-600')
                ui.label('Cela va réinitialiser tous les paramètres à leurs valeurs par défaut.')
                
                with ui.row().classes('mt-4 gap-2'):
                    ui.button('Annuler', on_click=dialog.close).props('flat')
                    
                    def reset():
                        default_config = self.config.get_default_user_config()
                        self.config.save_user_config(default_config)
                        dialog.close()
                        ui.notify('Configuration réinitialisée', type='positive')
                        ui.navigate.to('/parametres')
                    
                    ui.button('Réinitialiser', on_click=reset).classes('bg-orange-600 text-white')
        
        dialog.open()
    
    async def _cleanup_temp(self):
        """Nettoie les fichiers temporaires."""
        output_dir = self.config.OUTPUT_DIR
        extensions = ['.aux', '.log', '.out', '.toc', '.lof', '.lot', '.fls', '.fdb_latexmk']
        
        count = 0
        for ext in extensions:
            for file in output_dir.glob(f'*{ext}'):
                file.unlink()
                count += 1
        
        ui.notify(f'{count} fichiers temporaires supprimés', type='positive')


def render():
    """Point d'entrée pour le rendu de la page."""
    page = ParametresPage()
    page.render()
