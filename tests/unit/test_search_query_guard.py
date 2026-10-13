import pytest

from app.web import SearchQueryBuilder, WebSearchSafetyError


@pytest.mark.parametrize("query", [
    "查询 alice@example.com 的德国签证状态",
    "查询 +49 151 23456789 的移民记录",
    "查询身份证 11010519491231002X 的签证",
    "用 TAVILY_API_KEY=secret-value 查询德国政策",
    "搜索内部文件：CONFIDENTIAL customer notes",
    "德国政策\n附件全文：PRIVATE_FILE_TEXT",
])
def test_sensitive_or_private_candidate_is_rejected_without_echoing_input(query):
    with pytest.raises(WebSearchSafetyError) as exc_info:
        SearchQueryBuilder().build(query)
    assert query not in str(exc_info.value)


def test_mixed_query_strips_common_attachment_reference_and_keeps_public_topic():
    query = SearchQueryBuilder().build("比较我的附件与最新德国劳动法", mixed_sources=True)
    assert query == "最新德国劳动法"


def test_no_safe_fallback_to_original_text_when_mixed_query_only_has_attachment_reference():
    with pytest.raises(WebSearchSafetyError):
        SearchQueryBuilder().build("比较附件与", mixed_sources=True)


def test_mixed_ausbildung_question_sends_only_the_public_web_topic():
    query = SearchQueryBuilder().build(
        "对照我上传的德语学习计划与德国目前 Ausbildung 签证的公开语言要求，分析我的学习计划还缺少哪些内容。分别标明附件信息与网页信息的来源。",
        mixed_sources=True,
    )
    assert query == "德国目前 Ausbildung 签证的公开语言要求"
    assert "学习计划" not in query
    assert "附件信息" not in query
