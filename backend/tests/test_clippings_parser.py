from pathlib import Path

from app.services.clippings_parser import parse_file, parse_text


def test_parse_sample_file() -> None:
    fixture = Path(__file__).parent / "fixtures" / "my_clippings_sample.txt"

    result = parse_file(fixture)

    assert len(result.records) == 4
    assert result.skipped == 0
    assert result.errors == []

    first = result.records[0]
    assert first.book_title == "Atomic Habits"
    assert first.author == "James Clear"
    assert first.highlight_type == "highlight"
    assert first.page == 45
    assert first.location_start == 689
    assert first.location_end == 691
    assert first.date_added == "2025-03-03T00:00:00"
    assert first.content_hash


def test_parse_note_as_note_field() -> None:
    fixture = Path(__file__).parent / "fixtures" / "my_clippings_sample.txt"

    result = parse_file(fixture)
    note = result.records[1]

    assert note.highlight_type == "note"
    assert note.content == ""
    assert note.note == "Remember to connect this with attention residue."


def test_parse_missing_author() -> None:
    text = """==========
Book Without Author
- Your Highlight at location 88 | Added on March 4, 2025

A useful line.
=========="""

    result = parse_text(text)

    assert len(result.records) == 1
    assert result.records[0].book_title == "Book Without Author"
    assert result.records[0].author is None


def test_skip_empty_content() -> None:
    text = """==========
Hidden Book (Someone)
- Your Highlight at location 88 | Added on March 4, 2025

=========="""

    result = parse_text(text)

    assert result.records == []
    assert result.skipped == 1


def test_strips_invisible_title_characters() -> None:
    text = """==========
\ufeffLa agonía del Eros (Han, Byung-Chul)
- Your Highlight at location 88 | Added on March 4, 2025

A useful line.
=========="""

    result = parse_text(text)

    assert result.records[0].book_title == "La agonía del Eros"
    assert result.records[0].author == "Han, Byung-Chul"


def test_parse_spanish_kindle_metadata() -> None:
    text = """==========
La agonía del Eros (Han, Byung-Chul)
- Tu resaltado en la página 5 | posición 51-52 | Añadido el miércoles, 8 de abril de 2026 0:24:41

Una cita útil.
=========="""

    result = parse_text(text)
    record = result.records[0]

    assert record.page == 5
    assert record.location_start == 51
    assert record.location_end == 52
    assert record.date_added == "2026-04-08T00:24:41"
