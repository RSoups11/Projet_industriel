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
import json
import requests
from xml.sax.saxutils import escape

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.core.config import AppConfig

POPPLER_PATH = os.getenv("POPPLER_PATH")
TESSERACT_CMD = os.getenv("TESSERACT_CMD")

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

if pytesseract is not None and TESSERACT_CMD:
    try:
        pytesseract.pytesseract.tesseract_cmd = TESSERACT_CMD
    except Exception:
        pass

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    ListFlowable,
    ListItem,
    Preformatted,
)

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL_NAME = "mistral"
MIN_TEXT_CHARS_BEFORE_OCR = 800

ASSISTANT_STATE_KEY = "assistant_state_v1"
ASSISTANT_EXTRACTION_KEY = "assistant_extraction_v1"

MAX_CHARS_PER_DOC = 20000
MAX_TOTAL_CHARS = 80000


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
        self.fields_container = None
        self.last_extract_label = None

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

    def _extract_text_ocr(self, path: Path) -> str:
        if convert_from_path is None or pytesseract is None:
            raise RuntimeError("OCR non disponible (pdf2image/pytesseract/tesseract/poppler manquants)")
        if POPPLER_PATH:
            images = convert_from_path(str(path), dpi=250, poppler_path=POPPLER_PATH)
        else:
            images = convert_from_path(str(path), dpi=250)
        return "\n".join(pytesseract.image_to_string(img, lang="fra") for img in images).strip()

    def _extract_text(self, path: Path) -> str:
        txt = self._extract_text_pypdf(path)
        if len(txt) < MIN_TEXT_CHARS_BEFORE_OCR:
            ocr_txt = self._extract_text_ocr(path)
            if len(ocr_txt) > len(txt):
                txt = ocr_txt
        return txt

    def _truncate_text(self, text: str, max_chars: int) -> str:
        if len(text) <= max_chars:
            return text
        return text[:max_chars] + "\n[...]"

    def _prepare_docs_for_llm(self, docs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        remaining = MAX_TOTAL_CHARS
        prepared: List[Dict[str, Any]] = []
        for d in docs:
            raw = d.get("text", "") or ""
            chunk = raw[: min(MAX_CHARS_PER_DOC, remaining)]
            prepared.append({"filename": d.get("filename", "document.pdf"), "text": chunk})
            remaining -= len(chunk)
            if remaining <= 0:
                break
        return prepared

    def _ollama_generate(self, prompt: str) -> str:
        r = requests.post(
            OLLAMA_URL,
            json={"model": MODEL_NAME, "prompt": prompt, "stream": False},
            timeout=600,
        )
        r.raise_for_status()
        return (r.json().get("response") or "").strip()

    def _ollama_generate_json(self, prompt: str) -> Dict[str, Any]:
        r = requests.post(
            OLLAMA_URL,
            json={"model": MODEL_NAME, "prompt": prompt, "stream": False, "format": "json"},
            timeout=600,
        )
        r.raise_for_status()
        raw = (r.json().get("response") or "").strip()
        if not raw:
            return {}
        try:
            return json.loads(raw)
        except Exception:
            pass
        start = raw.find("{")
        end = raw.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(raw[start : end + 1])
            except Exception:
                return {}
        return {}

    def _build_analysis_prompt(self, docs: List[Dict[str, Any]]) -> str:
        corpus = "\n".join(f"\n===== {d['filename']} =====\n{d['text']}\n" for d in docs)
        return f"""
Tu es un assistant pour reponse a appel d'offres BTP.
Analyse les documents du DCE et retourne un JSON STRICT avec les cles suivantes.
Si une information est absente, mets une chaine vide.

JSON attendu:
{{
  "fields": {{
    "intitule_operation": "",
    "intitule_lot": "",
    "maitre_ouvrage": "",
    "adresse_chantier": "",
    "maitre_oeuvre": "",
    "type_marche_procedure": "",
    "date_limite_remise_offres": "",
    "duree_delai_execution": "",
    "visite_obligatoire": "",
    "contact_referent": "",
    "montant_estime_budget": "",
    "variantes_pse": "",
    "criteres_attribution": ""
  }},
  "dates_importantes": [],
  "sources": [],
  "summary_markdown": ""
}}

Contraintes:
- summary_markdown: en markdown lisible, sections obligatoires:
  1) ## Checklist Memoire technique
  2) ## Exigences administratives (RC/CCAP)
  3) ## Exigences techniques (CCTP/CCTC)
  4) ## Notation / criteres d'attribution
  5) ## Points de vigilance
  6) ## Pieces / livrables a fournir
- Dans "criteres_attribution", inclure les ponderations si elles existent (ex: Prix 40% / Valeur technique 60%).
- Dans "dates_importantes", mettre des items courts "JJ/MM/AAAA - evenement".
- "sources" peut contenir des noms de fichiers utiles (RC, CCTP, CCAP...).

Documents:
{corpus}
""".strip()

    def _normalize_value(self, value: Any) -> str:
        if value is None:
            return ""
        v = str(value).strip()
        if not v:
            return ""
        lower = v.lower()
        if lower in {"non mentionne", "non mentionnee", "non precis", "non precise", "n/a"}:
            return ""
        return v

    def _format_markdown_inline(self, text: str) -> str:
        text = escape(text)
        text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
        text = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"<i>\1</i>", text)
        text = re.sub(r"`([^`]+)`", r'<font face="Courier">\1</font>', text)
        return text

    def _markdown_to_flowables(self, md: str) -> List[Any]:
        styles = getSampleStyleSheet()
        h1 = ParagraphStyle("H1", parent=styles["Heading1"], fontSize=14, spaceAfter=6)
        h2 = ParagraphStyle("H2", parent=styles["Heading2"], fontSize=12, spaceAfter=4)
        body = ParagraphStyle("Body", parent=styles["BodyText"], fontSize=10, leading=13)
        code_style = ParagraphStyle("Code", parent=styles["BodyText"], fontName="Courier", fontSize=9, leading=11)

        flowables: List[Any] = []
        para_lines: List[str] = []
        list_items: List[str] = []
        in_code = False
        code_lines: List[str] = []

        def flush_paragraph():
            if not para_lines:
                return
            text = " ".join(line.strip() for line in para_lines if line.strip())
            if text:
                flowables.append(Paragraph(self._format_markdown_inline(text), body))
                flowables.append(Spacer(1, 6))
            para_lines.clear()

        def flush_list():
            if not list_items:
                return
            items = [ListItem(Paragraph(self._format_markdown_inline(it), body), leftIndent=12) for it in list_items]
            flowables.append(ListFlowable(items, bulletType="bullet", leftIndent=12))
            flowables.append(Spacer(1, 6))
            list_items.clear()

        def flush_code():
            if not code_lines:
                return
            content = "\n".join(code_lines)
            flowables.append(Preformatted(content, code_style))
            flowables.append(Spacer(1, 6))
            code_lines.clear()

        lines = md.splitlines()
        for line in lines + [""]:
            if line.strip().startswith("```"):
                if in_code:
                    in_code = False
                    flush_code()
                else:
                    in_code = True
                    flush_paragraph()
                    flush_list()
                continue

            if in_code:
                code_lines.append(line)
                continue

            if not line.strip():
                flush_paragraph()
                flush_list()
                continue

            if line.startswith("# "):
                flush_paragraph()
                flush_list()
                flowables.append(Paragraph(self._format_markdown_inline(line[2:].strip()), h1))
                flowables.append(Spacer(1, 6))
                continue
            if line.startswith("## "):
                flush_paragraph()
                flush_list()
                flowables.append(Paragraph(self._format_markdown_inline(line[3:].strip()), h2))
                flowables.append(Spacer(1, 4))
                continue

            bullet = re.match(r"^(\*|-|\d+\.)\s+(.*)", line.strip())
            if bullet:
                flush_paragraph()
                list_items.append(bullet.group(2))
                continue

            para_lines.append(line)

        flush_paragraph()
        flush_list()
        return flowables

    def _write_markdown_pdf(self, path: Path, title: str, fields: Dict[str, str], summary_md: str) -> None:
        doc = SimpleDocTemplate(
            str(path),
            pagesize=A4,
            leftMargin=2 * cm,
            rightMargin=2 * cm,
            topMargin=2 * cm,
            bottomMargin=2 * cm,
        )
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle("Title", parent=styles["Title"], fontSize=16, spaceAfter=12)
        body = ParagraphStyle("Body", parent=styles["BodyText"], fontSize=10, leading=13)

        flowables: List[Any] = []
        flowables.append(Paragraph(self._format_markdown_inline(title), title_style))

        table_data = [["Champ", "Information extraite"]]
        for key, label in [
            ("intitule_operation", "Intitule de l'operation"),
            ("intitule_lot", "Intitule du lot"),
            ("maitre_ouvrage", "Maitre d'ouvrage"),
            ("adresse_chantier", "Adresse du chantier"),
            ("maitre_oeuvre", "Maitre d'oeuvre"),
            ("type_marche_procedure", "Type de marche / procedure"),
            ("date_limite_remise_offres", "Date limite remise des offres"),
            ("duree_delai_execution", "Duree / delai d'execution"),
            ("visite_obligatoire", "Visite obligatoire"),
            ("contact_referent", "Contact / referent"),
            ("montant_estime_budget", "Montant estime / budget"),
            ("variantes_pse", "Variantes / PSE"),
            ("criteres_attribution", "Criteres d'attribution"),
        ]:
            value = fields.get(key, "") or "Non mentionne"
            table_data.append([label, value])

        table = Table(table_data, colWidths=[6.0 * cm, 9.5 * cm])
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2C3E50")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, 0), 10),
                    ("BACKGROUND", (0, 1), (-1, -1), colors.whitesmoke),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.lightgrey),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                    ("FONTSIZE", (0, 1), (-1, -1), 9),
                    ("LEFTPADDING", (0, 0), (-1, -1), 6),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ]
            )
        )
        flowables.append(table)
        flowables.append(Spacer(1, 12))

        if summary_md.strip():
            flowables.extend(self._markdown_to_flowables(summary_md))
        else:
            flowables.append(Paragraph("Aucun resume disponible.", body))

        doc.build(flowables)

    def _generate_summary_blocking(self) -> Dict[str, Any]:
        uploaded = self._get_uploaded()
        docs: List[Dict[str, Any]] = []
        for f in uploaded:
            text = self._extract_text(Path(f["abs_path"]))
            docs.append({"filename": f["filename"], "text": text})

        prepared_docs = self._prepare_docs_for_llm(docs)
        analysis = self._ollama_generate_json(self._build_analysis_prompt(prepared_docs))

        fields = analysis.get("fields") if isinstance(analysis.get("fields"), dict) else {}
        summary_md = str(analysis.get("summary_markdown") or "")
        dates_importantes = analysis.get("dates_importantes") if isinstance(analysis.get("dates_importantes"), list) else []
        sources = analysis.get("sources") if isinstance(analysis.get("sources"), list) else []

        normalized_fields = {k: self._normalize_value(v) for k, v in fields.items()}

        prefill = {
            "intitule": normalized_fields.get("intitule_operation", ""),
            "lot": normalized_fields.get("intitule_lot", ""),
            "moa": normalized_fields.get("maitre_ouvrage", ""),
            "adresse": normalized_fields.get("adresse_chantier", ""),
        }

        out_pdf = self.session_dir / "resume_ia.pdf"
        self._write_markdown_pdf(out_pdf, "Resume IA - Memoire technique", normalized_fields, summary_md)

        payload = {
            "fields": normalized_fields,
            "summary_markdown": summary_md,
            "dates_importantes": dates_importantes,
            "sources": sources,
            "prefill": prefill,
            "created_at": datetime.now().isoformat(timespec="seconds"),
        }

        app.storage.user[ASSISTANT_EXTRACTION_KEY] = payload

        return {
            "url": f"/_uploads/{self.session_id}/resume_ia.pdf",
            "data": payload,
        }

    def _render_extracted_fields(self, data: Dict[str, Any]) -> None:
        if not self.fields_container:
            return

        self.fields_container.clear()

        fields = data.get("fields") if isinstance(data.get("fields"), dict) else {}
        dates = data.get("dates_importantes") if isinstance(data.get("dates_importantes"), list) else []
        sources = data.get("sources") if isinstance(data.get("sources"), list) else []

        rows = []
        for key, label in [
            ("intitule_operation", "Intitule de l'operation"),
            ("intitule_lot", "Intitule du lot"),
            ("maitre_ouvrage", "Maitre d'ouvrage"),
            ("adresse_chantier", "Adresse du chantier"),
            ("maitre_oeuvre", "Maitre d'oeuvre"),
            ("type_marche_procedure", "Type de marche / procedure"),
            ("date_limite_remise_offres", "Date limite remise des offres"),
            ("duree_delai_execution", "Duree / delai d'execution"),
            ("visite_obligatoire", "Visite obligatoire"),
            ("contact_referent", "Contact / referent"),
            ("montant_estime_budget", "Montant estime / budget"),
            ("variantes_pse", "Variantes / PSE"),
            ("criteres_attribution", "Criteres d'attribution"),
        ]:
            value = fields.get(key, "") or "Non mentionne"
            rows.append({"champ": label, "valeur": value})

        if dates:
            rows.append({"champ": "Dates importantes", "valeur": " | ".join(str(d) for d in dates)})
        if sources:
            rows.append({"champ": "Sources", "valeur": ", ".join(str(s) for s in sources)})

        with self.fields_container:
            if not rows:
                ui.label("Aucune extraction disponible.").classes("text-sm text-gray-500")
            else:
                ui.table(
                    columns=[
                        {"name": "champ", "label": "Champ", "field": "champ", "align": "left"},
                        {"name": "valeur", "label": "Information extraite", "field": "valeur", "align": "left"},
                    ],
                    rows=rows,
                    row_key="champ",
                ).classes("w-full text-sm").props("dense")

    async def _on_click_analyze(self) -> None:
        if not self._get_uploaded():
            ui.notify("Aucun PDF uploadé", type="warning")
            return

        ui.notify("Analyse en cours (OCR + IA)...", type="info")
        if self.summary_md:
            self.summary_md.set_content("Analyse en cours...")

        try:
            result = await asyncio.to_thread(self._generate_summary_blocking)
            data = result.get("data", {}) if isinstance(result, dict) else {}

            self.summary_link_row.clear()
            with self.summary_link_row:
                ui.html(
                    f"""
                    <a href="{result['url']}"
                       target="_blank"
                       download
                       class="text-blue-700 underline font-medium">
                       Telecharger le PDF resume
                    </a>
                    """,
                    sanitize=False,
                )

            if self.last_extract_label and isinstance(data, dict):
                created_at = data.get("created_at", "")
                if created_at:
                    self.last_extract_label.text = f"Derniere analyse : {created_at}"

            if isinstance(data, dict):
                self._render_extracted_fields(data)

            if self.summary_md and isinstance(data, dict):
                summary_md = str(data.get("summary_markdown") or "")
                if summary_md.strip():
                    self.summary_md.set_content(summary_md)
                else:
                    self.summary_md.set_content("_Aucun resume disponible._")

            ui.notify("Analyse terminee. PDF genere.", type="positive")

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
            ui.label("3) Analyse + generation PDF").classes("text-lg font-semibold")
            ui.button("Analyser + Generer PDF", on_click=self._on_click_analyze).props("color=primary").classes("w-full")
            self.summary_link_row = ui.row().classes("items-center mt-2").style("gap: 12px;")

        ui.separator().classes("my-4")
        with ui.card().classes("p-4"):
            ui.label("4) Synthese extraite").classes("text-lg font-semibold")
            self.last_extract_label = ui.label("Derniere analyse : -").classes("text-xs text-gray-500")
            self.fields_container = ui.column().classes("w-full")
            ui.separator().classes("my-3")
            ui.label("Resume (markdown)").classes("text-sm text-gray-600")
            self.summary_md = ui.markdown("").classes("mt-2 w-full")

        existing = app.storage.user.get(ASSISTANT_EXTRACTION_KEY)
        if isinstance(existing, dict):
            created_at = existing.get("created_at", "")
            if created_at and self.last_extract_label:
                self.last_extract_label.text = f"Derniere analyse : {created_at}"
            self._render_extracted_fields(existing)
            if self.summary_md:
                summary_md = str(existing.get("summary_markdown") or "")
                if summary_md.strip():
                    self.summary_md.set_content(summary_md)


def render():
    AssistantPage().render()
