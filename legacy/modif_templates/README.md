# 📋 Générateur de Mémoire Technique - Interface Web

## 🚀 Démarrage

### Prérequis
- Python 3.8+
- Virtual environment activé

```bash
# Activer le venv
source venv/bin/activate

# Installer les dépendances (si nécessaire)
pip install streamlit jinja2
```

### Lancement de l'application

```bash
cd modif_templates
streamlit run app.py
```

L'application s'ouvrira automatiquement dans votre navigateur à l'adresse : `http://localhost:8501`

---

## 📚 Fonctionnalités

### 🏗️ Sections disponibles

L'interface web vous permet de générer et modifier 9 sections techniques du mémoire technique :

| Onglet | Contenu | Fichier généré |
|--------|---------|----------------|
| **Administratif** | Qualifications, effectif, chiffre d'affaires | `situation_administrative_generated.tex` |
| **Moyens Matériel** | Parc matériel, équipements, sécurité | `moyens_materiel_generated.tex` |
| **Matière Première** | Certifications, labels, fournisseurs | `matiere_premiere_generated.tex` |
| **Sécurité & Santé** | Conditions de travail, prévention | `securite_sante_generated.tex` |
| **Env. Chantiers** | Gestion déchets, tri collectif | `demarche_env_chantiers_generated.tex` |
| **Env. Atelier** | Démarche environnementale en atelier | `demarche_env_atelier_generated.tex` |
| **HQE** | Haute Qualité Environnementale | `demarche_hqe_generated.tex` |
| **Traitement** | Méthodologie de traitement bois | `methodologie_traitement_generated.tex` |
| **Organigramme** | Structure organisationnelle | `organigramme.tex` |

---

## 🔄 Synchronisation automatique

### ⚡ Double sauvegarde

Quand vous modifiez et générez une section via l'interface, les fichiers sont automatiquement sauvegardés dans **deux emplacements** :

1. **Local** : `modif_templates/output_tex/`
2. **Principal** : `../templates/`

Cette synchronisation garantit que :
- Les modifications sont disponibles immédiatement pour le générateur principal
- Vous avez une sauvegarde locale de travail
- Les templates utilisés par l'application principale sont toujours à jour

### 📂 Structure des fichiers

```
pi_bois_techniques/
├── modif_templates/
│   ├── app.py                    # Interface web Streamlit
│   ├── templates/               # Templates Jinja2
│   │   ├── situation_administrative.tex.j2
│   │   ├── moyen_materiel.tex.j2
│   │   └── ...
│   ├── output_tex/              # Fichiers générés locaux
│   │   ├── situation_administrative_generated.tex
│   │   └── ...
│   └── data/                    # Données JSON
│       ├── situation_administrative.json
│       └── ...
│
└── templates/                   # Templates principaux (synchronisés)
    ├── situation_administrative_generated.tex
    ├── moyens_materiel_generated.tex
    └── ...
```

---

## 🎯 Comment utiliser chaque section

### 1. **Administratif**
- Modifiez les qualifications de l'entreprise
- Mettez à jour l'effectif et le label
- Saisissez les chiffres d'affaires par année
- Cliquez sur "Générer Administratif"

### 2. **Moyens Matériel**
- Éditez le texte d'introduction
- Modifiez les listes d'équipements par catégorie
- Catégories disponibles : Conception, Sécurité, Atelier, Transport, etc.

### 3. **Matière Première**
- Personnalisez les textes pour chaque certification
- Labels disponibles : Label Vert, PEFC/FSC, Achats Locaux, Zone Verte
- Modifiez le bloc "Santé & Environnement"

### 4. **Sécurité & Santé**
- Ajustez le texte d'introduction
- Saisissez le nombre d'accidents et d'années sans accident
- Modifiez les blocs de détails

### 5. **Environnement Chantiers**
- Personnalisez les textes d'introduction
- Modifiez les cas de gestion des déchets (cas n°1, n°2, n°3)
- Ajoutez/supprimez des éléments dans les listes

### 6. **Environnement Atelier**
- Éditez les textes d'introduction
- Modifiez les listes d'actions concrètes, tri sélectif, etc.
- Personnalisez le texte de sensibilisation

### 7. **HQE**
- **Éco-Construction** : Cibles n°02 et n°03
- **Éco-Gestion** : Cibles n°04 et n°06  
- **Confort** : Cibles n°08 et n°09
- **Santé** : Cible n°14
- Utilisez les accordéons pour développer chaque section

### 8. **Traitement**
- Modifiez le texte d'introduction
- Personnalisez les étapes de préparation
- Ajustez les détails pour grosses pièces et chevrons

### 9. **Organigramme**
- Modifiez les informations de contact
- Mettez à jour les informations du directeur
- Éditez les détails de l'équipe
- Personnalisez les points de réunion quotidienne

---

## 💡 Conseils d'utilisation

### ✨ Bonnes pratiques
1. **Sauvegardez régulièrement** : Cliquez sur le bouton de génération après chaque modification importante
2. **Utilisez les accordéons** : Développez les sections pour voir tous les champs disponibles
3. **Vérifiez la syntaxe** : Le LaTeX est sensible aux caractères spéciaux, utilisez les champs prévus
4. **Testez la compilation** : Après modification, compilez un test pour valider le résultat

### ⚠️ Points d'attention
- **Organigramme** : Génère un fichier `.tex` qui doit être compilé séparément
- **Caractères spéciaux** : Évitez les caractères spéciaux non échappés dans les champs texte
- **Formatage LaTeX** : Les champs texte acceptent le code LaTeX de base

---

## 🔧 Personnalisation

### Modifier les templates
Les templates Jinja2 se trouvent dans `modif_templates/templates/` :
- Fichiers `.tex.j2` : Templates de génération
- Variables accessibles : `{{ variable }}`
- Structures de contrôle : `{% if condition %}...{% endif %}`

### Modifier les données
Les fichiers JSON se trouvent dans `modif_templates/data/` :
- Structure hiérarchique avec sections et sous-sections
- Modifiables directement ou via l'interface

---

## 🐛 Dépannage

### Problèmes courants

**Erreur "Module not found"**
```bash
source venv/bin/activate
pip install streamlit jinja2
```

**Fichiers non synchronisés**
- Vérifiez que vous avez bien cliqué sur le bouton "Générer"
- Contrôlez les permissions d'écriture dans les dossiers

**Erreurs de compilation LaTeX**
- Vérifiez les caractères spéciaux dans les champs
- Testez avec des valeurs simples d'abord

---

## 📞 Support

Pour toute question ou problème :
1. Vérifiez la console Streamlit pour les erreurs
2. Contrôlez les permissions des fichiers
3. Validez le format des données JSON
4. Testez avec l'environnement virtuel activé

---

## 🎉 Conclusion

Cette interface web simplifie grandement la personnalisation des templates LaTeX du mémoire technique. Grâce à la synchronisation automatique, vos modifications sont immédiatement disponibles pour l'application principale de génération.