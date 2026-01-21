import os
import subprocess
import re
from typing import Callable, Optional
import jinja2
import pandas as pd

def markdown_to_latex(texte: str) -> str:
    """Convertit les patterns markdown en LaTeX: **texte** -> \\textbf{texte}"""
    if not texte:
        return texte
    texte = re.sub(r'\*\*([^*]+)\*\*', r'\\textbf{\1}', texte)
    return texte

class MemoireGenerator:
    def __init__(self, assets_dir: str = None):
        self.assets_dir = assets_dir or resource_path('assets')
        self.templates_dir = os.path.join(self.assets_dir, 'templates')
        self.data_csv = os.path.join(self.assets_dir, 'data.csv')
        self.env = jinja2.Environment(
            loader=jinja2.FileSystemLoader(self.templates_dir),
            autoescape=False
        )
        # Registrar filtro markdown_to_latex
        self.env.filters['markdown_to_latex'] = markdown_to_latex

    def generate_pdf(self, data_dict: dict, output_path: str, callback: Optional[Callable[[str], None]] = None) -> bool:
        try:
            if callback:
                callback('Chargement du template LaTeX...')
            template = self.env.get_template('template.tex')
            if callback:
                callback('Rendu du document LaTeX...')
            rendered_tex = template.render(**data_dict)
            tex_path = output_path.replace('.pdf', '.tex')
            with open(tex_path, 'w', encoding='utf-8') as f:
                f.write(rendered_tex)
            if callback:
                callback('Compilation PDF avec pdflatex...')
            result = subprocess.run([
                'pdflatex', '-interaction=nonstopmode', '-output-directory', os.path.dirname(output_path), tex_path
            ], capture_output=True, text=True)
            if result.returncode != 0:
                if callback:
                    callback('Erreur LaTeX :\n' + result.stderr)
                return False
            if callback:
                callback('PDF généré avec succès.')
            return True
        except Exception as e:
            if callback:
                callback(f'Erreur inattendue : {e}')
            return False

def resource_path(relative_path: str) -> str:
    """Get absolute path to resource, works for dev and for PyInstaller bundle."""
    try:
        base_path = sys._MEIPASS  # type: ignore
    except Exception:
        base_path = os.path.abspath('.')
    return os.path.join(base_path, relative_path)
