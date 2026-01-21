"""
Service de gestion des templates.
"""

import os
import re
from pathlib import Path
from typing import Dict, List, Any, Optional
import jinja2


class TemplateService:
    """Service pour gérer et modifier les templates LaTeX/Jinja2."""
    
    def __init__(self, templates_dir: Path):
        self.templates_dir = templates_dir
    
    def lister_templates(self) -> List[Dict[str, Any]]:
        """Liste tous les templates disponibles."""
        templates = []
        
        for file in self.templates_dir.glob("*.tex.j2"):
            templates.append({
                "nom": file.stem.replace(".tex", ""),
                "fichier": file.name,
                "chemin": str(file),
                "type": "jinja2",
                "taille": file.stat().st_size,
                "modifie": file.stat().st_mtime
            })
        
        for file in self.templates_dir.glob("*.tex"):
            if not file.name.endswith(".tex.j2"):
                templates.append({
                    "nom": file.stem,
                    "fichier": file.name,
                    "chemin": str(file),
                    "type": "latex",
                    "taille": file.stat().st_size,
                    "modifie": file.stat().st_mtime
                })
        
        return sorted(templates, key=lambda x: x["nom"])
    
    def lire_template(self, nom_fichier: str) -> str:
        """Lit le contenu d'un template."""
        chemin = self.templates_dir / nom_fichier
        if not chemin.exists():
            raise FileNotFoundError(f"Template non trouvé: {nom_fichier}")
        
        with open(chemin, 'r', encoding='utf-8') as f:
            return f.read()
    
    def sauvegarder_template(self, nom_fichier: str, contenu: str):
        """Sauvegarde un template."""
        chemin = self.templates_dir / nom_fichier
        
        # Backup automatique
        if chemin.exists():
            backup_path = chemin.with_suffix(chemin.suffix + ".bak")
            with open(chemin, 'r', encoding='utf-8') as f:
                with open(backup_path, 'w', encoding='utf-8') as fb:
                    fb.write(f.read())
        
        with open(chemin, 'w', encoding='utf-8') as f:
            f.write(contenu)
    
    def creer_template(self, nom: str, contenu: str = "", type_template: str = "jinja2"):
        """Crée un nouveau template."""
        extension = ".tex.j2" if type_template == "jinja2" else ".tex"
        nom_fichier = nom + extension
        chemin = self.templates_dir / nom_fichier
        
        if chemin.exists():
            raise FileExistsError(f"Le template {nom_fichier} existe déjà")
        
        with open(chemin, 'w', encoding='utf-8') as f:
            f.write(contenu)
        
        return nom_fichier
    
    def supprimer_template(self, nom_fichier: str):
        """Supprime un template (avec backup)."""
        chemin = self.templates_dir / nom_fichier
        if not chemin.exists():
            raise FileNotFoundError(f"Template non trouvé: {nom_fichier}")
        
        # Backup avant suppression
        backup_dir = self.templates_dir / ".trash"
        backup_dir.mkdir(exist_ok=True)
        backup_path = backup_dir / nom_fichier
        
        chemin.rename(backup_path)
    
    def extraire_variables(self, contenu: str) -> List[str]:
        """Extrait les variables Jinja2 d'un template."""
        # Pattern pour {{ variable }} et {% for item in variable %}
        pattern_var = r'\{\{\s*(\w+)'
        pattern_loop = r'\{%\s*for\s+\w+\s+in\s+(\w+)'
        
        variables = set()
        variables.update(re.findall(pattern_var, contenu))
        variables.update(re.findall(pattern_loop, contenu))
        
        # Filtrer les variables système Jinja2
        system_vars = {'loop', 'range', 'true', 'false', 'none'}
        return sorted(variables - system_vars)
    
    def extraire_sections(self, contenu: str) -> List[Dict[str, Any]]:
        """Extrait les sections LaTeX d'un template."""
        sections = []
        
        # Pattern pour \section{...} et \subsection{...}
        pattern = r'\\(section|subsection|subsubsection)\{([^}]+)\}'
        
        for match in re.finditer(pattern, contenu):
            sections.append({
                "type": match.group(1),
                "titre": match.group(2),
                "position": match.start()
            })
        
        return sections
    
    def valider_syntaxe_jinja(self, contenu: str) -> tuple[bool, Optional[str]]:
        """Valide la syntaxe Jinja2 d'un template."""
        try:
            env = jinja2.Environment()
            env.parse(contenu)
            return True, None
        except jinja2.TemplateSyntaxError as e:
            return False, f"Erreur ligne {e.lineno}: {e.message}"
    
    def remplacer_section(
        self, 
        contenu: str, 
        pattern_debut: str, 
        pattern_fin: str, 
        remplacement: str
    ) -> str:
        """
        Remplace une section du template entre deux patterns.
        Utile pour les sections dynamiques (HQE, environnement, etc.)
        """
        pattern = f'({re.escape(pattern_debut)}).*?(?={re.escape(pattern_fin)})'
        return re.sub(pattern, remplacement, contenu, flags=re.DOTALL)
    
    def inserer_input(self, contenu: str, position_pattern: str, fichier_input: str) -> str:
        """
        Insère un \\input{fichier} à une position donnée.
        """
        input_cmd = f"\\input{{{fichier_input}}}"
        return contenu.replace(position_pattern, f"{position_pattern}\n    {input_cmd}")
