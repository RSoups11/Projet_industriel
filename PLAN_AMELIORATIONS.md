# Plan d'amélioration de l'interface - Détail des travaux

## 🔍 Audit réalisé

### ✅ Corrections apportées (fait)
- [x] Assistant page ajoutée aux onglets de navigation
- [x] Un seul checkbox coché par défaut (1ère section)
- [x] Correction majeure de l'échappement LaTeX (protection des commandes valides)
- [x] Amélioration de la génération de contenu (pas de double-échappement)

### ⏳ Fonctionnalités complexes restantes

#### 1. **Tableaux éditables (Fixation/Assemblage, Méthodologie)**
   - **Complexité** : Haute
   - **Effort estimé** : 4-6 heures
   - **Dépendances** : Refonte majeure du système de rendu de sous-sections
   - **Détail du travail** :
     - Créer widget tableau interactif dans generation.py
     - Ajouter boutons "Ajouter ligne" / "Ajouter colonne"
     - Convertir état tableau → LaTeX tabular au moment de la génération
     - Gérer validation du contenu (pas de caractères LaTeX spéciaux dans les cellules)
     - Tester avec template_v2.tex.j2
   
#### 2. **Ajout/suppression dynamique d'options dans checkboxes**
   - **Complexité** : Moyenne
   - **Effort estimé** : 2-3 heures
   - **Dépendances** : Gestion état dynamique
   - **Détail du travail** :
     - Ajouter bouton "Ajouter option" dans les sections multi_check
     - Créer input popup pour nouvelle option
     - Stocker nouvelles options dans config.json
     - Persister les options entre sessions
     - Tester dans Base de données et Nouveau mémoire

#### 3. **Ajout/suppression de matériels**
   - **Complexité** : Moyenne
   - **Effort estimé** : 2-3 heures
   - **Dépendances** : CSV service, persistance données
   - **Détail du travail** :
     - Créer formulaire ajout matériel dans LISTE DES MATERIAUX
     - Sauvegarder dans bd_interface.csv ou nouvelle table
     - Permettre suppression de matériels
     - Synchroniser avec Base de données

#### 4. **Ajout de sections**
   - **Complexité** : Moyenne
   - **Effort estimé** : 2-3 heures
   - **Dépendances** : Config, CSV, templates
   - **Détail du travail** :
     - Bouton "Ajouter section" dans Paramètres
     - Form de création (nom, template par défaut)
     - Sauvegarder dans config.json
     - Mettre à jour generation.py avec nouvelle section
     - Gérer le rendu dans template

#### 5. **Parité génération LaTeX (resultat_interface vs resultat-terminal)**
   - **Complexité** : Très haute
   - **Effort estimé** : 6-10 heures
   - **Dépendances** : Tous les points ci-dessus
   - **Problèmes identifiés** :
     - Escaping différent entre CLI et interface
     - Format d'entrée CSV vs données interface
     - Structure de données finale non alignée
     - Traitement des images différent
   
   **Solutions** :
   - Utiliser même fonction echapper_latex pour CLI
   - Normaliser format d'entrée CSV
   - Aligner structure de données (data_finale)
   - Ajouter tests de parité

## 📋 Recommandations priorité

**Phase 1 (Court terme - 4-6h)** :
1. ✅ Assistant navigation (FAIT)
2. ✅ First checkbox default (FAIT)
3. ✅ LaTeX escaping (FAIT)
4. Ajout options dynamiques dans checkboxes
5. Ajout matériels simples

**Phase 2 (Moyen terme - 6-8h)** :
1. Tableaux éditables pour fixation/assemblage
2. Ajout sections
3. Amélioration métadonnées

**Phase 3 (Long terme - 10h+)** :
1. Parité complète CLI ↔ Interface
2. Synchronisation state ↔ CSV
3. Export/import mémoires
4. Gestion versions

## 🔧 Architecture proposée

```
app/
├── pages/
│   ├── generation.py          (refonte widget tableaux)
│   ├── components/            (NEW)
│   │   ├── editable_table.py  (widget tableau)
│   │   └── dynamic_form.py    (formulaires ajout)
├── core/
│   ├── latex_service.py       (finalisé)
│   └── csv_service.py         (amélioration)
└── utils/
    └── latex_utils.py         (NEW - normalisation)
```

## 📊 Effort total estimé

- Corrections appliquées : 2h ✅
- Fonctionnalités complexes : 20-30h
- **Total pour parité complète : 22-32h**

**Recommandation** : Implémenter par phases avec tests à chaque étape.
