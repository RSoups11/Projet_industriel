import os
import glob
import ollama
import chromadb
from chromadb.utils import embedding_functions
from pypdf import PdfReader

# --- CONFIGURATION ---
DOSSIER_DOCUMENTS = "./dce"
MODEL_NAME = "mistral"

# --- STRATÉGIES (Prompts adaptés) ---
STRATEGIES = {
    "RC": {
        "keywords": ["rc", "reglement", "consultation"],
        "questions": [
            "Quels sont les CRITÈRES DE JUGEMENT des offres et leur PONDÉRATION (x%) ?",
            "Quels sont les documents ou notes méthodologiques EXIGÉS dans le mémoire technique ?",
            "Quelle est la date et l'heure limite de remise des offres ?"
        ]
    },
    "CCTP": {
        "keywords": ["cctp", "technique", "clauses techniques"],
        "questions": [
            "Quelles sont les contraintes d'INSTALLATION DE CHANTIER (accès, base vie, fluides) ?",
            "Quelles sont les exigences précises sur la GESTION DES DÉCHETS et l'environnement ?",
            "Cite les contraintes techniques majeures ou les matériaux imposés.",
            "Y a-t-il des exigences de planning, de phasage ou de délais ?"
        ]
    },
    "CCAP": {
        "keywords": ["ccap", "administratif"],
        "questions": [
            "Quelles sont les pénalités de retard ?",
            "Quels sont les délais d'exécution ?",
            "Quelles sont les conditions de paiement ou d'avance ?"
        ]
    },
    "DEFAUT": {
        "keywords": [],
        "questions": ["De quoi parle ce document ?", "Quelles sont les obligations de l'entreprise ?"]
    }
}


def lire_pdf(filepath):
    """Lit un PDF et retourne le texte brut."""
    reader = PdfReader(filepath)
    text = ""
    for page in reader.pages:
        content = page.extract_text()
        if content:
            text += content + "\n"
    return text


def decouper_texte(texte, taille_chunk=1000, recouvrement=100):
    """Découpe le texte en morceaux pour que l'IA puisse les digérer."""
    morceaux = []
    debut = 0
    while debut < len(texte):
        fin = debut + taille_chunk
        morceau = texte[debut:fin]
        morceaux.append(morceau)
        debut += (taille_chunk - recouvrement)
    return morceaux


def detecter_type_doc(filename):
    fname = filename.lower()
    for type_doc, data in STRATEGIES.items():
        for kw in data["keywords"]:
            if kw in fname:
                return type_doc
    return "DEFAUT"


def main():
    print("--- 🏗️  ANALYSE DCE (MODE DIRECT) ---")

    if not os.path.exists(DOSSIER_DOCUMENTS):
        os.makedirs(DOSSIER_DOCUMENTS)
        print(f"Dossier '{DOSSIER_DOCUMENTS}' créé. Mets tes PDF dedans et relance.")
        return

    # 1. Initialisation de la base de données vectorielle (ChromaDB)
    # On utilise le modèle par défaut 'all-MiniLM-L6-v2' intégré à Chroma
    print("Initialisation de la mémoire vectorielle...")
    chroma_client = chromadb.Client()

    # On utilise une fonction d'embedding par défaut (télécharge un petit modèle auto)
    emb_fn = embedding_functions.SentenceTransformerEmbeddingFunction(model_name="all-MiniLM-L6-v2")

    pdf_files = glob.glob(os.path.join(DOSSIER_DOCUMENTS, "*.pdf"))
    if not pdf_files:
        print("Aucun PDF trouvé.")
        return

    for pdf_path in pdf_files:
        nom_fichier = os.path.basename(pdf_path)
        type_doc = detecter_type_doc(nom_fichier)
        questions = STRATEGIES[type_doc]["questions"]

        print(f"\n📄 TRAITEMENT : {nom_fichier} ({type_doc})")

        # 2. Lecture et Découpage
        print("   ↳ Lecture et découpage...")
        texte_complet = lire_pdf(pdf_path)
        chunks = decouper_texte(texte_complet)

        # 3. Indexation
        # On crée une collection temporaire pour ce fichier
        try:
            chroma_client.delete_collection(name="doc_temp")  # Nettoyage précédent au cas où
        except:
            pass

        collection = chroma_client.create_collection(name="doc_temp", embedding_function=emb_fn)

        # On ajoute les morceaux à la base (avec des IDs uniques)
        ids = [f"id_{i}" for i in range(len(chunks))]
        collection.add(documents=chunks, ids=ids)

        print("-" * 60)

        # 4. Interrogation (RAG Manuel)
        for question in questions:
            print(f"❓ {question}")

            # A. On cherche les 5 morceaux les plus pertinents
            resultats = collection.query(query_texts=[question], n_results=5)
            contexte = "\n".join(resultats['documents'][0])

            # B. On construit le prompt pour Ollama
            prompt_final = f"""
            Tu es un expert BTP. Analyse les extraits de texte suivants pour répondre à la question.
            Sois précis et synthétique. Si l'information n'est pas dans le texte, dis "Non précisé".

            EXTRAITS DU DOCUMENT :
            {contexte}

            QUESTION : 
            {question}
            """

            # C. Appel à Ollama
            try:
                reponse = ollama.chat(model=MODEL_NAME, messages=[
                    {'role': 'user', 'content': prompt_final},
                ])
                print(f"💡 {reponse['message']['content'].strip()}\n")
            except Exception as e:
                print(f"❌ Erreur Ollama : {e}")
                print("   (Vérifie que 'ollama serve' tourne bien)")

            print("." * 40 + "\n")

        # Nettoyage de la collection
        chroma_client.delete_collection(name="doc_temp")


if __name__ == "__main__":
    main()