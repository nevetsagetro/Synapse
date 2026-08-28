from app.services.book_identity import authors_compatible, normalize_identity


def test_normalize_identity_strips_invisible_characters_and_case() -> None:
    assert normalize_identity("﻿La  agonía   del Eros ") == "la agonía del eros"


def test_authors_compatible_treats_empty_as_wildcard() -> None:
    assert authors_compatible("", "Someone") is True
    assert authors_compatible(None, "Someone") is True
    assert authors_compatible("Someone", None) is True


def test_authors_compatible_matches_reordered_last_first() -> None:
    assert authors_compatible("James Clear", "Clear, James") is True


def test_authors_compatible_matches_primary_author_inside_full_contributor_list() -> None:
    # The real bug: My Clippings.txt stores just the primary author as
    # "Last, First"; the Kindle Notebook scraper captures Amazon's full
    # contributor line including translators. Same book, very different
    # author strings.
    assert (
        authors_compatible(
            "Han, Byung-Chul",
            "Byung-Chul Han, Antoni Martínez Riu, Raúl Gabás, Alain Badiou, and Ferran Fernández",
        )
        is True
    )


def test_authors_compatible_rejects_different_people_sharing_a_first_name() -> None:
    assert authors_compatible("Stephen King", "Stephen Hawking") is False


def test_authors_compatible_rejects_different_mononyms() -> None:
    assert authors_compatible("Plato", "Aristotle") is False
