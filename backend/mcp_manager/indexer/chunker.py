"""Split text into chunks for embedding."""


def chunk_text(text: str, max_chars: int = 1500, overlap: int = 200) -> list[str]:
    """Split text into overlapping chunks of roughly max_chars characters.

    Tries to split on paragraph boundaries, falls back to sentence boundaries.
    """
    if not text or len(text) <= max_chars:
        return [text] if text else []

    chunks: list[str] = []
    start = 0

    while start < len(text):
        end = start + max_chars

        if end >= len(text):
            chunks.append(text[start:].strip())
            break

        # Try to break at paragraph boundary
        para_break = text.rfind("\n\n", start, end)
        if para_break > start + max_chars // 2:
            end = para_break

        # Try to break at newline
        elif (nl := text.rfind("\n", start, end)) > start + max_chars // 2:
            end = nl

        # Try to break at sentence
        elif (dot := text.rfind(". ", start, end)) > start + max_chars // 2:
            end = dot + 1

        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)

        start = end - overlap

    return chunks
