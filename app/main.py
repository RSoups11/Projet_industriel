#!/usr/bin/env python3
"""
Application Bois & Techniques - Générateur de Mémoires Techniques
Interface unifiée NiceGUI pour la génération de PDF et la gestion des templates.
"""

from nicegui import ui, app
import os
import sys
import secrets

# Ajouter le dossier parent au path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.config import AppConfig
from app.pages import generation, templates, parametres, assistant


def create_header():
    """Cree le header de l'application."""
    with ui.header().classes('bg-blue-900 text-white items-center justify-between'):
        with ui.row().classes('items-center gap-4'):
            ui.icon('carpenter', size='lg')
            ui.label('BOIS & TECHNIQUES').classes('text-xl font-bold')
        
        with ui.row().classes('gap-2'):
            ui.button('Nouveau memoire', on_click=lambda: ui.navigate.to('/')).props('flat color=white')
            ui.button('Base de donnees', on_click=lambda: ui.navigate.to('/templates')).props('flat color=white')
            ui.button('Parametres', on_click=lambda: ui.navigate.to('/parametres')).props('flat color=white')
            ui.button('Assistant (WIP)', on_click=lambda: ui.navigate.to('/assistant')).props('flat color=white')


def create_footer():
    """Crée le footer de l'application."""
    with ui.footer().classes('bg-gray-100 text-gray-600 text-center py-2'):
        ui.label('© 2025 Bois & Techniques - Générateur de Mémoires Techniques')


@ui.page('/')
def page_generation():
    """Page principale de génération de mémoires."""
    create_header()
    generation.render()
    create_footer()


@ui.page('/templates')
def page_templates():
    """Page de gestion des templates."""
    create_header()
    templates.render()
    create_footer()


@ui.page('/parametres')
def page_parametres():
    """Page des paramètres."""
    create_header()
    parametres.render()
    create_footer()


@ui.page('/assistant')
def page_assistant():
    """Page Assistant WIP: import de PDF."""
    create_header()
    assistant.render()
    create_footer()


def main():
    """Point d'entrée principal de l'application."""
    config = AppConfig()
    
    print(f"\n{'='*60}")
    print("  BOIS & TECHNIQUES - Générateur de Mémoires Techniques")
    print(f"{'='*60}")
    print(f"\n📁 Dossier de sortie PDF : {config.OUTPUT_DIR}")
    print(f"📁 Dossier templates     : {config.TEMPLATES_DIR}")
    print(f"📁 Dossier données CSV   : {config.DATA_DIR}")
    print(f"\n🌐 L'application s'ouvre dans votre navigateur...\n")

    storage_secret = os.environ.get("NICEGUI_STORAGE_SECRET") or secrets.token_urlsafe(32)

    
    ui.run(
        title='Bois & Techniques - Générateur de Mémoires',
        port=8080,
        reload=False,
        show=True,
        native=False,  # Utiliser le navigateur web (pas besoin de GTK/QT)
        storage_secret=storage_secret,
    )


if __name__ in {"__main__", "__mp_main__"}:
    main()
