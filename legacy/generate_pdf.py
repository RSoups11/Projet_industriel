import jinja2
import subprocess
import os
import sys
import re
import pdf_data_extractor

# Configurations
NOM_TEMPLATE = 'template.tex.j2'
NOM_FICHIER_TEX_FINAL = 'rapport_final.tex'
COMPILATEUR = 'pdflatex'

def markdown_to_latex(texte: str) -> str:
    """Convertit les patterns markdown en LaTeX: **texte** -> \\textbf{texte}"""
    if not texte:
        return texte
    texte = re.sub(r'\*\*([^*]+)\*\*', r'\\textbf{\1}', texte)
    return texte

def generer_fichier_tex(data):
    print(f"Étape 1 : Rendu du template '{NOM_TEMPLATE}' en '{NOM_FICHIER_TEX_FINAL}'")

    latex_jinja_env = jinja2.Environment(
        block_start_string='{%',
        block_end_string='%}',
        variable_start_string='{{',
        variable_end_string='}}',
        loader=jinja2.FileSystemLoader(os.path.abspath('.')),
        autoescape=False
    )
    # Registrar filtro markdown_to_latex
    latex_jinja_env.filters['markdown_to_latex'] = markdown_to_latex

    try:
        template = latex_jinja_env.get_template(NOM_TEMPLATE)
        latex_output = template.render(data)

        with open(NOM_FICHIER_TEX_FINAL, 'w', encoding='utf-8') as f:
            f.write(latex_output)

        print("Fichier .tex généré avec succès.")
        return True

    except jinja2.exceptions.TemplateNotFound:
        print(f"Le template '{NOM_TEMPLATE}' est introuvable.")
        return False
    except Exception as e:
        print(f"Erreur Jinja2 : {e}")
        return False

def compiler_latex(nom_fichier_tex):
    print(f"\nÉtape 2 : Compilation LaTeX de {nom_fichier_tex}")

    commande = [
        COMPILATEUR,
        '-interaction=nonstopmode',
        '-output-directory=' + os.path.dirname(os.path.abspath(nom_fichier_tex)),
        nom_fichier_tex
    ]

    for i in range(1, 3):
        print(f"-> Compilation LaTeX {i}/2...")
        try:
            subprocess.run(
                commande,
                check=True,
                capture_output=True,
                text=True,
                encoding='latin-1',
                timeout=30
            )
        except subprocess.CalledProcessError as e:
            print(f"Erreur LaTeX (passe {i}) : {e.stderr[:400]}")
            return False
        except FileNotFoundError:
            print("Compilateur pdflatex introuvable. Installez TeX Live ou MikTeX.")
            return False
        except subprocess.TimeoutExpired:
            print("Compilation trop longue. Arrêt forcé.")
            return False

    print(f"Compilation LaTeX réussie : {os.path.splitext(nom_fichier_tex)[0]}.pdf")
    return True

# Programme Principal
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage : python generate_pdf.py fichier1.pdf fichier2.pdf ...")
        sys.exit(1)

    chemins = sys.argv[1:]
    print(f"Chargement des documents PDF : {chemins}")

    data_projet = pdf_data_extractor.extraire_depuis_plusieurs_pdfs(chemins)

    if generer_fichier_tex(data_projet):
        compiler_latex(NOM_FICHIER_TEX_FINAL)
