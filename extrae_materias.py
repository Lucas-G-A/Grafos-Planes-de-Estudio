import re
import json
import sys
from pathlib import Path
from typing import Dict, List
from pdfminer.high_level import extract_text

# Detect semester headers including accents and later semesters
SEM_HEADER_RE = re.compile(
    r'\b('
    r'PRIMER|SEGUNDO|TERCER|CUARTO|QUINTO|SEXTO|'
    r'S[EÉ]PTIMO|SEPTIMO|OCTAVO|NOVENO|D[ÉE]CIMO|DECIMO'
    r')\s+SEMESTRE\b',
    re.IGNORECASE
)

COURSE_CODE_RE = re.compile(r'\b[A-Z]{3}-\d{5}\b')
CREDITS_LINE_RE = re.compile(r'(\d{1,2})\s*$')  # credits 1..12 typically at end

SEM_ORD_TO_NUM = {
    'PRIMER': 1,
    'SEGUNDO': 2,
    'TERCER': 3,
    'CUARTO': 4,
    'QUINTO': 5,
    'SEXTO': 6,
    'SEPTIMO': 7, 'SÉPTIMO': 7,
    'OCTAVO': 8,
    'NOVENO': 9,
    'DECIMO': 10, 'DÉCIMO': 10,
    'UNDECIMO': 11, 'UNDÉCIMO': 11,
}

def normalize_spaces(s: str) -> str:
    s = s.replace('\xa0', ' ').replace(' ', ' ')
    s = re.sub(r'\s+', ' ', s).strip()
    return s

def is_header(line: str) -> bool:
    return bool(SEM_HEADER_RE.search(line))

def clean_name(name: str) -> str:
    name = normalize_spaces(name)
    # remove (A) or similar trailing markers
    name = re.sub(r'\s*\([A-Za-z0-9]+\)\s*$', '', name)
    # remove duplicated spaces and separators
    name = name.strip(' -–—:;.,')
    return name

def chunk_course_records(lines: List[str]) -> List[str]:
    """
    Join wrapped lines until we hit a line that ends with credits (1-2 digits).
    Ignore obvious headers or table headings.
    """
    records = []
    buf = ""
    for raw in lines:
        line = normalize_spaces(raw)
        if not line:
            continue
        # skip column headers and notes
        if re.search(r'\b(Prerrequisitos?|Clave|Materia|Cr[eé]ditos)\b', line, re.IGNORECASE):
            continue
        if re.search(r'\b(NOTAS AL PLAN|LICENCIATURA EN|PLAN CONJUNTO|PARA ALUMNOS|TITULACI[ÓO]N|SERVICIO SOCIAL)\b', line, re.IGNORECASE):
            continue
        if is_header(line):
            # flush incomplete buffer (discard if no credits)
            buf = ""
            continue

        # accumulate; if buffer empty start with current line, else append
        buf = f"{buf} {line}".strip() if buf else line

        # if line ends with digits (credits), we close the record
        if CREDITS_LINE_RE.search(line):
            records.append(buf)
            buf = ""
    # no need to keep trailing buf without credits
    return records

def parse_record(rec: str):
    """
    Parse a full joined record like:
    'ADM-12108 y ECO-12102 ECO-11103 Economía III 6'
    -> prereqs=['ADM-12108','ECO-12102'], clave='ECO-11103', nombre='Economía III', creditos=6
    """
    rec = normalize_spaces(rec)
    mcred = CREDITS_LINE_RE.search(rec)
    if not mcred:
        return None
    creditos = int(mcred.group(1))
    left = normalize_spaces(rec[:mcred.start()])

    # find all codes and their spans
    code_spans = [(m.group(0), m.span()) for m in COURSE_CODE_RE.finditer(left)]
    if not code_spans:
        return None

    # Assume the last code before the credits is the course's own key
    clave, (cstart, cend) = code_spans[-1]

    # prereqs are any codes that appear BEFORE that last code
    prereqs = [code for code, (s, e) in code_spans[:-1]]

    # course name is the text between the end of the last code and credits
    nombre = clean_name(left[cend:])

    # guardrails: if name accidentally starts with connectors
    nombre = re.sub(r'^(y|e|,)\s+', '', nombre, flags=re.IGNORECASE).strip()

    # If name looks empty (some PDFs can split awkwardly), try to salvage by
    # using tokens after last code that are not codes
    if not nombre:
        # remove any trailing codes and connectors, leave words
        tmp = re.sub(COURSE_CODE_RE, '', left)
        tmp = re.sub(r'\b(y|e|,|y\s+)\b', ' ', tmp, flags=re.IGNORECASE)
        nombre = clean_name(tmp)

    if not nombre:
        return None

    return clave, nombre, creditos, prereqs

def pdf_to_json(pdf_path: str) -> Dict[str, dict]:
    text = extract_text(pdf_path) or ""
    lines = text.splitlines()
    # We'll walk lines to know in which semester we are
    current_sem = None
    data: Dict[str, dict] = {}

    # First pass: annotate each line with semester (carry forward)
    sem_annotated = []
    for raw in lines:
        line = normalize_spaces(raw)
        if not line:
            sem_annotated.append((current_sem, line))
            continue
        msem = SEM_HEADER_RE.search(line)
        if msem:
            key = msem.group(1).upper().replace('É', 'E')
            current_sem = SEM_ORD_TO_NUM.get(key, current_sem)
            sem_annotated.append((current_sem, ""))  # marker row (ignored later)
        else:
            sem_annotated.append((current_sem, line))

    # Group by contiguous blocks with the same semester and parse records inside
    block_lines: List[str] = []
    block_sem = None

    def flush_block():
        nonlocal block_lines, block_sem, data
        if block_sem is None:
            block_lines = []
            return
        records = chunk_course_records(block_lines)
        for rec in records:
            parsed = parse_record(rec)
            if parsed:
                clave, nombre, creditos, prereqs = parsed
                data[clave] = {
                    "nombre": nombre,
                    "creditos": creditos,
                    "prerreqs": prereqs,
                    "coreqs": [],
                    "estado": 0,
                    "semestre": block_sem
                }
        block_lines = []

    for sem, line in sem_annotated:
        if sem != block_sem:
            # semester changed; flush previous
            flush_block()
            block_sem = sem
        if line:
            block_lines.append(line)
    # flush last
    flush_block()

    return data

def ensure_dir(path: Path):
    path.mkdir(parents=True, exist_ok=True)

def process_single(pdf_file: Path, out_target: Path) -> Path:
    data = pdf_to_json(str(pdf_file))

    # out_target puede ser archivo .json o un directorio
    if out_target.suffix.lower() == ".json":
        out_path = out_target
    else:
        ensure_dir(out_target)
        out_path = out_target / (pdf_file.stem + ".json")

    with out_path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"[OK] {pdf_file.name} -> {out_path.name}   ({len(data)} materias)")
    return out_path

def process_folder(in_dir: Path, out_dir: Path):
    ensure_dir(out_dir)
    pdfs = sorted([p for p in in_dir.glob("*.pdf") if p.is_file()])
    if not pdfs:
        print("No se encontraron PDFs en", in_dir)
        return
    total = 0
    for pdf in pdfs:
        try:
            process_single(pdf, out_dir)
            total += 1
        except Exception as e:
            print(f"[ERROR] {pdf.name}: {e}")
    print(f"Listo. Convertidos {total} archivos PDF a JSON en {out_dir}")

def main():
    """
    USO:
      1) Procesar TODOS los PDFs de un folder a otro folder:
         python extrae_materias.py <carpeta_pdf> <carpeta_json>

      2) Procesar un solo PDF a un archivo JSON específico:
         python extrae_materias.py <archivo.pdf> <salida.json>

      3) Procesar un solo PDF y guardar en una carpeta (mismo nombre base):
         python extrae_materias.py <archivo.pdf> <carpeta_salida>
    """
    if len(sys.argv) < 3:
        print("Uso: python extrae_materias.py <entrada> <salida>")
        print("  - Si <entrada> es carpeta: <salida> debe ser carpeta (se crearán .json con el mismo nombre base).")
        print("  - Si <entrada> es archivo .pdf: <salida> puede ser archivo .json o carpeta.")
        sys.exit(1)

    entrada = Path(sys.argv[1])
    salida = Path(sys.argv[2])

    if entrada.is_dir():
        if not (not salida.exists() or salida.is_dir()):
            print("Error: Cuando 'entrada' es carpeta, 'salida' debe ser una carpeta.")
            sys.exit(1)
        process_folder(entrada, salida)
    elif entrada.is_file():
        process_single(entrada, salida)
    else:
        print("Error: <entrada> no existe.")
        sys.exit(1)

if __name__ == "__main__":
    main()
