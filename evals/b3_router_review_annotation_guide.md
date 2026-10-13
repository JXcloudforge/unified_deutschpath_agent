# B3 router review candidate annotation guide

File: b3_router_review_candidates.csv (150 author-prepared candidates). This is an
unreviewed candidate set, not an evaluation result. The blank labels must be filled
by two human annotators independently before adjudication. Do not use this file to
tune rules or prompts before it is frozen and evaluated.

## Intent labels

- rag: asks for established German-learning knowledge or information from an available
  local attachment/session.
- web_search: asks for current or external public facts, including requests that also
  require comparing an attachment.
- no_tool: asks for translation, rewriting, correction, conversation, or generation
  that does not require retrieval.

There are exactly three intent values. mixed_sources is a separate boolean: true only
when the request needs both a local attachment/session and current public information.
It does not create a fourth intent.

Annotators should populate annotator_1_* and annotator_2_* independently. Use the
literal values true or false for mixed_sources. Then discuss disagreements and record
the adjudicated values; only then set review_status to adjudicated. Record ambiguous
interpretation and rationale in notes. Filter final metrics to adjudicated rows only
and retain a frozen copy with a checksum before evaluating.

The candidates were prepared during engineering work, so they are not claimed as a
random sample of production traffic. They have not been human reviewed and provide no
evidence for the 98% target.
