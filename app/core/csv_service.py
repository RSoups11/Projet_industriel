"""
Service de gestion des fichiers CSV.
"""

import csv
import pandas as pd
from pathlib import Path
from collections import defaultdict
from typing import List, Dict, Any, Optional
import re
import unicodedata


class CSVService:
    """Service pour charger et manipuler les fichiers CSV."""
    
    def __init__(self, csv_path: Optional[Path] = None):
        self.csv_path = csv_path
        self._data: Optional[pd.DataFrame] = None
    
    @staticmethod
    def normaliser_texte(s: str) -> str:
        """
        Normalise un texte pour comparaison :
        - remplace les retours à la ligne par des espaces
        - remplace les apostrophes courbes
        - enlève les accents
        - compresse les espaces multiples
        - passe en minuscules
        """
        if s is None:
            return ""
        s = s.replace("\n", " ")
        s = s.replace("\u2019", "'").replace("\u2018", "'")
        s = s.strip().lower()
        s = unicodedata.normalize("NFD", s)
        s = "".join(c for c in s if unicodedata.category(c) != "Mn")
        s = re.sub(r"\s+", " ", s)
        return s
    
    @staticmethod
    def normaliser_titre(titre: str) -> str:
        """Normalise un titre pour comparaison stricte."""
        s = CSVService.normaliser_texte(titre)
        if not s:
            return ""
        s = s.replace('Œ', 'OE').replace('œ', 'oe')
        return re.sub(r'[^a-zA-Z0-9]', '', s).upper()
    
    @staticmethod
    def nettoyer_str(valeur) -> str:
        """Nettoie une valeur string."""
        if pd.isna(valeur):
            return ""
        s = str(valeur).strip()
        return "" if s.lower() == "nan" else s
    
    def charger_csv(self, csv_path: Optional[Path] = None) -> pd.DataFrame:
        """Charge un fichier CSV et retourne un DataFrame."""
        path = csv_path or self.csv_path
        if not path:
            raise ValueError("Aucun chemin CSV spécifie")
        
        # Essayer differents encodages
        encodings = ['utf-8', 'latin-1', 'iso-8859-1', 'cp1252']
        df = None
        
        for encoding in encodings:
            try:
                df = pd.read_csv(
                    path, 
                    sep=";", 
                    dtype=str, 
                    encoding=encoding, 
                    on_bad_lines='skip'
                )
                break  # Succes, on sort de la boucle
            except UnicodeDecodeError:
                continue  # Essayer l'encodage suivant
        
        if df is None:
            raise ValueError(f"Impossible de lire le fichier CSV avec les encodages: {encodings}")
        
        df = df.fillna("")
        df.columns = df.columns.str.strip().str.lower()
        
        # Ajouter la colonne normalisée
        if 'section' in df.columns:
            df['section_norm'] = df['section'].apply(self.normaliser_titre)
        
        self._data = df
        return df
    
    def get_sections_hierarchiques(self, df: Optional[pd.DataFrame] = None) -> List[Dict[str, Any]]:
        """
        # ==============================================================================
        # ANCIENNE FONCTION - NON UTILISÉE
        # Transforme le DataFrame en structure hiérarchique.
        # Le chargement est fait directement avec pd.read_csv() dans les pages.
        # ==============================================================================
        """
        if df is None:
            df = self._data
        if df is None:
            return []
        
        sections = defaultdict(list)
        
        for _, row in df.iterrows():
            section_nom = self.nettoyer_str(row.get("section", ""))
            sous_section_nom = self.nettoyer_str(row.get("sous-section", ""))
            texte = self.nettoyer_str(row.get("texte", ""))
            image = self.nettoyer_str(row.get("image", "")) or None
            
            if not sous_section_nom:
                titre_norm = self.normaliser_texte(section_nom)
                if "chantiers references en rapport avec l'operation" in titre_norm:
                    sous_section_nom = "Références"
                else:
                    continue
            
            sections[section_nom].append({
                "nom": sous_section_nom,
                "contenu": texte,
                "contenu_brut": texte,
                "image": image,
            })
        
        return [
            {"titre": titre, "sous_sections": sous_secs}
            for titre, sous_secs in sections.items()
        ]
    
    def get_sections_par_titre(self, df: pd.DataFrame, titres_autorises: List[str]) -> Dict[str, pd.DataFrame]:
        """
        # ==============================================================================
        # ANCIENNE FONCTION - NON UTILISÉE
        # Retourne un dict de DataFrames groupés par section autorisée.
        # ==============================================================================
        """
        result = {}
        for titre in titres_autorises:
            titre_norm = self.normaliser_titre(titre)
            rows = df[df['section_norm'] == titre_norm]
            if not rows.empty:
                result[titre] = rows
        return result
    
    def sauvegarder_csv(self, df: pd.DataFrame, output_path: Path):
        """
        # ==============================================================================
        # ANCIENNE FONCTION - NON UTILISÉE
        # Sauvegarde faite directement avec df.to_csv() dans les pages.
        # ==============================================================================
        """
        df.to_csv(output_path, sep=";", index=False, encoding='utf-8')
    
    def ajouter_ligne(self, df: pd.DataFrame, section: str, sous_section: str, 
                      texte: str, image: str = "") -> pd.DataFrame:
        """
        # ==============================================================================
        # ANCIENNE FONCTION - NON UTILISÉE
        # Ajout fait directement avec pd.concat() dans les pages.
        # ==============================================================================
        """
        nouvelle_ligne = pd.DataFrame([{
            'section': section,
            'sous-section': sous_section,
            'texte': texte,
            'image': image
        }])
        return pd.concat([df, nouvelle_ligne], ignore_index=True)
    
    def modifier_ligne(self, df: pd.DataFrame, index: int, 
                       **kwargs) -> pd.DataFrame:
        """
        # ==============================================================================
        # ANCIENNE FONCTION - NON UTILISÉE  
        # ==============================================================================
        """
        for col, val in kwargs.items():
            if col in df.columns:
                df.at[index, col] = val
        return df
    
    def supprimer_ligne(self, df: pd.DataFrame, index: int) -> pd.DataFrame:
        """
        # ==============================================================================
        # ANCIENNE FONCTION - NON UTILISÉE
        # ==============================================================================
        """
        return df.drop(index).reset_index(drop=True)
