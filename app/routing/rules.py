"""Small deterministic Stage 3 P1 router; external search is intentionally not implemented here."""

from __future__ import annotations

import re

from .models import Intent, RouteDecision, RoutingContext

_NO_TOOL_TASK = re.compile(
    r"\b(translate|translation|rewrite|rephrase|proofread|correct|write|create|tell|template|dialogue|story|flashcard)\b|翻译|改写|润色|纠错|纠正|改正|修改|修正|校对|模板|故事|对话|闪卡|聊天|你好|您好|(?:用\S{0,12})?写(?:一|个|首|封|段)",
    re.IGNORECASE,
)
_EXPLICIT_WEB = re.compile(
    r"(?:查(?:一下)?(?:网上|网络|互联网)|搜索(?:网上|网络)?|联网查|网页搜索|web\s*search|search\s+(?:the\s+)?web|browse)"
    r"|(?:(?:最新|实时|目前|当前|现行|今日|今天|最近|现在|latest|current|real[- ]?time|today)[^\n]{0,24}"
    r"(?:新闻|消息|政策|法规|天气|汇率|价格|股价|比赛|赛程|签证|news|weather|exchange\s*rate|price|stock|score|schedule|policy|law|visa))"
    r"|(?:(?:新闻|天气|汇率|价格|股价|比赛|赛程|签证|news|weather|exchange\s*rate|price|stock|score|schedule|policy|law|visa)[^\n]{0,24}"
    r"(?:最新|实时|目前|当前|现行|今日|今天|最近|现在|latest|current|real[- ]?time|today))",
    re.IGNORECASE,
)
_RAG_KNOWLEDGE = re.compile(
    r"\b(dativ|akkusativ|genitiv|ausbildung|grammar|vocabulary|germany)\b|德语|语法|词汇|发音|句型|德国|知识库|资料|文档|文章",
    re.IGNORECASE,
)
_LOCAL_SOURCE = re.compile(r"文件|附件|上传|资料|文档|document|attachment|attached|uploaded|knowledge base", re.IGNORECASE)
_FRESHNESS = re.compile(r"最新|实时|目前|现行|当前|今日|今天|最近|现在|latest|current|real[- ]?time|today", re.IGNORECASE)
_COMPARISON = re.compile(r"对照|比较|对比|是否矛盾|compare|contrast|conflict", re.IGNORECASE)
_NO_RETRIEVAL = re.compile(r"(?:不需要|无需|不用)[^。！？\n]{0,12}(?:查询|检索|参考)(?:资料|文件|附件|网页)?|(?:without|do not|don't)[^.!?\n]{0,24}(?:search|retriev|look up)", re.IGNORECASE)
_CURRENT_EXTERNAL = re.compile(
    r"(?:实时查询|(?:最新|实时|目前|当前|现行|今日|今天|最近|现在|latest|current|today)[^\n]{0,40}"
    r"(?:油价|列车状态|车次状态|出行建议|travel advisory|train status|fuel price))",
    re.IGNORECASE,
)


def is_explicit_web_request(message: str) -> bool:
    """Recognize a request for current external facts, not merely an isolated time word."""
    return bool(_EXPLICIT_WEB.search(message) or _CURRENT_EXTERNAL.search(message))


def is_explicit_learning_knowledge_request(message: str) -> bool:
    """Product policy: established German-learning knowledge is local RAG, not an LLM override target."""
    return bool(re.search(r"\b(dativ|akkusativ|genitiv|grammar|vocabulary|ausbildung|pronunciation|pronounce)\b|德语语法|语法|词汇|发音|句型|(?:解释|讲解|说明)[^。！？\n]{0,25}德语", message, re.IGNORECASE))


def is_explicit_local_source_request(message: str) -> bool:
    """Identify a named local source even when session metadata is unavailable."""
    return bool(_LOCAL_SOURCE.search(message))


class RuleBasedIntentRouter:
    """Deterministic baseline for P1; later semantic routing can implement the same protocol."""

    def route(self, message: str, context: RoutingContext) -> RouteDecision:
        if not isinstance(message, str) or not message.strip():
            raise ValueError("message must be a non-empty string")
        normalized = message.strip()

        # Translation and text-editing requests may mention time words without asking for live facts.
        if _NO_TOOL_TASK.search(normalized) and not is_explicit_web_request(normalized) and (not _LOCAL_SOURCE.search(normalized) or _NO_RETRIEVAL.search(normalized)):
            return RouteDecision(Intent.NO_TOOL, 0.94, "text generation or casual conversation does not require retrieval")

        if context.has_attachment and _LOCAL_SOURCE.search(normalized) and _FRESHNESS.search(normalized) and _COMPARISON.search(normalized):
            return RouteDecision(Intent.WEB_SEARCH, 0.97, "request compares local material with current external facts", query=normalized, mixed_sources=True)

        if is_explicit_web_request(normalized):
            mixed = context.has_attachment and bool(_LOCAL_SOURCE.search(normalized))
            reason = "request explicitly needs current external facts"
            if mixed:
                reason = "request combines uploaded/local material with current external facts"
            return RouteDecision(Intent.WEB_SEARCH, 0.95, reason, query=normalized, mixed_sources=mixed)

        if context.has_attachment or _LOCAL_SOURCE.search(normalized):
            return RouteDecision(Intent.RAG, 0.99, "request refers to available or named local material", query=normalized)

        if _RAG_KNOWLEDGE.search(normalized) or re.search(r"\b(pronounce|pronunciation|knowledge base)\b", normalized, re.IGNORECASE):
            return RouteDecision(Intent.RAG, 0.90, "question targets local German/Germany knowledge", query=normalized)

        return RouteDecision(Intent.NO_TOOL, 0.72, "no retrieval or real-time capability is required")
