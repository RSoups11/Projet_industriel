"""
Page de gestion de la Base de Données du mémoire.
Interface similaire à "Nouveau mémoire" mais avec sauvegarde permanente.
Les modifications faites ici s'appliqueront à tous les nouveaux mémoires.
"""

from nicegui import ui, events
from pathlib import Path
import pandas as pd
import json
import re
from datetime import datetime
from typing import Dict, List, Any, Optional

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.config import AppConfig, SECTION_ICONS
from app.core.csv_service import CSVService

# Couleurs LaTeX disponibles avec leur équivalent CSS
# SYNCHRONISÉ avec generation.py - Toutes ces couleurs sont définies dans template_v2.tex.j2
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
    # Mapper les anciennes couleurs vers les nouvelles
    mapping = {
        'red': 'ecoRouge',
        'red!70!black': 'ecoRouge',
        'orange': 'ecoOrange',
        'orange!80!black': 'ecoOrange',
        'purple': 'ecoViolet',
        'purple!70!black': 'ecoViolet',
        'gray': 'ecoBleu',
        'gray!70!black': 'ecoBleu',
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
    s = s.replace('Œ', 'OE').replace('œ', 'oe')
    return re.sub(r'[^a-zA-Z0-9]', '', s).upper()


class DatabasePage:
    """Page de gestion de la base de données avec sauvegarde permanente."""
    
    def __init__(self):
        self.config = AppConfig()
        self.csv_service = CSVService()
        self.df = None
        self.template_data = self._load_template_data()
        self.edit_widgets = {}  # Pour tracker les modifications
        self.sections_autorisees = self.config.user_config.get("sections_autorisees", [])
        self.has_unsaved_changes = False
    
    def _load_template_data(self) -> Dict[str, Any]:
        """Charge les données de templates depuis template_data.json."""
        template_data_path = self.config.BASE_DIR / "app" / "template_data.json"
        if template_data_path.exists():
            with open(template_data_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}
    
    def _save_template_data(self):
        """Sauvegarde template_data.json."""
        template_data_path = self.config.BASE_DIR / "app" / "template_data.json"
        with open(template_data_path, 'w', encoding='utf-8') as f:
            json.dump(self.template_data, f, ensure_ascii=False, indent=4)
    
    def render(self):
        """Rendu principal de la page."""
        with ui.column().classes('w-full min-h-screen'):
            # Barre d'info et sauvegarde
            with ui.row().classes('w-full bg-amber-50 p-4 items-center justify-between'):
                with ui.row().classes('items-center gap-2'):
                    ui.icon('edit_note', size='md').classes('text-amber-700')
                    ui.label('Mode Édition Base de Données').classes('text-lg font-bold text-amber-800')
                ui.label('Les modifications seront sauvegardées de façon permanente').classes('text-amber-700')
                
                with ui.row().classes('gap-2'):
                    ui.button('Recharger', on_click=self._reload_data, icon='refresh').props('flat')
                    self.save_btn = ui.button('Sauvegarder tout', on_click=self._save_all, icon='save').classes('bg-green-600 text-white')
            
            # Contenu principal
            with ui.row().classes('w-full flex-grow'):
                # Zone principale
                self.main_container = ui.column().classes('flex-grow p-4 gap-4')
        
        # Stocker pour rebuild
        self.sections_container = None
        
        # Charger les données
        ui.timer(0.3, self._load_data, once=True)
    
    async def _load_data(self):
        """Charge les données du CSV."""
        csv_path = self.config.DATA_DIR / "bd_interface.csv"
        
        if not csv_path.exists():
            csv_path = self.config.DEFAULT_CSV_FILE
        
        if not csv_path.exists():
            with self.main_container:
                ui.label('Fichier CSV introuvable').classes('text-red-600')
            return
        
        try:
            for encoding in ['utf-8', 'latin-1', 'iso-8859-1', 'cp1252']:
                try:
                    self.df = pd.read_csv(csv_path, sep=";", dtype=str, encoding=encoding, on_bad_lines='skip')
                    break
                except UnicodeDecodeError:
                    continue
            
            if self.df is None:
                raise ValueError("Impossible de lire le fichier")
            
            self.df = self.df.fillna("")
            self.df.columns = self.df.columns.str.strip().str.lower()
            
            # Normaliser les sections
            self.df['section_norm'] = self.df['section'].apply(normaliser_titre)
            
            await self._build_sections()
            
        except Exception as ex:
            ui.notify(f'Erreur de chargement: {str(ex)}', type='negative')
    
    async def _reload_data(self):
        """Recharge les données (perd les modifications non sauvegardées)."""
        self.main_container.clear()
        self.edit_widgets = {}
        self.template_data = self._load_template_data()
        await self._load_data()
        ui.notify('Données rechargées', type='info')
    
    async def _build_sections(self):
        """Construit les sections comme dans Nouveau mémoire."""
        self.main_container.clear()
        
        with self.main_container:
            with ui.row().classes('w-full justify-between items-center mb-4'):
                with ui.column():
                    ui.label('Sections du mémoire').classes('text-xl font-bold text-blue-900 mb-2')
                    ui.label('Cliquez sur une section pour modifier ses données par défaut.').classes('text-gray-600')
                ui.button('+ Ajouter section', on_click=self._show_add_section_dialog, icon='add').props('color=blue')
            
            # Container pour les sections (pour rebuild)
            self.sections_container = ui.column().classes('w-full gap-4')
            
            self._build_all_sections()
    
    def _build_all_sections(self):
        """Construit toutes les sections."""
        if self.sections_container:
            self.sections_container.clear()
        
        with self.sections_container:
            # ===== SECTION SPÉCIALE : Configuration globale (Préambule uniquement) =====
            with ui.expansion('📝 Configuration globale', icon='settings').classes('w-full bg-yellow-50 shadow rounded-lg border-l-4 border-yellow-500'):
                with ui.column().classes('w-full gap-4 p-2'):
                    # Préambule
                    self._build_preambule_editor()
            
            for titre_officiel in self.sections_autorisees:
                titre_norm = normaliser_titre(titre_officiel)
                rows = self.df[self.df['section_norm'] == titre_norm]
                
                icon = SECTION_ICONS.get(titre_officiel, 'folder')
                titre_upper = titre_officiel.upper()
                
                # Déterminer le type de section
                # Sections avec tableaux spéciaux
                if 'LISTE DES MATERIAUX' in titre_upper or 'MATERIAUX' in titre_upper:
                    with ui.expansion(titre_officiel, icon='inventory').classes('w-full bg-white shadow rounded-lg'):
                        self._build_liste_materiaux_editor(titre_officiel, rows)
                
                # Sections avec config globale (template_data) - mais sous-sections CSV
                elif 'QSE' in titre_upper or 'HYGIENE' in titre_upper or 'HQE' in titre_upper:
                    with ui.expansion(titre_officiel, icon='eco').classes('w-full bg-white shadow rounded-lg'):
                        self._build_qse_editor()
                
                elif 'SITUATION ADMINISTRATIVE' in titre_upper:
                    with ui.expansion(titre_officiel, icon='business').classes('w-full bg-white shadow rounded-lg'):
                        self._build_situation_admin_editor()
                
                # Section METHODOLOGIE avec Transport/Levage spécial
                elif 'METHODOLOGIE' in titre_upper or 'MÉTHODOLOGIE' in titre_upper:
                    with ui.expansion(titre_officiel, icon='timeline').classes('w-full bg-white shadow rounded-lg'):
                        with ui.column().classes('w-full gap-4'):
                            # Éditeur Transport/Levage (template_data)
                            self._build_transport_levage_editor()
                            
                            # Autres sous-sections du CSV (filtrer transport et levage)
                            ui.label('Autres sous-sections').classes('text-lg font-bold text-blue-900 mt-4 mb-2 border-b-2 border-blue-200 pb-2')
                            def filter_methodologie(ss):
                                ss_lower = ss.lower()
                                return not ('transport' in ss_lower and 'levage' in ss_lower)
                            self._build_csv_section_editor_filtered(titre_officiel, rows, filter_methodologie)
                
                # Section MOYENS HUMAINS avec équipe + sécurité/santé
                elif 'MOYENS HUMAINS' in titre_upper:
                    with ui.expansion(titre_officiel, icon='people').classes('w-full bg-white shadow rounded-lg'):
                        self._build_moyens_humains_editor(titre_officiel, rows)
                
                # Section MOYENS MATERIEL
                elif 'MOYENS MATERIEL' in titre_upper:
                    with ui.expansion(titre_officiel, icon='build').classes('w-full bg-white shadow rounded-lg'):
                        self._build_moyens_materiel_editor(titre_officiel, rows)
                
                # Section CONTEXTE DU PROJET
                elif 'CONTEXTE' in titre_upper and 'PROJET' in titre_upper:
                    with ui.expansion(titre_officiel, icon='location_on').classes('w-full bg-white shadow rounded-lg'):
                        self._build_contexte_projet_editor(titre_officiel, rows)
                
                # Section CHANTIERS REFERENCES - Gestion spéciale des nouvelles sous-sections
                elif 'CHANTIER' in titre_upper and 'REFERENCE' in titre_upper:
                    with ui.expansion(titre_officiel, icon='work').classes('w-full bg-white shadow rounded-lg'):
                        self._build_chantiers_references_editor(titre_officiel, rows)
                
                # Section PLANNING
                elif 'PLANNING' in titre_upper:
                    with ui.expansion(titre_officiel, icon='schedule').classes('w-full bg-white shadow rounded-lg'):
                        self._build_planning_editor(titre_officiel, rows)
                
                else:
                    # TOUTES les autres sections : éditeur CSV standard avec réordonnancement
                    with ui.expansion(titre_officiel, icon=icon).classes('w-full bg-white shadow rounded-lg'):
                        self._build_csv_section_editor(titre_officiel, rows)
    
    def _build_csv_section_editor(self, titre: str, rows: pd.DataFrame):
        """Éditeur pour sections basées sur le CSV avec réordonnancement."""
        # Convertir les rows en liste pour pouvoir les réordonner
        section_key = f'section_order_{normaliser_titre(titre)}'
        
        # Initialiser la liste ordonnée des sous-sections
        if section_key not in self.edit_widgets:
            items = []
            for idx, row in rows.iterrows():
                sous_section = nettoyer_str(row.get('sous-section', ''))
                texte = nettoyer_str(row.get('texte', ''))
                image = nettoyer_str(row.get('image', ''))
                couleur = nettoyer_str(row.get('couleur', 'ecoBleu')) or 'ecoBleu'
                
                if not sous_section and not texte:
                    continue
                
                items.append({
                    'idx': idx,
                    'sous_section': sous_section,
                    'texte': texte,
                    'image': image,
                    'couleur': couleur,
                    'section': titre
                })
            
            self.edit_widgets[section_key] = {
                'type': 'ordered_section',
                'items': items,
                'section': titre
            }
        
        section_data = self.edit_widgets[section_key]
        items = section_data['items']
        
        # Container principal
        main_container = ui.column().classes('w-full gap-3 p-2')
        
        def rebuild_section():
            """Reconstruit l'affichage de la section."""
            main_container.clear()
            with main_container:
                for i, item in enumerate(items):
                    self._build_subsection_card(items, i, rebuild_section, titre)
                
                # Bouton ajouter
                def add_new():
                    new_item = {
                        'idx': -1,  # Nouveau
                        'sous_section': 'Nouvelle sous-section',
                        'texte': '',
                        'image': '',
                        'section': titre,
                        'is_new': True
                    }
                    items.append(new_item)
                    self._mark_changed()
                    rebuild_section()
                    ui.notify('Sous-section ajoutée', type='positive')
                
                ui.button('+ Ajouter une sous-section', on_click=add_new, icon='add').props('outline color=blue')
        
        rebuild_section()
    
    def _build_subsection_card(self, items: list, index: int, rebuild_fn, section_title: str):
        """Construit une carte de sous-section avec contrôles de réordonnancement."""
        item = items[index]
        
        # Valider et corriger la couleur (convertit 'red' -> 'ecoRouge', etc.)
        item['couleur'] = valider_couleur(item.get('couleur', 'ecoBleu'))
        
        couleur_css = LATEX_COLORS.get(item['couleur'], LATEX_COLORS['ecoBleu'])['css']
        
        with ui.card().classes('w-full p-4').style(f'border-left: 4px solid {couleur_css};'):
            # Barre de contrôle en haut
            with ui.row().classes('w-full justify-between items-center mb-3'):
                with ui.row().classes('items-center gap-1'):
                    ui.label(f'#{index + 1}').classes('text-xs text-gray-400 font-mono')
                    
                    # Boutons de déplacement
                    def move_up(idx=index):
                        if idx > 0:
                            items[idx], items[idx-1] = items[idx-1], items[idx]
                            self._mark_changed()
                            rebuild_fn()
                    
                    def move_down(idx=index):
                        if idx < len(items) - 1:
                            items[idx], items[idx+1] = items[idx+1], items[idx]
                            self._mark_changed()
                            rebuild_fn()
                    
                    ui.button(icon='arrow_upward', on_click=move_up).props('flat dense size=sm').classes('text-gray-500').tooltip('Monter')
                    ui.button(icon='arrow_downward', on_click=move_down).props('flat dense size=sm').classes('text-gray-500').tooltip('Descendre')
                
                # Bouton supprimer
                def delete_item(idx=index):
                    if len(items) > 0:
                        items.pop(idx)
                        self._mark_changed()
                        rebuild_fn()
                        # Note: ui.notify removed here to avoid slot deletion error
                
                ui.button(icon='delete', on_click=delete_item).props('flat dense size=sm color=red').tooltip('Supprimer')
                
                # Sélecteur de couleur
                color_options = {k: f"{v['nom']}" for k, v in LATEX_COLORS.items()}
                def update_color(e, it=item):
                    it['couleur'] = e.value
                    self._mark_changed()
                    rebuild_fn()
                
                with ui.row().classes('items-center gap-1 ml-2'):
                    ui.icon('palette', size='xs').classes('text-gray-400')
                    ui.select(
                        options=color_options,
                        value=item.get('couleur', 'ecoBleu'),
                        on_change=update_color
                    ).props('dense outlined').classes('w-28').style(f'background-color: {couleur_css}20;')
            
            # Titre de la sous-section
            ui.label('Titre:').classes('text-xs text-gray-500')
            def update_ss(e, it=item):
                it['sous_section'] = e.value
                self._mark_changed()
            ss_input = ui.input(value=item['sous_section'], on_change=update_ss).classes('w-full mb-2')
            
            # Contenu
            ui.label('Contenu:').classes('text-xs text-gray-500')
            if "/// ou ///" in item.get('texte', ''):
                ui.label('Options séparées par "/// ou ///"').classes('text-xs text-orange-500')
            
            texte = item.get('texte', '')
            rows_count = max(3, min(10, len(texte) // 50 + 1))
            def update_texte(e, it=item):
                it['texte'] = e.value
                self._mark_changed()
            texte_input = ui.textarea(value=texte, on_change=update_texte).classes('w-full').props(f'rows={rows_count} outlined')
            
            # Image
            with ui.row().classes('items-center gap-2 mt-2'):
                ui.label('Image:').classes('text-xs text-gray-500')
                def update_img(e, it=item):
                    it['image'] = e.value
                    self._mark_changed()
                image_input = ui.input(value=item.get('image', ''), placeholder='Chemin image (optionnel)', on_change=update_img).classes('flex-grow')
    
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
                        # Ajouter à la liste locale
                        self.sections_autorisees.append(new_section)
                        
                        # Sauvegarder dans la config
                        self.config.user_config["sections_autorisees"] = self.sections_autorisees
                        self.config.save_user_config(self.config.user_config)
                        
                        # Ajouter une ligne dans le CSV pour la nouvelle section
                        new_row = pd.DataFrame([{
                            'section': new_section,
                            'sous-section': 'Nouvelle sous-section',
                            'texte': '',
                            'image': '',
                            'section_norm': normaliser_titre(new_section)
                        }])
                        self.df = pd.concat([self.df, new_row], ignore_index=True)
                        
                        # Rebuild les sections
                        self._build_all_sections()
                        self._mark_changed()
                        
                        ui.notify(f'Section "{new_section}" ajoutée', type='positive')
                        dialog.close()
                    else:
                        ui.notify('Section déjà existante ou nom invalide', type='warning')
                
                ui.button('Ajouter', on_click=add_section).props('color=blue')
        
        dialog.open()
    
    def _build_csv_section_editor_filtered(self, titre: str, rows: pd.DataFrame, filter_fn=None):
        """Éditeur pour sections CSV avec réordonnancement et filtre optionnel."""
        section_key = f'section_order_{normaliser_titre(titre)}'
        
        # Initialiser la liste ordonnée des sous-sections
        if section_key not in self.edit_widgets:
            items = []
            for idx, row in rows.iterrows():
                sous_section = nettoyer_str(row.get('sous-section', ''))
                texte = nettoyer_str(row.get('texte', ''))
                image = nettoyer_str(row.get('image', ''))
                couleur = nettoyer_str(row.get('couleur', 'ecoBleu')) or 'ecoBleu'
                
                if not sous_section and not texte:
                    continue
                
                # Appliquer le filtre si fourni
                if filter_fn and not filter_fn(sous_section):
                    continue
                
                items.append({
                    'idx': idx,
                    'sous_section': sous_section,
                    'texte': texte,
                    'image': image,
                    'couleur': couleur,
                    'section': titre
                })
            
            self.edit_widgets[section_key] = {
                'type': 'ordered_section',
                'items': items,
                'section': titre
            }
        
        section_data = self.edit_widgets[section_key]
        items = section_data['items']
        
        # Container principal
        main_container = ui.column().classes('w-full gap-3')
        
        def rebuild_section():
            """Reconstruit l'affichage de la section."""
            main_container.clear()
            with main_container:
                for i, item in enumerate(items):
                    self._build_subsection_card(items, i, rebuild_section, titre)
                
                # Bouton ajouter
                def add_new():
                    new_item = {
                        'idx': -1,
                        'sous_section': 'Nouvelle sous-section',
                        'texte': '',
                        'image': '',
                        'section': titre,
                        'is_new': True
                    }
                    items.append(new_item)
                    self._mark_changed()
                    rebuild_section()
                    ui.notify('Sous-section ajoutée', type='positive')
                
                ui.button('+ Ajouter une sous-section', on_click=add_new, icon='add').props('outline color=blue')
        
        rebuild_section()
    
    def _build_preambule_editor(self):
        """Éditeur pour le préambule du mémoire."""
        data = self.template_data.get('preambule', {})
        
        with ui.card().classes('w-full p-4 border-l-4 border-yellow-500'):
            ui.label('📜 Préambule du mémoire').classes('font-bold text-yellow-700 mb-2 text-lg')
            ui.label('Ce texte apparaît au début de chaque mémoire technique').classes('text-xs text-gray-500 mb-2')
            
            preambule_text = data.get('texte', '')
            preambule_input = ui.textarea(value=preambule_text, placeholder='Texte du préambule...').classes('w-full').props('rows=8 outlined')
            preambule_input.on('change', lambda: self._mark_changed())
            self.edit_widgets['preambule_texte'] = preambule_input
    
    def _build_securite_sante_cards_editor(self):
        """Éditeur pour Sécurité/Santé avec cartes réordonnables (comme dans Nouveau mémoire)."""
        data_ss = self.template_data.get('securite_sante', {})
        
        ui.label('Réordonnez les cadres avec les flèches, personnalisez titres et couleurs').classes('text-xs text-gray-500 mb-2')
        
        # Initialiser la liste ordonnée des cadres sécurité/santé
        ss_order_key = '_securite_order_'
        if ss_order_key not in self.edit_widgets:
            # Récupérer les couleurs et noms existants ou définir par défaut
            couleurs = data_ss.get('couleurs', {})
            noms = data_ss.get('noms', {})
            
            self.edit_widgets[ss_order_key] = [
                {'key': 'organisation_production', 'nom': noms.get('organisation_production', 'Organisation de production'), 'type': 'text', 
                 'contenu': data_ss.get('organisation_production', ''), 'couleur': couleurs.get('organisation_production', 'ecoBleu')},
                {'key': 'confort_travail', 'nom': noms.get('confort_travail', 'Confort de travail'), 'type': 'text',
                 'contenu': data_ss.get('confort_travail', ''), 'couleur': couleurs.get('confort_travail', 'ecoVert')},
                {'key': 'accueil_nouveaux', 'nom': noms.get('accueil_nouveaux', 'Accueil des nouveaux salariés'), 'type': 'text',
                 'contenu': data_ss.get('accueil_nouveaux', ''), 'couleur': couleurs.get('accueil_nouveaux', 'ecoOrange')},
                {'key': 'securite_generale', 'nom': noms.get('securite_generale', 'Sécurité et santé sur les chantiers'), 'type': 'text',
                 'contenu': data_ss.get('securite_generale', ''), 'couleur': couleurs.get('securite_generale', 'ecoRouge')},
                {'key': 'concretement', 'nom': noms.get('concretement', 'Concrètement'), 'type': 'list',
                 'contenu': data_ss.get('concretement', []), 'couleur': couleurs.get('concretement', 'ecoMarron')},
                {'key': 'habilitations', 'nom': noms.get('habilitations', 'Habilitations'), 'type': 'list',
                 'contenu': data_ss.get('habilitations', []), 'couleur': couleurs.get('habilitations', 'ecoViolet')},
                {'key': 'controle_annuel', 'nom': noms.get('controle_annuel', 'Contrôle annuel'), 'type': 'text',
                 'contenu': data_ss.get('controle_annuel', ''), 'couleur': couleurs.get('controle_annuel', 'ecoJaune')},
            ]
        
        ss_items = self.edit_widgets[ss_order_key]
        ss_container = ui.column().classes('w-full gap-3')
        
        def rebuild_ss():
            """Reconstruit l'affichage des cadres sécurité/santé."""
            ss_container.clear()
            with ss_container:
                for i in range(len(ss_items)):
                    self._build_securite_sante_card(ss_items, i, rebuild_ss)
        
        # Appel initial direct (pas dans le contexte)
        rebuild_ss()
    
    def _build_situation_admin_editor(self):
        """Éditeur pour Situation Administrative (template_data)."""
        data = self.template_data.get('situation_administrative', {})
        
        with ui.column().classes('w-full gap-4 p-2'):
            # Qualifications
            with ui.card().classes('w-full p-4'):
                ui.label('Qualifications RGE QUALIBAT').classes('font-bold text-blue-700 mb-2')
                qualifs = data.get('qualifications', [])
                qualifs_text = '\n'.join(qualifs) if qualifs else ''
                qualifs_input = ui.textarea(value=qualifs_text, placeholder='Une qualification par ligne').classes('w-full').props('rows=5 outlined')
                qualifs_input.on('change', lambda: self._mark_changed())
                self.edit_widgets['situation_admin_qualifications'] = qualifs_input
            
            # Effectif
            with ui.card().classes('w-full p-4'):
                ui.label('Effectif').classes('font-bold text-blue-700 mb-2')
                with ui.row().classes('gap-4'):
                    date_input = ui.input(value=data.get('effectif_date', ''), label='Date').classes('w-40')
                    nombre_input = ui.input(value=data.get('effectif_nombre', ''), label='Nombre de salariés').classes('w-40')
                date_input.on('change', lambda: self._mark_changed())
                nombre_input.on('change', lambda: self._mark_changed())
                self.edit_widgets['situation_admin_effectif_date'] = date_input
                self.edit_widgets['situation_admin_effectif_nombre'] = nombre_input
            
            # Chiffre d'affaires
            with ui.card().classes('w-full p-4'):
                ui.label('Chiffre d\'affaires').classes('font-bold text-blue-700 mb-2')
                ca_list = data.get('chiffre_affaires', [])
                for i, ca in enumerate(ca_list):
                    with ui.row().classes('gap-2 items-center'):
                        annee_input = ui.input(value=ca.get('annee', ''), label='Année').classes('w-24')
                        montant_input = ui.input(value=ca.get('montant', ''), label='Montant').classes('w-40')
                        annee_input.on('change', lambda: self._mark_changed())
                        montant_input.on('change', lambda: self._mark_changed())
                        self.edit_widgets[f'situation_admin_ca_{i}_annee'] = annee_input
                        self.edit_widgets[f'situation_admin_ca_{i}_montant'] = montant_input
    
    def _build_securite_sante_editor(self):
        """Éditeur pour Sécurité et Santé (template_data)."""
        data = self.template_data.get('securite_sante', {})
        
        with ui.column().classes('w-full gap-4 p-2'):
            fields = [
                ('organisation_production', 'Organisation de production'),
                ('confort_travail', 'Confort de travail'),
                ('accueil_nouveaux', 'Accueil des nouveaux salariés'),
                ('securite_generale', 'Sécurité générale'),
                ('controle_annuel', 'Contrôle annuel'),
            ]
            
            for key, label in fields:
                with ui.card().classes('w-full p-4'):
                    ui.label(label).classes('font-bold text-blue-700 mb-2')
                    value = data.get(key, '')
                    input_widget = ui.textarea(value=value).classes('w-full').props('rows=4 outlined')
                    input_widget.on('change', lambda: self._mark_changed())
                    self.edit_widgets[f'securite_sante_{key}'] = input_widget
            
            # Habilitations (liste)
            with ui.card().classes('w-full p-4'):
                ui.label('Habilitations').classes('font-bold text-blue-700 mb-2')
                habs = data.get('habilitations', [])
                habs_text = '\n'.join(habs) if habs else ''
                habs_input = ui.textarea(value=habs_text, placeholder='Une habilitation par ligne').classes('w-full').props('rows=5 outlined')
                habs_input.on('change', lambda: self._mark_changed())
                self.edit_widgets['securite_sante_habilitations'] = habs_input
            
            # Concrètement (liste)
            with ui.card().classes('w-full p-4'):
                ui.label('Concrètement').classes('font-bold text-blue-700 mb-2')
                concr = data.get('concretement', [])
                concr_text = '\n'.join(concr) if concr else ''
                concr_input = ui.textarea(value=concr_text, placeholder='Un élément par ligne').classes('w-full').props('rows=6 outlined')
                concr_input.on('change', lambda: self._mark_changed())
                self.edit_widgets['securite_sante_concretement'] = concr_input
    
    def _build_moyens_materiel_editor(self, titre: str, rows: pd.DataFrame):
        """Éditeur pour Moyens Matériel (template_data) avec sous-sections réordonnables."""
        data = self.template_data.get('moyens_materiel', {})
        
        with ui.column().classes('w-full gap-4 p-2'):
            # ===== DONNÉES TEMPLATE =====
            ui.label('Configuration par défaut').classes('text-lg font-bold text-blue-900 mb-2 border-b-2 border-blue-200 pb-2')
            
            # Introduction
            with ui.card().classes('w-full p-4'):
                ui.label('Texte d\'introduction').classes('font-bold text-blue-700 mb-2')
                intro = data.get('intro', '')
                intro_input = ui.textarea(value=intro).classes('w-full').props('rows=3 outlined')
                intro_input.on('change', lambda: self._mark_changed())
                self.edit_widgets['moyens_materiel_intro'] = intro_input
            
            # Listes d'équipements
            lists = [
                ('conception', 'Conception et Précision'),
                ('securite', 'Sécurité'),
                ('atelier', 'Atelier de taille'),
                ('levage', 'Levage et montage'),
                ('transport', 'Transport'),
                ('machine_portative', 'Machines portatives'),
                ('protection_nettoyage', 'Protection et nettoyage'),
                ('gestion_dechet', 'Gestion des déchets'),
            ]
            
            for key, label in lists:
                with ui.card().classes('w-full p-4'):
                    ui.label(label).classes('font-bold text-blue-700 mb-2')
                    items = data.get(key, [])
                    items_text = '\n'.join(items) if items else ''
                    input_widget = ui.textarea(value=items_text, placeholder='Un élément par ligne').classes('w-full').props('rows=4 outlined')
                    input_widget.on('change', lambda: self._mark_changed())
                    self.edit_widgets[f'moyens_materiel_{key}'] = input_widget
            
            # ===== SOUS-SECTIONS CSV RÉORDONNABLES =====
            ui.label('Sous-sections personnalisées').classes('text-lg font-bold text-blue-900 mt-4 mb-2 border-b-2 border-blue-200 pb-2')
            self._build_csv_section_editor_filtered(titre, rows)
    
    def _build_liste_materiaux_editor(self, titre: str, rows: pd.DataFrame):
        """Éditeur pour Liste des Matériaux avec tableaux et sous-sections réordonnables."""
        with ui.column().classes('w-full gap-4 p-2'):
            # ===== TABLEAUX SPÉCIAUX =====
            ui.label('Tableaux de données').classes('text-lg font-bold text-blue-900 mb-2 border-b-2 border-blue-200 pb-2')
            
            # Tableau Fixation et Assemblage
            self._build_table_editor(
                'table_fixation_assemblage',
                'Fixation et Assemblage',
                'Tableau des éléments de fixation (sauvegarde permanente)',
                'Fixation et assemblage',
                titre
            )
            
            # Tableau Traitement Préventif
            self._build_table_editor(
                'table_traitement_preventif',
                'Traitement Préventif des Bois',
                'Produits de traitement préventif',
                'Traitement préventif',
                titre
            )
            
            # Tableau Traitement Curatif
            self._build_table_editor(
                'table_traitement_curatif',
                'Traitement Curatif des Bois',
                'Produits de traitement curatif',
                'Traitement curatif',
                titre
            )
            
            # ===== SOUS-SECTIONS RÉORDONNABLES =====
            ui.label('Sous-sections').classes('text-lg font-bold text-blue-900 mt-4 mb-2 border-b-2 border-blue-200 pb-2')
            
            # Filtrer les sous-sections (exclure fixation/traitement qui sont en tableaux)
            def should_include(ss):
                ss_lower = ss.lower()
                return not (('fixation' in ss_lower and 'assemblage' in ss_lower) or 
                           ('traitement' in ss_lower and ('préventif' in ss_lower or 'preventif' in ss_lower or 'curatif' in ss_lower)))
            
            self._build_csv_section_editor_filtered(titre, rows, should_include)
    
    def _build_table_editor(self, table_key: str, title: str, subtitle: str, csv_subsection: str = '', section_name: str = ''):
        """Construit un éditeur de tableau générique avec sélecteur de couleur."""
        import copy
        
        with ui.card().classes('w-full p-4'):
            with ui.row().classes('w-full items-center gap-4 mb-2'):
                ui.label(title).classes('font-bold text-blue-700 flex-1')
                
                # Sélecteur de couleur pour ce tableau
                if csv_subsection and section_name:
                    # Trouver la couleur actuelle dans le CSV
                    section_norm = normaliser_titre(section_name)
                    mask = (self.df['section_norm'] == section_norm) & (self.df['sous-section'].str.lower() == csv_subsection.lower())
                    matching_rows = self.df[mask]
                    current_color = 'ecoVert'  # défaut
                    if not matching_rows.empty:
                        current_color = matching_rows.iloc[0].get('couleur', 'ecoVert') or 'ecoVert'
                    
                    color_options = ['ecoBleu', 'ecoVert', 'ecoRouge', 'ecoOrange', 'ecoViolet', 'ecoMarron', 'ecoGris', 'ecoJaune']
                    
                    def make_color_handler(subsec, sec_norm):
                        def on_color_change(e):
                            mask = (self.df['section_norm'] == sec_norm) & (self.df['sous-section'].str.lower() == subsec.lower())
                            if self.df[mask].any().any():
                                self.df.loc[mask, 'couleur'] = e.value
                            self._mark_changed()
                            ui.notify(f'Couleur {subsec} changée en {e.value}', type='info')
                        return on_color_change
                    
                    ui.label('Couleur:').classes('text-sm text-gray-600')
                    ui.select(
                        options=color_options,
                        value=current_color,
                        on_change=make_color_handler(csv_subsection, section_norm)
                    ).classes('w-32').props('dense outlined')
            
            ui.label(subtitle).classes('text-sm text-gray-600 mb-3')
            
            # Récupérer données existantes ou défaut
            table_data = self.template_data.get(table_key, [])
            if not table_data:
                table_data = []
            
            # Stocker une copie profonde pour édition (important pour ne pas modifier l'original)
            if table_key not in self.edit_widgets:
                self.edit_widgets[table_key] = {'type': 'table', 'data': copy.deepcopy(table_data)}
            
            local_data = self.edit_widgets[table_key]['data']
            
            # Headers
            with ui.row().classes('w-full gap-2 bg-gray-100 p-2 rounded font-bold text-xs'):
                ui.label('Nature des éléments').classes('flex-1')
                ui.label('Marque, type, performance').classes('flex-1')
                ui.label('Provenance').classes('w-28')
                ui.label('Doc').classes('w-14')
                ui.label('').classes('w-8')
            
            # Container pour les lignes
            rows_container = ui.column().classes('w-full gap-1')
            
            def rebuild_table(container, data_list):
                """Reconstruit le tableau."""
                container.clear()
                with container:
                    for idx, row_data in enumerate(data_list):
                        create_row(idx, row_data, container, data_list)
            
            def create_row(row_idx, row_data, container, data_list):
                """Crée une ligne du tableau."""
                # Stocker l'index et la liste comme attributs pour les callbacks
                def make_handler(field, idx, dl):
                    def handler(e):
                        dl[idx][field] = e.value
                        self._mark_changed()
                    return handler
                
                with ui.row().classes('w-full gap-2 items-center'):
                    ui.input(
                        value=row_data.get('nature', ''),
                        on_change=make_handler('nature', row_idx, data_list)
                    ).classes('flex-1').props('dense')
                    
                    ui.input(
                        value=row_data.get('marque', ''),
                        on_change=make_handler('marque', row_idx, data_list)
                    ).classes('flex-1').props('dense')
                    
                    ui.input(
                        value=row_data.get('provenance', ''),
                        on_change=make_handler('provenance', row_idx, data_list)
                    ).classes('w-28').props('dense')
                    
                    ui.select(
                        ['OUI', 'NON'],
                        value=row_data.get('doc', 'OUI'),
                        on_change=make_handler('doc', row_idx, data_list)
                    ).classes('w-14').props('dense')
                    
                    # Bouton supprimer
                    def delete_row(i=row_idx, cont=container, dl=data_list):
                        if len(dl) > 1:
                            dl.pop(i)
                            rebuild_table(cont, dl)
                            self._mark_changed()
                            ui.notify('Ligne supprimée', type='info')
                        else:
                            ui.notify('Impossible de supprimer la dernière ligne', type='warning')
                    
                    ui.button(icon='delete', on_click=delete_row).props('flat dense color=red size=sm').classes('w-8')
            
            # Construire le tableau initial
            with rows_container:
                for idx, row_data in enumerate(local_data):
                    create_row(idx, row_data, rows_container, local_data)
            
            # Bouton ajouter
            def add_row(cont=rows_container, dl=local_data):
                new_row = {"nature": "", "marque": "", "provenance": "", "doc": "OUI"}
                dl.append(new_row)
                rebuild_table(cont, dl)
                self._mark_changed()
                ui.notify('Ligne ajoutée', type='positive')
            
            ui.button('+ Ajouter une ligne', on_click=add_row).props('flat color=blue size=sm').classes('mt-2')
    
    def _build_qse_editor(self):
        """Éditeur pour QSE/HQE (template_data)."""
        with ui.column().classes('w-full gap-4 p-2'):
            # Démarche HQE
            data_hqe = self.template_data.get('demarche_hqe', {})
            with ui.card().classes('w-full p-4'):
                ui.label('Démarche HQE - Introduction').classes('font-bold text-green-700 mb-2')
                intro = data_hqe.get('intro', '')
                intro_input = ui.textarea(value=intro).classes('w-full').props('rows=4 outlined')
                intro_input.on('change', lambda: self._mark_changed())
                self.edit_widgets['demarche_hqe_intro'] = intro_input
            
            # Note: Éco-construction a une structure complexe (cible_02, cible_03, etc.) 
            # et doit être modifié via "Nouveau mémoire"
            with ui.card().classes('w-full p-4 bg-gray-50'):
                ui.label('Éco-construction').classes('font-bold text-gray-500 mb-2')
                ui.label('⚠️ Cette section a une structure complexe. Modifiez-la dans "Nouveau mémoire".').classes('text-sm text-gray-500 italic')
            
            # Démarche env atelier
            data_atelier = self.template_data.get('demarche_env_atelier', {})
            with ui.card().classes('w-full p-4'):
                ui.label('Démarche environnementale Atelier - Introduction').classes('font-bold text-green-700 mb-2')
                intro_at = data_atelier.get('intro', '')
                intro_at_input = ui.textarea(value=intro_at).classes('w-full').props('rows=4 outlined')
                intro_at_input.on('change', lambda: self._mark_changed())
                self.edit_widgets['demarche_env_atelier_intro'] = intro_at_input
            
            # Démarche env chantiers
            data_chantiers = self.template_data.get('demarche_env_chantiers', {})
            with ui.card().classes('w-full p-4'):
                ui.label('Démarche environnementale Chantiers - Introduction').classes('font-bold text-green-700 mb-2')
                intro_ch = data_chantiers.get('intro', '')
                intro_ch_input = ui.textarea(value=intro_ch).classes('w-full').props('rows=4 outlined')
                intro_ch_input.on('change', lambda: self._mark_changed())
                self.edit_widgets['demarche_env_chantiers_intro'] = intro_ch_input
    
    def _build_securite_sante_card(self, items: list, index: int, rebuild_fn):
        """Construit une carte de sécurité/santé avec contrôles de réordonnancement et couleur."""
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
                            self._mark_changed()
                    
                    def move_down(idx=index):
                        if idx < len(items) - 1:
                            items[idx], items[idx+1] = items[idx+1], items[idx]
                            rebuild_fn()
                            self._mark_changed()
                    
                    ui.button(icon='arrow_upward', on_click=move_up).props('flat dense size=sm').classes('text-gray-500').tooltip('Monter')
                    ui.button(icon='arrow_downward', on_click=move_down).props('flat dense size=sm').classes('text-gray-500').tooltip('Descendre')
                
                with ui.row().classes('items-center gap-2'):
                    # Bouton supprimer
                    def delete_item(idx=index):
                        if len(items) > 1:  # Garder au moins un cadre
                            items.pop(idx)
                            self._mark_changed()
                            rebuild_fn()
                            # Note: ui.notify removed here to avoid slot deletion error
                    
                    ui.button(icon='delete', on_click=delete_item).props('flat dense size=sm color=red').tooltip('Supprimer ce cadre')
                    
                    # Sélecteur de couleur
                    color_options = {k: f"{v['nom']}" for k, v in LATEX_COLORS.items()}
                    def update_color(e, it=item):
                        it['couleur'] = e.value
                        rebuild_fn()
                        self._mark_changed()
                    
                    ui.icon('palette', size='xs').classes('text-gray-400')
                    ui.select(options=color_options, value=item.get('couleur', 'ecoBleu'), on_change=update_color).props('dense outlined').classes('w-28').style(f'background-color: {couleur_css}20;')
            
            # Titre du cadre (éditable)
            ui.label('Titre :').classes('text-xs text-gray-500')
            def update_nom(e, it=item):
                it['nom'] = e.value
                self._mark_changed()
            ui.input(value=item.get('nom', 'Cadre'), on_change=update_nom).props('outlined').classes('font-bold text-blue-700 mb-2 w-full')
            
            # Contenu selon le type
            item_type = item.get('type', 'text')
            
            if item_type == 'list':
                # Pour les listes (concretement, habilitations)
                contenu = item.get('contenu', [])
                if isinstance(contenu, list):
                    contenu_str = '\n'.join(contenu)
                else:
                    contenu_str = str(contenu)
                
                ui.label('(un élément par ligne)').classes('text-xs text-gray-400 italic mb-1')
                
                def update_list_content(e, it=item):
                    lines = [l.strip() for l in e.value.split('\n') if l.strip()]
                    it['contenu'] = lines
                    self._mark_changed()
                
                ui.textarea(value=contenu_str, on_change=update_list_content).classes('w-full').props('rows=6 outlined')
            else:
                # Pour les textes
                contenu = item.get('contenu', '')
                
                def update_text_content(e, it=item):
                    it['contenu'] = e.value
                    self._mark_changed()
                
                ui.textarea(value=contenu, on_change=update_text_content).classes('w-full').props('rows=4 outlined')

    def _build_equipe_card(self, items: list, index: int, rebuild_fn):
        """Construit une carte de membre d'équipe avec contrôles de réordonnancement et couleur."""
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
                            self._mark_changed()
                    
                    def move_down(idx=index):
                        if idx < len(items) - 1:
                            items[idx], items[idx+1] = items[idx+1], items[idx]
                            rebuild_fn()
                            self._mark_changed()
                    
                    ui.button(icon='arrow_upward', on_click=move_up).props('flat dense size=sm').classes('text-gray-500').tooltip('Monter')
                    ui.button(icon='arrow_downward', on_click=move_down).props('flat dense size=sm').classes('text-gray-500').tooltip('Descendre')
                
                with ui.row().classes('items-center gap-2'):
                    # Bouton supprimer
                    def delete_item(idx=index):
                        if len(items) > 1:
                            items.pop(idx)
                            rebuild_fn()
                            self._mark_changed()
                            ui.notify('Membre supprimé', type='info')
                    
                    ui.button(icon='delete', on_click=delete_item).props('flat dense size=sm color=red').tooltip('Supprimer')
                    
                    # Sélecteur de couleur
                    color_options = {k: f"{v['nom']}" for k, v in LATEX_COLORS.items()}
                    def update_color(e, it=item):
                        it['couleur'] = e.value
                        rebuild_fn()
                        self._mark_changed()
                    
                    ui.icon('palette', size='xs').classes('text-gray-400')
                    ui.select(options=color_options, value=item.get('couleur', 'ecoBleu'), on_change=update_color).props('dense outlined').classes('w-28').style(f'background-color: {couleur_css}20;')
            
            # Titre du membre (éditable)
            ui.label('Titre / Nom :').classes('text-xs text-gray-500')
            def update_nom(e, it=item):
                it['nom'] = e.value
                self._mark_changed()
            ui.input(value=item.get('nom', 'Membre'), on_change=update_nom).props('outlined').classes('font-bold text-blue-700 mb-2 w-full')
            
            # Description / texte
            ui.label('Description :').classes('text-xs text-gray-500')
            def update_texte(e, it=item):
                it['texte'] = e.value
                self._mark_changed()
            ui.textarea(value=item.get('texte', ''), on_change=update_texte).classes('w-full').props('rows=4 outlined')

    def _build_moyens_humains_editor(self, titre: str, rows: pd.DataFrame):
        """Éditeur pour Moyens Humains avec équipe réordonnables. Sécurité/santé avec cartes."""
        data_mh = self.template_data.get('moyens_humains', {})
        
        with ui.column().classes('w-full gap-4 p-2'):
            # ===== SECTION 1: L'ÉQUIPE (cartes réordonnables) =====
            ui.label('L\'ÉQUIPE').classes('text-lg font-bold text-blue-900 mt-2 mb-2 border-b-2 border-blue-200 pb-2')
            ui.label('Réordonnez les membres avec les flèches, personnalisez titres et couleurs').classes('text-xs text-gray-500 mb-2')
            
            # Initialiser la liste ordonnée des membres d'équipe
            equipe_order_key = '_equipe_order_'
            if equipe_order_key not in self.edit_widgets:
                # Charger depuis template_data ou créer par défaut
                ca = data_mh.get('charge_affaires', {})
                chefs = data_mh.get('chefs_equipe', {})
                charp = data_mh.get('charpentiers', {})
                
                # Chefs noms
                chefs_noms = chefs.get('noms', [])
                chefs_noms_str = ' /// ou /// '.join(chefs_noms) if isinstance(chefs_noms, list) else chefs_noms
                
                # Charpentiers noms
                charp_noms = charp.get('noms', [])
                charp_noms_str = ' /// ou /// '.join(charp_noms) if isinstance(charp_noms, list) else charp_noms
                
                self.edit_widgets[equipe_order_key] = [
                    {'key': 'charge_affaires', 'nom': f"Chargé d'affaires : {ca.get('nom', 'Frédéric ANSELM')}", 
                     'texte': ca.get('description', ''), 'couleur': 'ecoBleu', 'type': 'text'},
                    {'key': 'chef_equipe', 'nom': f"Chef d'équipe : {chefs_noms_str or 'Jimmy FROGER /// ou /// THROO Stéphane'}", 
                     'texte': chefs.get('description', ''), 'couleur': 'ecoVert', 'type': 'text'},
                    {'key': 'charpentiers', 'nom': f"Charpentiers : {charp_noms_str or 'DA COSTA Tristan /// ou /// Thomas MURA'}", 
                     'texte': charp.get('description', ''), 'couleur': 'ecoOrange', 'type': 'text'},
                ]
            
            equipe_items = self.edit_widgets[equipe_order_key]
            equipe_container = ui.column().classes('w-full gap-3')
            
            def rebuild_equipe():
                """Reconstruit l'affichage de l'équipe."""
                equipe_container.clear()
                with equipe_container:
                    for i in range(len(equipe_items)):
                        self._build_equipe_card(equipe_items, i, rebuild_equipe)
                    
                    # Bouton pour ajouter un nouveau membre
                    def add_member():
                        new_item = {
                            'key': f'custom_{len(equipe_items)}',
                            'nom': 'Nouveau membre',
                            'texte': '',
                            'couleur': 'ecoBleu',
                            'type': 'text'
                        }
                        equipe_items.append(new_item)
                        rebuild_equipe()
                        self._mark_changed()
                        ui.notify('Membre ajouté', type='positive')
                    
                    ui.button('+ Ajouter un membre', on_click=add_member, icon='add').props('outline color=blue').classes('mt-2')
            
            rebuild_equipe()
            
            # ===== SECTION 2: SÉCURITÉ ET SANTÉ SUR LES CHANTIERS (cartes réordonnables) =====
            ui.label('SÉCURITÉ ET SANTÉ SUR LES CHANTIERS').classes('text-lg font-bold text-blue-900 mt-6 mb-2 border-b-2 border-blue-200 pb-2')
            self._build_securite_sante_cards_editor()
            
            # ===== SECTION 3: ORGANIGRAMME =====
            ui.label('ORGANIGRAMME').classes('text-lg font-bold text-blue-900 mt-6 mb-2 border-b-2 border-blue-200 pb-2')
            
            # Organigramme
            with ui.card().classes('w-full p-4'):
                ui.label('Chemin de l\'image de l\'organigramme').classes('text-xs text-gray-500')
                org_img = data_mh.get('organigramme', {}).get('image', '../images/organigramme.png')
                org_input = ui.input(value=org_img, placeholder='../images/organigramme.png').classes('w-full')
                org_input.on('change', lambda: self._mark_changed())
                self.edit_widgets['moyens_humains_organigramme'] = org_input
            
            # ===== SOUS-SECTIONS CSV RÉORDONNABLES =====
            ui.label('Autres sous-sections').classes('text-lg font-bold text-blue-900 mt-6 mb-2 border-b-2 border-blue-200 pb-2')
            
            # Filtrer pour exclure ce qu'on a déjà géré (équipe + sécurité/santé + organigramme)
            def filter_mh(ss):
                ss_lower = ss.lower()
                # Exclure les sous-sections déjà gérées par les éditeurs spéciaux
                is_equipe = ('chargé' in ss_lower and 'affaires' in ss_lower) or \
                           ('chef' in ss_lower and 'équipe' in ss_lower) or \
                           'charpentier' in ss_lower
                is_organigramme = 'organigramme' in ss_lower
                # Exclure aussi les sous-sections sécurité/santé (gérées par _build_securite_sante_cards_editor)
                is_securite_sante = 'sécurité' in ss_lower or 'securite' in ss_lower or \
                                   'santé' in ss_lower or 'sante' in ss_lower or \
                                   'organisation' in ss_lower or 'confort' in ss_lower or \
                                   'accueil' in ss_lower or 'habilitation' in ss_lower or \
                                   'contrôle' in ss_lower or 'controle' in ss_lower or \
                                   'concrètement' in ss_lower or 'concretement' in ss_lower
                return not is_equipe and not is_organigramme and not is_securite_sante
            
            self._build_csv_section_editor_filtered(titre, rows, filter_mh)
    
    def _build_chantiers_references_editor(self, titre: str, rows: pd.DataFrame):
        """Éditeur pour Chantiers Références avec cadres individuels (pas d'options multiples).
        Chaque sous-section du CSV devient un cadre séparé dans l'interface."""
        
        section_key = f'section_order_{normaliser_titre(titre)}'
        
        # Initialiser la liste ordonnée des sous-sections
        if section_key not in self.edit_widgets:
            items = []
            for idx, row in rows.iterrows():
                sous_section = nettoyer_str(row.get('sous-section', ''))
                texte = nettoyer_str(row.get('texte', ''))
                image = nettoyer_str(row.get('image', ''))
                couleur = nettoyer_str(row.get('couleur', 'ecoBleu')) or 'ecoBleu'
                
                if not sous_section and not texte:
                    continue
                
                # Pour les références, chaque entrée devient un cadre
                # Si le texte contient "/// ou ///", c'est une liste de références existantes
                # On crée un item pour chaque référence individuelle OU on garde tel quel
                items.append({
                    'idx': idx,
                    'sous_section': sous_section,
                    'texte': texte,
                    'image': image,
                    'couleur': couleur,
                    'section': titre
                })
            
            self.edit_widgets[section_key] = {
                'type': 'ordered_section',
                'items': items,
                'section': titre
            }
        
        section_data = self.edit_widgets[section_key]
        items = section_data['items']
        
        with ui.column().classes('w-full gap-3 p-2'):
            ui.label('Chaque cadre ci-dessous représente une sous-section qui apparaîtra dans le mémoire.').classes('text-xs text-gray-500 mb-2')
            ui.label('💡 Astuce: Pour ajouter plusieurs références, créez une sous-section et listez-les dans le contenu (une par ligne avec "-")').classes('text-xs text-orange-600 mb-2')
            
            # Container principal pour les cadres
            main_container = ui.column().classes('w-full gap-3')
            
            def rebuild_section():
                """Reconstruit l'affichage de la section."""
                main_container.clear()
                with main_container:
                    for i, item in enumerate(items):
                        self._build_subsection_card(items, i, rebuild_section, titre)
                    
                    # Bouton ajouter
                    def add_new():
                        new_item = {
                            'idx': -1,  # Nouveau
                            'sous_section': 'Nouvelle référence chantier',
                            'texte': '',
                            'image': '',
                            'couleur': 'ecoBleu',
                            'section': titre,
                            'is_new': True
                        }
                        items.append(new_item)
                        self._mark_changed()
                        rebuild_section()
                        ui.notify('Nouvelle référence ajoutée', type='positive')
                    
                    ui.button('+ Ajouter une référence chantier', on_click=add_new, icon='add').props('outline color=blue')
            
            rebuild_section()
    
    def _build_contexte_projet_editor(self, titre: str, rows: pd.DataFrame):
        """Éditeur pour Contexte du Projet avec date de visite et adresse."""
        data = self.template_data.get('contexte_projet', {})
        
        with ui.column().classes('w-full gap-4 p-2'):
            # Contexte visite (date + adresse par défaut)
            with ui.card().classes('w-full p-4 border-l-4 border-blue-500'):
                ui.label('🗓️ Visite de site (valeurs par défaut)').classes('font-bold text-blue-700 mb-2')
                ui.label('Ces valeurs seront utilisées si non modifiées dans "Nouveau mémoire"').classes('text-xs text-gray-500 mb-3')
                
                with ui.row().classes('w-full gap-4'):
                    with ui.column().classes('flex-1'):
                        ui.label('Date de visite par défaut').classes('text-sm text-gray-600')
                        date_val = data.get('date_visite_defaut', '')
                        date_input = ui.input(value=date_val, placeholder='Ex: à compléter').classes('w-full')
                        date_input.on('change', lambda: self._mark_changed())
                        self.edit_widgets['contexte_date_visite'] = date_input
                    
                    with ui.column().classes('flex-1'):
                        ui.label('Texte d\'introduction visite').classes('text-sm text-gray-600')
                        intro_visite = data.get('intro_visite', 'Nous nous sommes rendus sur les lieux le')
                        intro_input = ui.input(value=intro_visite, placeholder='Nous nous sommes rendus sur les lieux le').classes('w-full')
                        intro_input.on('change', lambda: self._mark_changed())
                        self.edit_widgets['contexte_intro_visite'] = intro_input
            
            # Environnement / Localisation
            with ui.card().classes('w-full p-4'):
                ui.label('Environnement / Localisation').classes('font-bold text-blue-700 mb-2')
                ui.label('Types d\'environnement disponibles (séparés par "/// ou ///")').classes('text-xs text-gray-500')
                
                env_options = data.get('environnement_options', [])
                env_str = ' /// ou /// '.join(env_options) if env_options else ''
                # Fallback depuis CSV
                if not env_str:
                    for idx, row in rows.iterrows():
                        ss = nettoyer_str(row.get('sous-section', '')).lower()
                        if 'environnement' in ss:
                            env_str = nettoyer_str(row.get('texte', ''))
                            break
                
                env_input = ui.input(value=env_str, placeholder='Pavillonnaire /// ou /// Zone industrielle').classes('w-full')
                env_input.on('change', lambda: self._mark_changed())
                self.edit_widgets['contexte_environnement'] = env_input
                
                ui.label('💡 Note: "Environnement" dans la base s\'affiche comme "Localisation" dans le PDF.').classes('text-xs text-orange-600 mt-2')
            
            # Accès chantier
            with ui.card().classes('w-full p-4'):
                ui.label('Accès chantier et stationnement').classes('font-bold text-blue-700 mb-2')
                acces_val = data.get('acces_chantier', '')
                # Fallback CSV
                if not acces_val:
                    for idx, row in rows.iterrows():
                        ss = nettoyer_str(row.get('sous-section', '')).lower()
                        if 'accès' in ss and 'stationnement' in ss:
                            acces_val = nettoyer_str(row.get('texte', ''))
                            break
                
                acces_input = ui.textarea(value=acces_val, placeholder='Selon PGC délivrée a l\'entreprise retenue').classes('w-full').props('rows=2 outlined')
                acces_input.on('change', lambda: self._mark_changed())
                self.edit_widgets['contexte_acces'] = acces_input
            
            # Levage
            with ui.card().classes('w-full p-4'):
                ui.label('Levage').classes('font-bold text-blue-700 mb-2')
                ui.label('Options de levage (séparées par "/// ou ///")').classes('text-xs text-gray-500')
                
                levage_val = data.get('levage_options', '')
                # Fallback CSV
                if not levage_val:
                    for idx, row in rows.iterrows():
                        ss = nettoyer_str(row.get('sous-section', '')).lower()
                        if ss == 'levage':
                            levage_val = nettoyer_str(row.get('texte', ''))
                            break
                
                levage_input = ui.input(value=levage_val, placeholder='Grue automotrice /// ou /// Camion grue').classes('w-full')
                levage_input.on('change', lambda: self._mark_changed())
                self.edit_widgets['contexte_levage'] = levage_input
            
            # Contraintes du chantier
            with ui.card().classes('w-full p-4'):
                ui.label('Contraintes du chantier').classes('font-bold text-blue-700 mb-2')
                ui.label('Options de contraintes (séparées par "/// ou ///")').classes('text-xs text-gray-500')
                
                contraintes_val = data.get('contraintes_options', '')
                # Fallback CSV
                if not contraintes_val:
                    for idx, row in rows.iterrows():
                        ss = nettoyer_str(row.get('sous-section', '')).lower()
                        if 'contrainte' in ss:
                            contraintes_val = nettoyer_str(row.get('texte', ''))
                            break
                
                contraintes_input = ui.textarea(value=contraintes_val, placeholder='Travaux hauteur /// ou /// Chute de hauteur').classes('w-full').props('rows=3 outlined')
                contraintes_input.on('change', lambda: self._mark_changed())
                self.edit_widgets['contexte_contraintes'] = contraintes_input
            
            # ===== SOUS-SECTIONS CSV RÉORDONNABLES =====
            ui.label('Autres sous-sections').classes('text-lg font-bold text-blue-900 mt-4 mb-2 border-b-2 border-blue-200 pb-2')
            
            # Filtrer pour exclure ce qu'on a déjà géré
            def filter_contexte(ss):
                ss_lower = ss.lower()
                return not ('visite' in ss_lower) and \
                       not ('environnement' in ss_lower or 'localisation' in ss_lower) and \
                       not ('accès' in ss_lower and 'stationnement' in ss_lower) and \
                       not (ss_lower == 'levage') and \
                       not ('contrainte' in ss_lower)
            
            self._build_csv_section_editor_filtered(titre, rows, filter_contexte)

    def _build_planning_editor(self, titre: str, rows: pd.DataFrame):
        """Éditeur pour Planning avec texte modifiable et couleur (comme dans Nouveau mémoire)."""
        data = self.template_data.get('planning', {})
        
        with ui.column().classes('w-full gap-4 p-2'):
            ui.label('Configuration du Planning').classes('text-lg font-bold text-blue-900 mb-2 border-b-2 border-blue-200 pb-2')
            ui.label('Ce texte sera affiché dans la section Planning du mémoire').classes('text-xs text-gray-500 mb-2')
            
            # Récupérer les couleurs et créer la liste pour le sélecteur
            planning_order_key = '_planning_order_'
            if planning_order_key not in self.edit_widgets:
                couleur = data.get('couleur', 'ecoBleu')
                texte = data.get('texte', '')
                
                # Fallback depuis CSV si pas de texte
                if not texte:
                    for idx, row in rows.iterrows():
                        row_texte = nettoyer_str(row.get('texte', ''))
                        if row_texte and len(row_texte) > 100:
                            texte = row_texte
                            couleur = valider_couleur(nettoyer_str(row.get('couleur', 'ecoBleu')))
                            break
                
                # Texte par défaut si toujours vide
                if not texte:
                    texte = "Lors de l'étude du planning transmis dans le cadre du dossier de consultation, nous avons porté une attention particulière à la durée prévue par le planning pour la phase de montage. Au regard des caractéristiques techniques du projet, du volume des éléments à assembler, des conditions d'accès au site, ainsi que de nos retours d'expérience sur des opérations similaires, cette durée apparaît ........... pour garantir une exécution conforme aux exigences de qualité, de sécurité et de coordination des intervenants. Nos prévisions internes, fondées sur une simulation détaillée estiment le besoin réel à ...... semaines. Nous recommandons donc d'ajuster le planning initial sur cette base afin d'assurer une exécution réaliste fluide et sans tension sur les ressources."
                
                self.edit_widgets[planning_order_key] = {
                    'texte': texte,
                    'couleur': couleur
                }
            
            planning_data = self.edit_widgets[planning_order_key]
            couleur_css = LATEX_COLORS.get(planning_data['couleur'], LATEX_COLORS['ecoBleu'])['css']
            
            with ui.card().classes('w-full p-4').style(f'border-left: 4px solid {couleur_css};'):
                with ui.row().classes('w-full justify-between items-center mb-3'):
                    ui.label('Analyse du planning').classes('font-bold text-blue-700')
                    
                    # Sélecteur de couleur
                    color_options = {k: f"{v['nom']}" for k, v in LATEX_COLORS.items()}
                    def update_color(e, pd=planning_data):
                        pd['couleur'] = e.value
                        self._mark_changed()
                    
                    with ui.row().classes('items-center gap-1'):
                        ui.icon('palette', size='xs').classes('text-gray-400')
                        ui.select(
                            options=color_options,
                            value=planning_data.get('couleur', 'ecoBleu'),
                            on_change=update_color
                        ).props('dense outlined').classes('w-28')
                
                # Texte éditable
                def update_texte(e, pd=planning_data):
                    pd['texte'] = e.value
                    self._mark_changed()
                
                planning_input = ui.textarea(
                    value=planning_data['texte'],
                    on_change=update_texte
                ).classes('w-full').props('rows=8 outlined')
                self.edit_widgets['planning_texte'] = planning_input
            
            # Autres sous-sections du CSV pour Planning (si nécessaire)
            ui.label('Autres sous-sections').classes('text-lg font-bold text-blue-900 mt-4 mb-2 border-b-2 border-blue-200 pb-2')
            self._build_csv_section_editor_filtered(titre, rows, lambda ss: True)

    def _build_transport_levage_editor(self):
        """Éditeur pour Transport/Levage avec cartes réordonnables (comme Sécurité/Santé)."""
        data = self.template_data.get('transport_levage', {})
        
        ui.label('Configuration Transport et Levage').classes('text-lg font-bold text-blue-900 mb-2 border-b-2 border-blue-200 pb-2')
        ui.label('Réordonnez les cadres avec les flèches, personnalisez titres et couleurs').classes('text-xs text-gray-500 mb-2')
        
        # Initialiser la liste ordonnée des cadres transport/levage
        tl_order_key = '_transport_levage_order_'
        if tl_order_key not in self.edit_widgets:
            couleurs = data.get('couleurs', {})
            noms = data.get('noms', {})
            
            self.edit_widgets[tl_order_key] = [
                {'key': 'intro', 'nom': noms.get('intro', 'Introduction'), 'type': 'text',
                 'contenu': data.get('intro', ''), 'couleur': couleurs.get('intro', 'ecoBleu')},
                {'key': 'livraison', 'nom': noms.get('livraison', 'Livraison'), 'type': 'list',
                 'contenu': data.get('livraison_options', []), 'couleur': couleurs.get('livraison', 'ecoVert')},
                {'key': 'levage', 'nom': noms.get('levage', 'Levage'), 'type': 'list',
                 'contenu': data.get('levage_options', []), 'couleur': couleurs.get('levage', 'ecoOrange')},
                {'key': 'ouvrages_livres', 'nom': noms.get('ouvrages_livres', 'Stockage des ouvrages livrés'), 'type': 'text',
                 'contenu': data.get('ouvrages_livres', ''), 'couleur': couleurs.get('ouvrages_livres', 'ecoMarron')},
                {'key': 'encadrement', 'nom': noms.get('encadrement', 'Encadrement'), 'type': 'text',
                 'contenu': data.get('encadrement', ''), 'couleur': couleurs.get('encadrement', 'ecoViolet')},
                {'key': 'sous_traitance', 'nom': noms.get('sous_traitance', 'Sous-traitance'), 'type': 'text',
                 'contenu': data.get('sous_traitance', ''), 'couleur': couleurs.get('sous_traitance', 'ecoJaune')},
            ]
        
        tl_items = self.edit_widgets[tl_order_key]
        tl_container = ui.column().classes('w-full gap-3')
        
        def rebuild_tl():
            """Reconstruit l'affichage des cadres transport/levage."""
            tl_container.clear()
            with tl_container:
                for i in range(len(tl_items)):
                    self._build_transport_levage_card(tl_items, i, rebuild_tl)
                
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
                    self._mark_changed()
                    ui.notify('Section ajoutée', type='positive')
                
                ui.button('+ Ajouter une section', on_click=add_card, icon='add').props('outline color=blue').classes('mt-2')
        
        with tl_container:
            rebuild_tl()

    def _build_transport_levage_card(self, items: list, index: int, rebuild_fn):
        """Construit une carte de transport/levage avec contrôles de réordonnancement et couleur."""
        item = items[index]
        item['couleur'] = valider_couleur(item.get('couleur', 'ecoBleu'))
        
        couleur_css = LATEX_COLORS.get(item['couleur'], LATEX_COLORS['ecoBleu'])['css']
        
        with ui.card().classes('w-full p-4').style(f'border-left: 4px solid {couleur_css};'):
            with ui.row().classes('w-full justify-between items-center mb-3'):
                with ui.row().classes('items-center gap-1'):
                    ui.label(f'#{index + 1}').classes('text-xs text-gray-400 font-mono')
                    
                    def move_up(idx=index):
                        if idx > 0:
                            items[idx], items[idx-1] = items[idx-1], items[idx]
                            self._mark_changed()
                            rebuild_fn()
                    
                    def move_down(idx=index):
                        if idx < len(items) - 1:
                            items[idx], items[idx+1] = items[idx+1], items[idx]
                            self._mark_changed()
                            rebuild_fn()
                    
                    ui.button(icon='arrow_upward', on_click=move_up).props('flat dense size=sm').classes('text-gray-500').tooltip('Monter')
                    ui.button(icon='arrow_downward', on_click=move_down).props('flat dense size=sm').classes('text-gray-500').tooltip('Descendre')
                
                with ui.row().classes('items-center gap-2'):
                    def delete_item(idx=index):
                        if len(items) > 1:
                            items.pop(idx)
                            self._mark_changed()
                            rebuild_fn()
                            # Note: ui.notify removed here to avoid slot deletion error
                    
                    ui.button(icon='delete', on_click=delete_item).props('flat dense size=sm color=red').tooltip('Supprimer ce cadre')
                    
                    color_options = {k: f"{v['nom']}" for k, v in LATEX_COLORS.items()}
                    def update_color(e, it=item):
                        it['couleur'] = e.value
                        self._mark_changed()
                        rebuild_fn()
                    
                    ui.icon('palette', size='xs').classes('text-gray-400')
                    ui.select(options=color_options, value=item.get('couleur', 'ecoBleu'), on_change=update_color).props('dense outlined').classes('w-28').style(f'background-color: {couleur_css}20;')
            
            # Titre du cadre (éditable)
            ui.label('Titre :').classes('text-xs text-gray-500')
            def update_nom(e, it=item):
                it['nom'] = e.value
                self._mark_changed()
            ui.input(value=item.get('nom', 'Cadre'), on_change=update_nom).props('outlined').classes('font-bold text-blue-700 mb-2 w-full')
            
            # Contenu selon le type
            item_type = item.get('type', 'text')
            
            if item_type == 'list':
                contenu = item.get('contenu', [])
                if isinstance(contenu, list):
                    contenu_str = '\n'.join(contenu)
                else:
                    contenu_str = str(contenu)
                
                ui.label('Contenu (une option par ligne) :').classes('text-xs text-gray-400 italic mb-1')
                
                def update_list_content(e, it=item):
                    lines = [l.strip() for l in e.value.split('\n') if l.strip()]
                    it['contenu'] = lines
                    self._mark_changed()
                
                ui.textarea(value=contenu_str, on_change=update_list_content).classes('w-full').props('rows=4 outlined')
            else:
                # Type text
                contenu = item.get('contenu', '')
                if not isinstance(contenu, str):
                    contenu = str(contenu) if contenu else ''
                
                ui.label('Contenu :').classes('text-xs text-gray-400')
                
                def update_text_content(e, it=item):
                    it['contenu'] = e.value
                    self._mark_changed()
                
                ui.textarea(value=contenu, on_change=update_text_content).classes('w-full').props('rows=3 outlined')

    def _mark_changed(self):
        """Marque qu'il y a des modifications non sauvegardées."""
        self.has_unsaved_changes = True
        self.save_btn.classes('bg-orange-600 text-white', remove='bg-green-600')
    
    def _add_csv_row(self, section: str):
        """Ajoute une nouvelle ligne au CSV."""
        new_row = pd.DataFrame([{
            'section': section,
            'sous-section': 'Nouvelle sous-section',
            'texte': '',
            'image': '',
            'section_norm': normaliser_titre(section)
        }])
        self.df = pd.concat([self.df, new_row], ignore_index=True)
        self._mark_changed()
        ui.notify('Sous-section ajoutée. N\'oubliez pas de sauvegarder.', type='info')
    
    async def _save_all(self):
        """Sauvegarde toutes les modifications de façon permanente."""
        try:
            # Sous-sections spéciales à préserver pour LISTE DES MATERIAUX (entrées tableaux)
            SPECIAL_SUBSECTIONS = {
                'liste des materiaux': [
                    ('Fixation et assemblage', 'ecoMarron'),
                    ('Traitement préventif', 'ecoVert'),
                    ('Traitement curatif', 'ecoVert'),
                ]
            }
            
            # 1. Sauvegarder les sections ordonnées (nouveau format)
            for key, widget_data in self.edit_widgets.items():
                if isinstance(widget_data, dict) and widget_data.get('type') == 'ordered_section':
                    section_name = widget_data.get('section', '')
                    items = widget_data.get('items', [])
                    
                    # Supprimer les anciennes lignes de cette section
                    section_norm = normaliser_titre(section_name)
                    
                    # Sauvegarder les entrées spéciales AVANT suppression (pour préserver leurs couleurs)
                    special_entries = {}
                    if section_norm in SPECIAL_SUBSECTIONS or 'materiaux' in section_norm:
                        old_rows = self.df[self.df['section_norm'] == section_norm]
                        for _, row in old_rows.iterrows():
                            ss = row.get('sous-section', '').lower()
                            if 'fixation' in ss or 'traitement' in ss:
                                special_entries[row.get('sous-section', '')] = row.get('couleur', 'ecoVert')
                    
                    self.df = self.df[self.df['section_norm'] != section_norm]
                    
                    # Ajouter les nouvelles lignes dans l'ordre
                    for item in items:
                        new_row = pd.DataFrame([{
                            'section': section_name,
                            'sous-section': item.get('sous_section', ''),
                            'texte': item.get('texte', ''),
                            'image': item.get('image', ''),
                            'couleur': item.get('couleur', 'ecoBleu'),
                            'section_norm': section_norm
                        }])
                        self.df = pd.concat([self.df, new_row], ignore_index=True)
                    
                    # Réajouter les entrées spéciales après les items
                    if section_norm in SPECIAL_SUBSECTIONS or 'materiaux' in section_norm:
                        for subsection, default_color in SPECIAL_SUBSECTIONS.get('liste des materiaux', []):
                            # Utiliser la couleur sauvegardée si disponible, sinon la couleur par défaut
                            color = special_entries.get(subsection, default_color)
                            new_row = pd.DataFrame([{
                                'section': section_name,
                                'sous-section': subsection,
                                'texte': '',
                                'image': '',
                                'couleur': color,
                                'section_norm': section_norm
                            }])
                            self.df = pd.concat([self.df, new_row], ignore_index=True)
            
            # 2. Sauvegarder les modifications CSV (ancien format - pour compatibilité)
            for key, widget_data in self.edit_widgets.items():
                if isinstance(widget_data, dict) and widget_data.get('type') == 'csv':
                    idx = widget_data['idx']
                    if idx in self.df.index:
                        if widget_data.get('sous_section') is not None:
                            self.df.at[idx, 'sous-section'] = widget_data['sous_section'].value
                        if widget_data.get('texte') is not None:
                            self.df.at[idx, 'texte'] = widget_data['texte'].value
                        if widget_data.get('image') is not None:
                            self.df.at[idx, 'image'] = widget_data['image'].value
            
            # Sauvegarder CSV
            csv_path = self.config.DATA_DIR / "bd_interface.csv"
            # Backup
            backup_path = csv_path.with_suffix('.csv.bak')
            if csv_path.exists():
                import shutil
                shutil.copy(csv_path, backup_path)
            
            # Exclure la colonne section_norm avant sauvegarde
            df_save = self.df.drop(columns=['section_norm'], errors='ignore')
            df_save.to_csv(csv_path, sep=";", index=False, encoding='utf-8')
            
            # 3. Sauvegarder template_data.json
            self._update_template_data_from_widgets()
            self._save_template_data()
            
            self.has_unsaved_changes = False
            self.save_btn.classes('bg-green-600 text-white', remove='bg-orange-600')
            ui.notify('Toutes les modifications ont été sauvegardées !', type='positive')
            
        except Exception as ex:
            import traceback
            traceback.print_exc()
            ui.notify(f'Erreur de sauvegarde: {str(ex)}', type='negative')
    
    def _update_template_data_from_widgets(self):
        """Met à jour template_data depuis les widgets."""
        # Préambule
        if 'preambule_texte' in self.edit_widgets and self.edit_widgets['preambule_texte'] is not None:
            self.template_data.setdefault('preambule', {})['texte'] = self.edit_widgets['preambule_texte'].value
        
        # Situation administrative
        if 'situation_admin_qualifications' in self.edit_widgets and self.edit_widgets['situation_admin_qualifications'] is not None:
            qualifs_text = self.edit_widgets['situation_admin_qualifications'].value
            self.template_data.setdefault('situation_administrative', {})['qualifications'] = [q.strip() for q in qualifs_text.split('\n') if q.strip()]
        
        if 'situation_admin_effectif_date' in self.edit_widgets and self.edit_widgets['situation_admin_effectif_date'] is not None:
            self.template_data.setdefault('situation_administrative', {})['effectif_date'] = self.edit_widgets['situation_admin_effectif_date'].value
        
        if 'situation_admin_effectif_nombre' in self.edit_widgets and self.edit_widgets['situation_admin_effectif_nombre'] is not None:
            self.template_data.setdefault('situation_administrative', {})['effectif_nombre'] = self.edit_widgets['situation_admin_effectif_nombre'].value
        
        # Chiffre d'affaires
        ca_list = []
        for i in range(10):
            annee_key = f'situation_admin_ca_{i}_annee'
            montant_key = f'situation_admin_ca_{i}_montant'
            if annee_key in self.edit_widgets and self.edit_widgets[annee_key] is not None:
                annee = self.edit_widgets[annee_key].value
                montant = self.edit_widgets[montant_key].value if montant_key in self.edit_widgets and self.edit_widgets[montant_key] is not None else ''
                if annee or montant:
                    ca_list.append({'annee': annee, 'montant': montant})
        if ca_list:
            self.template_data.setdefault('situation_administrative', {})['chiffre_affaires'] = ca_list
        
        # Sécurité santé - Nouveau format avec cartes ordonnées et couleurs
        ss_order_key = '_securite_order_'
        if ss_order_key in self.edit_widgets and isinstance(self.edit_widgets[ss_order_key], list):
            ss_items = self.edit_widgets[ss_order_key]
            securite_sante = self.template_data.setdefault('securite_sante', {})
            
            # Sauvegarder l'ordre des cadres
            securite_sante['_order'] = [item['key'] for item in ss_items]
            
            # Sauvegarder les couleurs
            couleurs = {}
            for item in ss_items:
                couleurs[item['key']] = item.get('couleur', 'ecoBleu')
            securite_sante['couleurs'] = couleurs
            
            # Sauvegarder les noms personnalisés
            noms = {}
            for item in ss_items:
                noms[item['key']] = item.get('nom', item['key'])
            securite_sante['noms'] = noms
            
            # Sauvegarder les contenus
            for item in ss_items:
                key = item['key']
                contenu = item.get('contenu', '')
                securite_sante[key] = contenu
        
        # Moyens matériel
        if 'moyens_materiel_intro' in self.edit_widgets and self.edit_widgets['moyens_materiel_intro'] is not None:
            self.template_data.setdefault('moyens_materiel', {})['intro'] = self.edit_widgets['moyens_materiel_intro'].value
        
        for key in ['conception', 'securite', 'atelier', 'levage', 'transport', 'machine_portative', 'protection_nettoyage', 'gestion_dechet']:
            widget_key = f'moyens_materiel_{key}'
            if widget_key in self.edit_widgets and self.edit_widgets[widget_key] is not None:
                items_text = self.edit_widgets[widget_key].value
                self.template_data.setdefault('moyens_materiel', {})[key] = [i.strip() for i in items_text.split('\n') if i.strip()]
        
        # Démarche HQE - Ne pas toucher à eco_construction qui a une structure complexe
        if 'demarche_hqe_intro' in self.edit_widgets and self.edit_widgets['demarche_hqe_intro'] is not None:
            self.template_data.setdefault('demarche_hqe', {})['intro'] = self.edit_widgets['demarche_hqe_intro'].value
        
        # Note: eco_construction n'est pas modifié ici car sa structure est complexe (cible_02, cible_03, etc.)
        
        # Démarche env atelier
        if 'demarche_env_atelier_intro' in self.edit_widgets and self.edit_widgets['demarche_env_atelier_intro'] is not None:
            self.template_data.setdefault('demarche_env_atelier', {})['intro'] = self.edit_widgets['demarche_env_atelier_intro'].value
        
        # Démarche env chantiers
        if 'demarche_env_chantiers_intro' in self.edit_widgets and self.edit_widgets['demarche_env_chantiers_intro'] is not None:
            self.template_data.setdefault('demarche_env_chantiers', {})['intro'] = self.edit_widgets['demarche_env_chantiers_intro'].value
        
        # Tableaux de fixation et traitement
        import copy
        for table_key in ['table_fixation_assemblage', 'table_traitement_preventif', 'table_traitement_curatif']:
            if table_key in self.edit_widgets and isinstance(self.edit_widgets[table_key], dict):
                table_widget = self.edit_widgets[table_key]
                if table_widget.get('type') == 'table' and 'data' in table_widget:
                    # Copie profonde pour être sûr de sauvegarder les valeurs actuelles
                    self.template_data[table_key] = copy.deepcopy(table_widget['data'])
        
        # Moyens Humains - NOUVEAU FORMAT avec cartes équipe ordonnées
        moyens_humains = self.template_data.setdefault('moyens_humains', {})
        
        # Équipe avec cartes ordonnées
        equipe_order_key = '_equipe_order_'
        if equipe_order_key in self.edit_widgets and isinstance(self.edit_widgets[equipe_order_key], list):
            equipe_items = self.edit_widgets[equipe_order_key]
            
            # Parser les cartes pour extraire les données
            for item in equipe_items:
                nom = item.get('nom', '')
                texte = item.get('texte', '')
                key = item.get('key', '')
                
                # Chargé d'affaires
                if 'charge_affaires' in key or ("chargé" in nom.lower() and "affaires" in nom.lower()):
                    # Extraire le nom depuis le titre (format: "Chargé d'affaires : NOM")
                    parts = nom.split(':')
                    extracted_nom = parts[1].strip() if len(parts) > 1 else nom
                    moyens_humains.setdefault('charge_affaires', {})['nom'] = extracted_nom
                    moyens_humains.setdefault('charge_affaires', {})['description'] = texte
                    moyens_humains.setdefault('charge_affaires', {})['couleur'] = item.get('couleur', 'ecoBleu')
                
                # Chef d'équipe
                elif 'chef_equipe' in key or ("chef" in nom.lower() and "équipe" in nom.lower()):
                    parts = nom.split(':')
                    noms_str = parts[1].strip() if len(parts) > 1 else ''
                    noms_list = [n.strip() for n in noms_str.split('/// ou ///') if n.strip()]
                    moyens_humains.setdefault('chefs_equipe', {})['noms'] = noms_list
                    moyens_humains.setdefault('chefs_equipe', {})['description'] = texte
                    moyens_humains.setdefault('chefs_equipe', {})['couleur'] = item.get('couleur', 'ecoVert')
                
                # Charpentiers
                elif 'charpentier' in key or 'charpentier' in nom.lower():
                    parts = nom.split(':')
                    noms_str = parts[1].strip() if len(parts) > 1 else ''
                    noms_list = [n.strip() for n in noms_str.split('/// ou ///') if n.strip()]
                    moyens_humains.setdefault('charpentiers', {})['noms'] = noms_list
                    moyens_humains.setdefault('charpentiers', {})['description'] = texte
                    moyens_humains.setdefault('charpentiers', {})['couleur'] = item.get('couleur', 'ecoOrange')
        
        # Fallback pour ancien format (widgets individuels)
        elif 'moyens_humains_ca_nom' in self.edit_widgets and self.edit_widgets['moyens_humains_ca_nom'] is not None:
            moyens_humains.setdefault('charge_affaires', {})['nom'] = self.edit_widgets['moyens_humains_ca_nom'].value
            if 'moyens_humains_ca_desc' in self.edit_widgets and self.edit_widgets['moyens_humains_ca_desc'] is not None:
                moyens_humains.setdefault('charge_affaires', {})['description'] = self.edit_widgets['moyens_humains_ca_desc'].value
            
            if 'moyens_humains_chefs_noms' in self.edit_widgets and self.edit_widgets['moyens_humains_chefs_noms'] is not None:
                noms_str = self.edit_widgets['moyens_humains_chefs_noms'].value
                noms_list = [n.strip() for n in noms_str.split('/// ou ///') if n.strip()]
                moyens_humains.setdefault('chefs_equipe', {})['noms'] = noms_list
            if 'moyens_humains_chefs_desc' in self.edit_widgets and self.edit_widgets['moyens_humains_chefs_desc'] is not None:
                moyens_humains.setdefault('chefs_equipe', {})['description'] = self.edit_widgets['moyens_humains_chefs_desc'].value
            
            if 'moyens_humains_charp_noms' in self.edit_widgets and self.edit_widgets['moyens_humains_charp_noms'] is not None:
                noms_str = self.edit_widgets['moyens_humains_charp_noms'].value
                noms_list = [n.strip() for n in noms_str.split('/// ou ///') if n.strip()]
                moyens_humains.setdefault('charpentiers', {})['noms'] = noms_list
            if 'moyens_humains_charp_desc' in self.edit_widgets and self.edit_widgets['moyens_humains_charp_desc'] is not None:
                moyens_humains.setdefault('charpentiers', {})['description'] = self.edit_widgets['moyens_humains_charp_desc'].value
        
        if 'moyens_humains_securite_desc' in self.edit_widgets and self.edit_widgets['moyens_humains_securite_desc'] is not None:
            moyens_humains.setdefault('securite_chantier', {})['description'] = self.edit_widgets['moyens_humains_securite_desc'].value
        
        if 'moyens_humains_organigramme' in self.edit_widgets and self.edit_widgets['moyens_humains_organigramme'] is not None:
            moyens_humains.setdefault('organigramme', {})['image'] = self.edit_widgets['moyens_humains_organigramme'].value
        
        # Contexte du Projet
        contexte_projet = self.template_data.setdefault('contexte_projet', {})
        
        if 'contexte_date_visite' in self.edit_widgets and self.edit_widgets['contexte_date_visite'] is not None:
            contexte_projet['date_visite_defaut'] = self.edit_widgets['contexte_date_visite'].value
        if 'contexte_intro_visite' in self.edit_widgets and self.edit_widgets['contexte_intro_visite'] is not None:
            contexte_projet['intro_visite'] = self.edit_widgets['contexte_intro_visite'].value
        
        if 'contexte_environnement' in self.edit_widgets and self.edit_widgets['contexte_environnement'] is not None:
            env_str = self.edit_widgets['contexte_environnement'].value
            env_list = [e.strip() for e in env_str.split('/// ou ///') if e.strip()]
            contexte_projet['environnement_options'] = env_list
        
        if 'contexte_acces' in self.edit_widgets and self.edit_widgets['contexte_acces'] is not None:
            contexte_projet['acces_chantier'] = self.edit_widgets['contexte_acces'].value
        
        if 'contexte_levage' in self.edit_widgets and self.edit_widgets['contexte_levage'] is not None:
            contexte_projet['levage_options'] = self.edit_widgets['contexte_levage'].value
        
        if 'contexte_contraintes' in self.edit_widgets and self.edit_widgets['contexte_contraintes'] is not None:
            contexte_projet['contraintes_options'] = self.edit_widgets['contexte_contraintes'].value
        
        # Transport et Levage (nouveau format avec cartes ordonnées)
        transport_levage = self.template_data.setdefault('transport_levage', {})
        
        tl_order_key = '_transport_levage_order_'
        if tl_order_key in self.edit_widgets:
            tl_items = self.edit_widgets[tl_order_key]
            
            # Sauvegarder l'ordre
            transport_levage['_order'] = [item['key'] for item in tl_items]
            
            # Sauvegarder les couleurs
            couleurs = {}
            for item in tl_items:
                couleurs[item['key']] = item.get('couleur', 'ecoBleu')
            transport_levage['couleurs'] = couleurs
            
            # Sauvegarder les noms personnalisés
            noms = {}
            for item in tl_items:
                noms[item['key']] = item.get('nom', item['key'])
            transport_levage['noms'] = noms
            
            # Sauvegarder les contenus
            for item in tl_items:
                key = item['key']
                contenu = item.get('contenu', '')
                
                # Pour certaines clés, mapper vers le bon format
                if key == 'intro':
                    transport_levage['intro'] = contenu if isinstance(contenu, str) else ''
                elif key == 'livraison':
                    transport_levage['livraison_options'] = contenu if isinstance(contenu, list) else []
                elif key == 'levage':
                    transport_levage['levage_options'] = contenu if isinstance(contenu, list) else []
                elif key == 'ouvrages_livres':
                    transport_levage['ouvrages_livres'] = contenu if isinstance(contenu, str) else ''
                elif key == 'encadrement':
                    transport_levage['encadrement'] = contenu if isinstance(contenu, str) else ''
                elif key == 'sous_traitance':
                    transport_levage['sous_traitance'] = contenu if isinstance(contenu, str) else ''
                else:
                    # Clé personnalisée
                    transport_levage[key] = contenu
        
        # Planning
        planning_order_key = '_planning_order_'
        if planning_order_key in self.edit_widgets and isinstance(self.edit_widgets[planning_order_key], dict):
            planning_data = self.edit_widgets[planning_order_key]
            planning = self.template_data.setdefault('planning', {})
            planning['texte'] = planning_data.get('texte', '')
            planning['couleur'] = planning_data.get('couleur', 'ecoBleu')


def render():
    """Point d'entrée pour le rendu de la page."""
    page = DatabasePage()
    page.render()
