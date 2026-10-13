import pytest

from app.routing import Intent, RoutingContext, RuleBasedIntentRouter


def test_local_knowledge_question_routes_to_rag():
    decision = RuleBasedIntentRouter().route("请解释 Dativ 的用法", RoutingContext())
    assert decision.intent is Intent.RAG


def test_explicit_current_external_fact_routes_to_web_search():
    decision = RuleBasedIntentRouter().route("德国最新签证政策是什么？", RoutingContext())
    assert decision.intent is Intent.WEB_SEARCH
    assert decision.query == "德国最新签证政策是什么？"


def test_translation_and_chat_route_to_no_tool():
    router = RuleBasedIntentRouter()
    assert router.route("把今天的作业翻译成德语", RoutingContext()).intent is Intent.NO_TOOL
    assert router.route("你好", RoutingContext()).intent is Intent.NO_TOOL


def test_time_word_without_external_fact_does_not_trigger_web_search():
    decision = RuleBasedIntentRouter().route("今天我想练习德语自我介绍", RoutingContext())
    assert decision.intent is Intent.RAG


def test_attachment_question_is_protected_as_rag():
    decision = RuleBasedIntentRouter().route("请总结这个文件", RoutingContext(has_attachment=True, has_session=True))
    assert decision.intent is Intent.RAG


def test_mixed_local_and_current_request_is_explicitly_marked():
    decision = RuleBasedIntentRouter().route("根据上传文件和最新签证政策给建议", RoutingContext(has_attachment=True))
    assert decision.intent is Intent.WEB_SEARCH
    assert decision.mixed_sources is True


def test_action_and_dual_source_priority_are_not_overridden_by_german_keywords():
    router = RuleBasedIntentRouter()
    assert router.route("纠正这句德语：Er gehen nach Hause", RoutingContext()).intent is Intent.NO_TOOL
    decision = router.route("比较附件与最新德国劳动法", RoutingContext(has_attachment=True))
    assert decision.intent is Intent.WEB_SEARCH and decision.mixed_sources is True


def test_uploaded_ausbildung_plan_against_current_visa_requirements_is_mixed_web():
    message = "对照我上传的德语学习计划与德国目前 Ausbildung 签证的公开语言要求，分析我的学习计划还缺少哪些内容。分别标明附件信息与网页信息的来源。"
    decision = RuleBasedIntentRouter().route(message, RoutingContext(has_attachment=True))
    assert decision.intent is Intent.WEB_SEARCH
    assert decision.mixed_sources is True


@pytest.mark.parametrize(
    ("message", "attachment", "expected"),
    [
        ("How do I pronounce the German ch sound?", False, Intent.RAG),
        ("Use the knowledge base to explain German articles", False, Intent.RAG),
        ("Find the phrase in the attached markdown", False, Intent.RAG),
        ("实时查询柏林到汉堡的列车状态", False, Intent.WEB_SEARCH),
        ("现在德国油价是多少？", False, Intent.WEB_SEARCH),
        ("latest Germany travel advisory", False, Intent.WEB_SEARCH),
        ("用德语写一首短诗", False, Intent.NO_TOOL),
        ("写一个学习计划，不需要查询资料", False, Intent.NO_TOOL),
        ("翻译我上传的文件", True, Intent.RAG),
    ],
)
def test_task_action_and_source_priority_across_languages(message, attachment, expected):
    assert RuleBasedIntentRouter().route(message, RoutingContext(has_attachment=attachment)).intent is expected
