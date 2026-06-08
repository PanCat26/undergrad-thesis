from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.rag.extract import Segment

_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=150)


def chunk_segments(segments: list[Segment]) -> list[dict]:
    """Split text segments into overlapping chunks, carrying location metadata."""
    chunks: list[dict] = []
    for text, loc in segments:
        for piece in _splitter.split_text(text):
            if piece.strip():
                chunks.append({"text": piece, "loc": loc})
    return chunks
