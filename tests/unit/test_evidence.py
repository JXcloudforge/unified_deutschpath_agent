from app.agent.evidence import Evidence, EvidenceAggregator, EvidenceSource
from app.schemas import ParsedDocument, SearchResult
from app.web import WebSearchResult


def test_evidence_aggregator_preserves_source_identifiers_urls_and_deduplicates():
    aggregator = EvidenceAggregator(max_items=4, max_characters=100, max_item_characters=60)
    local = aggregator.direct_attachment(ParsedDocument("private.txt", "txt", "same text", {"document_id": "file-7"}))
    same_local = Evidence(EvidenceSource.LOCAL_FILE, " same   text ", "duplicate", document_id="other")
    web = aggregator.web_results((WebSearchResult("Web title", "https://example.test/a", "web text", "2026-10-10"),))
    bundle = aggregator.aggregate([local, same_local], web)
    assert len(bundle.items) == 2
    assert "document_id=file-7" in bundle.render()
    assert "url=https://example.test/a" in bundle.render()
    assert "private.txt" in bundle.citations() and "https://example.test/a" in bundle.citations()


def test_evidence_aggregator_bounds_long_results_and_keeps_local_chunk_id():
    aggregator = EvidenceAggregator(max_items=2, max_characters=25, max_item_characters=20)
    local = aggregator.local_results([SearchResult("chunk-9", "x" * 50, 0.1, {"filename": "large.pdf"})])
    bundle = aggregator.aggregate(local)
    assert bundle.truncated is True
    assert bundle.items[0].document_id == "chunk-9"
    assert len(bundle.items[0].content) == 20
