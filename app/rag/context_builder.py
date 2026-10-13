from app.schemas import ContextBundle, ParsedDocument, SearchResult


class ContextBuilder:
    """One prompt-context boundary for knowledge, attachment, history, state, and tools."""
    def from_results(self, results: list[SearchResult], label: str = "Retrieved sources") -> str:
        return "\n\n".join(f"[{label} S{index}] source={item.metadata.get('filename', 'unknown')}\n{item.text}" for index, item in enumerate(results, 1))

    def direct_attachment(self, document: ParsedDocument, *, max_characters: int = 12000) -> str:
        text = document.text[:max_characters]
        suffix = "\n[Attachment truncated for direct context]" if len(document.text) > max_characters else ""
        return f"[Attachment: {document.filename}, {document.file_type}]\n{text}{suffix}"

    def bundle(self, **kwargs: str) -> ContextBundle:
        return ContextBundle(**kwargs)
