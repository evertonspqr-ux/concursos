import re
import unicodedata
from dataclasses import asdict, dataclass, field
from datetime import date


def normalized(value: str) -> str:
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode().lower()
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", " ", value)).strip()


def br_date(value: str) -> str | None:
    try:
        day, month, year = (int(piece) for piece in re.split(r"[/.-]", value))
        return date(year, month, day).isoformat()
    except ValueError:
        return None


@dataclass
class ParsedSubject:
    name: str
    weight: float = 1
    topics: list[str] = field(default_factory=list)


def analyze_notice(text: str) -> dict:
    compact = re.sub(r"[ \t]+", " ", text)
    lower = normalized(compact)
    boards = ["CEBRASPE", "FGV", "FCC", "VUNESP", "IBFC", "AOCP", "QUADRIX", "CESGRANRIO", "FUNDATEC"]
    board = next((item for item in boards if normalized(item) in lower), None)
    vacancies = [int(item) for item in re.findall(r"(?:\b(\d{1,5})\s*(?:vagas?|postos?))|(?:vagas?\s*(?:de|:)?\s*(\d{1,5}))", compact, re.I) for item in item if item]
    dates = [br_date(item) for item in re.findall(r"\b\d{1,2}[/.\-]\d{1,2}[/.\-]\d{4}\b", compact)]
    dates = [item for item in dates if item]
    positions = []
    for match in re.finditer(r"(?:cargo|emprego|fun[cç][aã]o)\s*(?:de)?\s*[:\-]?\s*([A-ZÀ-Ú][A-ZÀ-Ú .\-/]{3,80})", compact):
        name = re.sub(r"\s+", " ", match.group(1)).strip(" .:-")
        if name and name not in positions:
            positions.append(name.title())
    subjects = []
    aliases = {"Língua Portuguesa": ["lingua portuguesa", "portugues"], "Raciocínio Lógico": ["raciocinio logico", "matematica"], "Informática": ["informatica"], "Direito Constitucional": ["direito constitucional"], "Direito Administrativo": ["direito administrativo"], "Conhecimentos Específicos": ["conhecimentos especificos"]}
    for name, patterns in aliases.items():
        if not any(pattern in lower for pattern in patterns):
            continue
        pattern = "|".join(re.escape(part) for part in patterns)
        weight_match = re.search(rf"(?:{pattern}).{{0,80}}?(?:peso|pondera[cç][aã]o)\s*[:=]?\s*(\d+(?:[,.]\d+)?)", lower)
        weight = float(weight_match.group(1).replace(",", ".")) if weight_match else 1
        subjects.append(ParsedSubject(name=name, weight=weight))
    return {"examining_board": board, "vacancies_total": sum(vacancies) or None, "dates_found": dates, "positions": positions, "subjects": [asdict(item) for item in subjects], "confidence": {"examining_board": 0.95 if board else 0, "dates": 0.7 if dates else 0, "subjects": 0.7 if subjects else 0}}
