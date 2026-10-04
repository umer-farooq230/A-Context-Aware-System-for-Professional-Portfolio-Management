import os
import google.genai
from google.genai import types

from google.genai import Client
from rag.retriever import retrieve
from dotenv import load_dotenv


client = Client(api_key=os.getenv("API_KEY"))

SYSTEM_PROMPT = (
    "You are a portfolio assistant. Answer using ONLY the context snippets "
    "provided. When explaining a price move, follow this structure if the "
    "data supports it: (1) state the ticker's move, (2) compare it to the "
    "Nasdaq/index move, (3) compare it to the sector move, (4) cite any "
    "specific news headline or SEC filing as a possible catalyst. "
    "Use hedged language for causality — e.g. 'the broader tech-sector "
    "decline accounts for part of the move, but the larger decline "
    "suggests a company-specific component' — never assert a headline "
    "definitively caused a price move; you only have correlated signals, "
    "not confirmed causation. If the context lacks enough data to explain "
    "a move, say so plainly instead of guessing."
)

def answer_question(question: str) -> dict:
    docs = retrieve(question)
    context = "\n".join(f"- {d.text}" for d in docs) or "No relevant data found."

    response = client.models.generate_content(
        model="gemini-3.6-flash",
        contents=f"Context:\n{context}\n\nQuestion: {question}",
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
        ),
    )

    return {
        "answer": response.text,
        "sources": [{"ticker": d.ticker, "kind": d.kind, "text": d.text} for d in docs],
    }