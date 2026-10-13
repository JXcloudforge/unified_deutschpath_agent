# Deutschpath routing policy

This policy is the evaluation reference, not a claim that every natural-language request is unambiguous.

| User need | Decision |
| --- | --- |
| German grammar, vocabulary, pronunciation, and product knowledge explanation | `rag` |
| Explicit knowledge-base request, attachment, or uploaded personal material | `rag` |
| Translation, rewrite, template, story, dialogue, flashcards, casual chat | `no_tool` |
| Current policy, market data, news, weather, schedules, or other real-time facts | `web_search` |
| Local attachment/material plus current external facts | `web_search` with `mixed_sources=true` |

Ambiguous requests are labelled as candidate data during engineering evaluation. They require human review before becoming formal acceptance truth. Explicit real-time requests remain protected from fallback to ungrounded generation.

Direct text editing takes priority over incidental German-language terms. An attachment plus an explicit current comparison takes priority over attachment-only RAG.
