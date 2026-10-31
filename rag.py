from typing import List, Dict

class KnowledgeBase:
    """Lazy-loaded local Chroma index; retrieval is empty until docs are indexed."""
    def __init__(self, persist_dir: str = ".datasentinel/chroma"):
        self.persist_dir = persist_dir
        self._store = None

    def _load_store(self):
        if self._store is None:
            from langchain_chroma import Chroma
            from langchain_huggingface import HuggingFaceEmbeddings
            embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
            self._store = Chroma(collection_name="datasentinel_knowledge",
                                 embedding_function=embeddings, persist_directory=self.persist_dir)
        return self._store

    def add_documents(self, docs: List[Dict]) -> int:
        from langchain_core.documents import Document
        chunks = []
        for item in docs:
            text, start = item["text"], 0
            while start < len(text):
                chunk = text[start:start+900]
                if chunk.strip():
                    chunks.append(Document(page_content=chunk,
                        metadata={"source": item["name"], "chunk_start": start}))
                start += 780
        if chunks:
            self._load_store().add_documents(chunks)
        return len(chunks)

    def retrieve(self, query: str, k: int = 4) -> List[Dict]:
        try:
            docs = self._load_store().similarity_search_with_relevance_scores(query, k=k)
            return [{"source": doc.metadata.get("source", "unknown"),
                     "chunk_start": doc.metadata.get("chunk_start"),
                     "text": doc.page_content[:1200], "relevance": round(float(score), 3)}
                    for doc, score in docs]
        except Exception:
            return []
