import json

from google import genai
from sqlmodel import Session, select
from app.models.ai_cache import AIRecommendationCache

from app.config import get_settings
from app.services.insights import get_insights_summary


def get_ai_book_recommendations(session: Session, refresh: bool = False) -> list[dict[str, str]]:
    settings = get_settings()
    if not settings.gemini_api_key:
        return []

    if not refresh:
        cached = session.exec(select(AIRecommendationCache).order_by(AIRecommendationCache.created_at.desc())).first()
        if cached:
            try:
                parsed = json.loads(cached.recommendations_json)
                if isinstance(parsed, list) and len(parsed) > 0 and "genre" not in parsed[0]:
                    return [{"genre": "General Recommendations", "books": parsed}]
                return parsed
            except Exception:
                pass

    # Fetch history of recommended books to avoid duplicates
    all_caches = session.exec(select(AIRecommendationCache)).all()
    past_books = []
    for c in all_caches:
        try:
            data = json.loads(c.recommendations_json)
            for item in data:
                if "genre" in item:
                    for b in item.get("books", []):
                        if b.get("title"): past_books.append(b["title"])
                else:
                    if item.get("title"): past_books.append(item["title"])
        except Exception:
            pass

    # Gather context from insights
    insights = get_insights_summary(session)
    top_authors = [a["name"] for a in insights["top_authors"][:5] if a["name"]]
    top_books = [b["title"] for b in insights["books_to_revisit"][:5] if b["title"]]

    if not top_authors and not top_books:
        return []

    client = genai.Client(api_key=settings.gemini_api_key)

    past_books_instruction = ""
    if past_books:
        past_books_instruction = f"\n    Do NOT recommend any of these books, as the user has already received them as recommendations: {', '.join(past_books)}"

    prompt = f"""
    Based on the following reading habits of the user:
    Top Authors: {", ".join(top_authors)}
    Top Books: {", ".join(top_books)}
    {past_books_instruction}

    Based on these preferences, generate exactly 3 distinct literary genres that would strongly appeal to this user. 
    For each genre, recommend exactly 2 books that the user has probably not read yet.

    Return the response as a JSON array of objects, where each object represents a genre. Each genre object must have the following keys:
    - "genre": The name of the genre (e.g. "Philosophy", "Sci-Fi", "Business Strategy")
    - "books": A JSON array of exactly 2 book objects. Each book object must have:
       - "title": The title of the recommended book
       - "author": The author of the recommended book
       - "reason": A 1-2 sentence explanation of why this book is recommended based on their specific reading history.
    
    Ensure the output is strictly valid JSON without markdown formatting blocks, just the JSON array.
    """

    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=genai.types.GenerateContentConfig(
                system_instruction="You are an expert literary advisor. Always return raw JSON arrays without markdown blocks.",
                temperature=0.7
            )
        )

        content = response.text.strip()
        if content.startswith("```json"):
            content = content[7:]
        if content.endswith("```"):
            content = content[:-3]
        
        parsed = json.loads(content)
        
        # Ensure it conforms to the new format if the model messed up
        if isinstance(parsed, list) and len(parsed) > 0 and "genre" not in parsed[0]:
            parsed = [{"genre": "General Recommendations", "books": parsed}]
        
        # Save to cache
        cache = AIRecommendationCache(recommendations_json=json.dumps(parsed))
        session.add(cache)
        session.commit()
        
        return parsed
    except Exception as e:
        print("Failed to fetch AI recommendations:", e)
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail=str(e))
