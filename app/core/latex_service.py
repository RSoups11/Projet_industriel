"""
Service de génération LaTeX et PDF.
"""

import os
import re
import subprocess
from pathlib import Path
from typing import Dict, List, Any, Optional, Callable
import jinja2


class LaTeXService:
    """Service pour générer des fichiers LaTeX et les compiler en PDF."""
    
    def __init__(self, templates_dir: Path, output_dir: Path):
        self.templates_dir = templates_dir
        self.output_dir = output_dir
        self.env = jinja2.Environment(
            loader=jinja2.FileSystemLoader(str(templates_dir)),
            autoescape=False,
        )
        # Ajouter le filtre pour convertir markdown bold en LaTeX
        self.env.filters['markdown_to_latex'] = self.markdown_to_latex
        # Ajouter le filtre pour échapper les caractères LaTeX
        self.env.filters['escape_latex'] = self.escape_latex_filter
        # Ajouter le filtre pour normaliser texte (sans accents, minuscules)
        self.env.filters['normalize'] = self.normalize_text
    
    @staticmethod
    def escape_latex_filter(texte: str) -> str:
        """Filtre Jinja2 pour échapper les caractères spéciaux LaTeX."""
        if not texte:
            return texte
        # Échapper les caractères spéciaux LaTeX
        replacements = [
            ('&', r'\&'),
            ('%', r'\%'),
            ('$', r'\$'),
            ('#', r'\#'),
            ('_', r'\_'),
        ]
        for old, new in replacements:
            texte = texte.replace(old, new)
        return texte
    
    @staticmethod
    def normalize_text(texte: str) -> str:
        """Normalise le texte: minuscules, sans accents pour comparaisons."""
        if not texte:
            return texte
        # Convertir en minuscules
        texte = texte.lower()
        # Remplacer les accents
        accents = {
            'à': 'a', 'â': 'a', 'ä': 'a', 'á': 'a',
            'è': 'e', 'ê': 'e', 'ë': 'e', 'é': 'e',
            'ì': 'i', 'î': 'i', 'ï': 'i', 'í': 'i',
            'ò': 'o', 'ô': 'o', 'ö': 'o', 'ó': 'o',
            'ù': 'u', 'û': 'u', 'ü': 'u', 'ú': 'u',
            'ç': 'c', 'ñ': 'n'
        }
        for accent, sans in accents.items():
            texte = texte.replace(accent, sans)
        return texte
    
    @staticmethod
    def markdown_to_latex(texte: str) -> str:
        """Convertit les patterns markdown en LaTeX: **texte** -> \\textbf{texte}"""
        if not texte:
            return texte
        # Remplacer **texte** par \textbf{texte}
        texte = re.sub(r'\*\*([^*]+)\*\*', r'\\textbf{\1}', texte)
        return texte
    
    @staticmethod
    def echapper_latex(texte: str) -> str:
        """
        Échappe les caractères spéciaux LaTeX de manière sécurisée.
        Préserve les commandes LaTeX existantes (commençant par \).
        Convertit aussi les patterns "img : chemin" en inclusion d'image LaTeX.
        """
        if not texte:
            return texte
        
        # Protéger les commandes LaTeX légitimes temporairement
        # Capture \cmd ou \cmd{...} ou \cmd[...] 
        latex_commands = []
        def protect_latex_cmd(match):
            idx = len(latex_commands)
            latex_commands.append(match.group(0))
            return f"<<<LATEX_CMD_{idx}>>>"
        
        # Protéger \begin, \end, \item, \textbf, etc.
        texte = re.sub(r'\\(?:begin|end|item|text[a-z]+|includegraphics|hline|&|%)[^{]*(?:\{[^}]*\})?', protect_latex_cmd, texte)
        
        # Pattern pour capturer les chemins d'images
        img_pattern = re.compile(r'img\s*:\s*([^\n]+?)(?:\n|$)', re.IGNORECASE)
        
        images_trouvees = []
        def remplacer_img(match):
            chemin = match.group(1).strip()
            if not chemin.lower().endswith(('.png', '.jpg', '.jpeg', '.pdf')):
                chemin = chemin + '.png'
            idx = len(images_trouvees)
            images_trouvees.append(chemin)
            return f"<<<IMG_PLACEHOLDER_{idx}>>>\n"
        
        texte = img_pattern.sub(remplacer_img, texte)
        
        # Échappement des caractères spéciaux (sauf \ qui est gérée différemment)
        replacements = [
            ('&', r'\&'),
            ('%', r'\%'),
            ('$', r'\$'),
            ('#', r'\#'),
            ('_', r'\_'),
            ('{', r'\{'),
            ('}', r'\}'),
            ('~', r'\textasciitilde{}'),
            ('^', r'\textasciicircum{}'),
        ]
        
        for old, new in replacements:
            texte = texte.replace(old, new)
        
        # Restaurer les commandes LaTeX
        for idx, cmd in enumerate(latex_commands):
            texte = texte.replace(f"<<<LATEX_CMD_{idx}>>>", cmd)
        
        # Remettre les images avec le code LaTeX approprié
        for idx, chemin in enumerate(images_trouvees):
            latex_img = f"\n\\begin{{center}}\n    \\includegraphics[width=0.9\\textwidth]{{{chemin}}}\n\\end{{center}}\n"
            texte = texte.replace(f"<<<IMG_PLACEHOLDER_{idx}>>>", latex_img)
        
        return texte
    
    def convertir_fixation_en_tableau(self, texte: str) -> str:
        """
        # ==============================================================================
        # ANCIENNE FONCTION - NON UTILISÉE
        # La version utilisée est dans src/table_converters.py
        # ==============================================================================
        """
        if not texte:
            return ""
        
        lignes = texte.strip().split('\n')
        lignes_tableau = []
        
        for ligne in lignes:
            ligne = ligne.strip()
            if not ligne:
                continue
            
            # Parser "Élément : Description"
            if ':' in ligne:
                parts = ligne.split(':', 1)
                element = self.echapper_latex(parts[0].strip())
                description = self.echapper_latex(parts[1].strip()) if len(parts) > 1 else ""
                lignes_tableau.append(f"        {element} & {description} \\\\")
            else:
                lignes_tableau.append(f"        {self.echapper_latex(ligne)} & \\\\")
        
        if not lignes_tableau:
            return ""
        
        tableau = """\\begin{tabular}{|l|p{10cm}|}
    \\hline
    \\textbf{Élément} & \\textbf{Description} \\\\
    \\hline
""" + "\n        \\hline\n".join(lignes_tableau) + """
    \\hline
\\end{tabular}"""
        
        return tableau
    
    def convertir_traitement_en_tableau(self, texte: str) -> str:
        """
        # ==============================================================================
        # ANCIENNE FONCTION - NON UTILISÉE
        # La version utilisée est dans src/table_converters.py
        # ==============================================================================
        """
        if not texte:
            return ""
        
        lignes = texte.strip().split('\n')
        lignes_tableau = []
        
        for ligne in lignes:
            ligne = ligne.strip()
            if not ligne:
                continue
            
            if ':' in ligne:
                parts = ligne.split(':', 1)
                type_trait = self.echapper_latex(parts[0].strip())
                description = self.echapper_latex(parts[1].strip()) if len(parts) > 1 else ""
                lignes_tableau.append(f"        {type_trait} & {description} \\\\")
            else:
                lignes_tableau.append(f"        {self.echapper_latex(ligne)} & \\\\")
        
        if not lignes_tableau:
            return ""
        
        tableau = """\\begin{tabular}{|l|p{10cm}|}
    \\hline
    \\textbf{Type} & \\textbf{Traitement} \\\\
    \\hline
""" + "\n        \\hline\n".join(lignes_tableau) + """
    \\hline
\\end{tabular}"""
        
        return tableau
    
    def generer_tex(
        self, 
        data: List[Dict[str, Any]], 
        infos_projet: Dict[str, str],
        images: Optional[Dict[str, str]] = None,
        template_name: str = "template_v2.tex.j2",
        output_filename: str = "resultat.tex",
        template_data: Optional[Dict[str, Any]] = None,
        couleurs_sections: Optional[Dict[str, str]] = None
    ) -> Path:
        """
        Génère un fichier .tex à partir du template et des données.
        
        Args:
            data: Liste de sections avec sous_sections
            infos_projet: Infos de la page de garde
            images: Chemins des images
            template_name: Nom du template Jinja2
            output_filename: Nom du fichier de sortie
            template_data: Données pour les sous-templates (situation_admin, etc.)
            couleurs_sections: Couleurs par section
        
        Returns:
            Path du fichier généré
        """
        if images is None:
            images = {}
        if template_data is None:
            template_data = {}
        if couleurs_sections is None:
            couleurs_sections = {}
        
        template = self.env.get_template(template_name)
        
        contexte = {
            "data": data,
            "Intitule_operation": infos_projet.get("Intitule_operation", ""),
            "Lot_Intitule": infos_projet.get("Lot_Intitule", ""),
            "Maitre_ouvrage_nom": infos_projet.get("Maitre_ouvrage_nom", ""),
            "Adresse_chantier": infos_projet.get("Adresse_chantier", ""),
            "image_garde": images.get("image_garde", ""),
            "attestation_visite": images.get("attestation_visite", ""),
            "plan_emplacement": images.get("plan_emplacement", ""),
            "image_grue": images.get("image_grue", ""),
            # Données des sous-templates
            "situation_admin": template_data.get("situation_administrative", {}),
            "securite_sante": template_data.get("securite_sante", {}),
            "moyens_materiel": template_data.get("moyens_materiel", {}),
            "demarche_hqe": template_data.get("demarche_hqe", {}),
            "demarche_env_atelier": template_data.get("demarche_env_atelier", {}),
            "demarche_env_chantiers": template_data.get("demarche_env_chantiers", {}),
            "matiere_premiere": template_data.get("matiere_premiere", {}),
            "methodologie_traitement": template_data.get("methodologie_traitement", {}),
            "planning": template_data.get("planning", {}),
            # Préambule: peut être une chaîne ou un dict avec "texte"
            "preambule": template_data.get("preambule", "") if isinstance(template_data.get("preambule"), str) else template_data.get("preambule", {}).get("texte", ""),
            # Couleurs dynamiques pour les sections
            "situation_admin_couleur": couleurs_sections.get("SITUATION ADMINISTRATIVE", "ecoBleu"),
            "securite_sante_couleur": couleurs_sections.get("SECURITE_SANTE", couleurs_sections.get("MOYENS HUMAINS", "ecoBleu")),
            "moyens_materiel_couleur": couleurs_sections.get("MOYENS MATERIEL", "ecoBleu"),
            "planning_couleur": couleurs_sections.get("PLANNING", "ecoBleu"),
        }
        
        resultat_tex = template.render(**contexte)
        
        output_path = self.output_dir / output_filename
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(resultat_tex)
        
        return output_path
    
    def compiler_pdf(
        self, 
        tex_path: Path,
        callback: Optional[Callable[[str], None]] = None
    ) -> tuple[bool, str]:
        """
        Compile un fichier .tex en PDF avec pdflatex.
        
        Args:
            tex_path: Chemin du fichier .tex
            callback: Fonction de callback pour les messages de progression
        
        Returns:
            Tuple (success, message)
        """
        if callback:
            callback("Compilation PDF en cours...")
        
        output_dir = tex_path.parent
        
        try:
            # Deux passes pour les références
            for i in range(2):
                if callback:
                    callback(f"Compilation pdflatex (passe {i+1}/2)...")
                
                result = subprocess.run(
                    [
                        'pdflatex',
                        '-interaction=nonstopmode',
                        '-output-directory', str(output_dir),
                        str(tex_path)
                    ],
                    capture_output=True,
                    text=False,  # Utiliser bytes pour eviter les erreurs d'encodage
                    cwd=str(output_dir),
                    timeout=120
                )
                
                if result.returncode != 0 and i == 1:
                    # Log l'erreur mais continue (souvent warnings non bloquants)
                    try:
                        stdout = result.stdout.decode('utf-8', errors='replace')
                    except:
                        stdout = str(result.stdout)
                    error_lines = [l for l in stdout.split('\n') if '!' in l]
                    if error_lines:
                        return False, "Erreur LaTeX:\n" + "\n".join(error_lines[:5])
            
            pdf_path = tex_path.with_suffix('.pdf')
            if pdf_path.exists():
                if callback:
                    callback(f"PDF généré avec succès: {pdf_path}")
                return True, str(pdf_path)
            else:
                return False, "Le fichier PDF n'a pas été créé"
        
        except subprocess.TimeoutExpired:
            return False, "Timeout lors de la compilation (>120s)"
        except FileNotFoundError:
            return False, "pdflatex non trouvé. Veuillez installer TexLive."
        except Exception as e:
            return False, f"Erreur inattendue: {str(e)}"
    
    def nettoyer_fichiers_temp(self, base_path: Path):
        """Supprime les fichiers temporaires LaTeX."""
        extensions = ['.aux', '.log', '.out', '.toc', '.lof', '.lot', '.fls', '.fdb_latexmk']
        for ext in extensions:
            temp_file = base_path.with_suffix(ext)
            if temp_file.exists():
                temp_file.unlink()
