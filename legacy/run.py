#!/usr/bin/env python3
"""
Script de lancement rapide de l'application.
"""

import subprocess
import sys
import os

def main():
    # S'assurer d'être dans le bon répertoire
    app_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(app_dir)
    
    # Vérifier les dépendances
    try:
        import nicegui
    except ImportError:
        print("Installation des dépendances...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
    
    # Lancer l'application
    from main import main as run_app
    run_app()

if __name__ == "__main__":
    main()
