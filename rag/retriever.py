from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from rag.ingest import get_documents, Doc


def retrieve(question: str, top_k: int = 8) -> list[Doc]:
    docs = get_documents()
    if not docs:
        return []

    corpus = [d.text for d in docs]
    vectorizer = TfidfVectorizer(stop_words="english")
    matrix = vectorizer.fit_transform(corpus + [question])
    doc_vectors, query_vector = matrix[:-1], matrix[-1]

    sims = cosine_similarity(query_vector, doc_vectors)[0]

    # Boost docs whose ticker is explicitly named in the question
    q_upper = question.upper()
    boosted = [
        sim * 1.5 if d.ticker.split("-")[0] in q_upper else sim
        for sim, d in zip(sims, docs)
    ]

    ranked = sorted(zip(boosted, docs), key=lambda x: x[0], reverse=True)
    return [d for score, d in ranked[:top_k] if score > 0]