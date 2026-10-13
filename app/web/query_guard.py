"""Fail-closed boundary for text leaving the application for web search.

This is deliberately a small guard, not a promise of complete PII detection.  It
rejects common high-risk forms and never falls back to the original message
after rejection.  A caller can therefore ask the user for a public search topic
instead of accidentally disclosing an attachment excerpt or personal detail.
"""

from __future__ import annotations

import re

from .provider import WebSearchSafetyError


class SearchQueryBuilder:
    """Build a bounded public-topic query for an external search provider."""

    max_characters = 320
    _EMAIL = re.compile(r"\b[\w.+-]+@[\w-]+(?:\.[\w-]+)+\b")
    _PHONE = re.compile(r"(?<!\w)(?:\+?\d[\d .()/-]{7,}\d)(?!\w)")
    _IDENTIFIER = re.compile(r"(?<!\d)\d{17}[\dXx](?!\d)")
    _SECRET = re.compile(
        r"(?:api[ _-]?key|access[ _-]?token|bearer\s+\S+|password|secret|"
        r"tavily[ _-]?api[ _-]?key|deepseek[ _-]?api[ _-]?key|sk-[a-z0-9_-]{12,})",
        re.IGNORECASE,
    )
    _PRIVATE_MARKER = re.compile(
        r"(?:内部(?:文件|资料|文档)|机密|保密|附件全文|private\s+(?:file|document)|"
        r"confidential|internal\s+(?:file|document)|身份证|护照|住址|手机号|邮箱)",
        re.IGNORECASE,
    )
    _MIXED_LOCAL_PREFIX = re.compile(
        r"(?:请)?(?:比较|对比|分析)?\s*(?:我(?:的)?|上传的|本地)?\s*"
        r"(?:附件|文件|文档|资料)(?:内容)?\s*(?:与|和|及|跟|against|with)\s*",
        re.IGNORECASE,
    )
    _MIXED_COMPARE_PREFIX = re.compile(
        r"^\s*(?:请)?(?:对照|比较|对比|分析)\s*"
        r"(?:我(?:已)?上传的|上传的|我(?:的)?(?:附件|文件|文档|资料)|(?:附件|文件|文档|资料))"
        r"[^，。；\n]{0,100}?\s*(?:与|和|及|跟|against|with)\s*",
        re.IGNORECASE,
    )
    _MIXED_TASK_SUFFIX = re.compile(
        r"\s*[，,;；。]\s*(?:分析|说明|分别|并|同时|标明|compare|explain|identify|list).*?$",
        re.IGNORECASE,
    )

    def build(self, candidate: str | None, *, mixed_sources: bool = False) -> str:
        """Return a public query or raise a controlled error without echoing it."""
        if not isinstance(candidate, str):
            raise WebSearchSafetyError("网页搜索需要公共搜索关键词。")
        query = " ".join(candidate.split())
        if mixed_sources:
            # Preserve only the public side of common "attachment versus current X" phrasing.
            query = self._MIXED_COMPARE_PREFIX.sub("", query, count=1).strip()
            query = self._MIXED_LOCAL_PREFIX.sub("", query).strip()
            query = self._MIXED_TASK_SUFFIX.sub("", query).strip()
        if not query or len(query) > self.max_characters or "\n" in candidate:
            raise WebSearchSafetyError("为保护隐私，请提供简短的公共搜索关键词。")
        if any(pattern.search(query) for pattern in (
            self._EMAIL, self._PHONE, self._IDENTIFIER, self._SECRET, self._PRIVATE_MARKER,
        )):
            raise WebSearchSafetyError("为保护隐私，请提供不含个人信息、密钥或内部资料的公共搜索关键词。")
        return query
