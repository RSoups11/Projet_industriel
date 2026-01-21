import re

with open('resultat.tex', 'r', encoding='utf-8') as f:
    content = f.read()

# Trouver et remplacer la section DEMARCHE HQE
pattern_hqe = r'(    \\subsection\{ DEMARCHE HQE \}.*?)(?=    \\subsection\{ DEMARCHE ENVIRONNEMENTALE : ATELIER)'
replacement_hqe = '''    % Inclusion du fichier spécial pour la démarche HQE
    \\input{demarche_hqe_generated.tex}
    
    '''

content = re.sub(pattern_hqe, replacement_hqe, content, flags=re.DOTALL)

# Trouver et remplacer la section DEMARCHE ENVIRONNEMENTALE : ATELIER & BUREAUX
pattern_atelier = r'(    \\subsection\{ DEMARCHE ENVIRONNEMENTALE : ATELIER & BUREAUX \}.*?)(?=    \\subsection\{ DEMARCHE ENVIRONNEMENTALE : SUR LES CHANTIERS \})'
replacement_atelier = '''    % Inclusion du fichier spécial pour la démarche environnementale atelier
    \\input{demarche_env_atelier_generated.tex}
    
    '''

content = re.sub(pattern_atelier, replacement_atelier, content, flags=re.DOTALL)

# Trouver et remplacer la section DEMARCHE ENVIRONNEMENTALE : SUR LES CHANTIERS
pattern_chantiers = r'(    \\subsection\{ DEMARCHE ENVIRONNEMENTALE : SUR LES CHANTIERS \}.*?)(?=    \\subsection\{ Respect des délais)'
replacement_chantiers = '''    % Inclusion du fichier spécial pour la démarche environnementale chantiers
    \\input{demarche_env_chantiers_generated.tex}
    
    '''

content = re.sub(pattern_chantiers, replacement_chantiers, content, flags=re.DOTALL)

with open('resultat.tex', 'w', encoding='utf-8') as f:
    f.write(content)

print("Sections remplacées avec succès")
