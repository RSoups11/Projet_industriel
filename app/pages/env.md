Variables d'environnements a exporté avant de lancer l'application

```bash
export OLLAMA_MODEL="qwen2.5:3b-instruct"
export OLLAMA_NUM_CTX="4096"
export OCR_DPI="200"
export DEBUG_TIMING="1"   # optionnel: logs temps OCR/LLM
python3 assistant.py
```
