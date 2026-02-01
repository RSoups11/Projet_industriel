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
import unicodedata
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

OLLAMA_URL = "http://localhost:11434"
MODEL_NAME = "qwen2.5:14b-instruct"
MIN_TEXT_CHARS_BEFORE_OCR = 800

ASSISTANT_STATE_KEY = "assistant_state_v1"
ASSISTANT_EXTRACTION_KEY = "assistant_extraction_v1"

_FALLBACK_STATE: Dict[str, Any] = {}


def _safe_user_get(key: str, default: Any = None) -> Any:
    try:
        return app.storage.user.get(key, default)
    except AssertionError:
        return _FALLBACK_STATE.get(key, default)


def _safe_user_set(key: str, value: Any) -> None:
    try:
        app.storage.user[key] = value
    except AssertionError:
        _FALLBACK_STATE[key] = value

MAX_CHARS_PER_DOC = 6000
MAX_TOTAL_CHARS = 12000

NUM_CTX = 16384
OCR_DPI = int(os.getenv("OCR_DPI", "350"))


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
    state = _safe_user_get(ASSISTANT_STATE_KEY)
    if not isinstance(state, dict):
        session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        session_dir = UPLOADS_ROOT / session_id
        session_dir.mkdir(parents=True, exist_ok=True)
        state = {"session_id": session_id, "session_dir": str(session_dir), "uploaded": []}
        _safe_user_set(ASSISTANT_STATE_KEY, state)
        return state

    session_dir = Path(state.get("session_dir", "") or "")
    if not str(session_dir):
        session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        session_dir = UPLOADS_ROOT / session_id
        state["session_id"] = session_id
        state["session_dir"] = str(session_dir)
        state["uploaded"] = []
        _safe_user_set(ASSISTANT_STATE_KEY, state)

    session_dir.mkdir(parents=True, exist_ok=True)
    if "uploaded" not in state or not isinstance(state["uploaded"], list):
        state["uploaded"] = []
        _safe_user_set(ASSISTANT_STATE_KEY, state)

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
        self.analyze_btn = None
        self.analyze_spinner = None

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
            _safe_user_set(ASSISTANT_STATE_KEY, self.state)
        return upl  # type: ignore[return-value]

    def _set_uploaded(self, uploaded: List[Dict[str, Any]]) -> None:
        self.state["uploaded"] = uploaded
        _safe_user_set(ASSISTANT_STATE_KEY, self.state)

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

    def _extract_text_ocr_page(self, path: Path, page_index: int) -> str:
        if convert_from_path is None or pytesseract is None:
            raise RuntimeError("OCR non disponible (pdf2image/pytesseract/tesseract/poppler manquants)")
        if POPPLER_PATH:
            images = convert_from_path(
                str(path),
                dpi=OCR_DPI,
                first_page=page_index + 1,
                last_page=page_index + 1,
                poppler_path=POPPLER_PATH,
                grayscale=True,
            )
        else:
            images = convert_from_path(
                str(path),
                dpi=OCR_DPI,
                first_page=page_index + 1,
                last_page=page_index + 1,
                grayscale=True,
            )
        if not images:
            return ""
        return pytesseract.image_to_string(images[0], lang="fra").strip()

    def _is_toc_page(self, text: str) -> bool:
        if not text:
            return False
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        if not lines:
            return False
        dot_lines = sum(1 for ln in lines if ln.count('.') >= 6)
        many_dots_ratio = dot_lines / max(1, len(lines))
        if many_dots_ratio > 0.25:
            return True
        # Many page numbers / leader dots
        leaders = sum(1 for ln in lines if re.search(r"\.{3,}\s*\d+", ln))
        if leaders >= 3:
            return True
        return False

    def _detect_doc_type(self, filename: str, first_page_text: str) -> str:
        name = self._norm_for_match(filename)
        text = self._norm_for_match(first_page_text)
        if "reglementdeconsultation" in name or "reglementdeconsultation" in text:
            return "RC"
        if "ccap" in name or "ccap" in text:
            return "CCAP"
        if "cctc" in name or "cctc" in text:
            return "CCTC"
        if "cctp" in name or "cctp" in text:
            return "CCTP"
        if "dpgf" in name or "decompositionduprixglobal" in text:
            return "DPGF"
        return "AUTRE"

    def _snippets_around_keywords(self, text: str, keywords: List[str], window: int = 4, max_chars: int = 3500) -> str:
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        if not lines:
            return ""
        nlines = [self._norm_for_match(ln) for ln in lines]
        nkeys = [self._norm_for_match(k) for k in keywords]
        keep = set()
        for i, nln in enumerate(nlines):
            if any(k in nln for k in nkeys):
                for j in range(max(0, i - window), min(len(lines), i + window + 1)):
                    keep.add(j)
        if not keep:
            out = "\n".join(lines[:60])
        else:
            out = "\n".join(lines[i] for i in sorted(keep))
        return out[:max_chars]

    def _retrieve_candidate_pages(self, pages: List[Dict[str, Any]], field: str, priorities: List[str], keywords: List[str], strict: bool = False) -> List[Dict[str, Any]]:
        filtered = [p for p in pages if p.get("doc_type") in priorities]
        if strict and not filtered:
            return []
        if not filtered:
            filtered = pages

        scored: List[Dict[str, Any]] = []
        for p in filtered:
            txt = p.get("text", "") or ""
            if not txt:
                continue
            if self._is_toc_page(txt):
                continue

            low = self._strip_accents(txt).lower()
            low = " ".join(low.split())
            score = 0
            for kw in keywords:
                kw2 = self._strip_accents(kw).lower()
                kw2 = " ".join(kw2.split())
                if kw2 in low:
                    score += 1
            if field == "contact_referent" and "@" in txt:
                score += 2
            if field == "date_limite_remise_offres" and re.search(r"\d{1,2}\s*[./-]\s*\d{1,2}\s*[./-]\s*\d{2,4}", txt):
                score += 2
            if field == "criteres_attribution" and "%" in txt:
                score += 2
            scored.append({"_score": score, "_len": len(txt), **p})

        scored.sort(key=lambda x: (x.get("_score", 0), x.get("_len", 0)), reverse=True)
        top = [p for p in scored if p.get("_score", 0) > 0][:12]
        if not top:
            top = scored[:12]
        if not top and filtered:
            top = filtered[:12]
        return top

    def _llm_extract_field(self, field: str, pages: List[Dict[str, Any]], keywords: List[str]) -> Dict[str, Any]:
        if not pages:
            return {"value": "NR", "confidence": 0.1}
        blocks = []
        for p in pages:
            snippet = self._snippets_around_keywords(p["text"], keywords)
            blocks.append("[DOC={}|TYPE={}|PAGE={}]\n{}".format(p["filename"], p["doc_type"], p["page"] + 1, snippet))
        context = "\n\n".join(blocks)
        prompt = f"""
Tu dois extraire uniquement le champ suivant: {field}.
Retourne STRICTEMENT un JSON valide, sans texte autour, avec ce schema:
{{
  \"champ\": \"{field}\",
  \"value\": \"...\",
  \"source\": {{\"document\": \"...\", \"page\": 1}},
  \"evidence\": \"...\",
  \"confidence\": 0.0
}}
Regles: si non trouve, value=\"NR\" et confidence<=0.2. Ne pas inventer.

CONTEXT:
{context}
""".strip()
        data = self._ollama_chat_json(prompt)
        if not isinstance(data, dict) or 'value' not in data:
            return {"value": "NR", "confidence": 0.1}
        return data
    def _extract_text_ocr(self, path: Path) -> str:
        if convert_from_path is None or pytesseract is None:
            raise RuntimeError("OCR non disponible (pdf2image/pytesseract/tesseract/poppler manquants)")
        if POPPLER_PATH:
            images = convert_from_path(str(path), dpi=OCR_DPI, poppler_path=POPPLER_PATH, grayscale=True)
        else:
            images = convert_from_path(str(path), dpi=OCR_DPI, grayscale=True)
        return "\n".join(pytesseract.image_to_string(img, lang="fra") for img in images).strip()

    def _extract_text(self, path: Path) -> str:
        txt = self._extract_text_pypdf(path)
        if len(txt) < MIN_TEXT_CHARS_BEFORE_OCR:
            ocr_txt = self._extract_text_ocr(path)
            if len(ocr_txt) > len(txt):
                txt = ocr_txt
        return txt

    def _extract_text_with_meta(self, path: Path) -> Dict[str, Any]:
        meta: Dict[str, Any] = {
            "filename": path.name,
            "pypdf_chars": 0,
            "ocr_chars": 0,
            "ocr_used": False,
            "ocr_error": "",
        }
        txt_pypdf = self._extract_text_pypdf(path)
        meta["pypdf_chars"] = len(txt_pypdf)

        if len(txt_pypdf) >= MIN_TEXT_CHARS_BEFORE_OCR:
            meta["text"] = txt_pypdf
            return meta

        meta["ocr_used"] = True
        try:
            ocr_txt = self._extract_text_ocr(path)
            meta["ocr_chars"] = len(ocr_txt)
            if len(ocr_txt) > len(txt_pypdf):
                meta["text"] = ocr_txt
            else:
                meta["text"] = txt_pypdf
        except Exception as ex:
            meta["ocr_error"] = str(ex)
            meta["text"] = txt_pypdf

        return meta

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

    def _strip_accents(self, text: str) -> str:
        return "".join(
            ch for ch in unicodedata.normalize("NFD", text) if unicodedata.category(ch) != "Mn"
        )

    def _norm_for_match(self, s: str) -> str:
        s = self._strip_accents(s).lower()
        s = s.replace("’", "'").replace("œ", "oe")
        s = re.sub(r"[^a-z0-9]+", "", s)
        return s

    def _normalize_lines(self, text: str) -> List[str]:
        return [ln.strip() for ln in text.splitlines() if ln.strip()]

    # Backward-compat alias for any older calls
    def _normalize_line(self, text: str) -> List[str]:
        return self._normalize_lines(text)

    def _find_lines_with(self, lines: List[str], patterns: List[str]) -> List[str]:
        out = []
        for ln in lines:
            nln = self._strip_accents(ln).lower()
            if any(re.search(pat, nln) for pat in patterns):
                out.append(ln)
        return out

    def _find_value_near(self, lines: List[str], patterns: List[str], max_lines: int = 4) -> str:
        nlines = [self._strip_accents(ln).lower() for ln in lines]
        for i, nln in enumerate(nlines):
            if any(re.search(pat, nln) for pat in patterns):
                # try same line
                if lines[i].strip() and len(lines[i].strip()) > 4:
                    return lines[i].strip()
                # else look ahead
                block = []
                for j in range(1, max_lines + 1):
                    if i + j >= len(lines):
                        break
                    nxt = lines[i + j].strip()
                    if not nxt:
                        break
                    block.append(nxt)
                return " ".join(block).strip()
        return ""

    def _find_date_near(self, lines: List[str], patterns: List[str]) -> str:
        mois_map = {
            "janvier": "01", "fevrier": "02", "f?vrier": "02", "mars": "03", "avril": "04",
            "mai": "05", "juin": "06", "juillet": "07", "aout": "08", "ao?t": "08",
            "septembre": "09", "octobre": "10", "novembre": "11", "decembre": "12", "d?cembre": "12",
        }
        nlines = [self._strip_accents(ln).lower() for ln in lines]
        for i, nln in enumerate(nlines):
            if any(re.search(pat, nln) for pat in patterns):
                m = re.search(r"(\d{1,2}\s*[./-]\s*\d{1,2}\s*[./-]\s*\d{2,4})", lines[i])
                if m:
                    return re.sub(r"\s+", "", m.group(1))
                for j in range(1, 4):
                    if i + j < len(lines):
                        m2 = re.search(r"(\d{1,2}\s*[./-]\s*\d{1,2}\s*[./-]\s*\d{2,4})", lines[i + j])
                        if m2:
                            return re.sub(r"\s+", "", m2.group(1))
        return ""

    def _parse_lot_from_filename(self, filename: str) -> str:
        name = self._strip_accents(filename).lower()
        m = re.search(r"lot\s*[_-]?\s*(\d{1,2})", name)
        if m:
            lot = f"Lot {m.group(1)}"
            if "charpente" in name:
                lot += " - Charpente"
            if "bois" in name:
                lot += " bois"
            return lot
        m = re.search(r"_lot_\s*(\d{1,2})", name)
        if m:
            lot = f"Lot {m.group(1)}"
            if "charpente" in name:
                lot += " - Charpente"
            if "bois" in name:
                lot += " bois"
            return lot
        return ""

    def _regex_extract(self, docs: List[Dict[str, Any]]) -> Dict[str, Any]:
        def score_address(line: str) -> int:
            nln = self._strip_accents(line).lower()
            score = 0
            if re.search(r"\d{1,3}\s+", line):
                score += 2
            if re.search(r"\b(rue|avenue|av\.|boulevard|bd|route|chemin|impasse|allee)\b", nln):
                score += 2
            if re.search(r"\b\d{5}\b", line):
                score += 2
            if re.search(r"\b(bp|boite postale)\b", nln):
                score -= 1
            if "commune" in nln or "mairie" in nln:
                score -= 1
            if "chantier" in nln:
                score += 1
            if "region" in nln or "zone" in nln or "site" in nln:
                score -= 2
            return score

        def best_line(lines: List[str], patterns: List[str]) -> str:
            candidates = self._find_lines_with(lines, patterns)
            if not candidates:
                return ""
            return max(candidates, key=len)

        def extract_roles(lines: List[str]) -> str:
            nlines = [self._strip_accents(ln).lower() for ln in lines]
            roles = []
            roles_map = [
                (r"architecte", "Architecte"),
                (r"economiste", "Economiste"),
                (r"be fluides|bet fluides|bureau d'etudes", "BET fluides"),
            ]
            for pat, label in roles_map:
                for i, nln in enumerate(nlines):
                    if re.search(pat, nln):
                        block = []
                        for j in range(1, 4):
                            if i + j >= len(lines):
                                break
                            nxt = lines[i + j].strip()
                            if not nxt:
                                break
                            if re.search(r"^(architecte|economiste|be fluides|maitre d.?oeuvre|maitre d.?ouvrage)", self._strip_accents(nxt).lower()):
                                break
                            block.append(nxt)
                        if block:
                            roles.append(f"{block[0]} ({label})")
                        break
            return " - ".join(roles).strip()

        def extract_criteria(lines: List[str]) -> str:
            nlines = [self._strip_accents(ln).lower() for ln in lines]
            for i, nln in enumerate(nlines):
                if "crit" in nln or "ponder" in nln:
                    window = " ".join(lines[i:i+4])
                    if "%" in window:
                        return window.strip()
            for ln in lines:
                if "%" in ln:
                    return ln.strip()
            return ""

        def extract_contact(lines: List[str]) -> str:
            emails = [ln for ln in lines if "@" in ln]
            if emails:
                return emails[0].strip()
            return self._find_value_near(lines, [r"contact", r"telephone", r"tel", r"courriel", r"email"], max_lines=3)

        def extract_visite(lines: List[str]) -> str:
            nlines = [self._strip_accents(ln).lower() for ln in lines]
            for i, nln in enumerate(nlines):
                if "visite" in nln:
                    window = " ".join(lines[i:i+3]).strip()
                    if window:
                        return window
            return ""

        def extract_duree(lines: List[str]) -> str:
            nlines = [self._strip_accents(ln).lower() for ln in lines]
            for i, nln in enumerate(nlines):
                if "delai d'execution" in nln or "duree d'execution" in nln or "delai" in nln:
                    window = " ".join(lines[i:i+2]).strip()
                    if window:
                        return window
            return ""

        operation = ""
        lot = ""
        moa = ""
        moe = ""
        adresse = ""
        type_proc = ""
        date_limite = ""
        duree = ""
        visite = ""
        contact = ""
        criteres = ""
        dates_all: List[str] = []

        for d in docs:
            filename = d.get("filename", "")
            text = d.get("text", "") or ""
            lines = self._normalize_lines(text)
            if not lines:
                continue

            if not lot:
                lot = self._parse_lot_from_filename(filename)
            if not lot:
                for ln in lines:
                    nln = self._strip_accents(ln).lower()
                    if re.search(r"\blot\b", nln):
                        # capture numeric + label if present
                        m = re.search(r"lot\s*n?\s*°?\s*(\d{1,2})", nln)
                        if m:
                            lot = f"Lot {m.group(1)}"
                        else:
                            lot = ln.strip()
                        # append known trade keywords
                        if "charpente" in nln and "charpente" not in lot.lower():
                            lot += " - Charpente"
                        if "bois" in nln and "bois" not in lot.lower():
                            lot += " bois"
                        break

            # Operation title
            op_line = best_line(lines, [r"renovation", r"rehabilitation", r"travaux", r"construction"])
            if op_line and len(op_line) > len(operation):
                operation = op_line
                # join with next short line if it looks like a title continuation
                try:
                    idx = lines.index(op_line)
                    if idx + 1 < len(lines):
                        nxt = lines[idx + 1]
                        if len(nxt) <= 30 and nxt.isupper():
                            operation = f"{operation} {nxt}".strip()
                    # try to capture chantier address right after operation title
                    for j in range(1, 4):
                        if idx + j < len(lines):
                            cand = lines[idx + j]
                            if score_address(cand) >= 3:
                                adresse = cand.strip()
                                break
                except Exception:
                    pass

            # MOA
            if not moa:
                moa = self._find_value_near(lines, [r"maitre d.?ouvrage", r"pouvoir adjudicateur"], max_lines=6)
            if not moa:
                moa = best_line(lines, [r"commune de", r"ville de", r"metropole", r"communaute"])

            # MOE
            if not moe:
                moe = extract_roles(lines)
            if not moe:
                moe = self._find_value_near(lines, [r"maitre d.?oeuvre", r"architecte"], max_lines=4)

            # Adresse chantier
            if not adresse:
                addr_candidates = [ln for ln in lines if score_address(ln) >= 3]
                if addr_candidates:
                    adresse = max(addr_candidates, key=score_address)
            if not adresse:
                adresse = self._find_value_near(lines, [r"adresse du chantier", r"adresse", r"chantier", r"lieu"], max_lines=3)

            # Type procedure + date limite: prefer RC doc
            if ("reglement" in self._strip_accents(filename).lower()) or ("rc" in self._strip_accents(filename).lower()):
                if not type_proc:
                    type_proc = best_line(lines, [r"procedure", r"marche public", r"marche selon procedure"])
                if not date_limite:
                    date_limite = self._find_date_near(lines, [r"date limite", r"remise des offres", r"limite de remise"])
                if not visite:
                    visite = extract_visite(lines)
                if not criteres:
                    criteres = extract_criteria(lines)
                if not contact:
                    contact = extract_contact(lines)

            if not duree:
                duree = extract_duree(lines)

            if not contact:
                contact = extract_contact(lines)

            dates_all.extend(re.findall(r"\d{1,2}[./-]\d{1,2}[./-]\d{2,4}", text))

        dates_importantes = list(dict.fromkeys(dates_all))[:8]

        return {
            "fields": {
                "intitule_operation": operation,
                "intitule_lot": lot,
                "maitre_ouvrage": moa,
                "adresse_chantier": adresse,
                "maitre_oeuvre": moe,
                "type_marche_procedure": type_proc,
                "date_limite_remise_offres": date_limite,
                "duree_delai_execution": duree,
                "visite_obligatoire": visite,
                "contact_referent": contact,
                "montant_estime_budget": "",
                "variantes_pse": "",
                "criteres_attribution": criteres,
            },
            "dates_importantes": dates_importantes,
        }

    def _ollama_generate(self, prompt: str) -> str:
        r = requests.post(
            f"{OLLAMA_URL}/api/generate",
            json={"model": MODEL_NAME, "prompt": prompt, "stream": False},
            timeout=600,
        )
        r.raise_for_status()
        return (r.json().get("response") or "").strip()

    def _ollama_generate_json(self, prompt: str) -> Dict[str, Any]:
        r = requests.post(
            f"{OLLAMA_URL}/api/generate",
            json={
                "model": MODEL_NAME,
                "prompt": prompt,
                "stream": False,
                "format": "json",
                "options": {"temperature": 0.2, "top_p": 0.9, "num_ctx": NUM_CTX},
            },
            timeout=600,
        )
        r.raise_for_status()
        raw = (r.json().get("response") or "").strip()
        return self._try_parse_json(raw)

    def _ollama_chat_json(self, prompt: str) -> Dict[str, Any]:
        system = (
            "Tu es un extracteur d'informations DCE. "
            "Reponds uniquement avec un JSON valide, sans texte autour."
        )
        payload = {
            "model": MODEL_NAME,
            "stream": False,
            "format": "json",
            "options": {"temperature": 0.2, "top_p": 0.9, "num_ctx": NUM_CTX},
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
        }
        r = requests.post(f"{OLLAMA_URL}/api/chat", json=payload, timeout=600)
        r.raise_for_status()
        raw = (r.json().get("message") or {}).get("content") or ""
        return self._try_parse_json(raw.strip())

    def _try_parse_json(self, raw: str) -> Dict[str, Any]:
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

    def _validate_field_value(self, field: str, value: str) -> str:
        if not value:
            return ""
        v = value.strip()
        if field == "date_limite_remise_offres":
            if not re.search(r"\b\d{1,2}[./-]\d{1,2}[./-]\d{2,4}\b", v):
                return ""
        if field == "criteres_attribution":
            if "%" not in v and not re.search(r"\b\d{1,2}\s*[:/-]\s*\d{1,2}\b", v):
                return ""
        if field == "intitule_lot":
            if len(v) > 80:
                return ""
            if not re.search(r"[A-Za-z]", v):
                return ""
        return v

    def _is_missing_value(self, v: Any) -> bool:
        if v is None:
            return True
        s = str(v).strip().lower()
        return s == "" or s in {"nr", "non mentionne", "non mentionnee", "n/a", "na"}

    def _extract_dates_importantes(self, pages: List[Dict[str, Any]]) -> List[str]:
        keywords = ["remise", "offres", "visite", "questions", "delai", "notification", "debut", "fin", "validite"]
        found: List[str] = []
        for p in pages:
            lines = [ln.strip() for ln in p.get("text", "").splitlines() if ln.strip()]
            if not lines:
                continue
            nlines = [self._norm_for_match(ln) for ln in lines]
            for i, ln in enumerate(lines):
                raw = re.findall(r"\b(\d{1,2}\s*[./-]\s*\d{1,2}\s*[./-]\s*\d{4})\b", ln)
                for m in raw:
                    d2 = re.sub(r"\s+", "", m)
                    try:
                        dd, mm, yyyy = re.split(r"[./-]", d2)
                        dd_i, mm_i, yy_i = int(dd), int(mm), int(yyyy)
                        if not (1 <= dd_i <= 31 and 1 <= mm_i <= 12 and 1900 <= yy_i <= 2100):
                            continue
                    except Exception:
                        continue
                    ctx = " ".join(nlines[max(0, i-1):min(len(nlines), i+2)])
                    if any(k in ctx for k in keywords):
                        found.append(d2)
        # unique, keep order
        out: List[str] = []
        seen = set()
        for d in found:
            if d in seen:
                continue
            seen.add(d)
            out.append(d)
        return out

    def _generate_summary_blocking(self) -> Dict[str, Any]:
        uploaded = self._get_uploaded()
        pages: List[Dict[str, Any]] = []
        debug_lines: List[str] = []

        debug_lines.append("== FICHIERS UPLOADES ==")
        for f in uploaded:
            try:
                size = Path(f["abs_path"]).stat().st_size
            except Exception:
                size = 0
            debug_lines.append(f"- {f.get('filename')} | path={f.get('abs_path')} | size={size} bytes")

        for f in uploaded:
            path = Path(f["abs_path"])
            filename = f["filename"]
            doc_pages: List[Dict[str, Any]] = []
            total_pages = 0
            pypdf_pages = 0
            ocr_pages = 0
            pypdf_chars = 0
            ocr_chars = 0

            first_pages_text = ""
            base_type = "AUTRE"
            if PdfReader is not None:
                try:
                    reader = PdfReader(str(path))
                    total_pages = len(reader.pages)
                    for i, page in enumerate(reader.pages):
                        txt = (page.extract_text() or "").strip()
                        if txt:
                            pypdf_pages += 1
                            pypdf_chars += len(txt)
                        # OCR if empty or too short
                        ocr_txt = ""
                        ocr_used = False
                        if len(txt) < MIN_TEXT_CHARS_BEFORE_OCR:
                            try:
                                ocr_txt = self._extract_text_ocr_page(path, i)
                            except Exception as ex:
                                debug_lines.append(f"  OCR error {filename} p{i+1}: {ex}")
                            if len(ocr_txt) > len(txt):
                                txt = ocr_txt
                                ocr_used = True
                        if ocr_used:
                            ocr_pages += 1
                            ocr_chars += len(ocr_txt)
                        if i < 2:
                            first_pages_text += " " + txt
                        page_norm = self._norm_for_match(txt)
                        if "dpgf" in page_norm or "decompositionduprixglobal" in page_norm:
                            doc_type_page = "DPGF"
                        elif "cctp" in page_norm:
                            doc_type_page = "CCTP"
                        elif "cctc" in page_norm:
                            doc_type_page = "CCTC"
                        else:
                            doc_type_page = "__BASE__"
                        doc_pages.append({
                            "filename": filename,
                            "page": i,
                            "text": txt,
                            "ocr": ocr_used,
                            "doc_type": doc_type_page,
                        })
                except Exception as ex:
                    debug_lines.append(f"  Error reading {filename}: {ex}")

            base_type = self._detect_doc_type(filename, first_pages_text)
            for p in doc_pages:
                if p.get("doc_type") == "__BASE__":
                    p["doc_type"] = base_type

            for p in doc_pages:
                pages.append(p)

            # Debug per-file summary
            debug_lines.append("")
            debug_lines.append(f"== {filename} ==")
            debug_lines.append(f"doc_type={base_type} total_pages={total_pages} pypdf_pages={pypdf_pages} ocr_pages={ocr_pages}")
            debug_lines.append(f"pypdf_chars={pypdf_chars} ocr_chars={ocr_chars}")
            # sample snippets
            if doc_pages:
                sample_pages = []
                if len(doc_pages) >= 1:
                    sample_pages.append(doc_pages[0])
                if len(doc_pages) >= 2:
                    sample_pages.append(doc_pages[1])
                longest = max(doc_pages, key=lambda x: len(x.get("text", "")))
                if longest not in sample_pages:
                    sample_pages.append(longest)
                for sp in sample_pages:
                    lines = [ln for ln in sp.get("text", "").splitlines() if ln.strip()]
                    preview = " | ".join(lines[:2]) if lines else ""
                    debug_lines.append(f"p{sp['page']+1} ocr={sp['ocr']} chars={len(sp.get('text',''))} :: {preview}")

        # Global stats by file
        debug_lines.append("")
        debug_lines.append("=== PAGE STATS ===")
        stats: Dict[str, Dict[str, int]] = {}
        for p in pages:
            fn = p.get("filename", "unknown")
            stats.setdefault(fn, {})
            stats[fn]["pages"] = stats[fn].get("pages", 0) + 1
            stats[fn]["non_empty"] = stats[fn].get("non_empty", 0) + (1 if p.get("text") else 0)
            stats[fn]["ocr_pages"] = stats[fn].get("ocr_pages", 0) + (1 if p.get("ocr") else 0)
            dtype = p.get("doc_type", "AUTRE")
            stats[fn][f"type_{dtype}"] = stats[fn].get(f"type_{dtype}", 0) + 1
        for fn, c in stats.items():
            types = " ".join([f"{k.replace('type_','')}={v}" for k, v in c.items() if k.startswith("type_")])
            debug_lines.append(f"{fn} | pages={c.get('pages',0)} non_empty={c.get('non_empty',0)} ocr_pages={c.get('ocr_pages',0)} | {types}")

        # Field config: priorities + keywords
        field_cfg = {
            "intitule_operation": {
                "priorities": ["CCTP", "CCTC", "DPGF", "CCAP", "RC"],
                "keywords": ["renovation", "rehabilitation", "travaux", "operation"],
                "strict": False,
            },
            "intitule_lot": {
                "priorities": ["CCTP", "DPGF"],
                "keywords": ["lot", "charpente", "bois"],
                "strict": True,
            },
            "maitre_ouvrage": {
                "priorities": ["RC", "CCAP", "CCTP", "CCTC"],
                "keywords": ["maitre d'ouvrage", "maitre d ouvrage", "pouvoir adjudicateur"],
                "strict": False,
            },
            "adresse_chantier": {
                "priorities": ["CCTP", "CCTC", "DPGF", "RC"],
                "keywords": ["adresse", "chantier", "lieu", "site", "liberation"],
                "strict": False,
            },
            "maitre_oeuvre": {
                "priorities": ["CCTP", "CCTC", "DPGF", "CCAP"],
                "keywords": ["architecte", "maitre d'oeuvre", "maitre d oeuvre", "economiste"],
                "strict": False,
            },
            "type_marche_procedure": {
                "priorities": ["RC"],
                "keywords": ["procedure", "marche public", "procedure adaptee"],
                "strict": True,
            },
            "date_limite_remise_offres": {
                "priorities": ["RC"],
                "keywords": ["date limite", "remise des offres", "limite de remise"],
                "strict": True,
            },
            "duree_delai_execution": {
                "priorities": ["RC", "CCAP"],
                "keywords": ["delai", "duree", "execution"],
                "strict": False,
            },
            "visite_obligatoire": {
                "priorities": ["RC"],
                "keywords": ["visite"],
                "strict": True,
            },
            "contact_referent": {
                "priorities": ["RC", "CCAP"],
                "keywords": ["courriel", "email", "contact", "telephone", "tel"],
                "strict": False,
            },
            "montant_estime_budget": {
                "priorities": ["DPGF"],
                "keywords": ["total", "total ht", "total ttc", "tva", "montant", "euros"],
                "strict": True,
            },
            "variantes_pse": {
                "priorities": ["RC"],
                "keywords": ["variante", "pse", "option"],
                "strict": True,
            },
            "criteres_attribution": {
                "priorities": ["RC"],
                "keywords": ["critere", "ponderation", "%"],
                "strict": True,
            },
        }

        fields: Dict[str, Any] = {}
        sources: List[str] = []
        debug_lines.append("")
        debug_lines.append("== SELECTION PAGES PAR CHAMP ==")

        # Deterministic extraction for specific fields (RC OCR)
        rc_pages = [p for p in pages if p.get("doc_type") == "RC" and p.get("text")]
        rc_text = "\n".join(p.get("text", "") for p in rc_pages)
        det_fields: Dict[str, str] = {}
        if rc_text:
            det_date = self._find_date_near(rc_text.splitlines(), ["date limite", "remise des offres", "heure limite"])
            if det_date:
                det_fields["date_limite_remise_offres"] = det_date
            low = self._strip_accents(rc_text).lower()
            if "visite" in low and ("non obligatoire" in low or "facultative" in low):
                det_fields["visite_obligatoire"] = "Non"
            elif "visite" in low and "obligatoire" in low:
                det_fields["visite_obligatoire"] = "Oui"
            emails = re.findall(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", rc_text)
            tels = re.findall(r"(?:\+33|0)\s*[1-9](?:[\s\.-]?\d{2}){4}", rc_text)
            contact_parts = []
            if emails:
                contact_parts.append(emails[0])
            if tels:
                contact_parts.append(tels[0])
            if contact_parts:
                det_fields["contact_referent"] = " - ".join(contact_parts)
        for field, cfg in field_cfg.items():
            candidate_pages = self._retrieve_candidate_pages(pages, field, cfg["priorities"], cfg["keywords"], strict=cfg.get("strict", False))
            if field in det_fields:
                value = det_fields[field]
                llm_data = {}
            else:
                llm_data = self._llm_extract_field(field, candidate_pages, cfg["keywords"])
                value = llm_data.get("value", "NR")
            fields[field] = self._validate_field_value(field, self._normalize_value(value))
            src = llm_data.get("source", {}) if isinstance(llm_data, dict) else {}
            if isinstance(src, dict) and src.get("document"):
                sources.append(str(src.get("document")))
            if candidate_pages:
                for p in candidate_pages:
                    debug_lines.append(f"{field}: {p.get('filename')} p{p.get('page',0)+1} type={p.get('doc_type')} score={p.get('_score','-')}")
            else:
                debug_lines.append(f"{field}: <no candidates>")

        # Regex merge as safety
        regex_data = self._regex_extract(pages)
        if isinstance(regex_data.get("fields"), dict):
            for k, v in regex_data["fields"].items():
                if self._is_missing_value(fields.get(k)) and not self._is_missing_value(v):
                    fields[k] = v

        dates_importantes = self._extract_dates_importantes(pages)

        prefill = {
            "intitule": fields.get("intitule_operation", ""),
            "lot": fields.get("intitule_lot", ""),
            "moa": fields.get("maitre_ouvrage", ""),
            "adresse": fields.get("adresse_chantier", ""),
        }

        out_pdf = self.session_dir / "resume_ia.pdf"
        self._write_markdown_pdf(out_pdf, "Resume IA - Memoire technique", fields, "")

        debug_path = self.session_dir / "debug_extraction.txt"
        try:
            debug_path.write_text("\n".join(debug_lines), encoding="utf-8")
        except Exception:
            pass

        payload = {
            "fields": fields,
            "summary_markdown": "",
            "dates_importantes": dates_importantes,
            "sources": list(dict.fromkeys(sources))[:8],
            "prefill": prefill,
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "debug_url": f"/_uploads/{self.session_id}/debug_extraction.txt",
        }

        _safe_user_set(ASSISTANT_EXTRACTION_KEY, payload)

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

        if self.analyze_btn:
            self.analyze_btn.disable()
        if self.analyze_spinner:
            self.analyze_spinner.set_visibility(True)

        try:
            ui.notify("Analyse en cours (OCR + IA)...", type="info")
        except Exception:
            pass
        if self.summary_md:
            try:
                self.summary_md.set_content("Analyse en cours...")
            except Exception:
                pass

        try:
            result = await asyncio.to_thread(self._generate_summary_blocking)
            data = result.get("data", {}) if isinstance(result, dict) else {}

            if self.summary_link_row:
                try:
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
                        if isinstance(data, dict) and data.get("debug_url"):
                            ui.html(
                                f"""
                                <a href="{data['debug_url']}"
                                   target="_blank"
                                   class="text-gray-700 underline text-sm">
                                   Ouvrir debug extraction
                                </a>
                                """,
                                sanitize=False,
                            )
                except Exception:
                    # Client was closed or element removed
                    return

            if self.last_extract_label and isinstance(data, dict):
                try:
                    created_at = data.get("created_at", "")
                    if created_at:
                        self.last_extract_label.text = f"Derniere analyse : {created_at}"
                except Exception:
                    return

            if isinstance(data, dict):
                try:
                    self._render_extracted_fields(data)
                except Exception:
                    return

            if self.summary_md:
                try:
                    self.summary_md.set_content("")
                except Exception:
                    pass

            try:
                ui.notify("Analyse terminee. PDF genere.", type="positive")
            except Exception:
                pass

        except Exception as e:
            try:
                ui.notify(f"Erreur analyse: {e}", type="negative")
            except Exception:
                pass
        finally:
            if self.analyze_spinner:
                self.analyze_spinner.set_visibility(False)
            if self.analyze_btn:
                self.analyze_btn.enable()

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
            ui.label("3) Analyse").classes("text-lg font-semibold")
            with ui.row().classes("items-center gap-2"):
                self.analyze_btn = ui.button("Analyser", on_click=self._on_click_analyze).props("color=primary").classes("w-full")
                self.analyze_spinner = ui.spinner(size="md").classes("text-blue-600").set_visibility(False)
            self.summary_link_row = ui.row().classes("items-center mt-2").style("gap: 12px;")

        ui.separator().classes("my-4")
        with ui.card().classes("p-4"):
            ui.label("4) Synthese extraite").classes("text-lg font-semibold")
            self.last_extract_label = ui.label("Derniere analyse : -").classes("text-xs text-gray-500")
            self.fields_container = ui.column().classes("w-full")
            ui.separator().classes("my-3")
            self.summary_md = ui.markdown("").classes("mt-2 w-full hidden")

        existing = _safe_user_get(ASSISTANT_EXTRACTION_KEY)
        if isinstance(existing, dict):
            created_at = existing.get("created_at", "")
            if created_at and self.last_extract_label:
                self.last_extract_label.text = f"Derniere analyse : {created_at}"
            self._render_extracted_fields(existing)
            if self.summary_md:
                self.summary_md.set_content("")


def render():
    AssistantPage().render()
