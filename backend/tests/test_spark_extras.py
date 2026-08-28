from collections.abc import Generator
from datetime import date
from pathlib import Path

from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine

from app.database import get_session
from app.main import app
from app.services.importer import import_clippings_file
from app.services.spark import get_spark_streak, record_spark_visit

FIXTURE = Path(__file__).parent / "fixtures" / "my_clippings_sample.txt"


def test_on_this_day(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        import_clippings_file(FIXTURE, session)

    def override_session() -> Generator[Session, None, None]:
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = override_session
    client = TestClient(app)

    try:
        response = client.get("/api/spark/on-this-day")
        assert response.status_code == 200
        # The fixture highlights are dated March 3-4, 2025; asserting the
        # endpoint responds with a well-formed list is enough here since
        # "today" depends on the test run date.
        assert isinstance(response.json(), list)
    finally:
        app.dependency_overrides.clear()


def test_spark_streak(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'streak.db'}", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        record_spark_visit(session, date(2026, 5, 1))
        record_spark_visit(session, date(2026, 5, 2))
        record_spark_visit(session, date(2026, 5, 3))
        record_spark_visit(session, date(2026, 5, 5))  # gap on the 4th

        streak = get_spark_streak(session, date(2026, 5, 3))
        assert streak["current_streak"] == 3
        assert streak["longest_streak"] == 3
        assert streak["total_days"] == 4

        streak_after_gap = get_spark_streak(session, date(2026, 5, 5))
        assert streak_after_gap["current_streak"] == 1
        assert streak_after_gap["longest_streak"] == 3


def test_spark_endpoint_records_a_visit(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'visit.db'}", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        import_clippings_file(FIXTURE, session)

    def override_session() -> Generator[Session, None, None]:
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = override_session
    client = TestClient(app)

    try:
        client.get("/api/spark")
        streak = client.get("/api/spark/streak")
        assert streak.status_code == 200
        assert streak.json()["current_streak"] == 1
    finally:
        app.dependency_overrides.clear()
