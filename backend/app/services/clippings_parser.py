from __future__ import annotations

import argparse
import hashlib
import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional


@dataclass(frozen=True)
class ParsedClipping:
    book_title: str
    author: Optional[str]
    content: str
    note: Optional[str]
    highlight_type: str
    page: Optional[int]
    location_start: Optional[int]
    location_end: Optional[int]
    date_added: Optional[str]
    source: str
    content_hash: str


@dataclass(frozen=True)
class ParseResult:
    records: list[ParsedClipping]
    skipped: int
    errors: list[str]


_DATE_FORMATS = (
    "%A, %B %d, %Y %I:%M:%S %p",
    "%A, %B %d, %Y %I:%M %p",
    "%A, %B %d, %Y",
    "%B %d, %Y %I:%M:%S %p",
    "%B %d, %Y %I:%M %p",
    "%B %d, %Y",
    "%d %B %Y %H:%M:%S",
    "%d %B %Y %H:%M",
    "%d %B %Y",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d",
)

_SPANISH_MONTHS = {
    "enero": "01",
    "febrero": "02",
    "marzo": "03",
    "abril": "04",
    "mayo": "05",
    "junio": "06",
    "julio": "07",
    "agosto": "08",
    "septiembre": "09",
    "setiembre": "09",
    "octubre": "10",
    "noviembre": "11",
    "diciembre": "12",
}


def normalize_text(raw: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-16", "latin-1"):
        try:
            text = raw.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    else:
        text = raw.decode("utf-8", errors="replace")

    return text.replace("\x00", "").replace("\r\n", "\n").replace("\r", "\n")


def parse_file(path: str | Path) -> ParseResult:
    file_path = Path(path)
    return parse_text(normalize_text(file_path.read_bytes()))


def parse_text(text: str) -> ParseResult:
    records: list[ParsedClipping] = []
    errors: list[str] = []
    skipped = 0

    for index, block in enumerate(_split_blocks(text), start=1):
        try:
            record = _parse_block(block)
        except ValueError as exc:
            skipped += 1
            errors.append(f"Record {index}: {exc}")
            continue

        if record is None:
            skipped += 1
            continue

        records.append(record)

    return ParseResult(records=records, skipped=skipped, errors=errors)


def result_to_json(result: ParseResult) -> str:
    return json.dumps(
        {
            "records": [asdict(record) for record in result.records],
            "skipped": result.skipped,
            "errors": result.errors,
        },
        indent=2,
    )


def _split_blocks(text: str) -> list[str]:
    return [block.strip() for block in re.split(r"\n?={10,}\n?", text) if block.strip()]


def _parse_block(block: str) -> ParsedClipping | None:
    lines = [line.rstrip() for line in block.split("\n")]
    lines = [line for line in lines if line.strip()]

    if len(lines) < 3:
        raise ValueError("expected title, metadata, and content")

    title_line = lines[0].strip()
    metadata = lines[1].strip()
    content = "\n".join(lines[2:]).strip()

    if not content:
        return None

    book_title, author = _parse_title_author(title_line)
    highlight_type = _parse_highlight_type(metadata)
    page = _parse_page(metadata)
    location_start, location_end = _parse_location(metadata)
    date_added = _parse_date(metadata)
    note = content if highlight_type == "note" else None
    highlight_content = "" if highlight_type == "note" else content

    return ParsedClipping(
        book_title=book_title,
        author=author,
        content=highlight_content,
        note=note,
        highlight_type=highlight_type,
        page=page,
        location_start=location_start,
        location_end=location_end,
        date_added=date_added.isoformat() if date_added else None,
        source="my_clippings",
        content_hash=_content_hash(book_title, author, highlight_content, note, location_start, location_end),
    )


def _parse_title_author(title_line: str) -> tuple[str, Optional[str]]:
    title_line = _clean_field(title_line)
    match = re.match(r"^(?P<title>.+?)\s+\((?P<author>[^()]*)\)$", title_line)
    if not match:
        return title_line.strip(), None

    return _clean_field(match.group("title")), _clean_field(match.group("author")) or None


def _parse_highlight_type(metadata: str) -> str:
    lowered = metadata.lower()
    if "note" in lowered or "nota" in lowered:
        return "note"
    if "bookmark" in lowered or "marcador" in lowered:
        return "bookmark"
    return "highlight"


def _parse_page(metadata: str) -> Optional[int]:
    match = re.search(r"\b(?:page|página)\s+(\d+)", metadata, flags=re.IGNORECASE)
    return int(match.group(1)) if match else None


def _parse_location(metadata: str) -> tuple[Optional[int], Optional[int]]:
    match = re.search(r"\b(?:location|posición)\s+(\d+)(?:\s*-\s*(\d+))?", metadata, flags=re.IGNORECASE)
    if not match:
        return None, None

    start = int(match.group(1))
    end = int(match.group(2)) if match.group(2) else start
    return start, end


def _parse_date(metadata: str) -> Optional[datetime]:
    raw_date = _extract_raw_date(metadata)
    if not raw_date:
        return None

    raw_date = re.sub(r"\s+", " ", raw_date)

    spanish_date = _parse_spanish_date(raw_date)
    if spanish_date:
        return spanish_date

    for date_format in _DATE_FORMATS:
        try:
            return datetime.strptime(raw_date, date_format)
        except ValueError:
            continue

    return None


def _extract_raw_date(metadata: str) -> Optional[str]:
    for marker in ("Added on ", "Añadido el "):
        if marker in metadata:
            return metadata.split(marker, 1)[1].strip()
    return None


def _parse_spanish_date(raw_date: str) -> Optional[datetime]:
    match = re.search(
        r"(?:lunes|martes|miércoles|miercoles|jueves|viernes|sábado|sabado|domingo),?\s+"
        r"(?P<day>\d{1,2})\s+de\s+(?P<month>[a-záéíóúñ]+)\s+de\s+(?P<year>\d{4})"
        r"(?:\s+(?P<hour>\d{1,2}):(?P<minute>\d{2})(?::(?P<second>\d{2}))?)?",
        raw_date,
        flags=re.IGNORECASE,
    )
    if not match:
        return None

    month = _SPANISH_MONTHS.get(_strip_accents(match.group("month").lower()))
    if not month:
        return None

    hour = int(match.group("hour") or 0)
    minute = int(match.group("minute") or 0)
    second = int(match.group("second") or 0)
    return datetime(
        int(match.group("year")),
        int(month),
        int(match.group("day")),
        hour,
        minute,
        second,
    )


def _strip_accents(value: str) -> str:
    return (
        value.replace("á", "a")
        .replace("é", "e")
        .replace("í", "i")
        .replace("ó", "o")
        .replace("ú", "u")
    )


def _content_hash(
    book_title: str,
    author: Optional[str],
    content: str,
    note: Optional[str],
    location_start: Optional[int],
    location_end: Optional[int],
) -> str:
    parts = [
        _normalize_hash_part(book_title),
        _normalize_hash_part(author or ""),
        _normalize_hash_part(content),
        _normalize_hash_part(note or ""),
        str(location_start or ""),
        str(location_end or ""),
    ]
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()


def _normalize_hash_part(value: str) -> str:
    return re.sub(r"\s+", " ", _clean_field(value).casefold())


def _clean_field(value: str) -> str:
    return re.sub(r"[\ufeff\u200b\u200c\u200d]", "", value).strip()


def main() -> None:
    parser = argparse.ArgumentParser(description="Parse Kindle My Clippings.txt files.")
    parser.add_argument("--input", required=True, help="Path to My Clippings.txt")
    parser.add_argument("--output", help="Optional JSON output path")
    parser.add_argument("--stats", action="store_true", help="Print parse statistics")
    args = parser.parse_args()

    result = parse_file(args.input)

    if args.stats:
        print(f"records={len(result.records)} skipped={result.skipped} errors={len(result.errors)}")

    payload = result_to_json(result)
    if args.output:
        Path(args.output).write_text(payload, encoding="utf-8")
    elif not args.stats:
        print(payload)


if __name__ == "__main__":
    main()
