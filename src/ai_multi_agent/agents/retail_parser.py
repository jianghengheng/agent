from __future__ import annotations

import calendar
import re
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Literal

from ai_multi_agent.agents.base import BaseAgent
from ai_multi_agent.graph.state import ConversationMessage, WorkflowState

RETAIL_METRIC_KEYWORDS = ("销售额", "销售", "营业额", "gmv", "业绩")
STORE_PATTERN = re.compile(r"([A-Za-z0-9\u4e00-\u9fa5·_-]{1,24}(?:店铺|门店|店))")
TOKEN_PATTERN = re.compile(r"[A-Za-z0-9\u4e00-\u9fa5]+")
FOLLOW_UP_MARKERS = (
    "那",
    "呢",
    "这个",
    "那个",
    "它",
    "她",
    "他",
    "继续",
    "再",
    "上周",
    "这周",
    "本周",
)
NON_RETAIL_CHAT_HINTS = ("天气", "几月几号", "星期", "日期", "你好", "您好", "谢谢")
MAX_RAW_HISTORY_MESSAGES = 8
MAX_RAW_HISTORY_CHARACTERS = 1200
RECENT_HISTORY_MESSAGES = 6


@dataclass(slots=True)
class RetailQueryResult:
    query_type: str
    keywords: list[str]
    metric: str | None
    store_name: str | None
    start_date: str | None
    end_date: str | None
    current_date: str


@dataclass(slots=True)
class ConversationContextBundle:
    mode: Literal["none", "raw", "summary"]
    summary: str
    recent_messages: list[ConversationMessage]
    last_user_message: str | None
    last_assistant_message: str | None


class RetailParserAgent(BaseAgent):
    async def run(self, state: WorkflowState) -> dict[str, object]:
        task = state.get("task", "")
        history_messages = _normalize_history_messages(state.get("messages", []))
        result = parse_retail_query(task, history_messages=history_messages)
        conversation_bundle = await self._prepare_conversation_context(
            task=task,
            context=state.get("context", ""),
            history_messages=history_messages,
        )
        answer_markdown = await self.complete(
            _build_answer_prompt(
                task=task,
                context=state.get("context", ""),
                result=result,
                conversation_bundle=conversation_bundle,
            )
        )

        return {
            "plan": _build_plan_markdown(result, conversation_bundle),
            "final_answer": answer_markdown,
            "approved": True,
            "revision_count": 0,
            "trace": [f"{self.name}: retail query parsed"],
        }

    async def _prepare_conversation_context(
        self,
        *,
        task: str,
        context: str,
        history_messages: list[ConversationMessage],
    ) -> ConversationContextBundle:
        if not history_messages:
            return ConversationContextBundle(
                mode="none",
                summary="",
                recent_messages=[],
                last_user_message=None,
                last_assistant_message=None,
            )

        total_characters = sum(len(message["content"]) for message in history_messages)
        last_user_message = _find_last_message_content(history_messages, role="user")
        last_assistant_message = _find_last_message_content(history_messages, role="assistant")

        if (
            len(history_messages) <= MAX_RAW_HISTORY_MESSAGES
            and total_characters <= MAX_RAW_HISTORY_CHARACTERS
        ):
            return ConversationContextBundle(
                mode="raw",
                summary="",
                recent_messages=history_messages,
                last_user_message=last_user_message,
                last_assistant_message=last_assistant_message,
            )

        recent_messages = history_messages[-RECENT_HISTORY_MESSAGES:]
        summary_source = history_messages[:-RECENT_HISTORY_MESSAGES]
        summary = ""

        if summary_source:
            summary = await self._summarize_history(
                task=task,
                context=context,
                history_messages=summary_source,
            )

        return ConversationContextBundle(
            mode="summary" if summary else "raw",
            summary=summary,
            recent_messages=(
                recent_messages if summary else history_messages[-MAX_RAW_HISTORY_MESSAGES:]
            ),
            last_user_message=last_user_message,
            last_assistant_message=last_assistant_message,
        )

    async def _summarize_history(
        self,
        *,
        task: str,
        context: str,
        history_messages: list[ConversationMessage],
    ) -> str:
        prompt = "\n".join(
            [
                "你是零售经营助手的上下文摘要器。",
                "请将较早的对话压缩成简短中文要点，供后续回答继续使用。",
                "保留以下信息：用户目标、已提到的门店、指标、时间范围、已回答结论、未解决问题。",
                "不要编造，不要扩写，不超过 6 条要点，输出 Markdown 列表。",
                "",
                f"业务上下文：{context or '无'}",
                f"当前最新用户问题：{task}",
                "",
                "较早对话：",
                _format_messages(history_messages),
            ]
        )

        return (
            await self.llm.ainvoke(
                agent_name="parser_summarizer",
                system_prompt=(
                    "You compress multi-turn retail assistant conversations into concise notes."
                ),
                user_prompt=prompt,
            )
        ).strip()


def parse_retail_query(
    task: str,
    today: date | None = None,
    history_messages: list[ConversationMessage] | None = None,
) -> RetailQueryResult:
    current_day = today or date.today()
    normalized_task = task.strip()
    history_context = _extract_history_retail_context(history_messages or [], current_day)
    keywords = _extract_keywords(normalized_task)
    metric = _extract_metric(normalized_task)
    store_name = _extract_store_name(normalized_task)
    start_date, end_date = _extract_date_range(normalized_task, current_day)

    if _should_treat_as_retail_query(
        task=normalized_task,
        metric=metric,
        store_name=store_name,
        start_date=start_date,
        end_date=end_date,
        history_context=history_context,
    ):
        merged_keywords = keywords
        if history_context:
            merged_keywords = _merge_keywords(keywords, history_context.keywords)
        return RetailQueryResult(
            query_type="retail_metric_query",
            keywords=merged_keywords,
            metric=metric or (history_context.metric if history_context else None) or "销售额",
            store_name=store_name or (history_context.store_name if history_context else None),
            start_date=start_date or (history_context.start_date if history_context else None),
            end_date=end_date or (history_context.end_date if history_context else None),
            current_date=current_day.isoformat(),
        )

    return RetailQueryResult(
        query_type="normal_chat",
        keywords=keywords,
        metric=None,
        store_name=None,
        start_date=None,
        end_date=None,
        current_date=current_day.isoformat(),
    )


def _extract_keywords(task: str) -> list[str]:
    seen: set[str] = set()
    keywords: list[str] = []

    for match in TOKEN_PATTERN.findall(task):
        token = match.strip()
        if len(token) <= 1:
            continue
        if token in seen:
            continue
        seen.add(token)
        keywords.append(token)

    return keywords[:8]


def _extract_metric(task: str) -> str | None:
    lowered = task.lower()
    for keyword in RETAIL_METRIC_KEYWORDS:
        if keyword in lowered:
            return keyword.upper() if keyword == "gmv" else keyword
    return None


def _extract_store_name(task: str) -> str | None:
    match = STORE_PATTERN.search(task)
    if not match:
        return None

    store_name = match.group(1).strip("，。！？、 ")
    return store_name or None


def _is_retail_metric_query(task: str) -> bool:
    lowered = task.lower()
    return any(keyword in lowered for keyword in RETAIL_METRIC_KEYWORDS)


def _should_treat_as_retail_query(
    *,
    task: str,
    metric: str | None,
    store_name: str | None,
    start_date: str | None,
    end_date: str | None,
    history_context: RetailQueryResult | None,
) -> bool:
    if _is_retail_metric_query(task):
        return True

    if not history_context:
        return False

    if any(hint in task for hint in NON_RETAIL_CHAT_HINTS):
        return False

    if metric or store_name or start_date or end_date:
        return True

    return len(task) <= 20 and any(marker in task for marker in FOLLOW_UP_MARKERS)


def _extract_date_range(task: str, current_day: date) -> tuple[str | None, str | None]:
    if "今天" in task or "今日" in task:
        return current_day.isoformat(), current_day.isoformat()

    if "昨天" in task or "昨日" in task:
        yesterday = current_day - timedelta(days=1)
        return yesterday.isoformat(), yesterday.isoformat()

    if "这周" in task or "本周" in task:
        week_start = current_day - timedelta(days=current_day.weekday())
        week_end = week_start + timedelta(days=6)
        return week_start.isoformat(), week_end.isoformat()

    if "上周" in task:
        this_week_start = current_day - timedelta(days=current_day.weekday())
        week_start = this_week_start - timedelta(days=7)
        week_end = week_start + timedelta(days=6)
        return week_start.isoformat(), week_end.isoformat()

    if "这月" in task or "本月" in task or "这个月" in task:
        month_start = current_day.replace(day=1)
        month_end = current_day.replace(
            day=calendar.monthrange(current_day.year, current_day.month)[1]
        )
        return month_start.isoformat(), month_end.isoformat()

    if "上个月" in task:
        previous_month_last_day = current_day.replace(day=1) - timedelta(days=1)
        month_start = previous_month_last_day.replace(day=1)
        month_end = previous_month_last_day.replace(
            day=calendar.monthrange(previous_month_last_day.year, previous_month_last_day.month)[1]
        )
        return month_start.isoformat(), month_end.isoformat()

    return None, None


def _extract_history_retail_context(
    history_messages: list[ConversationMessage],
    current_day: date,
) -> RetailQueryResult | None:
    for message in reversed(history_messages):
        if message["role"] != "user":
            continue

        candidate = parse_retail_query(message["content"], today=current_day, history_messages=[])
        if candidate.query_type == "retail_metric_query":
            return candidate

    return None


def _merge_keywords(current_keywords: list[str], history_keywords: list[str]) -> list[str]:
    merged = list(current_keywords)
    for keyword in history_keywords:
        if keyword not in merged:
            merged.append(keyword)
    return merged[:8]


def _normalize_history_messages(
    messages: list[ConversationMessage] | object,
) -> list[ConversationMessage]:
    if not isinstance(messages, list):
        return []

    normalized_messages: list[ConversationMessage] = []
    for message in messages:
        if not isinstance(message, dict):
            continue

        role = message.get("role")
        content = message.get("content")
        if role not in {"user", "assistant", "system"}:
            continue
        if not isinstance(content, str):
            continue

        normalized_content = content.strip()
        if not normalized_content:
            continue

        normalized_messages.append(
            {
                "role": role,
                "content": normalized_content,
            }
        )

    return normalized_messages


def _format_messages(messages: list[ConversationMessage]) -> str:
    if not messages:
        return "无"

    role_labels = {
        "user": "用户",
        "assistant": "助手",
        "system": "系统",
    }
    return "\n".join(
        f"[{role_labels[message['role']]}] {message['content']}" for message in messages
    )


def _find_last_message_content(
    messages: list[ConversationMessage],
    *,
    role: Literal["user", "assistant"],
) -> str | None:
    for message in reversed(messages):
        if message["role"] == role:
            return message["content"]
    return None


def _build_plan_markdown(
    result: RetailQueryResult,
    conversation_bundle: ConversationContextBundle,
) -> str:
    history_note = "无历史消息"
    if conversation_bundle.mode == "raw":
        history_note = f"直接携带 {len(conversation_bundle.recent_messages)} 条历史消息"
    if conversation_bundle.mode == "summary":
        history_note = (
            f"较早历史已摘要，保留最近 {len(conversation_bundle.recent_messages)} 条原始消息"
        )

    return "\n".join(
        [
            "## 解析计划",
            f"- 问句类型：{result.query_type}",
            f"- 关键词：{', '.join(result.keywords) if result.keywords else '未识别'}",
            f"- 店铺：{result.store_name or '未识别'}",
            f"- 时间范围：{result.start_date or '未识别'} ~ {result.end_date or '未识别'}",
            f"- 上下文处理：{history_note}",
        ]
    )


def _build_answer_prompt(
    *,
    task: str,
    context: str,
    result: RetailQueryResult,
    conversation_bundle: ConversationContextBundle,
) -> str:
    history_mode_label = {
        "none": "no_history",
        "raw": "raw_history",
        "summary": "summarized_history",
    }[conversation_bundle.mode]

    return "\n".join(
        [
            "你是零售经营助手的第一个智能体，当前职责是：",
            "1. 理解用户问题。",
            "2. 如果是普通问题，就直接回答用户，不要模板化自我介绍。",
            "3. 如果是零售经营问题，就结合已解析参数回答；"
            "如果没有真实数据，要明确说明当前是参数解析阶段，"
            "暂时没有真实经营数据。",
            "4. 输出必须是中文 Markdown。",
            "",
            f"Business Context: {context or '无'}",
            f"Current Date: {result.current_date}",
            f"History Mode: {history_mode_label}",
            f"Last User Message: {conversation_bundle.last_user_message or '无'}",
            f"Last Assistant Message: {conversation_bundle.last_assistant_message or '无'}",
            f"Question Type: {result.query_type}",
            f"User Question: {task}",
            f"Keywords: {', '.join(result.keywords) if result.keywords else '未识别'}",
            f"Metric: {result.metric or '未识别'}",
            f"Store Name: {result.store_name or '未识别'}",
            f"Start Date: {result.start_date or '未识别'}",
            f"End Date: {result.end_date or '未识别'}",
            "",
            "## Conversation Summary",
            conversation_bundle.summary or "无",
            "",
            "## Recent Conversation",
            _format_messages(conversation_bundle.recent_messages),
            "",
            "回答要求：",
            "- 优先结合上下文回答追问。",
            "- 对普通问题，直接回答用户问题本身。",
            "- 对零售问题，先给出一句直接回应，再给出解析结果。",
            "- 如果当前问句省略了店铺、指标或时间，但上下文足够明确，可以自然继承。",
            "- 如果上下文仍不足以明确零售参数，要明确指出缺失项。",
            "- 不要输出“我是第一个智能体”这类空话，除非有必要解释当前能力边界。",
        ]
    )
