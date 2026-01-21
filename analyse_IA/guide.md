
---

# 1. Préparation Hugging Face

L’outil utilise des modèles hébergés sur [Hugging Face](https://huggingface.co) (Qwen, Llama…).
Pour que ça fonctionne proprement, surtout avec Llama, il faut :

### 1.1. Créer un compte Hugging Face

1. Aller sur : [https://huggingface.co](https://huggingface.co)
2. Créer un compte


Pour certains modèles (ex. **Llama 3.2 1B Instruct**), il faut :

1. Aller sur la page du modèle (ex. `meta-llama/Llama-3.2-1B-Instruct`).
2. Cliquer sur **“Accept license” / “Agree”**.
3. Sans cette étape, il y aura une erreur d’accès lors du téléchargement.

Pour Qwen 0.5B Instruct, c’est directement téléchargeable.

### 1.2. Générer un **token d’accès**

1. Sur Hugging Face : cliquer sur ton avatar -> **“Settings”** -> **“Access Tokens”**.
2. Créer un **New token** (type : *Read*).
3. Copier le token.

Sur la machine -> deux options :

#### Option A - `huggingface-cli login`

```bash
pip install huggingface_hub
huggingface-cli login
```

Puis coller le token quand demandé.

#### Option B - Variable d’environnement

Sous Linux :

```bash
export HUGGINGFACE_HUB_TOKEN="TOKEN"
```

A mettre dans `~/.bashrc` ou `~/.zshrc` pour ne pas avoir à le refaire.

---

# 2. Installation des dépendances

Dans un **environnement Python** (conda/venv).

### 2.1. Installer PyTorch

Avec GPU (CUDA 13.0 par exemple) :

```bash
pip3 install torch torchvision --index-url https://download.pytorch.org/whl/cu130
```
Pour autre version de cuda, commandes visibles ["ici"](https://pytorch.org/get-started/locally/).

Pour vérifier sa version de cuda si GPU-Nvidia :

```bash
nvdia-smi
```

Sans GPU (CPU uniquement) :

```bash
pip install torch torchvision
```

### 2.2. Installer Transformers, Accelerate, Gradio, SentencePiece

```bash
pip install transformers accelerate gradio sentencepiece
```

Optionnel mais utile pour `huggingface-cli` :

```bash
pip install huggingface_hub
```

### 2.3. Fichiers attendus dans le dépôt

Dans le répertoire de projet :

```text
analyse_IA/
│
├── main.py               # Exemple console fourni par Mr Buet
├── torch_util.py         # Utilitaires (choix GPU/CPU, seed)
├── app_generation.py     # Interface web de test local (Gradio)
└── guide.md             # Documentation
```

---

# 3. Utilisation de l’outil

## 3.1. Mode console (script du prof)

Pour utiliser le script minimal fourni par le professeur (`main.py`) :

```bash
python3 main.py
```

* Le script demande une phrase -> le modèle répond.
* On peut changer le modèle utilisé en modifiant dans `main.py` :

```python
MODEL_NAME = "Qwen/Qwen2.5-0.5B-Instruct"
# ou bien :
# MODEL_NAME = "meta-llama/Llama-3.2-1B-Instruct"
```

C’est pratique pour des tests rapides, mais peu ergonomique pour des textes longs.

---

## 3.2. Mode interface web (outil de test pour paragraphes)

Pour tester des paragraphes réels du mémoire technique (texte multiligne, bullets point, etc.), on utilise **Gradio** via le script `app_generation.py`.

### Lancer l’interface :

```bash
python app_generation.py
```

Dans le terminal il y aura une URL locale du type :

```text
Running on local URL:  http://127.0.0.1:7860
```

### Interface :

1. **Choisir le modèle** :

   * `Qwen 0.5B Instruct` (rapide, léger)
   * `Llama 3.2 1B Instruct` (plus lourd, souvent meilleur style)

2. **Choisir le “mode d’amélioration”** du texte :

   * `Résumé (1 phrase)`
   * `Résumé (2-3 phrases)`
   * `Plus commercial / valorisant`
   * `Accent environnement / déchets`
   * `Prompt libre` (Ecrire son propre prompt)

3. **Coller le texte d’entrée** (multilignes)

   Exemple : un paragraphe “Organisation du chantier”, “Gestion des déchets”, etc. avec listes, phrases longues, etc.

4. (Si `Prompt libre`) écrire le prompt perso

   Exemple :

   > Réécris le texte suivant en le simplifiant sans perdre d'informations, en français : {texte}

5. Cliquer sur **“Générer”**

Le texte généré apparaît dans la zone de sortie :

* on peut le comparer avec l’original,
* voir si le style est acceptable pour un mémoire,
* juger la pertinence (est-ce qu’il invente des choses, est-ce que ça reste professionnel ?).

---

## 3.3. Utilité pour le moment

Cet outil sert à :

* **Explorer les capacités** de petits modèles (0.5B / 1B) en local sur les textes métiers.
* Tester plusieurs “modes” de réécriture : résumé, plus vendeur, accent environnement…
* Comparer Qwen vs Llama sur :

  * qualité de rédaction,
  * respect du sens,
  * temps de génération,
  * charge.

Ces tests permettront ensuite d’argumenter devant Bois & Techniques :

* Ce qu’il est **réaliste** de faire en local avec quel type de machine,
* Ce qu’il faudrait pour aller plus loin (modèle plus gros, cloud, etc.),
* Ou pourquoi il peut être raisonnable de rester, pour l’instant, sur une solution sans IA intégrée.

---
