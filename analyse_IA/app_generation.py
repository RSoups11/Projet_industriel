# app_generation.py

import gradio as gr
from transformers import pipeline
import torch

import torch_util as torchu  # ton fichier existant

SEED = 974
DEVICE = torchu.get_device()

# Modèles disponibles pour les tests
MODEL_CHOICES = {
    "Qwen 0.5B Instruct": "Qwen/Qwen2.5-0.5B-Instruct",
    "Llama 3.2 1B Instruct": "meta-llama/Llama-3.2-1B-Instruct",
    # tu peux en ajouter d'autres si besoin
}

# Prompts pré-définis
PROMPTS_PREDEFINIS = {
    "Résumé (1 phrase)": (
        "Considère l'intégralité du texte suivant et retourne en sortie "
        "un résumé de ce texte en une phrase, en français. "
        "Texte : \"{texte}\" Sortie :"
    ),
    "Résumé (2-3 phrases)": (
        "Considère l'intégralité du texte suivant et retourne en sortie "
        "un résumé de ce texte en deux ou trois phrases, en français. "
        "Texte : \"{texte}\" Sortie :"
    ),
    "Plus commercial / valorisant": (
        "Réécris le texte suivant pour qu'il soit plus commercial et valorisant, "
        "tout en restant factuel, professionnel et adapté à un mémoire technique. "
        "Garde le texte en français. "
        "Texte : \"{texte}\" Sortie :"
    ),
    "Accent environnement / déchets": (
        "Réécris le texte suivant en mettant particulièrement en avant la dimension "
        "environnementale (gestion des déchets, tri, valorisation, HQE, RGE, etc.). "
        "Texte : \"{texte}\" Sortie :"
    ),
}

# Cache des pipelines pour éviter de recharger le modèle à chaque clic
PIPELINES = {}


def get_pipeline(model_label: str):
    """Charge (ou récupère dans le cache) le pipeline pour le modèle choisi."""
    if model_label in PIPELINES:
        return PIPELINES[model_label]

    model_name = MODEL_CHOICES[model_label]
    print(f"[INFO] Chargement du modèle {model_name} sur {DEVICE}...")
    pipe = pipeline(
        task="text-generation",
        model=model_name,
        device=DEVICE,
        torch_dtype=torch.bfloat16 if torch.cuda.is_available() else torch.float32,
    )
    PIPELINES[model_label] = pipe
    return pipe


def generate_text(model_label: str, mode: str, texte: str, custom_prompt: str):
    """Fonction appelée par Gradio pour générer le texte."""
    torchu.set_seed(SEED)

    texte = (texte or "").strip()
    if not texte:
        return "Aucun texte en entrée."

    # Construction du prompt utilisateur
    if mode == "Prompt libre":
        custom_prompt = (custom_prompt or "").strip()
        if not custom_prompt:
            return "Mode 'Prompt libre' sélectionné, mais aucun prompt n'a été fourni."
        if "{texte}" in custom_prompt:
            user_prompt = custom_prompt.format(texte=texte)
        else:
            # On colle le texte brut à la fin si pas de placeholder
            user_prompt = custom_prompt + f'\n\nTexte à traiter : """{texte}"""'
    else:
        tmpl = PROMPTS_PREDEFINIS[mode]
        user_prompt = tmpl.format(texte=texte)

    chat_prompt = [
        {"role": "user", "content": user_prompt},
    ]

    pipe = get_pipeline(model_label)

    try:
        generation = pipe(
            chat_prompt,
            do_sample=True,
            temperature=0.2,
            top_k=30,
            top_p=0.95,
            max_new_tokens=512,
        )
        # Pour les modèles chat HF, la sortie est une liste de messages
        return generation[0]["generated_text"][-1]["content"]
    except Exception as e:
        return f"Erreur pendant la génération : {e}"


def toggle_custom_prompt(mode: str):
    """Affiche ou masque la zone 'prompt libre'."""
    visible = mode == "Prompt libre"
    return gr.update(visible=visible)


def build_ui():
    with gr.Blocks(title="Test génération texte - Bois & Techniques") as demo:
        gr.Markdown(
            """
        # Outil de test de génération de texte (local)

        - Choisissez un **modèle** (Qwen, Llama, etc.)
        - Choisissez un **mode d'amélioration**
        - Collez un paragraphe (multiligne) de votre mémoire technique
        - Cliquez sur **Générer**

        Cet outil est uniquement pour l'exploration (pas encore intégré au prototype).
        """
        )

        with gr.Row():
            model_radio = gr.Radio(
                choices=list(MODEL_CHOICES.keys()),
                value="Qwen 0.5B Instruct",
                label="Modèle",
            )
            mode_radio = gr.Radio(
                choices=list(PROMPTS_PREDEFINIS.keys()) + ["Prompt libre"],
                value="Résumé (2-3 phrases)",
                label="Type d'amélioration",
            )

        input_text = gr.Textbox(
            label="Texte d'entrée (paragraphe du mémoire, multiligne autorisé)",
            lines=12,
            placeholder="Collez ici votre texte (organisation de chantier, gestion des déchets, environnement, etc.)",
        )

        custom_prompt_tb = gr.Textbox(
            label="Prompt libre (utilisez {texte} pour insérer le texte d'entrée)",
            lines=4,
            visible=False,
            placeholder="Exemple : Réécris le texte suivant en le simplifiant sans perdre d'informations : {texte}",
        )

        btn = gr.Button("Générer")

        output_text = gr.Textbox(
            label="Texte généré",
            lines=12,
        )

        # Interactions
        mode_radio.change(
            toggle_custom_prompt,
            inputs=mode_radio,
            outputs=custom_prompt_tb,
        )

        btn.click(
            generate_text,
            inputs=[model_radio, mode_radio, input_text, custom_prompt_tb],
            outputs=output_text,
        )

    return demo


if __name__ == "__main__":
    ui = build_ui()
    ui.launch()
