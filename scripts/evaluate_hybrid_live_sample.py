"""Small, public-only DeepSeek routing trial; deliberately does not run the 300-case set."""
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.stdout.reconfigure(encoding="utf-8")

from app.llm import DeepSeekLLM, build_llm
from app.routing import HybridIntentRouter, LLMIntentRouter, RuleBasedIntentRouter, RoutingContext

CASES = [
    ("Translate this into German: I am ready", "no_tool", False),
    ("帮我润色这段自我介绍", "no_tool", False),
    ("给我一个德语自我介绍模板", "no_tool", False),
    ("Explain German Dativ with examples", "rag", False),
    ("What does my uploaded document say?", "rag", True),
    ("请根据附件总结项目风险", "rag", True),
    ("今天柏林天气怎么样？", "web_search", False),
    ("Search the web for current German visa news", "web_search", False),
    ("比较上传附件与网上最新签证政策", "web_search", True),
    ("Write a short German dialogue", "no_tool", False),
    ("What is the latest EUR exchange rate?", "web_search", False),
    ("德语 Ausbildung 申请需要哪些材料？", "rag", False),
    ("Rewrite this email politely", "no_tool", False),
    ("联网查德国火车今天是否罢工", "web_search", False),
    ("请从文件里找出联系人", "rag", True),
    ("Tell a short story about a cat", "no_tool", False),
    ("请联网找当前德国大学学费政策", "web_search", False),
    ("German grammar: when do I use weil?", "rag", False),
    ("Correct my German sentence: Ich gehe Schule", "no_tool", False),
    ("当前德国油价是多少？", "web_search", False),
]


def main() -> int:
    llm = build_llm()
    if not isinstance(llm, DeepSeekLLM):
        print(json.dumps({"executed": False, "reason": "DEEPSEEK_API_KEY is not configured"}))
        return 1
    rules = RuleBasedIntentRouter()
    semantic = LLMIntentRouter(llm, retries=0, timeout_seconds=30)
    hybrid = HybridIntentRouter(rules, semantic)
    rows = []
    for message, expected, has_attachment in CASES:
        context = RoutingContext(has_attachment=has_attachment)
        rule = rules.route(message, context)
        calls_before = semantic.metrics.calls
        hybrid_decision = hybrid.route(message, context)
        rows.append({"message": message, "expected": expected, "rule": rule.intent.value,
                     "hybrid": hybrid_decision.intent.value, "mixed_sources": hybrid_decision.mixed_sources,
                     "deepseek_called": semantic.metrics.calls > calls_before})
    report = {"executed": True, "sample_size": len(rows), "rows": rows, "metrics": semantic.metrics.report(),
              "actual_token_usage": None, "note": "DeepSeekLLM does not expose response usage; no estimated tokens are reported as actual billing."}
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
