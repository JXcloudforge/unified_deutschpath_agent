"""Thirty independently authored, public-only holdout prompts; max 30 semantic calls."""
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1])); sys.stdout.reconfigure(encoding="utf-8")
from app.llm import DeepSeekLLM, build_llm
from app.routing import HybridIntentRouter, LLMIntentRouter, RuleBasedIntentRouter
from app.routing.evaluation import IntentCase, evaluate
from app.routing.models import Intent

RAW = [
 ("请把这句话翻译成德语：我明天上课", "no_tool", False), ("写一个 A2 级别的餐厅对话", "no_tool", False),
 ("把这封邮件改得更礼貌", "no_tool", False), ("Create five German flashcards", "no_tool", False),
 ("Explain German separable verbs", "rag", False), ("德语 Konjunktiv II 如何使用？", "rag", False),
 ("知识库里关于德国医疗保险怎么解释？", "rag", False), ("附件中的姓名是什么？", "rag", True),
 ("Summarize my uploaded contract", "rag", True), ("请解释德语被动语态", "rag", False),
 ("最新德国最低工资是多少？", "web_search", False), ("Search the web for today's Berlin weather", "web_search", False),
 ("当前欧元汇率", "web_search", False), ("德国最近的科技新闻", "web_search", False),
 ("比较附件与最新德国劳动法", "web_search", True), ("compare my document with current visa rules", "web_search", True),
 ("Write a cheerful German greeting", "no_tool", False), ("纠正这句德语：Er gehen nach Hause", "no_tool", False),
 ("What does German trotzdem mean?", "rag", False), ("德语 B2 写作有哪些连接词？", "rag", False),
 ("查网上今天汉堡天气", "web_search", False), ("current German train strike status", "web_search", False),
 ("写一个关于旅行的短故事", "no_tool", False), ("给我一个求职信模板", "no_tool", False),
 ("附件的结论与最新新闻是否矛盾", "web_search", True), ("Explain German word order after weil", "rag", False),
 ("Rewrite this paragraph for a beginner", "no_tool", False), ("今日德国股市行情", "web_search", False),
 ("上传资料提到的日期是什么", "rag", True), ("德国词汇 Krankenhaus 的意思", "rag", False),
]
# One real call was already consumed by the 20-case diagnostic run; retain a hard 29-call upper bound.
RAW = RAW[:29]
cases=[IntentCase(m,Intent(e),a, a and e=="web_search") for m,e,a in RAW]
llm=build_llm()
if not isinstance(llm,DeepSeekLLM): raise SystemExit("DeepSeek unavailable")
rules=RuleBasedIntentRouter(); semantic=LLMIntentRouter(llm,retries=0,timeout_seconds=30); hybrid=HybridIntentRouter(rules,semantic)
report={"rules":evaluate(rules,cases),"hybrid":evaluate(hybrid,cases),"semantic":semantic.metrics.report(),"actual_token_usage":None,"label_status":"independent engineering holdout; human review pending"}
print(json.dumps(report,ensure_ascii=False,indent=2))
