from datetime import date
from pathlib import Path

from sqlmodel import Session, SQLModel, create_engine, select

from app.models.highlight import Highlight
from app.services.importer import import_clippings_file
from app.services.spark import mark_highlight_seen, select_daily_spark, set_highlight_favorite, set_highlight_hidden


def test_daily_spark_is_stable_for_same_day(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    SQLModel.metadata.create_all(engine)
    fixture = Path(__file__).parent / "fixtures" / "my_clippings_sample.txt"

    with Session(engine) as session:
        import_clippings_file(fixture, session)
        first = select_daily_spark(session, date(2026, 5, 10))
        second = select_daily_spark(session, date(2026, 5, 10))

    assert first is not None
    assert second is not None
    assert first.highlight.id == second.highlight.id


def test_spark_ignores_hidden_highlights(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    SQLModel.metadata.create_all(engine)
    fixture = Path(__file__).parent / "fixtures" / "my_clippings_sample.txt"

    with Session(engine) as session:
        import_clippings_file(fixture, session)
        highlights = session.exec(select(Highlight)).all()
        for highlight in highlights:
            set_highlight_hidden(session, highlight.id, True)

        assert select_daily_spark(session, date(2026, 5, 10)) is None


def test_spark_actions_update_highlight_state(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    SQLModel.metadata.create_all(engine)
    fixture = Path(__file__).parent / "fixtures" / "my_clippings_sample.txt"

    with Session(engine) as session:
        import_clippings_file(fixture, session)
        highlight = session.exec(select(Highlight)).first()
        assert highlight is not None

        seen = mark_highlight_seen(session, highlight.id)
        favorite = set_highlight_favorite(session, highlight.id, True)
        hidden = set_highlight_hidden(session, highlight.id, True)

    assert seen is not None
    assert seen.last_seen_at is not None
    assert favorite is not None
    assert favorite.is_favorite is True
    assert hidden is not None
    assert hidden.is_hidden is True
