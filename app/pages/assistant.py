"""
Assistant: Upload PDF DCE -> OCR -> Résumé IA -> PDF (ReportLab)

Upload:
- Persistance des uploads entre pages via app.storage.user
- Re-upload:
  - même nom => écrase le fichier + met à jour l'entrée
  - nouveau nom => ajoute
- Suppression manuelle via bouton "x"
- Bouton "Réinitialiser sélection" pour forcer le retrigger même si on re-choisit le même fichier
- Nettoyage des uploads à la fermeture (atexit) enregistré une seule fois
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
from reportlab.pdfgen import canvas
from reportlab.lib.units import cm

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL_NAME = "mistral"
MIN_TEXT_CHARS_PER_PAGE = 80
OCR_MAX_PAGES = 30
CHUNK_SIZE = 6000
CHUNK_OVERLAP = 400
MAX_CHARS_PER_DOC = 120000

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

    # ---- upload helpers ----
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

            # overwrite disque si même nom
            save_path = self.session_dir / filename
            save_path.write_bytes(content)

            uploaded = self._get_uploaded()
            pages = self._count_pages(save_path)
            entry = {"filename": save_path.name, "abs_path": str(save_path), "pages": pages}

            # overwrite dans la liste si même nom sinon append
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
        """
        Certains navigateurs ne retrigger pas l'upload si tu re-choisis exactement le même fichier.
        On force un reset (si la méthode existe) ou on recrée le widget.
        """
        if self.upload_widget is None:
            return

        # 1) reset si dispo
        if hasattr(self.upload_widget, "reset"):
            try:
                self.upload_widget.reset()
                return
            except Exception:
                pass

        # 2) sinon recrée
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

    # ---------- (le reste inchangé) extraction/IA/PDF ----------
    def _extract_text_pypdf(self, path: Path) -> str:
        if PdfReader is None:
            return ""
        try:
            reader = PdfReader(str(path))
            return "\n".join((p.extract_text() or "") for p in reader.pages).strip()
        except Exception:
            return ""

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
        images = convert_from_path(str(path), dpi=250)
        return "\n".join(pytesseract.image_to_string(img, lang="fra") for img in images).strip()

    def _ocr_pages(self, path: Path, pages: List[int]) -> Dict[int, str]:
        if convert_from_path is None or pytesseract is None:
            return {}
        if not pages:
            return {}

        pages = sorted(set(pages))[:OCR_MAX_PAGES]
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
                dpi=250,
                first_page=group[0],
                last_page=group[-1],
            )
            for offset, img in enumerate(images):
                page_number = group[0] + offset
                results[page_number] = pytesseract.image_to_string(img, lang="fra").strip()
        return results

    def _extract_text(self, path: Path) -> str:
        page_texts = self._extract_text_pypdf_pages(path)
        if not page_texts:
            return self._extract_text_ocr(path)

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

    def _ollama_generate(self, prompt: str, *, max_tokens: int = 900) -> str:
        r = requests.post(
            OLLAMA_URL,
            json={
                "model": MODEL_NAME,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0.1, "num_predict": max_tokens},
            },
            timeout=300,
        )
        r.raise_for_status()
        return (r.json().get("response") or "").strip()

    def _normalize_text(self, text: str) -> str:
        text = re.sub(r"\s+", " ", text)
        return text.strip()

    def _chunk_text(self, text: str) -> List[str]:
        if len(text) <= CHUNK_SIZE:
            return [text]
        chunks = []
        start = 0
        while start < len(text):
            end = min(len(text), start + CHUNK_SIZE)
            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)
            if end == len(text):
                break
            start = max(0, end - CHUNK_OVERLAP)
        return chunks

    def _build_extraction_prompt(self, filename: str, chunk: str) -> str:
        return f"""
Tu es un expert en analyse de DCE BTP.
Extrait UNIQUEMENT les informations utiles à la rédaction d'un mémoire technique de réponse à appel d'offres.
Rends une liste structurée en français, sans texte superflu, sous ce format exact:

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
- Informations clés (intitulé opération, adresse, MOA/MOE, dates limites, visite obligatoire, contact, format de remise):
  - ...

Source: {filename}
Extrait:
{chunk}
""".strip()

    def _build_final_prompt(self, extracts: List[str]) -> str:
        corpus = "\n\n".join(extracts)
        return f"""
Tu es un assistant expert pour réponses à appel d'offres BTP.
À partir des extractions suivantes, synthétise un résumé complet et actionnable.
N'invente rien. Regroupe et déduplique.

Structure obligatoire:
1) Checklist des attendus (mémoire technique)
2) Exigences administratives (RC/CCAP)
3) Exigences techniques (CCTP/CCTC)
4) Délais / planning / phasage
5) Points de vigilance / risques de non-conformité / pénalités
6) Champs extraits (intitulé opération, adresse, MOA/MOE, délai, date limite, visite obligatoire, contacts, pièces à fournir)

Extractions:
{corpus}
""".strip()

    def _write_pdf(self, path: Path, title: str, text: str) -> None:
        c = canvas.Canvas(str(path), pagesize=A4)
        _, h = A4
        x, y = 2 * cm, h - 2 * cm

        c.setFont("Helvetica-Bold", 14)
        c.drawString(x, y, title)
        y -= 1 * cm
        c.setFont("Helvetica", 10)

        max_chars = 110
        for paragraph in text.split("\n"):
            line = paragraph
            if not line.strip():
                y -= 12
                continue

            while len(line) > max_chars:
                chunk = line[:max_chars]
                line = line[max_chars:]
                if y < 2 * cm:
                    c.showPage()
                    c.setFont("Helvetica", 10)
                    y = h - 2 * cm
                c.drawString(x, y, chunk)
                y -= 12

            if y < 2 * cm:
                c.showPage()
                c.setFont("Helvetica", 10)
                y = h - 2 * cm
            c.drawString(x, y, line)
            y -= 12

        c.save()

    def _generate_summary_blocking(self) -> Dict[str, Any]:
        uploaded = self._get_uploaded()
        extracts: List[str] = []
        for f in uploaded:
            raw_text = self._extract_text(Path(f["abs_path"]))
            text = self._normalize_text(raw_text)[:MAX_CHARS_PER_DOC]
            if not text:
                continue
            chunks = self._chunk_text(text)
            for chunk in chunks:
                prompt = self._build_extraction_prompt(f["filename"], chunk)
                extract = self._ollama_generate(prompt, max_tokens=700)
                if extract:
                    extracts.append(extract)

        if extracts:
            summary = self._ollama_generate(self._build_final_prompt(extracts), max_tokens=1200)
        else:
            summary = "Aucune information exploitable n'a été extraite des documents fournis."
        out_pdf = self.session_dir / "resume_ia.pdf"
        self._write_pdf(out_pdf, "Résumé IA – Mémoire technique", summary)
        return {"url": f"/_uploads/{self.session_id}/resume_ia.pdf"}

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
                self.summary_md.set_content("✅ Résumé généré. Téléchargez le PDF ci-dessus.")
            ui.notify("PDF généré", type="positive")

        except Exception as e:
            ui.notify(f"Erreur analyse: {e}", type="negative")

    def render(self) -> None:
        ui.label("Assistant – OCR → Résumé IA → PDF").classes("text-2xl font-bold text-blue-900")
        ui.label("Upload des PDF du DCE, OCR si besoin, résumé IA, puis export en PDF.").classes("text-sm text-gray-600")
        ui.separator().classes("my-3")

        with ui.card().classes("p-4"):
            ui.label("1) Importer des PDF").classes("text-lg font-semibold")

            # upload + reset button
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
