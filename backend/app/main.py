from pydantic import BaseModel
from contextlib import asynccontextmanager
import csv
import io
import json
import os
from pathlib import Path
import signal
import threading
from tempfile import NamedTemporaryFile
from uuid import UUID

from fastapi import Depends, FastAPI, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from sqlmodel import Session, func, select

from app.config import get_settings
from app.database import get_session, init_db
from app.models.ai_cache import AIRecommendationCache
from app.models.book import Book
from app.models.highlight import Highlight
from app.models.import_log import ImportLog
from app.models.thought import Thought
from app.services.ai_recommendations import get_ai_book_recommendations
from app.services.covers import backfill_covers
from app.services.embeddings import backfill_embeddings, get_related_highlights
from app.services.importer import import_clippings_file
from app.services.insights import get_insights_summary
from app.services.search import search_highlights
from app.services.spark import mark_highlight_seen, select_daily_spark, set_highlight_favorite, set_highlight_hidden

settings = get_settings()
project_root = Path(__file__).resolve().parents[2]
default_clippings_file = project_root / "data" / "imports" / "My Clippings.txt"
default_obsidian_dir = project_root / "data" / "exports" / "obsidian"


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title=settings.app_name, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        f"http://localhost:{settings.frontend_port}",
        f"http://127.0.0.1:{settings.frontend_port}",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "app": settings.app_name}


def _shutdown_process() -> None:
    threading.Timer(0.5, lambda: os.kill(os.getpid(), signal.SIGTERM)).start()


@app.post("/api/shutdown")
def shutdown() -> dict[str, str]:
    _shutdown_process()
    return {"status": "shutting_down"}


@app.get("/api/summary")
def summary(session: Session = Depends(get_session)) -> dict[str, int | str | None]:
    books = session.exec(select(func.count(Book.id))).one()
    highlights = session.exec(select(func.count(Highlight.id))).one()
    imports = session.exec(select(func.count(ImportLog.id))).one()
    latest_import = session.exec(select(ImportLog).order_by(ImportLog.created_at.desc())).first()

    return {
        "books": books,
        "highlights": highlights,
        "imports": imports,
        "latest_import_at": latest_import.created_at.isoformat() if latest_import else None,
    }


@app.get("/api/insights")
def insights(session: Session = Depends(get_session)) -> dict[str, object]:
    return get_insights_summary(session)


@app.get("/api/insights/ai-recommendations")
def ai_recommendations(refresh: bool = False, session: Session = Depends(get_session)) -> list:
    return get_ai_book_recommendations(session, refresh=refresh)


@app.get("/api/insights/ai-recommendations/history")
def ai_recommendations_history(session: Session = Depends(get_session)) -> list[dict[str, object]]:
    from app.models.ai_cache import AIRecommendationCache
    import json
    # Get all caches except the most recent one
    caches = session.exec(select(AIRecommendationCache).order_by(AIRecommendationCache.created_at.desc()).offset(1)).all()
    history = []
    for c in caches:
        try:
            parsed = json.loads(c.recommendations_json)
            if isinstance(parsed, list) and len(parsed) > 0 and "genre" not in parsed[0]:
                parsed = [{"genre": "General Recommendations", "books": parsed}]
            history.append({
                "id": str(c.id),
                "created_at": c.created_at.isoformat(),
                "recommendations": parsed
            })
        except Exception:
            pass
    return history


@app.get("/api/books")
def books(session: Session = Depends(get_session)) -> list[dict[str, str | int | None]]:
    rows = session.exec(select(Book).order_by(Book.title)).all()
    return [
        {
            "id": str(book.id),
            "title": book.title,
            "author": book.author,
            "cover_url": book.cover_url,
            "total_highlights": book.total_highlights,
            "last_imported_at": book.last_imported_at.isoformat(),
        }
        for book in rows
    ]


@app.get("/api/books/{book_id}")
def book_detail(book_id: UUID, session: Session = Depends(get_session)) -> dict[str, object]:
    book = session.get(Book, book_id)
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")

    highlights = session.exec(
        select(Highlight)
        .where(Highlight.book_id == book.id)
        .order_by(Highlight.location_start, Highlight.page, Highlight.created_at)
    ).all()

    highlights_data = []
    for highlight in highlights:
        thoughts = session.exec(select(Thought).where(Thought.highlight_id == highlight.id).order_by(Thought.created_at.asc())).all()
        highlights_data.append({
            "id": str(highlight.id),
            "book_id": str(highlight.book_id),
            "content": highlight.content,
            "note": highlight.note,
            "highlight_type": highlight.highlight_type,
            "page": highlight.page,
            "location_start": highlight.location_start,
            "location_end": highlight.location_end,
            "date_added": highlight.date_added.isoformat() if highlight.date_added else None,
            "source": highlight.source,
            "is_favorite": highlight.is_favorite,
            "is_hidden": highlight.is_hidden,
            "thoughts": [{"id": str(t.id), "content": t.content, "created_at": t.created_at.isoformat()} for t in thoughts]
        })

    return {
        "book": {
            "id": str(book.id),
            "title": book.title,
            "author": book.author,
            "cover_url": book.cover_url,
            "total_highlights": book.total_highlights,
            "last_imported_at": book.last_imported_at.isoformat(),
        },
        "highlights": highlights_data,
    }


@app.get("/api/imports")
def imports(session: Session = Depends(get_session)) -> list[dict[str, str | int | None]]:
    rows = session.exec(select(ImportLog).order_by(ImportLog.created_at.desc()).limit(10)).all()
    return [
        {
            "id": str(log.id),
            "source": log.source,
            "file_name": log.file_name,
            "records_seen": log.records_seen,
            "records_created": log.records_created,
            "records_skipped": log.records_skipped,
            "records_failed": log.records_failed,
            "created_at": log.created_at.isoformat(),
            "error_summary": log.error_summary,
        }
        for log in rows
    ]


@app.post("/api/import/default")
def import_default(session: Session = Depends(get_session)) -> dict[str, str | int | None]:
    if not default_clippings_file.exists():
        raise HTTPException(status_code=404, detail=f"Missing {default_clippings_file}")

    result = import_clippings_file(default_clippings_file, session)
    return {
        "source": result.source,
        "file_name": result.file_name,
        "records_seen": result.records_seen,
        "records_created": result.records_created,
        "records_skipped": result.records_skipped,
        "records_failed": result.records_failed,
        "books_created": result.books_created,
        "import_log_id": result.import_log_id,
    }


@app.post("/api/import/upload")
async def import_upload(file: UploadFile, session: Session = Depends(get_session)) -> dict[str, str | int | None]:
    if not file.filename:
        raise HTTPException(status_code=400, detail="Missing file name")
    if not file.filename.lower().endswith(".txt"):
        raise HTTPException(status_code=400, detail="Please upload a .txt clipping file")

    contents = await file.read()
    with NamedTemporaryFile(delete=False, suffix=".txt") as temp_file:
        temp_file.write(contents)
        temp_path = Path(temp_file.name)

    try:
        result = import_clippings_file(temp_path, session)
    finally:
        temp_path.unlink(missing_ok=True)

    return {
        "source": result.source,
        "file_name": file.filename,
        "records_seen": result.records_seen,
        "records_created": result.records_created,
        "records_skipped": result.records_skipped,
        "records_failed": result.records_failed,
        "books_created": result.books_created,
        "import_log_id": result.import_log_id,
    }



class KindleNotebookImportRequest(BaseModel):
    headed: bool = False
    reset_session: bool = False


@app.post("/api/import/kindle-notebook")
async def import_kindle_notebook(
    req: KindleNotebookImportRequest = KindleNotebookImportRequest(),
    session: Session = Depends(get_session),
) -> dict[str, str | int | None]:
    """
    Scrape highlights from read.amazon.com/notebook and import them.

    First call: opens a visible browser and waits for manual Amazon login.
    Subsequent calls: reuses the saved session (~/.synapse/kindle_session.json).

    Pass `headed: true` to always open the browser window.
    Pass `reset_session: true` to delete the saved session and force re-login.
    """
    import asyncio

    try:
        from scripts.scrape_kindle_notebook import (
            scrape_highlights,
            import_kindle_highlights,
            SESSION_FILE,
        )
    except ImportError as exc:
        raise HTTPException(
            status_code=503,
            detail=(
                "Playwright is not installed. "
                "Run: pip install playwright && playwright install chromium"
            ),
        ) from exc

    def _run() -> dict:
        records = scrape_highlights(headed=req.headed, reset_session=req.reset_session)
        if not records:
            return {
                "source": "kindle_notebook",
                "records_seen": 0,
                "records_created": 0,
                "records_skipped": 0,
                "records_failed": 0,
                "books_created": 0,
                "import_log_id": None,
            }
        return import_kindle_highlights(records)


    try:
        result = await asyncio.to_thread(_run)
    except SystemExit as exc:
        raise HTTPException(status_code=500, detail="Scraper exited unexpectedly — check server logs.") from exc

    return result


def _serialize_highlight_with_book(highlight: Highlight, book: Book | None) -> dict[str, object]:
    return {
        "id": str(highlight.id),
        "book_id": str(highlight.book_id),
        "content": highlight.content,
        "note": highlight.note,
        "page": highlight.page,
        "location_start": highlight.location_start,
        "location_end": highlight.location_end,
        "date_added": highlight.date_added.isoformat() if highlight.date_added else None,
        "quoted_at": highlight.date_added.isoformat() if highlight.date_added else None,
        "source": highlight.source,
        "book_title": book.title if book else "Unknown",
        "author": book.author if book else None,
        "is_favorite": highlight.is_favorite,
        "is_hidden": highlight.is_hidden,
    }


@app.get("/api/spark")
def spark(session: Session = Depends(get_session)) -> dict[str, object | None]:
    item = select_daily_spark(session)
    if not item:
        return {"highlight": None}

    highlight = item.highlight
    book = item.book

    thoughts = session.exec(select(Thought).where(Thought.highlight_id == highlight.id).order_by(Thought.created_at.asc())).all()

    return {
        "highlight": {
            "id": str(highlight.id),
            "content": highlight.content,
            "note": highlight.note,
            "page": highlight.page,
            "location_start": highlight.location_start,
            "location_end": highlight.location_end,
            "quoted_at": highlight.date_added.isoformat() if highlight.date_added else None,
            "book_title": book.title if book else "Unknown",
            "author": book.author if book else None,
            "source": highlight.source,
            "is_favorite": highlight.is_favorite,
            "is_hidden": highlight.is_hidden,
            "last_seen_at": highlight.last_seen_at.isoformat() if highlight.last_seen_at else None,
            "thoughts": [{"id": str(t.id), "content": t.content, "created_at": t.created_at.isoformat()} for t in thoughts]
        }
    }


@app.post("/api/highlights/{highlight_id}/seen")
def mark_seen(highlight_id: UUID, session: Session = Depends(get_session)) -> dict[str, str | None]:
    highlight = mark_highlight_seen(session, highlight_id)
    if not highlight:
        raise HTTPException(status_code=404, detail="Highlight not found")
    return {"id": str(highlight.id), "last_seen_at": highlight.last_seen_at.isoformat() if highlight.last_seen_at else None}


@app.post("/api/highlights/{highlight_id}/favorite")
def favorite_highlight(highlight_id: UUID, session: Session = Depends(get_session)) -> dict[str, str | bool]:
    highlight = set_highlight_favorite(session, highlight_id, True)
    if not highlight:
        raise HTTPException(status_code=404, detail="Highlight not found")
    return {"id": str(highlight.id), "is_favorite": highlight.is_favorite}


@app.delete("/api/highlights/{highlight_id}/favorite")
def unfavorite_highlight(highlight_id: UUID, session: Session = Depends(get_session)) -> dict[str, str | bool]:
    highlight = set_highlight_favorite(session, highlight_id, False)
    if not highlight:
        raise HTTPException(status_code=404, detail="Highlight not found")
    return {"id": str(highlight.id), "is_favorite": highlight.is_favorite}


@app.post("/api/highlights/{highlight_id}/hidden")
def hide_highlight(highlight_id: UUID, session: Session = Depends(get_session)) -> dict[str, str | bool]:
    highlight = set_highlight_hidden(session, highlight_id, True)
    if not highlight:
        raise HTTPException(status_code=404, detail="Highlight not found")
    return {"id": str(highlight.id), "is_hidden": highlight.is_hidden}


@app.delete("/api/highlights/{highlight_id}/hidden")
def unhide_highlight(highlight_id: UUID, session: Session = Depends(get_session)) -> dict[str, str | bool]:
    highlight = set_highlight_hidden(session, highlight_id, False)
    if not highlight:
        raise HTTPException(status_code=404, detail="Highlight not found")
    return {"id": str(highlight.id), "is_hidden": highlight.is_hidden}


@app.get("/api/highlights/favorites")
def favorite_highlights(session: Session = Depends(get_session)) -> list[dict[str, object]]:
    highlights = session.exec(
        select(Highlight).where(Highlight.is_favorite == True).order_by(Highlight.updated_at.desc())  # noqa: E712
    ).all()
    return [_serialize_highlight_with_book(h, session.get(Book, h.book_id)) for h in highlights]


@app.get("/api/highlights/hidden")
def hidden_highlights(session: Session = Depends(get_session)) -> list[dict[str, object]]:
    highlights = session.exec(
        select(Highlight).where(Highlight.is_hidden == True).order_by(Highlight.updated_at.desc())  # noqa: E712
    ).all()
    return [_serialize_highlight_with_book(h, session.get(Book, h.book_id)) for h in highlights]


@app.get("/api/highlights/search")
def highlights_search(q: str = "", session: Session = Depends(get_session)) -> list[dict[str, object]]:
    highlights = search_highlights(session, q)
    return [_serialize_highlight_with_book(h, session.get(Book, h.book_id)) for h in highlights]


@app.get("/api/books/covers/status")
def covers_status(session: Session = Depends(get_session)) -> dict[str, int]:
    missing = session.exec(select(func.count(Book.id)).where(Book.cover_url.is_(None))).one()
    return {"missing": missing}


@app.post("/api/books/covers/backfill")
def covers_backfill(session: Session = Depends(get_session)) -> dict[str, int]:
    return backfill_covers(session)


@app.get("/api/embeddings/status")
def embedding_status(session: Session = Depends(get_session)) -> dict[str, int]:
    missing = session.exec(select(func.count(Highlight.id)).where(Highlight.embedding.is_(None))).one()
    return {"missing": missing}


@app.post("/api/embeddings/backfill")
def trigger_backfill(session: Session = Depends(get_session)) -> dict[str, int | str]:
    return backfill_embeddings(session)


@app.get("/api/highlights/{highlight_id}/related")
def related_highlights(highlight_id: UUID, session: Session = Depends(get_session)) -> list[dict[str, object]]:
    related = get_related_highlights(session, highlight_id)
    return [
        {
            "id": str(h.id),
            "book_id": str(h.book_id),
            "content": h.content,
            "note": h.note,
            "page": h.page,
            "location_start": h.location_start,
            "location_end": h.location_end,
            "quoted_at": h.date_added.isoformat() if h.date_added else None,
            "source": h.source,
            # we don't have book title natively in highlight model, but UI might want it
            # so we'll fetch books
            "book_title": session.get(Book, h.book_id).title if session.get(Book, h.book_id) else "Unknown",
        }
        for h in related
    ]


from pydantic import BaseModel
class ThoughtCreate(BaseModel):
    content: str

@app.post("/api/highlights/{highlight_id}/thoughts")
def add_thought(highlight_id: UUID, thought: ThoughtCreate, session: Session = Depends(get_session)) -> dict[str, str]:
    highlight = session.get(Highlight, highlight_id)
    if not highlight:
        raise HTTPException(status_code=404, detail="Highlight not found")
    
    new_thought = Thought(highlight_id=highlight_id, content=thought.content)
    session.add(new_thought)
    session.commit()
    session.refresh(new_thought)
    
    return {
        "id": str(new_thought.id),
        "content": new_thought.content,
        "created_at": new_thought.created_at.isoformat()
    }

@app.get("/api/export/json")
def export_json(session: Session = Depends(get_session)):
    highlights = session.exec(select(Highlight)).all()
    data = []
    for h in highlights:
        book = session.get(Book, h.book_id)
        data.append({
            "id": str(h.id),
            "book_title": book.title if book else None,
            "author": book.author if book else None,
            "content": h.content,
            "note": h.note,
            "page": h.page,
            "location_start": h.location_start,
            "location_end": h.location_end,
            "date_added": h.date_added.isoformat() if h.date_added else None,
            "source": h.source,
            "is_favorite": h.is_favorite,
        })
    
    return StreamingResponse(
        iter([json.dumps(data, indent=2)]),
        media_type="application/json",
        headers={"Content-Disposition": "attachment; filename=synapse_export.json"}
    )


@app.get("/api/export/csv")
def export_csv(session: Session = Depends(get_session)):
    highlights = session.exec(select(Highlight)).all()
    
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "id", "book_title", "author", "content", "note", "page", 
        "location_start", "location_end", "date_added", "source", "is_favorite"
    ])
    
    for h in highlights:
        book = session.get(Book, h.book_id)
        writer.writerow([
            str(h.id),
            book.title if book else "",
            book.author if book else "",
            h.content,
            h.note or "",
            h.page or "",
            h.location_start or "",
            h.location_end or "",
            h.date_added.isoformat() if h.date_added else "",
            h.source,
            "true" if h.is_favorite else "false"
        ])
    
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=synapse_export.csv"}
    )


@app.get("/api/export/sqlite")
def export_sqlite():
    settings = get_settings()
    db_path = settings.database_url.replace("sqlite:///", "")
    if not Path(db_path).exists():
        raise HTTPException(status_code=404, detail="Database not found")
    return FileResponse(
        db_path, 
        media_type="application/octet-stream", 
        filename="synapse_backup.db"
    )


frontend_dist = project_root / "frontend" / "dist"

if frontend_dist.exists():
    app.mount("/assets", StaticFiles(directory=frontend_dist / "assets"), name="assets")


@app.get("/{full_path:path}", include_in_schema=False)
def serve_frontend(full_path: str) -> FileResponse:
    index_file = frontend_dist / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return FileResponse(Path(__file__).resolve().parent / "static" / "not-built.html")
