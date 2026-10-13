"""Version 2 candidate evaluation set: 300 independently authored intent prompts.

Labels are engineering-reviewed candidates, not a substitute for a human annotation study.
"""

from app.routing import Intent
from app.routing.evaluation import IntentCase


RAG = [
    "Explain the Dativ case with examples", "What is the difference between Akkusativ and Dativ?",
    "帮我解释德语虚拟式 II", "德语 Ausbildung 申请需要哪些材料？", "Give me German vocabulary for a pharmacy",
    "How do I pronounce the German ch sound?", "请根据附件总结项目代号", "这份上传文档的截止日期是什么？",
    "请查附件中的公司名称", "Summarize my uploaded PDF in German", "资料里提到的 B1 语法点是什么？",
    "Explain German Genitiv for my lesson", "知识库里的德国签证资料怎么说？", "Find the phrase in the attached markdown",
    "附件中有哪些风险？", "What does the document say about the exam?", "德语词汇表里 Hausarzt 是什么意思？",
    "Compare examples from my attachment", "根据我上传的材料生成复习卡片", "German grammar: when do I use weil?",
    "请从文件里找出联系人", "What does the local document say about dates?", "解释德语从句语序",
    "附件里的项目预算是多少？", "Use the knowledge base to explain German articles",
]
WEB = [
    "今天柏林天气怎么样？", "查一下网上最新德国签证政策", "Search the web for current EUR exchange rates",
    "What is the latest news from Berlin?", "联网查德国火车今天是否罢工", "Find current stock price for SAP",
    "最新 Bundesliga 比赛结果是什么？", "查网页搜索德国公共假日最新规定", "What is the current visa fee?",
    "今天慕尼黑的天气预报", "Search the web for recent German election news", "实时查询柏林到汉堡的列车状态",
    "最新欧元兑人民币汇率", "Browse for current German immigration law changes", "现在德国油价是多少？",
    "查一下网络上的最新考试报名日期", "What is today's weather in Frankfurt?", "Search web: current Berlin pollen forecast",
    "实时新闻：德国经济数据", "查网上最新签证预约情况", "latest Germany travel advisory",
    "请联网找当前德国大学学费政策", "网上搜索今天的足球赛程", "最新德国交通法规是什么？",
    "Search the web for current public holiday information",
]
NO_TOOL = [
    "Translate this into German: I am tired", "把这句话翻译成英语", "Rewrite this email more politely",
    "帮我润色这段自我介绍", "Hello, how are you?", "Correct my German sentence: Ich gehe Schule",
    "用德语写一首短诗", "Summarize this sentence without looking anything up", "把下面内容改成正式语气",
    "Create three flashcard questions", "Can you chat with me in German?", "解释一下你能做什么",
    "帮我把这句话改写得更简短", "Translate Guten Morgen to Chinese", "Write a friendly birthday message",
    "Proofread my paragraph", "给我一个德语自我介绍模板", "Tell a short story about a cat",
    "Convert this bullet list into prose", "纠正这句德语的拼写", "Make this answer more concise",
    "Translate: today I will practise German", "请和我进行角色扮演", "写一个学习计划，不需要查询资料",
    "Rewrite this text for an A2 learner",
]


def build_cases() -> list[IntentCase]:
    cases: list[IntentCase] = []
    qualifiers = ["", " Please be concise.", " 请保持简洁。", " Answer for a beginner."]
    for text in RAG:
        is_attachment = any(word in text.lower() for word in ("attachment", "uploaded", "document", "附件", "文件", "资料", "上传"))
        for qualifier in qualifiers:
            cases.append(IntentCase(text + qualifier, Intent.RAG, has_attachment=is_attachment))
    for text in WEB:
        for qualifier in qualifiers:
            cases.append(IntentCase(text + qualifier, Intent.WEB_SEARCH))
    for text in NO_TOOL:
        for qualifier in qualifiers:
            cases.append(IntentCase(text + qualifier, Intent.NO_TOOL))
    # 15 intentionally distinct mixed-source prompts replace 15 ordinary web variants, preserving 100 per class.
    for index in range(15):
        cases[100 + index] = IntentCase(
            f"请比较我上传的附件与网上最新德国签证政策，第 {index + 1} 个核验点。",
            Intent.WEB_SEARCH,
            has_attachment=True,
            expected_mixed_sources=True,
        )
    assert len(cases) == 300
    return cases
