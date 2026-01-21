import torch
from transformers import pipeline

import torch_util as torchu

SEED = 42
DEVICE = torchu.get_device()

# Language model to be used ("Instruct" stands for instruction-tuned,
# i.e. the model has been optimized to follow specific instructions).

# Ungated model example
MODEL_NAME = "Qwen/Qwen2.5-0.5B-Instruct"  # https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct
# Gated model example (see README for instructions)
#MODEL_NAME = "meta-llama/Llama-3.2-1B-Instruct"  # https://huggingface.co/meta-llama/Llama-3.2-1B-Instruct

PROMPT = [
#    {"role": "system", "content": "You are a helpful assistant."},
    {"role": "user", "content": None},
]

# Use a pipeline as a high-level helper.
GENERATOR = pipeline(
    task="text-generation",
    model=MODEL_NAME,
    device=DEVICE,  # force the pipeline on the right device
    torch_dtype=torch.bfloat16
)


def generate():
    generation = GENERATOR(
        PROMPT,
        do_sample=True,  # stochastic generation (as opposed to deterministic generation)
        temperature=0.2,  # model "creativity"
        top_k=30,  # at each step, the model considers tokens among the `top_k` most probable
        top_p=0.95,  # at each step, the model considers tokens among the smallest set whose combined probability reaches `top_p`
        max_new_tokens=512  # limits the length of the generated content (takes less time to compute)
    )

    print(">", generation[0]["generated_text"][-1]["content"])


# MAIN  ################################################################################################################

def main():
    torchu.set_seed(SEED)

    print("Entrez votre commande :")
    user_prompt = input()
    while user_prompt != "stop":
        PROMPT[-1]["content"] = user_prompt
        generate()
        print("Entrez votre commande :")
        user_prompt = input()


if __name__ == "__main__":
    main()
