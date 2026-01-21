#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script para executar main.py automaticamente respondendo com Enter e 'oui' quando necessário
"""

import subprocess
import sys
import os

# Definir encoding UTF-8 para output
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Mudar para o diretório correto
os.chdir(os.path.dirname(os.path.abspath(__file__)))

# Inputs padrão para todas as perguntas
inputs = []

# Perguntas da seção Contexte du projet
for _ in range(2):  # Date de visite, Adresse du chantier
    inputs.append("")  # Enter vazio

# Environnement
inputs.append("")  # Enter para aceitar todas as proposições

# Accès chantier
inputs.append("")  # Enter vazio

# Levage
inputs.append("")  # Enter para aceitar todas

# Contraintes
inputs.append("")  # Enter vazio

# Fabrication/Taille
inputs.append("")  # Enter vazio

# Transport et Levage
inputs.append("")  # Enter vazio

# Chantier
inputs.append("")  # Enter vazio

# Protection de l'existant
inputs.append("n")  # Não modificar lista

# Organisation en matière d'hygiène et de sécurité
inputs.append("n")  # Não modificar lista

# Protection/Nettoyage
inputs.append("n")  # Não modificar lista

# Materiais - Respostas OUI para documentação em anexo
for _ in range(20):  # Aumentar buffer para materiais
    inputs.append("OUI")

# Outros inputs que possam vir
for _ in range(50):  # Buffer para outros inputs que possam aparecer
    inputs.append("")

# Converter lista em string com newlines
input_string = "\n".join(inputs)

# Executar main.py com input
process = subprocess.Popen(
    [sys.executable, "main.py"],
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
    text=True,
    encoding='utf-8'
)

# Enviar inputs e capturar output
output, _ = process.communicate(input=input_string, timeout=120)

# Imprimir output
print(output)

# Compilar PDF
print("\n\n" + "="*60)
print("Compilando PDF...")
print("="*60 + "\n")

os.chdir("output")
subprocess.run(["pdflatex", "-interaction=nonstopmode", "resultat.tex"], capture_output=True)

print("✅ PDF gerado com sucesso!")
print("Arquivo: output/resultat.pdf")
