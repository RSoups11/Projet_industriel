"""
Widget tableau éditable pour Jinja2/NiceGUI.
"""

from nicegui import ui
from typing import List, Dict, Any, Callable
import json


class EditableTable:
    """Widget tableau éditable avec ajout/suppression de lignes et colonnes."""
    
    def __init__(
        self,
        title: str = "Tableau",
        initial_data: List[Dict[str, str]] = None,
        columns: List[str] = None,
        on_change: Callable = None,
        allow_add_row: bool = True,
        allow_delete_row: bool = True,
        allow_add_column: bool = False
    ):
        self.title = title
        self.on_change = on_change
        self.allow_add_row = allow_add_row
        self.allow_delete_row = allow_delete_row
        self.allow_add_column = allow_add_column
        
        # Initialiser colonnes
        self.columns = columns or ["Élément", "Description"]
        
        # Initialiser données
        self.data: List[Dict[str, str]] = initial_data or [
            {col: "" for col in self.columns} for _ in range(3)
        ]
        
        # Widgets d'input
        self.input_widgets: List[List[Any]] = []
        self.row_delete_buttons: List[Any] = []
    
    def render(self) -> Dict[str, Any]:
        """Rend le tableau éditable."""
        with ui.column().classes('gap-2'):
            ui.label(self.title).classes('font-semibold text-lg text-blue-700')
            
            # Container pour le tableau
            table_container = ui.column().classes('gap-2 p-2 bg-gray-50 rounded')
            
            with table_container:
                # Headers
                with ui.row().classes('gap-2'):
                    for col in self.columns:
                        ui.label(col).classes('font-bold flex-grow text-sm')
                    
                    if self.allow_delete_row:
                        ui.label('').classes('w-8')  # Espace pour boutons delete
                
                # Lignes
                self.input_widgets = []
                for row_idx, row_data in enumerate(self.data):
                    with ui.row().classes('gap-2'):
                        row_inputs = []
                        for col_idx, col in enumerate(self.columns):
                            input_field = ui.input(
                                value=row_data.get(col, ""),
                                on_change=lambda e, r=row_idx, c=col_idx: self._on_cell_change(r, c, e.value)
                            ).classes('flex-grow')
                            row_inputs.append(input_field)
                        
                        if self.allow_delete_row:
                            btn_del = ui.button(
                                '🗑️',
                                on_click=lambda r=row_idx: self._delete_row(r)
                            ).props('flat dense').classes('w-8')
                            self.row_delete_buttons.append(btn_del)
                        
                        self.input_widgets.append(row_inputs)
            
            # Boutons d'action
            with ui.row().classes('gap-2 mt-2'):
                if self.allow_add_row:
                    ui.button(
                        '+ Ajouter ligne',
                        on_click=self._add_row
                    ).props('flat color=blue size=sm')
                
                if self.allow_add_column:
                    ui.button(
                        '+ Ajouter colonne',
                        on_click=self._add_column
                    ).props('flat color=blue size=sm')
        
        return self.get_data()
    
    def _on_cell_change(self, row_idx: int, col_idx: int, value: str):
        """Handler pour changement de cellule."""
        if row_idx < len(self.data) and col_idx < len(self.columns):
            col = self.columns[col_idx]
            self.data[row_idx][col] = value
            if self.on_change:
                self.on_change(self.data)
    
    def _add_row(self):
        """Ajoute une ligne au tableau."""
        new_row = {col: "" for col in self.columns}
        self.data.append(new_row)
        
        # Ajouter input widgets
        with ui.row().classes('gap-2'):
            row_inputs = []
            for col_idx, col in enumerate(self.columns):
                input_field = ui.input(
                    value="",
                    on_change=lambda e, r=len(self.data)-1, c=col_idx: self._on_cell_change(r, c, e.value)
                ).classes('flex-grow')
                row_inputs.append(input_field)
            
            if self.allow_delete_row:
                btn_del = ui.button(
                    '🗑️',
                    on_click=lambda r=len(self.data)-1: self._delete_row(r)
                ).props('flat dense').classes('w-8')
                self.row_delete_buttons.append(btn_del)
            
            self.input_widgets.append(row_inputs)
        
        ui.notify('Ligne ajoutée', type='positive')
        if self.on_change:
            self.on_change(self.data)
    
    def _delete_row(self, row_idx: int):
        """Supprime une ligne du tableau."""
        if 0 <= row_idx < len(self.data):
            self.data.pop(row_idx)
            # Regénérer le tableau (limité - NiceGUI ne permet pas facile suppression)
            ui.notify('Ligne supprimée', type='positive')
            if self.on_change:
                self.on_change(self.data)
    
    def _add_column(self):
        """Ajoute une colonne au tableau."""
        with ui.dialog() as dialog, ui.card().classes('w-80'):
            ui.label('Ajouter une colonne').classes('text-lg font-bold mb-4')
            
            input_field = ui.input(
                label='Nom de la colonne',
                placeholder='Ex: Quantité'
            ).classes('w-full')
            
            with ui.row().classes('justify-end gap-2 mt-4'):
                ui.button('Annuler', on_click=dialog.close).props('flat')
                ui.button('Ajouter', on_click=lambda: self._add_column_and_close(dialog, input_field.value)).props('color=blue')
        
        dialog.open()
    
    def _add_column_and_close(self, dialog, col_name: str):
        """Ajoute la colonne et ferme le dialog."""
        col_name = col_name.strip()
        if col_name and col_name not in self.columns:
            self.columns.append(col_name)
            # Ajouter colonne vide à tous les rows
            for row in self.data:
                row[col_name] = ""
            ui.notify(f'Colonne "{col_name}" ajoutée', type='positive')
            if self.on_change:
                self.on_change(self.data)
        else:
            ui.notify('Colonne déjà existante', type='warning')
        
        dialog.close()
    
    def get_data(self) -> List[Dict[str, str]]:
        """Retourne les données du tableau."""
        return self.data.copy()
    
    def to_latex_tabular(self) -> str:
        """Convertit le tableau en LaTeX tabular."""
        if not self.data or not self.columns:
            return ""
        
        # Créer la structure tabular
        col_spec = '|' + '|'.join(['l'] * len(self.columns)) + '|'
        
        lines = [f"\\begin{{tabular}}{{{col_spec}}}"]
        lines.append("\\hline")
        
        # Headers
        header = " & ".join([f"\\textbf{{{col}}}" for col in self.columns]) + " \\\\"
        lines.append(header)
        lines.append("\\hline")
        
        # Rows
        for row in self.data:
            row_values = []
            for col in self.columns:
                value = row.get(col, "").strip()
                if value:
                    row_values.append(value)
                else:
                    row_values.append("")
            
            row_str = " & ".join(row_values) + " \\\\"
            lines.append(row_str)
        
        lines.append("\\hline")
        lines.append("\\end{tabular}")
        
        return "\n".join(lines)
    
    def set_data(self, data: List[Dict[str, str]]):
        """Définit les données du tableau."""
        self.data = data
        # Mettre à jour les inputs si disponibles
        for row_idx, row_data in enumerate(data):
            if row_idx < len(self.input_widgets):
                for col_idx, col in enumerate(self.columns):
                    if col_idx < len(self.input_widgets[row_idx]):
                        value = row_data.get(col, "")
                        self.input_widgets[row_idx][col_idx].set_value(value)
