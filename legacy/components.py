"""
Composants réutilisables pour l'interface NiceGUI.
"""

from nicegui import ui
from typing import Callable, List, Dict, Any
import json
from pathlib import Path


class DynamicOptionsManager:
    """Gestionnaire pour ajouter/supprimer dynamiquement des options."""
    
    def __init__(self, config_path: Path, section_key: str):
        self.config_path = config_path
        self.section_key = section_key
        self.options: List[str] = []
        self.load_options()
    
    def load_options(self):
        """Charge les options depuis le fichier de configuration."""
        if self.config_path.exists():
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    self.options = config.get("dynamic_options", {}).get(self.section_key, [])
            except Exception:
                self.options = []
        else:
            self.options = []
    
    def save_options(self):
        """Sauvegarde les options dans le fichier de configuration."""
        try:
            config = {}
            if self.config_path.exists():
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
            
            if "dynamic_options" not in config:
                config["dynamic_options"] = {}
            
            config["dynamic_options"][self.section_key] = self.options
            
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Erreur sauvegarde options: {e}")
    
    def add_option(self, option: str) -> bool:
        """Ajoute une option si elle n'existe pas déjà."""
        option = option.strip()
        if option and option not in self.options:
            self.options.append(option)
            self.save_options()
            return True
        return False
    
    def remove_option(self, option: str) -> bool:
        """Supprime une option."""
        if option in self.options:
            self.options.remove(option)
            self.save_options()
            return True
        return False
    
    def get_options(self) -> List[str]:
        """Retourne la liste des options."""
        return self.options.copy()


class EditableCheckboxList:
    """Widget pour afficher et modifier une liste de checkboxes avec option d'ajout."""
    
    def __init__(
        self,
        title: str,
        options: List[str],
        on_change: Callable = None,
        allow_add: bool = True,
        options_manager: DynamicOptionsManager = None
    ):
        self.title = title
        self.options = options
        self.on_change = on_change
        self.allow_add = allow_add
        self.options_manager = options_manager
        self.checkbox_widgets: Dict[str, Any] = {}
        self.current_selections: Dict[str, bool] = {}
    
    def render(self) -> Dict[str, bool]:
        """Rend le widget et retourne les sélections."""
        with ui.column().classes('gap-2'):
            ui.label(self.title).classes('font-semibold text-blue-700')
            
            # Checkboxes
            with ui.column().classes('gap-1 ml-2'):
                for option in self.options:
                    cb = ui.checkbox(
                        option,
                        value=False,
                        on_change=lambda e, opt=option: self._on_checkbox_change(opt, e.value)
                    ).classes('text-sm')
                    self.checkbox_widgets[option] = cb
                    self.current_selections[option] = False
            
            # Bouton pour ajouter option
            if self.allow_add and self.options_manager:
                with ui.row().classes('gap-2 mt-2'):
                    ui.button('+ Ajouter option', on_click=self._show_add_dialog).props('flat color=blue size=sm')
        
        return self.current_selections
    
    def _on_checkbox_change(self, option: str, value: bool):
        """Handler pour changement de checkbox."""
        self.current_selections[option] = value
        if self.on_change:
            self.on_change(self.current_selections)
    
    def _show_add_dialog(self):
        """Affiche un dialog pour ajouter une option."""
        with ui.dialog() as dialog, ui.card().classes('w-96'):
            ui.label('Ajouter une nouvelle option').classes('text-lg font-bold mb-4')
            
            input_field = ui.input(
                label='Nouvelle option',
                placeholder='Ex: Option 1'
            ).classes('w-full')
            
            with ui.row().classes('justify-end gap-2 mt-4'):
                ui.button('Annuler', on_click=dialog.close).props('flat')
                ui.button('Ajouter', on_click=lambda: self._add_and_close(dialog, input_field.value)).props('color=blue')
        
        dialog.open()
    
    def _add_and_close(self, dialog, new_option: str):
        """Ajoute l'option et ferme le dialog."""
        if self.options_manager and self.options_manager.add_option(new_option):
            # Recharger les options
            self.options = self.options_manager.get_options()
            # Ajouter la nouvelle checkbox
            new_cb = ui.checkbox(
                new_option,
                value=False,
                on_change=lambda e, opt=new_option: self._on_checkbox_change(opt, e.value)
            ).classes('text-sm')
            self.checkbox_widgets[new_option] = new_cb
            self.current_selections[new_option] = False
            
            ui.notify(f'Option "{new_option}" ajoutée', type='positive')
        else:
            ui.notify('Option déjà existante', type='warning')
        
        dialog.close()
    
    def get_selected(self) -> List[str]:
        """Retourne les options sélectionnées."""
        return [opt for opt, selected in self.current_selections.items() if selected]
    
    def set_selected(self, selected: List[str]):
        """Définit les options sélectionnées."""
        for option, cb in self.checkbox_widgets.items():
            is_selected = option in selected
            cb.set_value(is_selected)
            self.current_selections[option] = is_selected
