"""
assistant.py

Assistant: Upload PDF DCE -> OCR -> Résumé IA -> PDF (ReportLab)

Points clés (perf + stabilité):
- Modèle configurable via env (par défaut qwen2.5:3b-instruct, adapté à 4GB VRAM)
- Réduction des appels LLM (chunks limités) + sélection répartie (début/milieu/fin)
- OCR limité + DPI abaissé (paramétrable)
- Tokens générés plafonnés + prompts contraints (limite de puces/section)
- Option profiling simple via env DEBUG_TIMING=1
"""

from __future__ import annotations

from nicegui import app, ui, events
from pathlib import Path
from typing import List, Dict, Any
from datetime import datetime
import os
import re
import sys
import shutil
import atexit
import asyncio
import time
import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.core.config import AppConfig

try:
    from pypdf import PdfReader  # type: ignore
except Exception:
    PdfReader = None

try:
    from pdf2image import convert_from_path  # type: ignore
    import pytesseract  # type: ignore
except Exception:
    convert_from_path = None
    pytesseract = None

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, ListFlowable, ListItem
from reportlab.lib.styles import getSampleStyleSheet
from xml.sax.saxutils import escape


# ----------------------------- ENV / PARAMS -----------------------------

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434/api/generate")

# Avec 4GB VRAM: qwen2.5:3b-instruct (1.9GB) est le plus stable.
# mistral:instruct (4.1GB) est borderline et peut ralentir si contexte long.
MODEL_NAME = os.getenv("OLLAMA_MODEL", "qwen2.5:3b-instruct")

OLLAMA_TEMPERATURE = float(os.getenv("OLLAMA_TEMPERATURE", "0.1"))
OLLAMA_TIMEOUT = int(os.getenv("OLLAMA_TIMEOUT", "240"))
OLLAMA_NUM_CTX = int(os.getenv("OLLAMA_NUM_CTX", "4096"))

# Optionnel. Par défaut on n'envoie pas num_gpu / num_thread (moins de surprises).
OLLAMA_NUM_GPU = int(os.getenv("OLLAMA_NUM_GPU", "0"))
OLLAMA_NUM_THREAD = int(os.getenv("OLLAMA_NUM_THREAD", "0"))

DEBUG_TIMING = os.getenv("DEBUG_TIMING", "0") == "1"

# Extraction texte / OCR
MIN_TEXT_CHARS_PER_PAGE = int(os.getenv("MIN_TEXT_CHARS_PER_PAGE", "120"))
OCR_MAX_PAGES = int(os.getenv("OCR_MAX_PAGES", "12"))
OCR_DPI = int(os.getenv("OCR_DPI", "200"))  # 200 = bon compromis vitesse/qualité

# Chunking (moins d'appels + couverture meilleure)
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "12000"))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "100"))
MAX_CHARS_PER_DOC = int(os.getenv("MAX_CHARS_PER_DOC", "60000"))
MAX_CHUNKS_PER_DOC = int(os.getenv("MAX_CHUNKS_PER_DOC", "3"))

# Limites de génération (vitesse)
EXTRACT_MAX_TOKENS = int(os.getenv("EXTRACT_MAX_TOKENS", "350"))
DOC_SYNTH_MAX_TOKENS = int(os.getenv("DOC_SYNTH_MAX_TOKENS", "450"))
FINAL_SYNTH_MAX_TOKENS = int(os.getenv("FINAL_SYNTH_MAX_TOKENS", "900"))

ASSISTANT_STATE_KEY = "assistant_state_v1"


def _safe_filename(name: str) -> str:
    name = str(name).strip().replace("\\", "/").split("/")[-1]
    name = re.sub(r"[^a-zA-Z0-9._-]+", "_", name)
    return name or "file.pdf"


_config_static = AppConfig()
UPLOADS_ROOT = _config_static.DATA_DIR / "uploads"
UPLOADS_ROOT.mkdir(parents=True, exist_ok=True)

if not hasattr(app, "_uploads_mounted"):
    app.add_static_files("/_uploads", str(UPLOADS_ROOT))
    app._uploads_mounted = True


def _cleanup_uploads_root() -> None:
    try:
        if UPLOADS_ROOT.exists():
            shutil.rmtree(UPLOADS_ROOT, ignore_errors=True)
        UPLOADS_ROOT.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass


if not hasattr(app, "_uploads_cleanup_registered"):
    atexit.register(_cleanup_uploads_root)
    app._uploads_cleanup_registered = True


def _get_or_init_state() -> Dict[str, Any]:
    state = app.storage.user.get(ASSISTANT_STATE_KEY)
    if not isinstance(state, dict):
        session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        session_dir = UPLOADS_ROOT / session_id
        session_dir.mkdir(parents=True, exist_ok=True)
        state = {"session_id": session_id, "session_dir": str(session_dir), "uploaded": []}
        app.storage.user[ASSISTANT_STATE_KEY] = state
        return state

    session_dir = Path(state.get("session_dir", "") or "")
    if not str(session_dir):
        session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        session_dir = UPLOADS_ROOT / session_id
        state["session_id"] = session_id
        state["session_dir"] = str(session_dir)
        state["uploaded"] = []
        app.storage.user[ASSISTANT_STATE_KEY] = state

    session_dir.mkdir(parents=True, exist_ok=True)
    if "uploaded" not in state or not isinstance(state["uploaded"], list):
        state["uploaded"] = []
        app.storage.user[ASSISTANT_STATE_KEY] = state

    return state


class AssistantPage:
    def __init__(self) -> None:
        self.config = AppConfig()
        self.state = _get_or_init_state()

        self.session_id: str = str(self.state["session_id"])
        self.session_dir: Path = Path(self.state["session_dir"])

        self.files_container = None
        self.summary_md = None
        self.summary_link_row = None

        self.upload_row = None
        self.upload_widget = None

    def _log(self, *args: Any) -> None:
        if DEBUG_TIMING:
            print("[assistant]", *args, flush=True)

    def _count_pages(self, path: Path) -> str:
        if PdfReader is None:
            return "n/a"
        try:
            return str(len(PdfReader(str(path)).pages))
        except Exception:
            return "n/a"

    def _get_uploaded(self) -> List[Dict[str, Any]]:
        upl = self.state.get("uploaded", [])
        if not isinstance(upl, list):
            upl = []
            self.state["uploaded"] = upl
            app.storage.user[ASSISTANT_STATE_KEY] = self.state
        return upl  # type: ignore[return-value]

    def _set_uploaded(self, uploaded: List[Dict[str, Any]]) -> None:
        self.state["uploaded"] = uploaded
        app.storage.user[ASSISTANT_STATE_KEY] = self.state

    def _refresh_list(self) -> None:
        if not self.files_container:
            return

        uploaded = self._get_uploaded()
        self.files_container.clear()

        with self.files_container:
            if not uploaded:
                ui.label("Aucun PDF uploadé").classes("text-sm text-gray-600")
                return

            for f in uploaded:
                filename = f.get("filename", "file.pdf")
                pages = f.get("pages", "n/a")

                with ui.row().classes("items-center gap-2"):
                    ui.label(f"• {filename} ({pages} pages)").classes("text-sm")
                    ui.button(
                        icon="close",
                        on_click=lambda _=None, fn=filename: asyncio.create_task(self._delete_file(fn)),
                    ).props("flat dense round color=negative").classes("ml-1")

    async def _delete_file(self, filename: str) -> None:
        try:
            uploaded = self._get_uploaded()
            idx = next((i for i, it in enumerate(uploaded) if it.get("filename") == filename), None)

            if idx is None:
                ui.notify("Fichier déjà supprimé / introuvable", type="warning")
                await asyncio.sleep(0)
                self._refresh_list()
                return

            abs_path = uploaded[idx].get("abs_path")
            if abs_path:
                p = Path(abs_path)
                if p.exists():
                    p.unlink()

            uploaded.pop(idx)
            self._set_uploaded(uploaded)

            ui.notify("Fichier supprimé", type="positive")
            await asyncio.sleep(0)
            self._refresh_list()

        except Exception as ex:
            try:
                ui.notify(f"Erreur suppression: {ex}", type="negative")
            except Exception:
                pass
            await asyncio.sleep(0)
            self._refresh_list()

    # ----------------------------- Upload helpers -----------------------------

    def _extract_filename(self, e: events.UploadEventArguments) -> str:
        up = getattr(e, "file", None)
        for obj in (up, e):
            if obj is None:
                continue
            for attr in ("name", "filename", "file_name"):
                v = getattr(obj, attr, None)
                if v:
                    return _safe_filename(v)
        return "file.pdf"

    async def _read_upload_bytes(self, e: events.UploadEventArguments) -> bytes:
        up = getattr(e, "file", None)

        c = getattr(e, "content", None)
        if c is not None:
            if hasattr(c, "read"):
                data = c.read()
                if data:
                    return data
            if isinstance(c, (bytes, bytearray, memoryview)):
                data = bytes(c)
                if data:
                    return data

        if up is not None:
            c2 = getattr(up, "content", None)
            if c2 is not None:
                if hasattr(c2, "read"):
                    data = c2.read()
                    if data:
                        return data
                if isinstance(c2, (bytes, bytearray, memoryview)):
                    data = bytes(c2)
                    if data:
                        return data

        if hasattr(e, "read"):
            try:
                data = await e.read()  # type: ignore[attr-defined]
                if data:
                    return data
            except Exception:
                pass

        if up is not None and hasattr(up, "read"):
            try:
                data = await up.read()  # type: ignore[attr-defined]
                if data:
                    return data
            except Exception:
                pass

        if up is not None:
            file_obj = getattr(up, "file", None)
            if file_obj is not None and hasattr(file_obj, "read"):
                data = file_obj.read()
                if data:
                    return data

        raise RuntimeError("Impossible de lire le contenu du fichier uploadé (API NiceGUI différente).")

    async def _handle_upload(self, e: events.UploadEventArguments) -> None:
        try:
            filename = self._extract_filename(e)
            if not filename.lower().endswith(".pdf"):
                ui.notify("Seuls les PDF sont acceptés", type="negative")
                return

            content = await self._read_upload_bytes(e)

            save_path = self.session_dir / filename
            save_path.write_bytes(content)

            uploaded = self._get_uploaded()
            pages = self._count_pages(save_path)
            entry = {"filename": save_path.name, "abs_path": str(save_path), "pages": pages}

            existing_idx = next((i for i, it in enumerate(uploaded) if it.get("filename") == save_path.name), None)
            if existing_idx is None:
                uploaded.append(entry)
            else:
                uploaded[existing_idx] = entry

            self._set_uploaded(uploaded)
            self._refresh_list()

            ui.notify("PDF importé (écrasé si existant)", type="positive")

        except Exception as ex:
            ui.notify(f"Erreur upload: {ex}", type="negative")

    def _reset_upload_widget(self) -> None:
        if self.upload_widget is None:
            return

        if hasattr(self.upload_widget, "reset"):
            try:
                self.upload_widget.reset()
                return
            except Exception:
                pass

        if self.upload_row is None:
            return
        try:
            self.upload_row.clear()
        except Exception:
            return

        with self.upload_row:
            self.upload_widget = ui.upload(
                on_upload=self._handle_upload,
                multiple=True,
                auto_upload=True,
                max_files=20,
            ).props('accept=".pdf" multiple')

    # ----------------------------- Text extraction / OCR -----------------------------

    def _extract_text_pypdf_pages(self, path: Path) -> List[str]:
        if PdfReader is None:
            return []
        try:
            reader = PdfReader(str(path))
            return [(p.extract_text() or "").strip() for p in reader.pages]
        except Exception:
            return []

    def _extract_text_ocr(self, path: Path) -> str:
        if convert_from_path is None or pytesseract is None:
            raise RuntimeError("OCR non disponible (pdf2image/pytesseract/tesseract/poppler manquants)")
        images = convert_from_path(str(path), dpi=OCR_DPI)
        return "\n".join(pytesseract.image_to_string(img, lang="fra") for img in images).strip()

    def _ocr_pages(self, path: Path, pages: List[int]) -> Dict[int, str]:
        if convert_from_path is None or pytesseract is None:
            return {}
        if not pages:
            return {}

        pages = sorted(set(pages))
        pages = self._select_pages_distributed(pages, OCR_MAX_PAGES)
        grouped: List[List[int]] = []
        current: List[int] = []
        for p in pages:
            if not current or p == current[-1] + 1:
                current.append(p)
            else:
                grouped.append(current)
                current = [p]
        if current:
            grouped.append(current)

        results: Dict[int, str] = {}
        for group in grouped:
            images = convert_from_path(
                str(path),
                dpi=OCR_DPI,
                first_page=group[0],
                last_page=group[-1],
            )
            for offset, img in enumerate(images):
                page_number = group[0] + offset
                results[page_number] = pytesseract.image_to_string(img, lang="fra").strip()
        return results

    def _extract_text(self, path: Path) -> str:
        # 1) try embedded text
        page_texts = self._extract_text_pypdf_pages(path)
        if not page_texts:
            # 2) fallback full OCR
            return self._extract_text_ocr(path)

        # OCR only sparse/empty pages
        pages_to_ocr = [
            idx + 1
            for idx, txt in enumerate(page_texts)
            if len(txt.strip()) < MIN_TEXT_CHARS_PER_PAGE
        ]
        if pages_to_ocr and convert_from_path is not None and pytesseract is not None:
            ocr_texts = self._ocr_pages(path, pages_to_ocr)
            for page_number, text in ocr_texts.items():
                page_texts[page_number - 1] = text

        return "\n".join(t for t in page_texts if t).strip()

    # ----------------------------- LLM call -----------------------------

    def _ollama_generate(self, prompt: str, *, max_tokens: int = 900) -> str:
        options: Dict[str, Any] = {
            "temperature": OLLAMA_TEMPERATURE,
            "num_predict": max_tokens,
            "num_ctx": OLLAMA_NUM_CTX,
        }
        # On n'envoie num_gpu/num_thread que si explicitement demandé.
        if OLLAMA_NUM_GPU > 0:
            options["num_gpu"] = OLLAMA_NUM_GPU
        if OLLAMA_NUM_THREAD > 0:
            options["num_thread"] = OLLAMA_NUM_THREAD

        r = requests.post(
            OLLAMA_URL,
            json={
                "model": MODEL_NAME,
                "prompt": prompt,
                "stream": False,
                "options": options,
            },
            timeout=OLLAMA_TIMEOUT,
        )
        r.raise_for_status()
        return (r.json().get("response") or "").strip()

    # ----------------------------- Chunking helpers -----------------------------

    def _normalize_text(self, text: str) -> str:
        text = re.sub(r"\s+", " ", text)
        return text.strip()

    def _trim_text_distributed(self, text: str, max_chars: int) -> str:
        if len(text) <= max_chars:
            return text
        if max_chars <= 1000:
            return text[:max_chars].strip()
        slice_size = max_chars // 3
        head = text[:slice_size].strip()
        mid_start = max(0, (len(text) // 2) - (slice_size // 2))
        mid = text[mid_start : mid_start + slice_size].strip()
        tail_size = max_chars - (len(head) + len(mid))
        tail = text[-tail_size:].strip() if tail_size > 0 else ""
        return " ".join(part for part in (head, mid, tail) if part).strip()

    def _chunk_text(self, text: str, *, chunk_size: int) -> List[str]:
        if len(text) <= chunk_size:
            return [text]
        chunks: List[str] = []
        start = 0
        while start < len(text):
            end = min(len(text), start + chunk_size)
            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)
            if end == len(text):
                break
            overlap = min(CHUNK_OVERLAP, max(50, chunk_size // 10))
            start = max(0, end - overlap)
        return chunks

    def _pick_chunks_distributed(self, chunks: List[str], k: int) -> List[str]:
        if k <= 0 or not chunks:
            return []
        if len(chunks) <= k:
            return chunks
        step = (len(chunks) - 1) / (k - 1)
        idxs = sorted({round(i * step) for i in range(k)})
        return [chunks[i] for i in idxs]

    def _select_pages_distributed(self, pages: List[int], limit: int) -> List[int]:
        if limit <= 0 or not pages:
            return []
        if len(pages) <= limit:
            return pages
        step = (len(pages) - 1) / (limit - 1)
        idxs = sorted({round(i * step) for i in range(limit)})
        return [pages[i] for i in idxs]

    def _estimate_chunk_size(self, filename: str) -> int:
        base_prompt = self._build_extraction_prompt(filename, "")
        prompt_tokens = max(1, len(base_prompt) // 4)
        available_tokens = max(256, OLLAMA_NUM_CTX - EXTRACT_MAX_TOKENS - prompt_tokens)
        estimated_size = available_tokens * 4
        return max(2000, min(CHUNK_SIZE, estimated_size))

    # ----------------------------- Prompts -----------------------------

    def _build_extraction_prompt(self, filename: str, chunk: str) -> str:
        return f"""
    Tu es un expert en analyse de DCE BTP.
    Extrait UNIQUEMENT les informations utiles à la rédaction d'un mémoire technique de réponse à appel d'offres.
    Réponds uniquement en français.
    Aucune invention. Si une info n'est pas dans l'extrait: ne l'ajoute pas.

    Contraintes de réponse:
    - Pas de texte superflu (pas d'intro/conclusion).
    - Maximum 12 puces par section. Regroupe si nécessaire.
    - Si une section est absente: mets une seule puce "non mentionné".
    - Respecte STRICTEMENT le format demandé.

    Format exact:
    - Exigences administratives:
    - ...
    - Exigences techniques:
    - ...
    - Attendus mémoire technique (contenu et pièces attendues):
    - ...
    - Délais / planning / phasage:
    - ...
    - Contraintes / risques / pénalités:
    - ...
    - Informations clés:
    - ...
    - Champs structurés pour auto-remplissage:
    - Intitulé de l'opération: ...
    - Intitulé du lot: ...
    - Adresse du chantier: ...
    - Maître d'ouvrage (MOA): ...
    - Maître d'œuvre (MOE): ...
    - Type de marché / procédure: ...
    - Date limite remise des offres: ...
    - Durée / délai d'exécution: ...
    - Visite obligatoire: ...
    - Contact / référent: ...
    - Montant estimé / budget: ...
    - Variantes / PSE: ...
    - Critères d'attribution: ...
    - Dates importantes: ...

    Règles pour "Champs structurés pour auto-remplissage":
    - Renseigne uniquement si explicitement présent dans l'extrait.
    - Sinon écris exactement "non mentionné" après les deux-points.
    - Pour "Dates importantes": liste les dates + leur signification (ex: "Date limite remise des offres: ...", "Visite obligatoire: ...").

    Source: {filename}
    Extrait:
    {chunk}
    """.strip()


    def _build_doc_synthesis_prompt(self, filename: str, extracts: List[str]) -> str:
        corpus = "\n\n".join(extracts)
        return f"""
    Tu es un expert en analyse de DCE BTP.
    À partir des extractions ci-dessous, consolide un résumé dédupliqué pour le document {filename}.
    Réponds uniquement en français. Aucune invention.

    Contraintes:
    - Maximum 15 puces par section (regroupe).
    - Si une section est absente: une seule puce "non mentionné".
    - Conserve les chiffres, dates, seuils, pénalités, pièces, formats et contacts tels quels quand ils existent.
    - Pour "Champs structurés": fusionne et choisis la valeur la plus complète si conflit.

    Format requis:
    - Exigences administratives:
    - ...
    - Exigences techniques:
    - ...
    - Attendus mémoire technique (contenu et pièces attendues):
    - ...
    - Délais / planning / phasage:
    - ...
    - Contraintes / risques / pénalités:
    - ...
    - Informations clés:
    - ...
    - Champs structurés pour auto-remplissage:
    - Intitulé de l'opération: ...
    - Intitulé du lot: ...
    - Adresse du chantier: ...
    - Maître d'ouvrage (MOA): ...
    - Maître d'œuvre (MOE): ...
    - Type de marché / procédure: ...
    - Date limite remise des offres: ...
    - Durée / délai d'exécution: ...
    - Visite obligatoire: ...
    - Contact / référent: ...
    - Montant estimé / budget: ...
    - Variantes / PSE: ...
    - Critères d'attribution: ...
    - Dates importantes: ...

    Règles "Champs structurés":
    - Si non trouvé dans les extractions: "non mentionné".
    - "Dates importantes": liste des items "événement: date".

    Extractions:
    {corpus}
    """.strip()


    def _build_final_prompt(self, doc_summaries: List[str]) -> str:
        corpus = "\n\n".join(doc_summaries)
        return f"""
    Tu es un assistant expert pour réponses à appel d'offres BTP.
    À partir des synthèses par document ci-dessous, produis un résumé final complet et actionnable.
    N'invente rien. Déduplique. Réponds uniquement en français.

    Contraintes:
    - Sois utile pour rédiger le mémoire technique.
    - Retourne uniquement du Markdown valide (titres + listes).
    - Maximum 12 puces par section (regroupe).
    - Si une info est absente des documents: écris "non mentionné".
    - Les "Champs structurés" doivent être cohérents et dédupliqués.

    Structure Markdown obligatoire:
    # Synthèse IA - Mémoire technique
    ## 1. Checklist des attendus (mémoire technique)
    - ...
    ## 2. Exigences administratives (RC/CCAP)
    - ...
    ## 3. Exigences techniques (CCTP/CCTC)
    - ...
    ## 4. Délais / planning / phasage
    - ...
    ## 5. Points de vigilance / risques / pénalités
    - ...
    ## 6. Champs structurés pour auto-remplissage
    - **Intitulé de l'opération**: ...
    - **Intitulé du lot**: ...
    - **Maître d'ouvrage (MOA)**: ...
    - **Adresse du chantier**: ...
    - **Maître d'œuvre (MOE)**: ...
    - **Type de marché / procédure**: ...
    - **Date limite remise des offres**: ...
    - **Durée / délai d'exécution**: ...
    - **Visite obligatoire**: ...
    - **Contact / référent**: ...
    - **Montant estimé / budget**: ...
    - **Variantes / PSE**: ...
    - **Critères d'attribution**: ...
    - **Dates importantes**: ...

    Règles section 6:
    - Si non trouvé: "non mentionné".
    - "Dates importantes": liste d'items "événement: date".

    Synthèses:
    {corpus}
    """.strip()


    # ----------------------------- PDF writer -----------------------------

    def _format_inline(self, text: str) -> str:
        escaped = escape(text)
        escaped = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", escaped)
        escaped = re.sub(r"\*(.+?)\*", r"<i>\1</i>", escaped)
        return escaped

    def _write_pdf_from_markdown(self, path: Path, title: str, markdown_text: str) -> None:
        styles = getSampleStyleSheet()
        title_style = styles["Title"]
        h1 = styles["Heading1"]
        h2 = styles["Heading2"]
        h3 = styles["Heading3"]
        body = styles["BodyText"]

        doc = SimpleDocTemplate(
            str(path),
            pagesize=A4,
            leftMargin=2 * cm,
            rightMargin=2 * cm,
            topMargin=2 * cm,
            bottomMargin=2 * cm,
        )

        story = []
        if title:
            story.append(Paragraph(self._format_inline(title), title_style))
            story.append(Spacer(1, 12))

        lines = markdown_text.splitlines()
        i = 0
        while i < len(lines):
            line = lines[i].rstrip()
            if not line.strip():
                story.append(Spacer(1, 8))
                i += 1
                continue

            if line.startswith("# "):
                story.append(Paragraph(self._format_inline(line[2:].strip()), h1))
                story.append(Spacer(1, 6))
                i += 1
                continue
            if line.startswith("## "):
                story.append(Paragraph(self._format_inline(line[3:].strip()), h2))
                story.append(Spacer(1, 4))
                i += 1
                continue
            if line.startswith("### "):
                story.append(Paragraph(self._format_inline(line[4:].strip()), h3))
                story.append(Spacer(1, 4))
                i += 1
                continue

            if line.lstrip().startswith("- "):
                bullet_items = []
                while i < len(lines) and lines[i].lstrip().startswith("- "):
                    bullet_text = lines[i].lstrip()[2:].strip()
                    bullet_items.append(ListItem(Paragraph(self._format_inline(bullet_text), body)))
                    i += 1
                story.append(ListFlowable(bullet_items, bulletType="bullet", leftIndent=14))
                story.append(Spacer(1, 6))
                continue

            story.append(Paragraph(self._format_inline(line), body))
            story.append(Spacer(1, 4))
            i += 1

        doc.build(story)

    # ----------------------------- Main pipeline -----------------------------

    def _generate_summary_blocking(self) -> Dict[str, Any]:
        uploaded = self._get_uploaded()
        doc_summaries: List[str] = []

        for f in uploaded:
            filename = f.get("filename", "document.pdf")
            abs_path = Path(f["abs_path"])

            t0 = time.time()
            raw_text = self._extract_text(abs_path)
            self._log(f"{filename} extract/OCR secs:", round(time.time() - t0, 2))

            text = self._normalize_text(raw_text)
            text = self._trim_text_distributed(text, MAX_CHARS_PER_DOC)
            if not text:
                continue

            chunk_size = self._estimate_chunk_size(filename)
            chunks_all = self._chunk_text(text, chunk_size=chunk_size)
            chunks = self._pick_chunks_distributed(chunks_all, MAX_CHUNKS_PER_DOC)

            chunk_extracts: List[str] = []
            for i, chunk in enumerate(chunks):
                prompt = self._build_extraction_prompt(filename, chunk)
                t1 = time.time()
                extract = self._ollama_generate(prompt, max_tokens=EXTRACT_MAX_TOKENS)
                self._log(f"{filename} LLM extract[{i}] secs:", round(time.time() - t1, 2))
                if extract:
                    chunk_extracts.append(extract)

            if not chunk_extracts:
                continue

            if len(chunk_extracts) == 1:
                doc_summary = chunk_extracts[0]
            else:
                doc_prompt = self._build_doc_synthesis_prompt(filename, chunk_extracts)
                t2 = time.time()
                doc_summary = self._ollama_generate(doc_prompt, max_tokens=DOC_SYNTH_MAX_TOKENS)
                self._log(f"{filename} LLM doc_synth secs:", round(time.time() - t2, 2))

            if doc_summary:
                doc_summaries.append(f"Document: {filename}\n{doc_summary}")

        if doc_summaries:
            final_prompt = self._build_final_prompt(doc_summaries)
            t3 = time.time()
            summary = self._ollama_generate(final_prompt, max_tokens=FINAL_SYNTH_MAX_TOKENS)
            self._log("FINAL LLM secs:", round(time.time() - t3, 2))
        else:
            summary = "Aucune information exploitable n'a été extraite des documents fournis."

        out_pdf = self.session_dir / "resume_ia.pdf"
        self._write_pdf_from_markdown(out_pdf, "Résumé IA – Mémoire technique", summary)
        return {"url": f"/_uploads/{self.session_id}/resume_ia.pdf", "summary": summary}

    async def _on_click_analyze(self) -> None:
        if not self._get_uploaded():
            ui.notify("Aucun PDF uploadé", type="warning")
            return

        ui.notify("Analyse en cours (OCR + IA)...", type="info")
        if self.summary_md:
            self.summary_md.set_content("⏳ Analyse en cours...")

        try:
            result = await asyncio.to_thread(self._generate_summary_blocking)

            self.summary_link_row.clear()
            with self.summary_link_row:
                ui.html(
                    f'''
                    <a href="{result["url"]}"
                       target="_blank"
                       download
                       class="text-blue-700 underline font-medium">
                       Télécharger le PDF résumé
                    </a>
                    ''',
                    sanitize=False,
                )

            if self.summary_md:
                self.summary_md.set_content(result.get("summary", "✅ Résumé généré. Téléchargez le PDF ci-dessus."))
            ui.notify("PDF généré", type="positive")

        except Exception as e:
            ui.notify(f"Erreur analyse: {e}", type="negative")

    # ----------------------------- UI -----------------------------

    def render(self) -> None:
        ui.label("Assistant – OCR → Résumé IA → PDF").classes("text-2xl font-bold text-blue-900")
        ui.label("Upload des PDF du DCE, OCR si besoin, résumé IA, puis export en PDF.").classes("text-sm text-gray-600")
        ui.separator().classes("my-3")

        with ui.card().classes("p-4"):
            ui.label("1) Importer des PDF").classes("text-lg font-semibold")

            self.upload_row = ui.row().classes("items-center gap-2")
            with self.upload_row:
                self.upload_widget = ui.upload(
                    on_upload=self._handle_upload,
                    multiple=True,
                    auto_upload=True,
                    max_files=20,
                ).props('accept=".pdf" multiple')

            ui.button(
                "Réinitialiser la sélection",
                on_click=self._reset_upload_widget,
            ).props("outline dense").classes("mt-2")

            ui.label(f"Session persistante : {self.session_id}").classes("text-xs text-gray-500 mt-2")
            ui.label(f"Dossier : {self.session_dir}").classes("text-xs text-gray-500")

            ui.separator().classes("my-2")
            ui.label("Réglages IA").classes("text-sm font-semibold text-gray-700")
            ui.label(f"Modèle: {MODEL_NAME} | num_ctx: {OLLAMA_NUM_CTX} | temp: {OLLAMA_TEMPERATURE}").classes(
                "text-xs text-gray-600"
            )
            ui.label(
                f"Chunks: size={CHUNK_SIZE}, overlap={CHUNK_OVERLAP}, max_chunks/doc={MAX_CHUNKS_PER_DOC} | OCR: dpi={OCR_DPI}, max_pages={OCR_MAX_PAGES}"
            ).classes("text-xs text-gray-600")

        ui.separator().classes("my-4")
        ui.label("2) Fichiers importés").classes("text-lg font-semibold")
        self.files_container = ui.column().classes("gap-1")
        self._refresh_list()

        ui.separator().classes("my-4")
        with ui.card().classes("p-4"):
            ui.label("3) Analyse + génération PDF").classes("text-lg font-semibold")
            ui.button("Analyser + Générer PDF", on_click=self._on_click_analyze).props("color=primary").classes("w-full")
            self.summary_link_row = ui.row().classes("items-center mt-2").style("gap: 12px;")

        self.summary_md = ui.markdown("").classes("mt-4 w-full")


def render():
    AssistantPage().render()
