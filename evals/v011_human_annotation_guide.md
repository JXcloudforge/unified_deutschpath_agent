# v0.1.1 Router human annotation worksheet

Use `v011_human_annotation_worksheet.csv` for independent review. All 150
candidate rows are currently unreviewed; predictions and machine labels must
not be entered as ground truth.

## Labels

- `rag`: established German learning knowledge or information requested from
  local material, including a named attachment or knowledge base.
- `web_search`: current public facts, such as live prices, policies, schedules,
  news, or other information whose freshness matters.
- `no_tool`: conversation, translation, correction, rewriting, or generation
  that needs neither local retrieval nor current public facts.
- `mixed_sources`: `true` only when both local material and current public
  facts are required. It is independent of the three-way intent and implies
  `web_search`.

Each annotator fills only their own intent and mixed-source columns. A third
reviewer records disagreements in `disagreement_reason`, enters the resolved
label in `adjudicated_*`, and sets `review_status` to `adjudicated`. Record the
reviewer in `adjudicator`. Freeze the adjudicated worksheet with a SHA-256
checksum and a `freeze_batch` identifier before running any evaluation. Do
not tune routing rules or prompts against that frozen set.

`v011_review_overlap.json` compares candidate text to the 300 engineering
development cases. It found zero normalized exact matches, zero character
similarity matches at 0.80 or above, and eight token-overlap flags at Jaccard
0.40 or above. Review these eight manually before freezing; these heuristics do
not prove semantic independence. The candidates were prepared during
engineering and still need human review before any formal 98% claim.
