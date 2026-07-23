from __future__ import annotations

import csv
import hmac
import io
import json
import mimetypes
import os
import re
import secrets
import shutil
import smtplib
import subprocess
import sys
import threading
import traceback
import zipfile
from datetime import datetime, timedelta
from email.message import EmailMessage
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from xml.etree import ElementTree as ET


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = Path(os.environ.get("DIPLOMAS_DATA_DIR", str(BASE_DIR / "data"))).resolve()
UPLOAD_DIR = DATA_DIR / "uploads"
GENERATED_DIR = DATA_DIR / "generated"
STATE_FILE = DATA_DIR / "state.json"
STATIC_DIR = BASE_DIR / "static"
DEFAULT_TEMPLATE_ID = "mainjobs-diploma-oficial"
DEFAULT_TEMPLATE_PATH = BASE_DIR / "DIPLOMA_VERSION_FINAL_CORREGIDA.docx"

REQUIRED_COLUMNS = [
    "NOMBRE",
    "APELLIDOS",
    "DNI",
    "FECHA",
    "ACTIVIDAD",
    "CONTENIDO",
    "ESPECIALIDAD",
    "HORAS",
]
OPTIONAL_COLUMNS = ["UBICACIÓN", "EMAIL", "ENVIADO"]
ALL_COLUMNS = ["UBICACIÓN", *REQUIRED_COLUMNS, "EMAIL", "ENVIADO"]
PLACEHOLDER_COLUMNS = ALL_COLUMNS
WORD_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
XML_NS = "http://www.w3.org/XML/1998/namespace"

USERS = {
    os.environ.get("ADMIN_USERNAME", "admin"): {
        "password": os.environ.get("ADMIN_PASSWORD", "admin123"),
        "role": "administrador",
        "name": os.environ.get("ADMIN_NAME", "Administrador"),
    },
    os.environ.get("USER_USERNAME", "usuario"): {
        "password": os.environ.get("USER_PASSWORD", "usuario123"),
        "role": "usuario",
        "name": os.environ.get("USER_NAME", "Usuario"),
    },
}

SESSIONS: dict[str, dict] = {}
STATE_LOCK = threading.RLock()


def ensure_dirs() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    GENERATED_DIR.mkdir(parents=True, exist_ok=True)
    if not STATE_FILE.exists():
        save_state(default_state())


def default_students() -> list[dict]:
    return [
        {
            "id": "demo-1",
            "UBICACIÓN": "Centro Ejemplo",
            "NOMBRE": "ALUMNO",
            "APELLIDOS": "EJEMPLO UNO",
            "DNI": "00000001A",
            "FECHA": "18/05/2026",
            "ACTIVIDAD": "Taller de empleabilidad",
            "CONTENIDO": "Búsqueda activa de empleo, elaboración de currículum y preparación de entrevista.",
            "ESPECIALIDAD": "Orientación laboral",
            "HORAS": "3",
            "EMAIL": "alumno1@example.com",
            "ENVIADO": "No",
            "cert_status": "pendiente",
            "errors": [],
            "files": [],
        },
        {
            "id": "demo-2",
            "UBICACIÓN": "Centro Ejemplo",
            "NOMBRE": "ALUMNA",
            "APELLIDOS": "EJEMPLO DOS",
            "DNI": "00000002B",
            "FECHA": "18/05/2026",
            "ACTIVIDAD": "Competencias digitales básicas",
            "CONTENIDO": "Uso básico del ordenador, gestión de archivos, correo electrónico y navegación segura.",
            "ESPECIALIDAD": "Informática básica",
            "HORAS": "4",
            "EMAIL": "alumna2@example.com",
            "ENVIADO": "No",
            "cert_status": "pendiente",
            "errors": [],
            "files": [],
        },
    ]


def builtin_template_record() -> dict:
    return {
        "id": DEFAULT_TEMPLATE_ID,
        "filename": "Diploma oficial Mainjobs.docx",
        "uploaded_at": None,
        "path": str(DEFAULT_TEMPLATE_PATH),
        "detected_fields": REQUIRED_COLUMNS.copy(),
        "is_builtin": True,
    }


def sync_active_template(state: dict) -> None:
    templates = [item for item in state.get("templates", []) if isinstance(item, dict)]
    builtin = builtin_template_record()
    templates = [item for item in templates if item.get("id") != DEFAULT_TEMPLATE_ID]
    templates.insert(0, builtin)

    legacy = state.get("template")
    if isinstance(legacy, dict) and legacy.get("path"):
        legacy_path = str(legacy.get("path"))
        known_paths = {str(item.get("path")) for item in templates}
        if legacy_path not in known_paths:
            legacy_item = dict(legacy)
            legacy_item.setdefault("id", f"plantilla-migrada-{secrets.token_hex(4)}")
            legacy_item.setdefault("is_builtin", False)
            templates.append(legacy_item)

    valid_ids = {item.get("id") for item in templates}
    active_id = state.get("active_template_id")
    if active_id not in valid_ids:
        legacy_path = str(legacy.get("path")) if isinstance(legacy, dict) else ""
        active_id = next(
            (item.get("id") for item in templates if str(item.get("path")) == legacy_path),
            DEFAULT_TEMPLATE_ID,
        )

    active = next((item for item in templates if item.get("id") == active_id), builtin)
    state["templates"] = templates
    state["active_template_id"] = active.get("id")
    state["template"] = dict(active)


def default_state() -> dict:
    builtin = builtin_template_record()
    return {
        "students": default_students(),
        "excel": {"filename": "Datos de ejemplo", "uploaded_at": None, "columns": ALL_COLUMNS},
        "templates": [builtin],
        "active_template_id": DEFAULT_TEMPLATE_ID,
        "template": dict(builtin),
        "history": [],
        "email_history": [],
        "settings": {
            "keep_certificates": True,
            "filename_base": "Certificado",
            "smtp": {
                "host": "",
                "port": "587",
                "username": "",
                "password": "",
                "from_email": "",
                "from_name": "Mainjobs Generador de Diplomas",
                "security": "starttls",
            },
            "email_template": {
                "subject": "Diploma de aprovechamiento - {{ACTIVIDAD}}",
                "body": (
                    "Buenos días,\n\n"
                    "Te escribimos desde Mainjobs, la empresa que gestiona las actividades de la Agencia para el Empleo, "
                    "para hacerte llegar el diploma de aprovechamiento correspondiente a la actividad {{ACTIVIDAD}} "
                    "en la que participaste el día {{FECHA}}.\n\n"
                    "Un cordial saludo"
                ),
            },
        },
        "email_attachment": {"filename": None, "path": None, "uploaded_at": None},
        "manual_email_attachment": {"filename": None, "path": None, "uploaded_at": None},
        "last_generation": None,
    }


def load_state() -> dict:
    ensure_dirs_no_state()
    if not STATE_FILE.exists():
        return default_state()
    with STATE_FILE.open("r", encoding="utf-8") as fh:
        state = json.load(fh)
    migrate_state(state)
    return state


def migrate_state(state: dict) -> None:
    defaults = default_state()
    state.setdefault("email_history", [])
    state.setdefault("email_attachment", defaults["email_attachment"])
    state.setdefault("manual_email_attachment", defaults["manual_email_attachment"])
    state.setdefault("settings", {})
    state["settings"].setdefault("keep_certificates", True)
    state["settings"].setdefault("filename_base", "Certificado")
    state["settings"].setdefault("smtp", {})
    state["settings"].setdefault("email_template", {})
    for key, value in defaults["settings"]["smtp"].items():
        state["settings"]["smtp"].setdefault(key, value)
    for key, value in defaults["settings"]["email_template"].items():
        state["settings"]["email_template"].setdefault(key, value)
    sync_active_template(state)


def ensure_dirs_no_state() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    GENERATED_DIR.mkdir(parents=True, exist_ok=True)


def save_state(state: dict) -> None:
    ensure_dirs_no_state()
    temporary_file = STATE_FILE.with_suffix(".json.tmp")
    with temporary_file.open("w", encoding="utf-8") as fh:
        json.dump(state, fh, ensure_ascii=False, indent=2)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(temporary_file, STATE_FILE)


def public_state(state: dict) -> dict:
    visible = json.loads(json.dumps(state, ensure_ascii=False))
    smtp = visible.get("settings", {}).get("smtp")
    if isinstance(smtp, dict):
        smtp["password"] = ""
    return visible


def reset_generated_outputs(state: dict) -> None:
    for student in state.get("students", []):
        student["files"] = []
        student["last_error"] = ""
        if student.get("cert_status") == "generado":
            student["cert_status"] = "pendiente"
    if GENERATED_DIR.exists():
        shutil.rmtree(GENERATED_DIR)
    GENERATED_DIR.mkdir(parents=True, exist_ok=True)


def json_response(handler, payload: dict, status: int = 200) -> None:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def text_response(handler, body: str, status: int = 200) -> None:
    raw = body.encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "text/plain; charset=utf-8")
    handler.send_header("Content-Length", str(len(raw)))
    handler.end_headers()
    handler.wfile.write(raw)


def parse_cookies(header: str | None) -> dict:
    cookies = {}
    if not header:
        return cookies
    for part in header.split(";"):
        if "=" in part:
            key, value = part.strip().split("=", 1)
            cookies[key] = value
    return cookies


def get_user(handler) -> dict | None:
    token = parse_cookies(handler.headers.get("Cookie")).get("diplomas_session")
    if not token:
        return None
    return SESSIONS.get(token)


def require_user(handler) -> dict | None:
    user = get_user(handler)
    if not user:
        json_response(handler, {"ok": False, "error": "Debes iniciar sesión."}, HTTPStatus.UNAUTHORIZED)
        return None
    return user


def clean_value(value) -> str:
    if value is None:
        return ""
    return str(value).strip()


def normalize_header(value: str) -> str:
    return clean_value(value).upper()


def validate_students(students: list[dict], columns: list[str]) -> dict:
    normalized_columns = {normalize_header(c) for c in columns}
    missing_columns = [c for c in REQUIRED_COLUMNS if c not in normalized_columns]
    correct = 0
    incomplete = 0
    with_errors = 0
    normalized_students = []
    for index, student in enumerate(students, start=1):
        if not isinstance(student, dict):
            student = {"NOMBRE": clean_value(student)}
        normalized_students.append(student)
        errors = []
        for column in REQUIRED_COLUMNS:
            if not clean_value(student.get(column)):
                errors.append(f"Falta {column}")
        if errors:
            with_errors += 1
            if any(error.startswith("Falta") for error in errors):
                incomplete += 1
            student["cert_status"] = "error"
        elif student.get("cert_status") == "error":
            student["cert_status"] = "pendiente"
        student["errors"] = errors
        student.setdefault("id", f"alumno-{index}")
        student.setdefault("files", [])
        if not errors:
            correct += 1
    if len(normalized_students) != len(students) or any(not isinstance(student, dict) for student in students):
        students[:] = normalized_students
    return {
        "total": len(students),
        "correct": correct,
        "with_errors": with_errors,
        "duplicates": 0,
        "incomplete": incomplete,
        "missing_columns": missing_columns,
    }


def parse_csv_file(raw: bytes) -> tuple[list[dict], list[str]]:
    text = raw.decode("utf-8-sig")
    sample = text[:2048]
    dialect = csv.Sniffer().sniff(sample, delimiters=",;	")
    reader = csv.DictReader(io.StringIO(text), dialect=dialect)
    original_headers = reader.fieldnames or []
    header_map = {header: normalize_header(header) for header in original_headers}
    columns = [header_map[header] for header in original_headers]
    students = []
    for index, row in enumerate(reader, start=1):
        student = {normalized: clean_value(row.get(original, "")) for original, normalized in header_map.items()}
        student["id"] = f"excel-{index}"
        student["cert_status"] = "pendiente"
        student["errors"] = []
        student["files"] = []
        students.append(student)
    return students, columns


def parse_xlsx_file(raw: bytes) -> tuple[list[dict], list[str]]:
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        shared_strings = read_shared_strings(archive)
        sheet_path = first_sheet_path(archive)
        root = ET.fromstring(archive.read(sheet_path))
    ns = {"main": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    raw_rows = []
    for row in root.findall(".//main:sheetData/main:row", ns):
        values = []
        max_col = 0
        for cell in row.findall("main:c", ns):
            ref = cell.attrib.get("r", "")
            col_index = column_index(ref)
            max_col = max(max_col, col_index)
            while len(values) < col_index:
                values.append("")
            values[col_index - 1] = {"value": cell_value(cell, shared_strings, ns), "style": cell.attrib.get("s", "")}
        if max_col:
            raw_rows.append(values)
    if not raw_rows:
        return [], []
    columns = [normalize_header(cell_dict(cell).get("value", "")) for cell in raw_rows[0]]
    students = []
    for row_number, row in enumerate(raw_rows[1:], start=1):
        student = {}
        for index, column in enumerate(columns):
            if column:
                cell = cell_dict(row[index]) if index < len(row) else {"value": "", "style": ""}
                student[column] = format_xlsx_value(column, cell)
        if any(student.values()):
            student["id"] = f"excel-{row_number}"
            student["cert_status"] = "pendiente"
            student["errors"] = []
            student["files"] = []
            students.append(student)
    return students, columns


def cell_dict(cell) -> dict:
    if isinstance(cell, dict):
        return cell
    return {"value": clean_value(cell), "style": ""}


def format_xlsx_value(column: str, cell: dict) -> str:
    value = clean_value(cell.get("value", ""))
    if column == "FECHA":
        converted = excel_serial_date_to_text(value)
        if converted:
            return converted
    return value


def excel_serial_date_to_text(value: str) -> str:
    if not re.fullmatch(r"\d+(\.\d+)?", value):
        return ""
    try:
        serial = float(value)
    except ValueError:
        return ""
    if serial < 1 or serial > 60000:
        return ""
    date = datetime(1899, 12, 30) + timedelta(days=serial)
    return date.strftime("%d/%m/%Y")


def read_shared_strings(archive: zipfile.ZipFile) -> list[str]:
    try:
        root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
    except KeyError:
        return []
    ns = {"main": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    strings = []
    for si in root.findall("main:si", ns):
        texts = [node.text or "" for node in si.findall(".//main:t", ns)]
        strings.append("".join(texts))
    return strings


def first_sheet_path(archive: zipfile.ZipFile) -> str:
    workbook = ET.fromstring(archive.read("xl/workbook.xml"))
    rels = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
    ns = {
        "main": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
        "rel": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
        "pkg": "http://schemas.openxmlformats.org/package/2006/relationships",
    }
    first_sheet = workbook.find(".//main:sheets/main:sheet", ns)
    if first_sheet is None:
        return "xl/worksheets/sheet1.xml"
    rel_id = first_sheet.attrib.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id")
    for rel in rels.findall("pkg:Relationship", ns):
        if rel.attrib.get("Id") == rel_id:
            target = rel.attrib["Target"].lstrip("/")
            return target if target.startswith("xl/") else f"xl/{target}"
    return "xl/worksheets/sheet1.xml"


def column_index(ref: str) -> int:
    letters = "".join(ch for ch in ref if ch.isalpha())
    index = 0
    for letter in letters:
        index = index * 26 + (ord(letter.upper()) - ord("A") + 1)
    return index or 1


def cell_value(cell, shared_strings: list[str], ns: dict) -> str:
    cell_type = cell.attrib.get("t")
    if cell_type == "inlineStr":
        return "".join(node.text or "" for node in cell.findall(".//main:t", ns))
    value_node = cell.find("main:v", ns)
    if value_node is None:
        return ""
    value = value_node.text or ""
    if cell_type == "s":
        try:
            return shared_strings[int(value)]
        except (ValueError, IndexError):
            return ""
    return value


def parse_multipart(handler) -> dict:
    content_type = handler.headers.get("Content-Type", "")
    match = re.search(r"boundary=(.+)", content_type)
    if not match:
        return {}
    boundary = match.group(1).strip('"').encode()
    length = int(handler.headers.get("Content-Length", "0"))
    body = handler.rfile.read(length)
    parts = {}
    for part in body.split(b"--" + boundary):
        part = part.strip(b"\r\n")
        if not part or part == b"--":
            continue
        header_blob, _, data = part.partition(b"\r\n\r\n")
        headers = header_blob.decode("utf-8", errors="ignore")
        name_match = re.search(r'name="([^"]+)"', headers)
        if not name_match:
            continue
        filename_match = re.search(r'filename="([^"]*)"', headers)
        name = name_match.group(1)
        if data.endswith(b"\r\n"):
            data = data[:-2]
        parts[name] = {
            "filename": filename_match.group(1) if filename_match else None,
            "data": data,
            "headers": headers,
        }
    return parts


def detect_docx_fields(path: Path) -> list[str]:
    if not path or not path.exists():
        return []
    text = ""
    with zipfile.ZipFile(path) as archive:
        for name in archive.namelist():
            if name.startswith("word/") and name.endswith(".xml"):
                try:
                    root = ET.fromstring(archive.read(name))
                except ET.ParseError:
                    continue
                text += "".join(root.itertext()) + "\n"
    fields = set(re.findall(r"«\s*([^»]+?)\s*»", text))
    fields.update(re.findall(r"\{\{\s*([^}]+?)\s*\}\}", text))
    fields.update(re.findall(r"[“\"]\s*([A-ZÁÉÍÓÚÜÑ_ ]+?)\s*[”\"]", text))
    return sorted({normalize_header(field) for field in fields})


def replace_placeholders_in_docx(template: Path, output: Path, values: dict) -> None:
    template_fields = detect_docx_fields(template)
    values = dict(values)
    if "APELLIDOS" not in template_fields and clean_value(values.get("APELLIDOS")):
        full_name = " ".join(part for part in [clean_value(values.get("NOMBRE")), clean_value(values.get("APELLIDOS"))] if part)
        values["NOMBRE"] = f" {full_name} "
    replacements = {}
    for key, value in values.items():
        normalized = normalize_header(key)
        value_text = str(value) if normalized == "NOMBRE" and str(value).startswith(" ") else clean_value(value)
        replacements[f"«{normalized}»"] = value_text
        replacements[f"{{{{{normalized}}}}}"] = value_text
        replacements[f"“{normalized}”"] = value_text
        replacements[f'"{normalized}"'] = value_text
    with zipfile.ZipFile(template, "r") as source:
        with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as target:
            for item in source.infolist():
                data = source.read(item.filename)
                if item.filename.startswith("word/") and item.filename.endswith(".xml"):
                    data = widen_content_placeholder_cell(data)
                    data = replace_text_nodes(data, replacements)
                target.writestr(item, data)


def widen_content_placeholder_cell(xml_data: bytes) -> bytes:
    try:
        root = ET.fromstring(xml_data)
    except ET.ParseError:
        return xml_data
    parents = {child: parent for parent in root.iter() for child in parent}
    changed = False
    for text_node in list(root.iter(f"{{{WORD_NS}}}t")):
        text = text_node.text or ""
        if not is_content_marker(text):
            continue
        cell = nearest_parent(text_node, parents, f"{{{WORD_NS}}}tc")
        row = nearest_parent(text_node, parents, f"{{{WORD_NS}}}tr")
        paragraph = nearest_parent(text_node, parents, f"{{{WORD_NS}}}p")
        if cell is None or row is None:
            continue
        cells = [child for child in list(row) if child.tag == f"{{{WORD_NS}}}tc"]
        if len(cells) <= 1:
            continue
        total_width = sum(read_cell_width(tc) for tc in cells)
        target_cell = cells[0]
        marker_children = [child for child in list(cell) if child.tag != f"{{{WORD_NS}}}tcPr"]
        for child in list(target_cell):
            if child.tag != f"{{{WORD_NS}}}tcPr":
                target_cell.remove(child)
        for child in marker_children:
            target_cell.append(child)
        for sibling in cells[1:]:
            row.remove(sibling)
        set_cell_width(target_cell, total_width)
        set_cell_grid_span(target_cell, len(cells))
        for content_paragraph in target_cell.iter(f"{{{WORD_NS}}}p"):
            tune_content_paragraph(content_paragraph)
        changed = True
    if not changed:
        return xml_data
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def is_content_marker(text: str) -> bool:
    compact = normalize_header(text).replace(" ", "")
    return compact in {"CONTENIDO", "«CONTENIDO»", "{{CONTENIDO}}", '"CONTENIDO"', "“CONTENIDO”"}


def nearest_parent(node, parents: dict, tag: str):
    current = node
    while current in parents:
        current = parents[current]
        if current.tag == tag:
            return current
    return None


def read_cell_width(cell) -> int:
    tc_pr = cell.find(f"{{{WORD_NS}}}tcPr")
    if tc_pr is None:
        return 0
    width = tc_pr.find(f"{{{WORD_NS}}}tcW")
    if width is None:
        return 0
    try:
        return int(width.attrib.get(f"{{{WORD_NS}}}w", "0"))
    except ValueError:
        return 0


def set_cell_width(cell, width: int) -> None:
    if width <= 0:
        return
    tc_pr = cell.find(f"{{{WORD_NS}}}tcPr")
    if tc_pr is None:
        tc_pr = ET.Element(f"{{{WORD_NS}}}tcPr")
        cell.insert(0, tc_pr)
    tc_w = tc_pr.find(f"{{{WORD_NS}}}tcW")
    if tc_w is None:
        tc_w = ET.Element(f"{{{WORD_NS}}}tcW")
        tc_pr.insert(0, tc_w)
    tc_w.set(f"{{{WORD_NS}}}w", str(width))
    tc_w.set(f"{{{WORD_NS}}}type", "dxa")


def set_cell_grid_span(cell, span: int) -> None:
    if span <= 1:
        return
    tc_pr = cell.find(f"{{{WORD_NS}}}tcPr")
    if tc_pr is None:
        tc_pr = ET.Element(f"{{{WORD_NS}}}tcPr")
        cell.insert(0, tc_pr)
    grid_span = tc_pr.find(f"{{{WORD_NS}}}gridSpan")
    if grid_span is None:
        grid_span = ET.Element(f"{{{WORD_NS}}}gridSpan")
        tc_pr.append(grid_span)
    grid_span.set(f"{{{WORD_NS}}}val", str(span))


def set_table_single_grid(table, width: int) -> None:
    if width <= 0:
        return
    grid = table.find(f"{{{WORD_NS}}}tblGrid")
    if grid is None:
        grid = ET.Element(f"{{{WORD_NS}}}tblGrid")
        table.insert(0, grid)
    for child in list(grid):
        grid.remove(child)
    col = ET.Element(f"{{{WORD_NS}}}gridCol")
    col.set(f"{{{WORD_NS}}}w", str(width))
    grid.append(col)


def tune_content_paragraph(paragraph) -> None:
    p_pr = paragraph.find(f"{{{WORD_NS}}}pPr")
    if p_pr is None:
        p_pr = ET.Element(f"{{{WORD_NS}}}pPr")
        paragraph.insert(0, p_pr)
    jc = p_pr.find(f"{{{WORD_NS}}}jc")
    if jc is None:
        jc = ET.Element(f"{{{WORD_NS}}}jc")
        p_pr.append(jc)
    jc.set(f"{{{WORD_NS}}}val", "center")
    ind = p_pr.find(f"{{{WORD_NS}}}ind")
    if ind is not None:
        ind.set(f"{{{WORD_NS}}}left", "0")
        ind.set(f"{{{WORD_NS}}}right", "0")
    p_run_pr = p_pr.find(f"{{{WORD_NS}}}rPr")
    if p_run_pr is not None:
        for tag in ("b", "bCs", "w"):
            item = p_run_pr.find(f"{{{WORD_NS}}}{tag}")
            if item is not None:
                p_run_pr.remove(item)
        for tag in ("sz", "szCs"):
            item = p_run_pr.find(f"{{{WORD_NS}}}{tag}")
            if item is None:
                item = ET.Element(f"{{{WORD_NS}}}{tag}")
                p_run_pr.append(item)
            item.set(f"{{{WORD_NS}}}val", "24")
    for run in paragraph.findall(f"{{{WORD_NS}}}r"):
        r_pr = run.find(f"{{{WORD_NS}}}rPr")
        if r_pr is None:
            r_pr = ET.Element(f"{{{WORD_NS}}}rPr")
            run.insert(0, r_pr)
        for tag in ("b", "bCs", "w"):
            item = r_pr.find(f"{{{WORD_NS}}}{tag}")
            if item is not None:
                r_pr.remove(item)
        sz = r_pr.find(f"{{{WORD_NS}}}sz")
        if sz is None:
            sz = ET.Element(f"{{{WORD_NS}}}sz")
            r_pr.append(sz)
        sz.set(f"{{{WORD_NS}}}val", "24")
        sz_cs = r_pr.find(f"{{{WORD_NS}}}szCs")
        if sz_cs is None:
            sz_cs = ET.Element(f"{{{WORD_NS}}}szCs")
            r_pr.append(sz_cs)
        sz_cs.set(f"{{{WORD_NS}}}val", "24")


def replace_text_nodes(xml_data: bytes, replacements: dict[str, str]) -> bytes:
    try:
        root = ET.fromstring(xml_data)
    except ET.ParseError:
        return xml_data
    changed = False
    parents = {child: parent for parent in root.iter() for child in parent}
    paragraphs = [node for node in root.iter() if node.tag == f"{{{WORD_NS}}}p"]
    for paragraph in paragraphs:
        if replace_in_container(paragraph, replacements, parents):
            changed = True
    if not changed:
        return xml_data
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def replace_in_container(container, replacements: dict[str, str], parents: dict) -> bool:
    text_nodes = [node for node in container.iter() if node.tag == f"{{{WORD_NS}}}t" and node.text]
    if not text_nodes:
        return False
    full_text = "".join(node.text or "" for node in text_nodes)
    positions = []
    cursor = 0
    for node in text_nodes:
        text = node.text or ""
        positions.append((node, cursor, cursor + len(text)))
        cursor += len(text)
    occurrences = []
    for marker, value in replacements.items():
        start = 0
        while True:
            index = full_text.find(marker, start)
            if index < 0:
                break
            occurrences.append((index, index + len(marker), value))
            start = index + len(marker)
    if not occurrences:
        return False

    simple_occurrences = []
    can_replace_in_place = True
    for start, end, value in occurrences:
        container_info = next((item for item in positions if item[1] <= start and end <= item[2]), None)
        if not container_info:
            can_replace_in_place = False
            break
        simple_occurrences.append((container_info[0], start - container_info[1], end - container_info[1], value))
    if can_replace_in_place:
        by_node: dict[object, list[tuple[int, int, str]]] = {}
        for node, start, end, value in simple_occurrences:
            by_node.setdefault(node, []).append((start, end, value))
        for node, node_occurrences in by_node.items():
            text = node.text or ""
            for start, end, value in sorted(node_occurrences, key=lambda item: item[0], reverse=True):
                text = text[:start] + value + text[end:]
            write_text_with_breaks(node, text, parents)
        return True

    changed = False
    for start, end, value in sorted(occurrences, key=lambda item: item[0], reverse=True):
        text_nodes = [node for node in container.iter() if node.tag == f"{{{WORD_NS}}}t" and node.text is not None]
        positions = []
        cursor = 0
        for node in text_nodes:
            text = node.text or ""
            positions.append((node, cursor, cursor + len(text)))
            cursor += len(text)
        start_info = next((item for item in positions if item[1] <= start <= item[2]), None)
        end_info = next((item for item in positions if item[1] < end <= item[2]), None)
        if not start_info or not end_info:
            continue
        start_node, start_node_from, _ = start_info
        end_node, end_node_from, _ = end_info
        before = (start_node.text or "")[: start - start_node_from]
        after = (end_node.text or "")[end - end_node_from :]
        write_text_with_breaks(start_node, before + value + after, parents)
        if start_node is end_node:
            changed = True
            continue
        deleting = False
        for node in text_nodes:
            if node is start_node:
                deleting = True
                continue
            if deleting:
                node.text = ""
            if node is end_node:
                deleting = False
        changed = True
    return changed


def write_text_with_breaks(text_node, text: str, parents: dict) -> None:
    if "\n" not in text:
        text_node.text = text
        text_node.set(f"{{{XML_NS}}}space", "preserve")
        return
    run = parents.get(text_node)
    if run is None:
        text_node.text = text
        text_node.set(f"{{{XML_NS}}}space", "preserve")
        return
    try:
        index = list(run).index(text_node)
    except ValueError:
        text_node.text = text
        text_node.set(f"{{{XML_NS}}}space", "preserve")
        return
    run.remove(text_node)
    parts = text.splitlines()
    if text.endswith("\n"):
        parts.append("")
    for offset, part in enumerate(parts):
        if offset:
            br = ET.Element(f"{{{WORD_NS}}}br")
            run.insert(index, br)
            index += 1
        new_text = ET.Element(f"{{{WORD_NS}}}t")
        new_text.set(f"{{{XML_NS}}}space", "preserve")
        new_text.text = part
        run.insert(index, new_text)
        index += 1


def safe_filename(value: str) -> str:
    value = re.sub(r"[\\/:*?\"<>|]+", "", value)
    value = re.sub(r"\s+", "_", value.strip())
    value = re.sub(r"_+", "_", value)
    return value or "Sin_nombre"


def short_safe_filename(value: str, limit: int = 42) -> str:
    value = safe_filename(value)
    if len(value) <= limit:
        return value
    return value[:limit].rstrip("._-") or "Sin_nombre"


def make_certificate_name(student: dict, extension: str, base: str) -> str:
    parts = [
        short_safe_filename(base, 10),
        short_safe_filename(student.get("NOMBRE", ""), 14),
        short_safe_filename(student.get("APELLIDOS", ""), 20),
        short_safe_filename(student.get("ACTIVIDAD", ""), 24),
        short_safe_filename(student.get("FECHA", ""), 10),
        short_safe_filename(student.get("DNI", ""), 10),
    ]
    return "_".join(part for part in parts if part) + f".{extension}"


def unique_path(path: Path) -> Path:
    if not path.exists():
        return path
    counter = 2
    while True:
        candidate = path.with_name(f"{path.stem}_{counter}{path.suffix}")
        if not candidate.exists():
            return candidate
        counter += 1


def convert_to_pdf(docx_path: Path) -> tuple[bool, str | None, Path | None]:
    soffice = find_libreoffice()
    pdf_path = docx_path.with_suffix(".pdf")
    messages = []
    if soffice:
        try:
            profile_dir = DATA_DIR / "libreoffice-profile"
            profile_dir.mkdir(parents=True, exist_ok=True)
            profile_uri = profile_dir.resolve().as_uri()
            result = subprocess.run(
                [
                    soffice,
                    "--headless",
                    "--invisible",
                    "--nologo",
                    "--nodefault",
                    "--nofirststartwizard",
                    "--norestore",
                    f"-env:UserInstallation={profile_uri}",
                    "--convert-to",
                    "pdf",
                    "--outdir",
                    str(docx_path.parent),
                    str(docx_path),
                ],
                capture_output=True,
                text=True,
                timeout=180,
            )
            if result.returncode == 0 and pdf_path.exists():
                return True, None, pdf_path
            messages.append(result.stderr.strip() or result.stdout.strip() or "LibreOffice no pudo convertir el archivo.")
        except Exception as exc:
            messages.append(f"LibreOffice: {exc}")
    else:
        messages.append("LibreOffice no está instalado o no está en PATH.")

    ok, message = convert_to_pdf_with_word(docx_path, pdf_path)
    if ok:
        return True, None, pdf_path
    messages.append(message)
    return False, " ".join(item for item in messages if item), None


def find_libreoffice() -> str | None:
    found = shutil.which("soffice") or shutil.which("libreoffice")
    if found:
        return found
    candidates = [
        Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "LibreOffice" / "program" / "soffice.exe",
        Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")) / "LibreOffice" / "program" / "soffice.exe",
        Path(r"C:\Program Files\LibreOffice\program\soffice.exe"),
        Path(r"C:\Program Files (x86)\LibreOffice\program\soffice.exe"),
    ]
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    return None


def pdf_converter_help() -> str:
    return (
        "No se encontró un conversor PDF disponible. Para activarlo en este PC:\n"
        "1. Entra en https://www.libreoffice.org/download/download-libreoffice/\n"
        "2. Descarga LibreOffice para Windows.\n"
        "3. Instálalo con las opciones por defecto.\n"
        "4. Cierra esta app y vuelve a ejecutar python app.py.\n"
        "5. Vuelve a Descargas y pulsa Convertir Word a PDF.\n\n"
        "También puede funcionar con Microsoft Word instalado, pero LibreOffice suele ser la opción gratuita más sencilla."
    )


def convert_generated_docx_to_pdf(student_ids: list[str] | None = None) -> dict:
    state = load_state()
    selected_ids = set(student_ids or [])
    converted = []
    errors = []
    for student in state.get("students", []):
        if selected_ids and student.get("id") not in selected_ids:
            continue
        files = student.get("files", [])
        has_pdf = any(file.get("type") == "pdf" and Path(file.get("path", "")).exists() for file in files)
        for file in list(files):
            if file.get("type") != "docx" or has_pdf:
                continue
            docx_path = Path(file.get("path", ""))
            if not is_safe_generated_path(docx_path) or not docx_path.exists():
                continue
            ok, message, pdf_path = convert_to_pdf(docx_path)
            if ok and pdf_path:
                pdf_file = {"type": "pdf", "name": pdf_path.name, "path": str(pdf_path)}
                student.setdefault("files", []).append(pdf_file)
                converted.append({"student_id": student.get("id"), "name": pdf_path.name})
                has_pdf = True
            else:
                errors.append({"student_id": student.get("id"), "message": message or "No se pudo convertir a PDF."})
    save_state(state)
    help_text = pdf_converter_help() if errors and not converted else ""
    return {"ok": True, "converted": converted, "errors": errors, "help": help_text, "state": public_state(state)}


def convert_to_pdf_with_word(docx_path: Path, pdf_path: Path) -> tuple[bool, str]:
    powershell = shutil.which("powershell")
    if not powershell:
        return False, "Microsoft Word no se pudo invocar porque PowerShell no está disponible."
    script = f"""
$ErrorActionPreference = 'Stop'
$word = New-Object -ComObject Word.Application
$word.Visible = $false
try {{
  $doc = $word.Documents.Open('{escape_powershell_path(docx_path)}', $false, $true)
  $doc.SaveAs([ref]'{escape_powershell_path(pdf_path)}', [ref]17)
  $doc.Close([ref]0)
}} finally {{
  $word.Quit()
}}
"""
    try:
        result = subprocess.run(
            [powershell, "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode == 0 and pdf_path.exists():
            return True, ""
        return False, result.stderr.strip() or result.stdout.strip() or "Microsoft Word no pudo exportar el PDF."
    except Exception as exc:
        return False, f"Microsoft Word: {exc}"


def escape_powershell_path(path: Path) -> str:
    return str(path.resolve()).replace("'", "''")


def generate_for_students(student_ids: list[str], fmt: str, user: dict) -> dict:
    state = load_state()
    fmt = str(fmt or "docx").strip().lower()
    if fmt in ("word", "doc", ".docx"):
        fmt = "docx"
    if fmt in (".pdf",):
        fmt = "pdf"
    if fmt in ("ambos", "word+pdf", "docx+pdf", "docx_pdf"):
        fmt = "both"
    template_path_value = state.get("template", {}).get("path")
    template_path = Path(template_path_value) if template_path_value else None
    if not template_path or not template_path.exists() or template_path.suffix.lower() != ".docx":
        return {"ok": False, "error": "Sube una plantilla Word antes de generar certificados."}
    students = state["students"]
    selected = [student for student in students if student.get("id") in student_ids]
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = GENERATED_DIR / timestamp
    output_dir.mkdir(parents=True, exist_ok=True)
    generated = []
    errors = []
    base = state.get("settings", {}).get("filename_base", "Certificado")
    for student in selected:
        student_files = []
        warnings = "; ".join(student.get("errors") or [])
        student["last_error"] = ""
        if student.get("cert_status") != "error":
            student["cert_status"] = "pendiente"
        try:
            docx_name = make_certificate_name(student, "docx", base)
            docx_path = unique_path(output_dir / docx_name)
            docx_name = docx_path.name
            replace_placeholders_in_docx(template_path, docx_path, student)
            if fmt in ("docx", "both"):
                student_files.append({"type": "docx", "name": docx_name, "path": str(docx_path)})
            if fmt in ("pdf", "both"):
                ok, message, pdf_path = convert_to_pdf(docx_path)
                if ok and pdf_path:
                    student_files.append({"type": "pdf", "name": pdf_path.name, "path": str(pdf_path)})
                else:
                    errors.append({"student_id": student["id"], "message": message})
                    if fmt == "pdf":
                        warnings = "; ".join(item for item in [warnings, f"PDF no generado: {message}"] if item)
                        raise RuntimeError(warnings)
            if not student_files:
                raise ValueError(f"Formato de generación no reconocido: {fmt}")
            student["files"] = student_files
            student["cert_status"] = "generado" if student_files else "pendiente"
            student["last_error"] = warnings
            generated.append(student["id"])
            append_history(state, user, student, fmt, "generado", warnings, ", ".join(file["name"] for file in student_files))
        except Exception as exc:
            message = str(exc)
            student["cert_status"] = "error"
            student["last_error"] = message
            student["files"] = []
            errors.append({"student_id": student["id"], "message": message})
            append_history(state, user, student, fmt, "error", message, "")
    state["last_generation"] = datetime.now().isoformat(timespec="seconds")
    save_state(state)
    return {"ok": True, "generated": generated, "errors": errors, "students": students}


def append_history(state: dict, user: dict, student: dict, fmt: str, status: str, message: str, filename: str) -> None:
    state.setdefault("history", []).insert(
        0,
        {
            "date": datetime.now().isoformat(timespec="seconds"),
            "user": user.get("name") or user.get("username"),
            "student": f"{student.get('NOMBRE', '')} {student.get('APELLIDOS', '')}".strip(),
            "dni": student.get("DNI", ""),
            "activity": student.get("ACTIVIDAD", ""),
            "specialty": student.get("ESPECIALIDAD", ""),
            "format": fmt.upper(),
            "status": status,
            "message": message,
            "filename": filename,
        },
    )


def make_zip(file_paths: list[Path]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        used_names = set()
        for path in file_paths:
            if path.exists():
                name = path.name
                if name in used_names:
                    name = f"{path.stem}_{len(used_names)}{path.suffix}"
                used_names.add(name)
                archive.write(path, name)
    return buffer.getvalue()


def generation_report(state: dict) -> str:
    output = io.StringIO()
    writer = csv.writer(output, delimiter=";")
    writer.writerow(["NOMBRE", "APELLIDOS", "DNI", "ACTIVIDAD", "ESPECIALIDAD", "ESTADO", "ERRORES", "ARCHIVOS"])
    for student in state.get("students", []):
        writer.writerow(
            [
                student.get("NOMBRE", ""),
                student.get("APELLIDOS", ""),
                student.get("DNI", ""),
                student.get("ACTIVIDAD", ""),
                student.get("ESPECIALIDAD", ""),
                student.get("cert_status", ""),
                " | ".join(student.get("errors") or [student.get("last_error", "")]).strip(),
                " | ".join(file.get("name", "") for file in student.get("files", [])),
            ]
        )
    return output.getvalue()


def render_template_text(template: str, student: dict) -> str:
    rendered = template or ""
    for key, value in student.items():
        normalized = normalize_header(key)
        value = clean_value(value)
        rendered = rendered.replace(f"«{normalized}»", value)
        rendered = rendered.replace(f"{{{{{normalized}}}}}", value)
    return rendered


def find_student_pdf(student: dict) -> Path | None:
    for file in student.get("files", []):
        if file.get("type") == "pdf":
            path = Path(file.get("path", ""))
            if is_safe_generated_path(path) and path.exists():
                return path
    return None


def get_manual_email_attachment(state: dict) -> Path | None:
    path = Path(state.get("email_attachment", {}).get("path") or "")
    if path.exists() and path.suffix.lower() == ".pdf":
        try:
            if UPLOAD_DIR.resolve() in path.resolve().parents:
                return path
        except OSError:
            return None
    return None


def get_manual_specific_email_attachment(state: dict) -> Path | None:
    path = Path(state.get("manual_email_attachment", {}).get("path") or "")
    if path.exists() and path.suffix.lower() == ".pdf":
        try:
            if UPLOAD_DIR.resolve() in path.resolve().parents:
                return path
        except OSError:
            return None
    return None


def send_certificates_by_email(student_ids: list[str], user: dict, subject: str, body: str, attachment_mode: str = "generated") -> dict:
    state = load_state()
    smtp_settings = state.get("settings", {}).get("smtp", {})
    missing = [key for key in ("host", "port", "from_email") if not clean_value(smtp_settings.get(key))]
    if missing:
        return {"ok": False, "error": "Configura servidor SMTP, puerto y email remitente antes de enviar."}

    students = [student for student in state.get("students", []) if student.get("id") in set(student_ids)]
    sent = []
    errors = []
    for student in students:
        email = clean_value(student.get("EMAIL"))
        pdf_path = get_manual_email_attachment(state) if attachment_mode == "manual" else find_student_pdf(student)
        if not email:
            message = "El alumno no tiene EMAIL."
            errors.append({"student_id": student.get("id"), "message": message})
            append_email_history(state, user, student, "error", message, "")
            continue
        if not pdf_path:
            message = "No hay PDF adjunto. Genera un PDF para este alumno o sube un PDF manual."
            errors.append({"student_id": student.get("id"), "message": message})
            append_email_history(state, user, student, "error", message, "")
            continue
        try:
            attachment_name = diploma_attachment_name(student)
            send_one_email(smtp_settings, email, render_template_text(subject, student), render_template_text(body, student), pdf_path, attachment_name)
            student["email_status"] = "enviado"
            student["email_sent_at"] = datetime.now().isoformat(timespec="seconds")
            sent.append(student.get("id"))
            append_email_history(state, user, student, "enviado", "", attachment_name)
        except Exception as exc:
            message = str(exc)
            student["email_status"] = "error"
            student["email_error"] = message
            errors.append({"student_id": student.get("id"), "message": message})
            append_email_history(state, user, student, "error", message, pdf_path.name)
    save_state(state)
    return {"ok": True, "sent": sent, "errors": errors, "state": public_state(state)}


def send_manual_emails(emails: list[str], user: dict, subject: str, body: str, attachment_mode: str = "manual", fallback_student_id: str = "") -> dict:
    state = load_state()
    smtp_settings = state.get("settings", {}).get("smtp", {})
    missing = [key for key in ("host", "port", "from_email") if not clean_value(smtp_settings.get(key))]
    if missing:
        return {"ok": False, "error": "Configura servidor SMTP, puerto y email remitente antes de enviar."}
    cleaned_emails = [email.strip() for email in emails if email.strip()]
    if not cleaned_emails:
        return {"ok": False, "error": "Escribe al menos un email manual."}
    student = next((item for item in state.get("students", []) if item.get("id") == fallback_student_id), None)
    attachment = None
    if attachment_mode == "manual":
        attachment = get_manual_specific_email_attachment(state) or get_manual_email_attachment(state)
    elif attachment_mode == "generated" and student:
        attachment = find_student_pdf(student)
    if attachment_mode != "none" and not attachment:
        return {"ok": False, "error": "Sube un PDF manual o selecciona un alumno que tenga PDF generado."}
    manual_specific = get_manual_specific_email_attachment(state)
    manual_info = state.get("manual_email_attachment", {}) if attachment == manual_specific else {}
    attachment_name = diploma_attachment_name(student) if attachment and student else ("Diploma de aprovechamiento.pdf" if attachment else "")
    template_student = student or {}
    sent = []
    errors = []
    for email in cleaned_emails:
        try:
            send_one_email(
                smtp_settings,
                email,
                render_template_text(subject, template_student),
                render_template_text(body, template_student),
                attachment,
                attachment_name or None,
            )
            sent.append(email)
            append_email_history(state, user, {"EMAIL": email, "NOMBRE": "Destinatario", "APELLIDOS": "manual"}, "enviado", "", attachment_name or "Sin adjunto")
        except Exception as exc:
            message = str(exc)
            errors.append({"email": email, "message": message})
            append_email_history(state, user, {"EMAIL": email, "NOMBRE": "Destinatario", "APELLIDOS": "manual"}, "error", message, attachment.name)
    save_state(state)
    return {"ok": True, "sent": sent, "errors": errors, "state": public_state(state)}


def send_one_email(smtp_settings: dict, to_email: str, subject: str, body: str, attachment: Path | None, attachment_name: str | None = None) -> None:
    from_email = clean_value(smtp_settings.get("from_email"))
    from_name = clean_value(smtp_settings.get("from_name")) or from_email
    message = EmailMessage()
    message["From"] = f"{from_name} <{from_email}>"
    message["To"] = to_email
    message["Subject"] = subject or "Certificado"
    message.set_content(body or "")

    if attachment:
        content_type, _ = mimetypes.guess_type(str(attachment))
        maintype, subtype = (content_type or "application/pdf").split("/", 1)
        message.add_attachment(attachment.read_bytes(), maintype=maintype, subtype=subtype, filename=attachment_name or attachment.name)

    host = clean_value(smtp_settings.get("host"))
    port = int(clean_value(smtp_settings.get("port")) or "587")
    username = clean_value(smtp_settings.get("username"))
    password = clean_value(smtp_settings.get("password"))
    security = clean_value(smtp_settings.get("security")) or "starttls"
    smtp_class = smtplib.SMTP_SSL if security == "ssl" else smtplib.SMTP
    with smtp_class(host, port, timeout=30) as server:
        if security == "starttls":
            server.starttls()
        if username:
            server.login(username, password)
        server.send_message(message)


def diploma_attachment_name(student: dict | None) -> str:
    if not student:
        return "Diploma de aprovechamiento.pdf"
    full_name = " ".join(
        part for part in [
            clean_value(student.get("NOMBRE")),
            clean_value(student.get("APELLIDOS")),
        ]
        if part
    )
    if not full_name:
        full_name = clean_value(student.get("DNI")) or "Alumno"
    activity = clean_value(student.get("ACTIVIDAD"))
    date = clean_value(student.get("FECHA"))
    parts = ["Diploma de aprovechamiento", full_name]
    if activity:
        parts.append(activity)
    if date:
        parts.append(date)
    return f"{safe_filename(' - '.join(parts))}.pdf"


def append_email_history(state: dict, user: dict, student: dict, status: str, message: str, filename: str) -> None:
    state.setdefault("email_history", []).insert(
        0,
        {
            "date": datetime.now().isoformat(timespec="seconds"),
            "user": user.get("name") or user.get("username"),
            "student": f"{student.get('NOMBRE', '')} {student.get('APELLIDOS', '')}".strip(),
            "dni": student.get("DNI", ""),
            "email": student.get("EMAIL", ""),
            "activity": student.get("ACTIVIDAD", ""),
            "status": status,
            "message": message,
            "filename": filename,
        },
    )


class DiplomaHandler(SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        super().end_headers()

    def translate_path(self, path):
        parsed = urlparse(path)
        clean_path = parsed.path
        if clean_path == "/":
            return str(STATIC_DIR / "index.html")
        if clean_path.startswith("/static/"):
            return str(BASE_DIR / clean_path.lstrip("/"))
        return str(STATIC_DIR / clean_path.lstrip("/"))

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path.startswith("/api/"):
            with STATE_LOCK:
                self.handle_api_get(parsed)
            return
        if parsed.path.startswith("/download/"):
            self.handle_download(parsed)
            return
        return super().do_GET()

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path.startswith("/api/"):
            with STATE_LOCK:
                self.handle_api_post(parsed)
            return
        text_response(self, "No encontrado", HTTPStatus.NOT_FOUND)

    def handle_api_get(self, parsed):
        if parsed.path == "/api/health":
            json_response(self, {"ok": True, "service": "mainjobs-generador-diplomas"})
            return
        if parsed.path == "/api/session":
            user = get_user(self)
            json_response(self, {"ok": True, "user": user})
            return
        user = require_user(self)
        if not user:
            return
        state = load_state()
        if parsed.path == "/api/state":
            validation = validate_students(state["students"], state.get("excel", {}).get("columns", ALL_COLUMNS))
            save_state(state)
            json_response(self, {"ok": True, "state": public_state(state), "validation": validation, "available_fields": available_fields(state)})
            return
        if parsed.path == "/api/report":
            body = generation_report(state).encode("utf-8-sig")
            self.send_response(200)
            self.send_header("Content-Type", "text/csv; charset=utf-8")
            self.send_header("Content-Disposition", 'attachment; filename="informe_generacion.csv"')
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        json_response(self, {"ok": False, "error": "Ruta no encontrada."}, HTTPStatus.NOT_FOUND)

    def handle_api_post(self, parsed):
        if parsed.path == "/api/login":
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length) or b"{}")
            username = payload.get("username", "")
            password = payload.get("password", "")
            account = USERS.get(username)
            if not account or not hmac.compare_digest(str(account["password"]), str(password)):
                json_response(self, {"ok": False, "error": "Usuario o contraseña incorrectos."}, HTTPStatus.UNAUTHORIZED)
                return
            token = secrets.token_urlsafe(32)
            user = {"username": username, "role": account["role"], "name": account["name"]}
            SESSIONS[token] = user
            body = json.dumps({"ok": True, "user": user}, ensure_ascii=False).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            secure_cookie = "; Secure" if os.environ.get("APP_ENV", "").lower() == "production" else ""
            self.send_header("Set-Cookie", f"diplomas_session={token}; HttpOnly; SameSite=Lax; Path=/{secure_cookie}")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        user = require_user(self)
        if not user:
            return
        try:
            if parsed.path == "/api/logout":
                token = parse_cookies(self.headers.get("Cookie")).get("diplomas_session")
                if token:
                    SESSIONS.pop(token, None)
                self.send_response(200)
                self.send_header("Set-Cookie", "diplomas_session=; Max-Age=0; Path=/")
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(b'{"ok": true}')
                return
            if parsed.path == "/api/upload-excel":
                self.upload_excel()
                return
            if parsed.path == "/api/upload-template":
                self.upload_template()
                return
            if parsed.path == "/api/select-template":
                self.select_template()
                return
            if parsed.path == "/api/delete-template":
                self.delete_template()
                return
            if parsed.path == "/api/upload-email-attachment":
                self.upload_email_attachment()
                return
            if parsed.path == "/api/upload-manual-email-attachment":
                self.upload_manual_email_attachment()
                return
            if parsed.path == "/api/students":
                self.update_students()
                return
            if parsed.path == "/api/generate":
                length = int(self.headers.get("Content-Length", "0"))
                payload = json.loads(self.rfile.read(length) or b"{}")
                result = generate_for_students(payload.get("student_ids", []), payload.get("format", "docx"), user)
                json_response(self, result, 200 if result.get("ok") else 400)
                return
            if parsed.path == "/api/convert-pdfs":
                length = int(self.headers.get("Content-Length", "0"))
                payload = json.loads(self.rfile.read(length) or b"{}")
                result = convert_generated_docx_to_pdf(payload.get("student_ids") or None)
                json_response(self, result)
                return
            if parsed.path == "/api/send-email":
                length = int(self.headers.get("Content-Length", "0"))
                payload = json.loads(self.rfile.read(length) or b"{}")
                result = send_certificates_by_email(
                    payload.get("student_ids", []),
                    user,
                    payload.get("subject", ""),
                    payload.get("body", ""),
                    payload.get("attachment_mode", "generated"),
                )
                json_response(self, result, 200 if result.get("ok") else 400)
                return
            if parsed.path in ("/api/send-manual-email", "/api/manual-email", "/api/send_manual_email"):
                length = int(self.headers.get("Content-Length", "0"))
                payload = json.loads(self.rfile.read(length) or b"{}")
                result = send_manual_emails(
                    payload.get("emails", []),
                    user,
                    payload.get("subject", ""),
                    payload.get("body", ""),
                    payload.get("attachment_mode", "manual"),
                    payload.get("fallback_student_id", ""),
                )
                json_response(self, result, 200 if result.get("ok") else 400)
                return
            if parsed.path == "/api/clear":
                self.clear_data()
                return
            if parsed.path == "/api/settings":
                self.update_settings()
                return
            json_response(self, {"ok": False, "error": "Ruta no encontrada."}, HTTPStatus.NOT_FOUND)
        except Exception as exc:
            traceback.print_exc()
            json_response(self, {"ok": False, "error": str(exc)}, HTTPStatus.INTERNAL_SERVER_ERROR)

    def upload_excel(self):
        parts = parse_multipart(self)
        file = parts.get("file")
        if not file or not file["filename"]:
            json_response(self, {"ok": False, "error": "Selecciona un archivo Excel o CSV."}, 400)
            return
        filename = Path(file["filename"]).name
        extension = Path(filename).suffix.lower()
        raw = file["data"]
        if extension == ".csv":
            students, columns = parse_csv_file(raw)
        elif extension == ".xlsx":
            students, columns = parse_xlsx_file(raw)
        else:
            json_response(self, {"ok": False, "error": "El archivo debe ser .xlsx o .csv."}, 400)
            return
        target = UPLOAD_DIR / f"excel_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{safe_filename(filename)}"
        target.write_bytes(raw)
        state = load_state()
        state["students"] = students
        state["excel"] = {"filename": filename, "uploaded_at": datetime.now().isoformat(timespec="seconds"), "columns": columns, "path": str(target)}
        reset_generated_outputs(state)
        validation = validate_students(state["students"], columns)
        save_state(state)
        json_response(self, {"ok": True, "state": public_state(state), "validation": validation, "available_fields": available_fields(state)})

    def upload_template(self):
        parts = parse_multipart(self)
        file = parts.get("file")
        if not file or not file["filename"]:
            json_response(self, {"ok": False, "error": "Selecciona una plantilla .docx."}, 400)
            return
        filename = Path(file["filename"]).name
        if Path(filename).suffix.lower() != ".docx":
            json_response(self, {"ok": False, "error": "La plantilla debe ser un archivo .docx."}, 400)
            return
        target = UPLOAD_DIR / f"plantilla_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}_{safe_filename(filename)}"
        target.write_bytes(file["data"])
        fields = detect_docx_fields(target)
        state = load_state()
        template = {
            "id": f"plantilla-{secrets.token_hex(8)}",
            "filename": filename,
            "uploaded_at": datetime.now().isoformat(timespec="seconds"),
            "path": str(target),
            "detected_fields": fields,
            "is_builtin": False,
        }
        state.setdefault("templates", []).append(template)
        state["active_template_id"] = template["id"]
        sync_active_template(state)
        reset_generated_outputs(state)
        save_state(state)
        json_response(self, {"ok": True, "state": public_state(state), "available_fields": available_fields(state)})

    def select_template(self):
        length = int(self.headers.get("Content-Length", "0"))
        payload = json.loads(self.rfile.read(length) or b"{}")
        template_id = str(payload.get("template_id", "")).strip()
        state = load_state()
        template = next((item for item in state.get("templates", []) if item.get("id") == template_id), None)
        if not template:
            json_response(self, {"ok": False, "error": "La plantilla seleccionada no existe."}, 404)
            return
        template_path = Path(str(template.get("path", "")))
        if not template_path.exists():
            json_response(
                self,
                {"ok": False, "error": "El archivo de esta plantilla ya no está disponible. Vuelve a subirla."},
                400,
            )
            return
        state["active_template_id"] = template_id
        sync_active_template(state)
        reset_generated_outputs(state)
        save_state(state)
        json_response(self, {"ok": True, "state": public_state(state), "available_fields": available_fields(state)})

    def delete_template(self):
        length = int(self.headers.get("Content-Length", "0"))
        payload = json.loads(self.rfile.read(length) or b"{}")
        template_id = str(payload.get("template_id", "")).strip()
        if template_id == DEFAULT_TEMPLATE_ID:
            json_response(self, {"ok": False, "error": "La plantilla oficial incluida no se puede eliminar."}, 400)
            return
        state = load_state()
        template = next((item for item in state.get("templates", []) if item.get("id") == template_id), None)
        if not template:
            json_response(self, {"ok": False, "error": "La plantilla seleccionada no existe."}, 404)
            return
        template_path = Path(str(template.get("path", ""))).resolve()
        try:
            template_path.relative_to(UPLOAD_DIR.resolve())
        except ValueError:
            json_response(self, {"ok": False, "error": "No se puede borrar este archivo protegido."}, 400)
            return
        if template_path.exists():
            template_path.unlink()
        state["templates"] = [item for item in state.get("templates", []) if item.get("id") != template_id]
        if state.get("active_template_id") == template_id:
            state["active_template_id"] = DEFAULT_TEMPLATE_ID
            reset_generated_outputs(state)
        sync_active_template(state)
        save_state(state)
        json_response(self, {"ok": True, "state": public_state(state), "available_fields": available_fields(state)})

    def upload_email_attachment(self):
        parts = parse_multipart(self)
        file = parts.get("file")
        if not file or not file["filename"]:
            json_response(self, {"ok": False, "error": "Selecciona un PDF para adjuntar."}, 400)
            return
        filename = Path(file["filename"]).name
        if Path(filename).suffix.lower() != ".pdf":
            json_response(self, {"ok": False, "error": "El adjunto debe ser un archivo PDF."}, 400)
            return
        target = UPLOAD_DIR / f"email_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{safe_filename(filename)}"
        target.write_bytes(file["data"])
        state = load_state()
        state["email_attachment"] = {"filename": filename, "path": str(target), "uploaded_at": datetime.now().isoformat(timespec="seconds")}
        save_state(state)
        json_response(self, {"ok": True, "state": public_state(state)})

    def upload_manual_email_attachment(self):
        parts = parse_multipart(self)
        file = parts.get("file")
        if not file or not file["filename"]:
            json_response(self, {"ok": False, "error": "Selecciona un PDF para adjuntar."}, 400)
            return
        filename = Path(file["filename"]).name
        if Path(filename).suffix.lower() != ".pdf":
            json_response(self, {"ok": False, "error": "El adjunto debe ser un archivo PDF."}, 400)
            return
        target = UPLOAD_DIR / f"email_manual_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{safe_filename(filename)}"
        target.write_bytes(file["data"])
        state = load_state()
        state["manual_email_attachment"] = {
            "filename": filename,
            "download_name": filename,
            "path": str(target),
            "uploaded_at": datetime.now().isoformat(timespec="seconds"),
        }
        save_state(state)
        json_response(self, {"ok": True, "state": public_state(state)})

    def update_students(self):
        length = int(self.headers.get("Content-Length", "0"))
        payload = json.loads(self.rfile.read(length) or b"{}")
        state = load_state()
        state["students"] = payload.get("students", state["students"])
        validation = validate_students(state["students"], state.get("excel", {}).get("columns", ALL_COLUMNS))
        save_state(state)
        json_response(self, {"ok": True, "state": public_state(state), "validation": validation})

    def update_settings(self):
        length = int(self.headers.get("Content-Length", "0"))
        payload = json.loads(self.rfile.read(length) or b"{}")
        state = load_state()
        existing_password = state.get("settings", {}).get("smtp", {}).get("password", "")
        state["settings"].update(payload)
        if "smtp" in payload:
            state["settings"].setdefault("smtp", {})
            if not payload["smtp"].get("password"):
                state["settings"]["smtp"]["password"] = existing_password
        save_state(state)
        json_response(self, {"ok": True, "state": public_state(state)})

    def clear_data(self):
        length = int(self.headers.get("Content-Length", "0"))
        payload = json.loads(self.rfile.read(length) or b"{}")
        state = load_state()
        target = payload.get("target")
        if target in ("temporary", "generated"):
            if GENERATED_DIR.exists():
                shutil.rmtree(GENERATED_DIR)
                GENERATED_DIR.mkdir(exist_ok=True)
            for student in state["students"]:
                student["files"] = []
                if student.get("cert_status") == "generado":
                    student["cert_status"] = "pendiente"
        if target in ("excel", "all"):
            state["students"] = default_students()
            state["excel"] = {"filename": "Datos de ejemplo", "uploaded_at": None, "columns": ALL_COLUMNS}
        if target == "all":
            if UPLOAD_DIR.exists():
                shutil.rmtree(UPLOAD_DIR)
                UPLOAD_DIR.mkdir(exist_ok=True)
            state["template"] = {"filename": None, "uploaded_at": None, "path": None, "detected_fields": []}
        validate_students(state["students"], state.get("excel", {}).get("columns", ALL_COLUMNS))
        save_state(state)
        json_response(self, {"ok": True, "state": public_state(state)})

    def handle_download(self, parsed):
        user = get_user(self)
        if not user:
            self.send_response(302)
            self.send_header("Location", "/")
            self.end_headers()
            return
        query = parse_qs(parsed.query)
        state = load_state()
        if parsed.path == "/download/file":
            path = Path(query.get("path", [""])[0])
            if not is_safe_generated_path(path) or not path.exists():
                text_response(self, "Archivo no encontrado", 404)
                return
            data = path.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "application/octet-stream")
            self.send_header("Content-Disposition", f'attachment; filename="{path.name}"')
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return
        if parsed.path == "/download/zip":
            ids = set(",".join(query.get("ids", [])).split(",")) if query.get("ids") else set()
            kind = query.get("kind", ["all"])[0]
            paths = []
            for student in state.get("students", []):
                if ids and student.get("id") not in ids:
                    continue
                for file in student.get("files", []):
                    if kind != "all" and file.get("type") != kind:
                        continue
                    path = Path(file.get("path", ""))
                    if is_safe_generated_path(path):
                        paths.append(path)
            data = make_zip(paths)
            self.send_response(200)
            self.send_header("Content-Type", "application/zip")
            self.send_header("Content-Disposition", 'attachment; filename="certificados.zip"')
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return
        text_response(self, "No encontrado", 404)


def is_safe_generated_path(path: Path) -> bool:
    try:
        return GENERATED_DIR.resolve() in path.resolve().parents
    except OSError:
        return False


def available_fields(state: dict) -> dict:
    columns = state.get("excel", {}).get("columns") or ALL_COLUMNS
    fields = [normalize_header(column) for column in columns if column]
    return {
        "latin": [f"«{field}»" for field in fields],
        "braces": [f"{{{{{field}}}}}" for field in fields],
    }


def main() -> None:
    ensure_dirs()
    port = int(os.environ.get("PORT", "8000"))
    host = os.environ.get("HOST", "127.0.0.1")
    server = ThreadingHTTPServer((host, port), DiplomaHandler)
    try:
        print(f"Generador de Diplomas disponible en http://{host}:{port}", flush=True)
    except OSError:
        pass
    server.serve_forever()


def _diploma_unique_filename(student, extension="docx"):
    parts = [
        "Diploma de aprovechamiento",
        student.get("NOMBRE", "") if isinstance(student, dict) else "",
        student.get("APELLIDOS", "") if isinstance(student, dict) else "",
        student.get("ACTIVIDAD", "") if isinstance(student, dict) else "",
        student.get("FECHA", "") if isinstance(student, dict) else "",
        student.get("DNI", "") if isinstance(student, dict) else "",
    ]
    base = " - ".join(str(part).strip() for part in parts if str(part).strip())
    cleaner = globals().get("sanitize_filename") or globals().get("clean_filename")
    if callable(cleaner):
        base = cleaner(base)
    else:
        base = "".join(ch if ch.isalnum() or ch in " ._-()" else "_" for ch in base).strip(" ._")
    extension = str(extension or "docx").lstrip(".")
    return f"{base}.{extension}"


def _student_identity_value(student, key):
    if not isinstance(student, dict):
        return ""
    return str(student.get(key, "") or "").strip()


def _student_row_key(student):
    """Stable key for one Excel row, including activity/date so repeated DNI is valid."""
    return "|".join(
        _student_identity_value(student, key).casefold()
        for key in ("id", "DNI", "NOMBRE", "APELLIDOS", "ACTIVIDAD", "FECHA", "ESPECIALIDAD", "HORAS")
    )


def _student_matches_identifier(student, identifier):
    identifier = str(identifier or "").strip()
    if not identifier:
        return False
    if _student_identity_value(student, "id") == identifier:
        return True
    if _student_identity_value(student, "_id") == identifier:
        return True
    if _student_row_key(student) == identifier.casefold():
        return True
    return False


def _find_student_by_identifier(students, identifier):
    for student in students or []:
        if _student_matches_identifier(student, identifier):
            return student
    return None


def _ensure_student_ids(students):
    """Every duplicate person/activity row needs its own id; DNI is not unique."""
    changed = False
    seen = set()
    for index, student in enumerate(students or [], start=1):
        if not isinstance(student, dict):
            continue
        current = str(student.get("id", "") or "").strip()
        if not current or current in seen:
            raw = "|".join(
                _student_identity_value(student, key)
                for key in ("DNI", "NOMBRE", "APELLIDOS", "ACTIVIDAD", "FECHA", "ESPECIALIDAD", "HORAS")
            )
            cleaner = globals().get("sanitize_filename") or globals().get("clean_filename")
            if callable(cleaner):
                clean = cleaner(raw)
            else:
                clean = "".join(ch if ch.isalnum() else "_" for ch in raw)
            current = f"fila_{index}_{clean[:80]}"
            student["id"] = current
            changed = True
        seen.add(current)
    return changed


def certificate_filename(student, extension="docx"):
    return _diploma_unique_filename(student, extension)


def build_certificate_filename(student, extension="docx"):
    return _diploma_unique_filename(student, extension)


def make_certificate_filename(student, extension="docx"):
    return _diploma_unique_filename(student, extension)


def generated_filename(student, extension="docx"):
    return _diploma_unique_filename(student, extension)


def certificate_file_name(student, extension="docx"):
    return _diploma_unique_filename(student, extension)


def build_certificate_file_name(student, extension="docx"):
    return _diploma_unique_filename(student, extension)


def get_certificate_filename(student, extension="docx"):
    return _diploma_unique_filename(student, extension)


def diploma_filename(student, extension="docx"):
    return _diploma_unique_filename(student, extension)


def build_diploma_filename(student, extension="docx"):
    return _diploma_unique_filename(student, extension)


def _patch_state_students_for_duplicate_activities():
    load_state_func = globals().get("load_state")
    save_state_func = globals().get("save_state")
    if not callable(load_state_func):
        return
    state = load_state_func()
    students = state.get("students") or state.get("alumnos") or []
    if _ensure_student_ids(students) and callable(save_state_func):
        save_state_func(state)


_patch_state_students_for_duplicate_activities()


def _patch_response_state_for_duplicate_activities():
    """Wrap JSON responses so duplicate-person rows keep unique ids in the UI too."""
    for obj in list(globals().values()):
        if not isinstance(obj, type) or not hasattr(obj, "send_json"):
            continue
        original = getattr(obj, "send_json")
        if getattr(original, "_duplicate_activity_patch", False):
            continue

        def patched_send_json(self, data, *args, __original=original, **kwargs):
            try:
                if isinstance(data, dict):
                    students = data.get("students") or data.get("alumnos")
                    if isinstance(students, list):
                        _ensure_student_ids(students)
                    state = data.get("state")
                    if isinstance(state, dict):
                        state_students = state.get("students") or state.get("alumnos")
                        if isinstance(state_students, list):
                            _ensure_student_ids(state_students)
            except Exception:
                pass
            return __original(self, data, *args, **kwargs)

        patched_send_json._duplicate_activity_patch = True
        setattr(obj, "send_json", patched_send_json)


_patch_response_state_for_duplicate_activities()


if __name__ == "__main__":
    try:
        main()
    except Exception:
        ensure_dirs_no_state()
        (DATA_DIR / "server_error.log").write_text(traceback.format_exc(), encoding="utf-8")
        raise
