"""
Configuration centralisée de l'application.
"""

import os
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Dict, Any
import json


@dataclass
class AppConfig:
    """Configuration principale de l'application."""
    
    # Chemins de base
    BASE_DIR: Path = field(default_factory=lambda: Path(__file__).parent.parent.parent)
    
    def __post_init__(self):
        # Dossiers
        self.TEMPLATES_DIR = self.BASE_DIR / "templates"
        self.DATA_DIR = self.BASE_DIR / "data"
        self.OUTPUT_DIR = self.BASE_DIR / "output"
        self.IMAGES_DIR = self.BASE_DIR / "images"
        self.CONFIG_FILE = self.BASE_DIR / "app" / "config.json"
        
        # Fichiers par défaut
        self.DEFAULT_CSV_FILE = self.DATA_DIR / "crack_clean.csv"
        self.DEFAULT_TEMPLATE = self.TEMPLATES_DIR / "template.tex.j2"
        self.DEFAULT_OUTPUT_TEX = self.OUTPUT_DIR / "resultat.tex"
        
        # Templates spéciaux
        self.TEMPLATE_DEMARCHE_HQE = self.TEMPLATES_DIR / "demarche_hqe.tex.j2"
        self.TEMPLATE_DEMARCHE_ENV_ATELIER = self.TEMPLATES_DIR / "demarche_env_atelier.tex.j2"
        self.TEMPLATE_DEMARCHE_ENV_CHANTIERS = self.TEMPLATES_DIR / "demarche_env_chantiers.tex.j2"
        
        # Créer les dossiers si nécessaires
        self.ensure_directories()
        
        # Charger la config utilisateur
        self.user_config = self.load_user_config()
    
    def ensure_directories(self):
        """Crée les dossiers nécessaires s'ils n'existent pas."""
        for directory in [self.TEMPLATES_DIR, self.DATA_DIR, self.OUTPUT_DIR]:
            directory.mkdir(parents=True, exist_ok=True)
    
    def load_user_config(self) -> Dict[str, Any]:
        """Charge la configuration utilisateur depuis le fichier JSON."""
        if self.CONFIG_FILE.exists():
            try:
                with open(self.CONFIG_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                pass
        return self.get_default_user_config()
    
    def save_user_config(self, config: Dict[str, Any]):
        """Sauvegarde la configuration utilisateur."""
        self.user_config = config
        with open(self.CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
    
    def get_default_user_config(self) -> Dict[str, Any]:
        """Retourne la configuration par défaut."""
        return {
            "defaults": {
                "intitule": "",
                "lot": "Lot N02 - Charpente bois",
                "moa": "",
                "adresse": ""
            },
            "sections_autorisees": [
                "SITUATION ADMINISTRATIVE DE L'ENTREPRISE",
                "CONTEXTE DU PROJET",
                "MOYENS HUMAINS AFFECTES AU PROJET",
                "MOYENS MATERIEL AFFECTES AU PROJET",
                "LISTE DES MATERIAUX",
                "METHODOLOGIE ET CHRONOLOGIE",
                "PLANNING",
                "CHANTIER REFERENCES",
                "PERFORMANCES ENVIRONNEMENTALES"
            ],
            "pdflatex_path": "pdflatex",
            "theme": "light"
        }


# Labels pour l'interface
FIELD_LABELS = {
    "intitule": "Intitulé de l'opération",
    "lot": "Intitulé du lot",
    "moa": "Maître d'ouvrage",
    "adresse": "Adresse du chantier"
}

# Sections avec leurs icônes
SECTION_ICONS = {
    "SITUATION ADMINISTRATIVE DE L'ENTREPRISE": "business",
    "CONTEXTE DU PROJET": "location_on",
    "LISTE DES MATERIAUX MIS EN OEUVRE": "inventory",
    "MOYENS HUMAINS AFFECTES AU PROJET": "groups",
    "MOYENS MATERIEL AFFECTES AU PROJET": "construction",
    "Méthodologie / Chronologie": "timeline",
    "Chantiers références en rapport avec l'opération": "work_history",
    "Planning": "calendar_month",
    "Annexes": "attachment"
}
