from __future__ import annotations

import asyncio
import calendar
import json
import re
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Literal

from ai_multi_agent.agents.base import BaseAgent
from ai_multi_agent.graph.state import ConversationMessage, WorkflowState

RETAIL_METRIC_KEYWORDS = ("销售额", "销售", "利润", "gmv", "业绩")
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
NON_RETAIL_CHAT_HINTS = (
    "天气", "几月几号", "几号", "几月", "星期", "日期", "几点",
    "今天是", "现在是", "什么时候",
    "你好", "您好", "谢谢", "感谢", "再见", "拜拜",
    "你是谁", "你叫什么", "介绍一下你",
)
STORE_PREFIXES = (
    "今天的",
    "今日的",
    "昨天的",
    "昨日的",
    "本周的",
    "这周的",
    "上周的",
    "本月的",
    "这月的",
    "这个月的",
    "上个月的",
    "今天",
    "今日",
    "昨天",
    "昨日",
    "本周",
    "这周",
    "上周",
    "本月",
    "这月",
    "这个月",
    "上个月",
)
RECENT_HISTORY_MESSAGES = 6
RAW_HISTORY_MESSAGES_LIMIT = 12
RAW_HISTORY_CHARACTERS_LIMIT = 4000
SUMMARY_TRIGGER_MESSAGES = 20
SUMMARY_TRIGGER_CHARACTERS = 8000
RECENT_ONLY_MESSAGES = 8


@dataclass(slots=True)
class RetailQueryResult:
    query_type: str
    keywords: list[str]
    metric: str | None
    store_name: str | None
    store_flag: bool
    start_date: str | None
    end_date: str | None
    comparison_type: str | None
    comparison_start_date: str | None
    comparison_end_date: str | None
    current_date: str


@dataclass(slots=True)
class ConversationContextBundle:
    mode: Literal["none", "raw", "recent_only", "summary"]
    summary: str
    recent_messages: list[ConversationMessage]
    last_user_message: str | None
    last_assistant_message: str | None


@dataclass(slots=True)
class RetailParserExecution:
    result: RetailQueryResult
    conversation_bundle: ConversationContextBundle
    answer_prompt: str


class RetailParserAgent(BaseAgent):
    async def run(self, state: WorkflowState) -> dict[str, object]:
        execution = await self.prepare(state)
        answer_markdown = await self.complete(execution.answer_prompt)

        return self._build_result_payload(execution=execution, answer_markdown=answer_markdown)

    async def prepare(self, state: WorkflowState) -> RetailParserExecution:
        task = state.get("task", "")
        history_messages = _normalize_history_messages(state.get("messages", []))
        result = parse_retail_query(task, history_messages=history_messages)

        # Run date extraction and conversation context in parallel
        async def _resolve_dates() -> RetailQueryResult:
            if result.query_type == "retail_metric_query":
                return await self._resolve_dates_with_llm(task, result, history_messages)
            return result

        resolved_result, conversation_bundle = await asyncio.gather(
            _resolve_dates(),
            self._prepare_conversation_context(
                task=task,
                context=state.get("context", ""),
                history_messages=history_messages,
            ),
        )

        return RetailParserExecution(
            result=resolved_result,
            conversation_bundle=conversation_bundle,
            answer_prompt=_build_answer_prompt(
                task=task,
                context=state.get("context", ""),
                result=resolved_result,
                conversation_bundle=conversation_bundle,
            ),
        )

    async def resolve_dates_only(self, state: WorkflowState) -> RetailQueryResult:
        """Resolve dates with rule-based extraction first, LLM fallback for ambiguous cases."""
        task = state.get("task", "")
        history_messages = _normalize_history_messages(state.get("messages", []))
        result = parse_retail_query(task, history_messages=history_messages)
        if result.query_type != "retail_metric_query":
            return result

        # Try rule-based date extraction first (instant, no LLM call)
        rule_result = _try_extract_dates_by_rules(task, result, history_messages)
        if rule_result is not None:
            return rule_result

        # Fallback to LLM for ambiguous date expressions
        return await self._resolve_dates_with_llm(task, result, history_messages)

    async def prepare_context_only(
        self, state: WorkflowState, resolved_result: RetailQueryResult,
    ) -> RetailParserExecution:
        """Build conversation context and execution (no date LLM call)."""
        task = state.get("task", "")
        history_messages = _normalize_history_messages(state.get("messages", []))
        conversation_bundle = await self._prepare_conversation_context(
            task=task,
            context=state.get("context", ""),
            history_messages=history_messages,
        )
        return RetailParserExecution(
            result=resolved_result,
            conversation_bundle=conversation_bundle,
            answer_prompt=_build_answer_prompt(
                task=task,
                context=state.get("context", ""),
                result=resolved_result,
                conversation_bundle=conversation_bundle,
            ),
        )

    async def _resolve_dates_with_llm(
        self,
        task: str,
        result: RetailQueryResult,
        history_messages: list[ConversationMessage],
    ) -> RetailQueryResult:
        history_hint = ""
        if history_messages:
            recent = history_messages[-4:]
            history_hint = "最近对话：\n" + _format_messages(recent)

        prompt = DATE_EXTRACTION_PROMPT.format(
            current_date=result.current_date,
            task=task,
            history_hint=history_hint,
        )

        try:
            raw = await self.llm.ainvoke(
                agent_name="date_extractor",
                system_prompt="You extract dates from Chinese text. Output JSON only.",
                user_prompt=prompt,
            )
            parsed = _parse_date_json(raw.strip())

            start_date = parsed.get("start_date")
            end_date = parsed.get("end_date")
            comparison_type = parsed.get("comparison_type", "同比")

            if start_date and not _is_valid_date(start_date):
                start_date = None
            if end_date and not _is_valid_date(end_date):
                end_date = None
            if not end_date and start_date:
                end_date = start_date

            if comparison_type not in ("同比", "环比"):
                comparison_type = "同比"

            comparison_start_date, comparison_end_date = _build_comparison_date_range(
                start_date=start_date,
                end_date=end_date,
                comparison_type=comparison_type,
            )

            print(f"\n🤖 AI 日期解析结果：start={start_date}, end={end_date}, "
                  f"comparison_type={comparison_type}, "
                  f"comp_start={comparison_start_date}, comp_end={comparison_end_date}")

            return RetailQueryResult(
                query_type=result.query_type,
                keywords=result.keywords,
                metric=result.metric,
                store_name=result.store_name,
                store_flag=result.store_flag,
                start_date=start_date,
                end_date=end_date,
                comparison_type=comparison_type,
                comparison_start_date=comparison_start_date,
                comparison_end_date=comparison_end_date,
                current_date=result.current_date,
            )
        except Exception:
            import logging
            logging.getLogger(__name__).exception("AI date extraction failed, dates unresolved")
            return result

    def build_plan_markdown(self, execution: RetailParserExecution) -> str:
        return _build_plan_markdown(execution.result, execution.conversation_bundle)

    def _build_result_payload(
        self,
        *,
        execution: RetailParserExecution,
        answer_markdown: str,
    ) -> dict[str, object]:
        return {
            "plan": _build_plan_markdown(execution.result, execution.conversation_bundle),
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
            len(history_messages) <= RAW_HISTORY_MESSAGES_LIMIT
            and total_characters <= RAW_HISTORY_CHARACTERS_LIMIT
        ):
            return ConversationContextBundle(
                mode="raw",
                summary="",
                recent_messages=history_messages,
                last_user_message=last_user_message,
                last_assistant_message=last_assistant_message,
            )

        if (
            len(history_messages) <= SUMMARY_TRIGGER_MESSAGES
            and total_characters <= SUMMARY_TRIGGER_CHARACTERS
        ):
            return ConversationContextBundle(
                mode="recent_only",
                summary="",
                recent_messages=history_messages[-RECENT_ONLY_MESSAGES:],
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
                recent_messages if summary else history_messages[-RAW_HISTORY_MESSAGES_LIMIT:]
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

    if _should_treat_as_retail_query(
        task=normalized_task,
        metric=metric,
        store_name=store_name,
        start_date=None,
        end_date=None,
        history_context=history_context,
    ):
        merged_keywords = keywords
        if history_context:
            merged_keywords = _merge_keywords(keywords, history_context.keywords)
        resolved_metric = metric or (history_context.metric if history_context else None)
        resolved_store_name = store_name or (
            history_context.store_name if history_context else None
        )
        store_flag = _resolve_store_flag(normalized_task, history_context)
        return RetailQueryResult(
            query_type="retail_metric_query",
            keywords=merged_keywords,
            metric=resolved_metric,
            store_name=resolved_store_name,
            store_flag=store_flag,
            start_date=None,
            end_date=None,
            comparison_type=None,
            comparison_start_date=None,
            comparison_end_date=None,
            current_date=current_day.isoformat(),
        )

    return RetailQueryResult(
        query_type="normal_chat",
        keywords=keywords,
        metric=None,
        store_name=None,
        store_flag=True,
        start_date=None,
        end_date=None,
        comparison_type=None,
        comparison_start_date=None,
        comparison_end_date=None,
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

    store_name = _strip_store_prefixes(match.group(1).strip("，。！？、 "))
    return store_name or None


def _should_treat_as_retail_query(
    *,
    task: str,
    metric: str | None,
    store_name: str | None,
    start_date: str | None,
    end_date: str | None,
    history_context: RetailQueryResult | None,
) -> bool:
    if any(hint in task for hint in NON_RETAIL_CHAT_HINTS):
        return False

    # Must have at least one retail signal: metric keyword, store name, or retail history context
    if metric:
        return True
    if store_name:
        return True
    if history_context:
        return True

    # Check for any retail-related keywords in the task
    retail_signals = (
        "销售", "业绩", "利润", "毛利", "营收", "收入", "gmv",
        "会员", "客流", "人效", "门店", "店铺",
        "环比", "同比", "增长", "下降", "对比",
        "蛋糕", "现烤", "线上", "堂食",
    )
    if any(signal in task.lower() for signal in retail_signals):
        return True

    return False


_MONTH_PATTERN = re.compile(r"(\d{1,2})\s*月")
_YEAR_MONTH_PATTERN = re.compile(r"(?:(\d{4})\s*年\s*)?(\d{1,2})\s*月")
_EXACT_DATE_PATTERN = re.compile(
    r"(?:(\d{4})\s*年\s*)?(\d{1,2})\s*月\s*(\d{1,2})\s*[日号]"
)


def _try_extract_dates_by_rules(
    task: str,
    result: RetailQueryResult,
    history_messages: list[ConversationMessage],
) -> RetailQueryResult | None:
    """Try to extract date range from common Chinese time expressions using rules.

    Returns a fully resolved RetailQueryResult if successful, or None to fall back to LLM.
    """
    today = date.fromisoformat(result.current_date)
    comparison_type = _extract_explicit_comparison_type(task) or "同比"

    start_date: date | None = None
    end_date: date | None = None

    # ── Exact date: "2024年3月15日", "3月15号" ──
    m = _EXACT_DATE_PATTERN.search(task)
    if m:
        year = int(m.group(1)) if m.group(1) else today.year
        month = int(m.group(2))
        day = int(m.group(3))
        try:
            start_date = end_date = date(year, month, day)
        except ValueError:
            pass

    # ── Today / yesterday ──
    if start_date is None:
        if "今天" in task or "今日" in task:
            start_date = end_date = today
        elif "昨天" in task or "昨日" in task:
            start_date = end_date = today - timedelta(days=1)
        elif "前天" in task:
            start_date = end_date = today - timedelta(days=2)

    # ── Week ──
    if start_date is None:
        if "本周" in task or "这周" in task:
            start_date = today - timedelta(days=today.weekday())
            end_date = start_date + timedelta(days=6)
        elif "上周" in task:
            last_monday = today - timedelta(days=today.weekday() + 7)
            start_date = last_monday
            end_date = last_monday + timedelta(days=6)

    # ── Month ──
    if start_date is None:
        if "本月" in task or "这个月" in task or "这月" in task:
            start_date = today.replace(day=1)
            end_date = today.replace(day=calendar.monthrange(today.year, today.month)[1])
        elif "上个月" in task or "上月" in task:
            first_of_this_month = today.replace(day=1)
            last_month_end = first_of_this_month - timedelta(days=1)
            start_date = last_month_end.replace(day=1)
            end_date = last_month_end

    # ── "去年N月", "N月" ──
    if start_date is None:
        ym = _YEAR_MONTH_PATTERN.search(task)
        if ym:
            year = int(ym.group(1)) if ym.group(1) else None
            month = int(ym.group(2))
            if 1 <= month <= 12:
                if year is None:
                    if "去年" in task:
                        year = today.year - 1
                    elif "前年" in task:
                        year = today.year - 2
                    else:
                        year = today.year
                last_day = calendar.monthrange(year, month)[1]
                start_date = date(year, month, 1)
                end_date = date(year, month, last_day)

    # ── "去年" (without specific month) ──
    if start_date is None:
        if "去年" in task:
            start_date = date(today.year - 1, 1, 1)
            end_date = date(today.year - 1, 12, 31)
        elif "前年" in task:
            start_date = date(today.year - 2, 1, 1)
            end_date = date(today.year - 2, 12, 31)

    if start_date is None:
        # ── Inherit from conversation history ──
        for msg in reversed(history_messages):
            if msg["role"] != "user":
                continue
            hist_result = parse_retail_query(msg["content"], today=today, history_messages=[])
            if hist_result.query_type == "retail_metric_query":
                hist_resolved = _try_extract_dates_by_rules(
                    msg["content"], hist_result, [],
                )
                if hist_resolved and hist_resolved.start_date:
                    start_date = date.fromisoformat(hist_resolved.start_date)
                    end_date = date.fromisoformat(hist_resolved.end_date) if hist_resolved.end_date else start_date
                    break
        # If still nothing, fall back to LLM
        if start_date is None:
            return None

    if end_date is None:
        end_date = start_date

    start_str = start_date.isoformat()
    end_str = end_date.isoformat()
    comp_start, comp_end = _build_comparison_date_range(
        start_date=start_str,
        end_date=end_str,
        comparison_type=comparison_type,
    )

    print(f"\n⚡ 规则日期解析结果：start={start_str}, end={end_str}, "
          f"comparison_type={comparison_type}, "
          f"comp_start={comp_start}, comp_end={comp_end}")

    return RetailQueryResult(
        query_type=result.query_type,
        keywords=result.keywords,
        metric=result.metric,
        store_name=result.store_name,
        store_flag=result.store_flag,
        start_date=start_str,
        end_date=end_str,
        comparison_type=comparison_type,
        comparison_start_date=comp_start,
        comparison_end_date=comp_end,
        current_date=result.current_date,
    )


DATE_EXTRACTION_PROMPT = """\
你是一个日期提取器。根据用户的问题、对话历史和当前日期，提取出用户想查询的时间范围。

当前日期：{current_date}

用户问题：{task}

{history_hint}

请严格按以下 JSON 格式输出，不要输出任何其他内容：
{{"start_date": "yyyy-MM-dd", "end_date": "yyyy-MM-dd", "comparison_type": "同比或环比"}}

规则：
- start_date 和 end_date 是用户想查的时间范围，格式 yyyy-MM-dd
- "1月"/"2月"等不带年份时，默认为当前年
- "去年"/"前年"等要换算成具体年份
- "去年3月" = 去年3月1日到3月最后一天
- "上周" = 上周一到上周日
- "昨天" = 昨天那一天
- 如果用户当前问题没有提到时间，但对话历史中有明确的时间范围，继承对话历史中最近一次的时间范围
- 只有当用户问题和对话历史中都完全没有提到任何时间时，start_date 和 end_date 才输出 null
- comparison_type：用户说"环比"就输出"环比"，否则默认"同比"
- 只输出 JSON，不要解释\
"""


_JSON_BLOCK_PATTERN = re.compile(r"\{[^}]+\}")


def _parse_date_json(raw: str) -> dict[str, str | None]:
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    match = _JSON_BLOCK_PATTERN.search(cleaned)
    if match:
        return json.loads(match.group())
    return {}


def _is_valid_date(value: str) -> bool:
    try:
        date.fromisoformat(value)
        return True
    except (ValueError, TypeError):
        return False


FAMILY_KEYWORDS = ("家族", "族群", "全部家族", "所有家族")


def _resolve_store_flag(task: str, history_context: RetailQueryResult | None) -> bool:
    if any(keyword in task for keyword in FAMILY_KEYWORDS):
        return False
    if history_context and not history_context.store_flag:
        return False
    return True


def _resolve_comparison_type(
    *,
    task: str,
    history_context: RetailQueryResult | None,
) -> str:
    explicit = _extract_explicit_comparison_type(task)
    if explicit:
        return explicit

    if history_context and history_context.comparison_type:
        return history_context.comparison_type

    return "同比"


def _extract_explicit_comparison_type(task: str) -> str | None:
    if "环比" in task:
        return "环比"

    year_over_year_markers = (
        "同比",
        "去年同期",
        "较去年",
        "对比去年",
        "和去年比",
    )
    if any(marker in task for marker in year_over_year_markers):
        return "同比"

    month_over_month_markers = (
        "比上周",
        "较上周",
        "对比上周",
        "和上周比",
        "比上月",
        "较上月",
        "对比上月",
        "和上月比",
    )
    if any(marker in task for marker in month_over_month_markers):
        return "环比"

    return None


def _build_comparison_date_range(
    *,
    start_date: str | None,
    end_date: str | None,
    comparison_type: str | None,
) -> tuple[str | None, str | None]:
    if not start_date or not end_date or not comparison_type:
        return None, None

    start_day = date.fromisoformat(start_date)
    end_day = date.fromisoformat(end_date)

    if comparison_type == "同比":
        return (
            _safe_replace_year(start_day, start_day.year - 1).isoformat(),
            _safe_replace_year(end_day, end_day.year - 1).isoformat(),
        )

    if comparison_type == "环比":
        period_days = (end_day - start_day).days + 1
        previous_end = start_day - timedelta(days=1)
        previous_start = previous_end - timedelta(days=period_days - 1)
        return previous_start.isoformat(), previous_end.isoformat()

    return None, None


def _safe_replace_year(day: date, target_year: int) -> date:
    max_day = calendar.monthrange(target_year, day.month)[1]
    return day.replace(year=target_year, day=min(day.day, max_day))


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


def _strip_store_prefixes(store_name: str) -> str:
    normalized = store_name
    while True:
        for prefix in STORE_PREFIXES:
            if normalized.startswith(prefix):
                normalized = normalized.removeprefix(prefix).strip()
                break
        else:
            return normalized


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
    if conversation_bundle.mode == "recent_only":
        history_note = f"仅保留最近 {len(conversation_bundle.recent_messages)} 条历史消息"
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
            f"- 对比方式：{result.comparison_type or '未识别'}",
            (
                "- 对比时间范围："
                f"{result.comparison_start_date or '未识别'} ~ "
                f"{result.comparison_end_date or '未识别'}"
            ),
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
        "recent_only": "recent_history_only",
        "summary": "summarized_history",
    }[conversation_bundle.mode]

    return "\n".join(
        [
            "你是零售经营助手，当前职责是：",
            "1. 理解用户问题。",
            "2. 如果是普通问题，就直接回答用户，不要模板化自我介绍。",
            "3. 如果是零售经营问题，就结合已解析参数回答；"
            "当前没有真实数据，请明确告知用户正在查询中或数据暂未获取到。",
            "4. 输出必须是中文 Markdown。",
            "",
            "## 核心原则",
            "- **严禁编造任何数字、金额、百分比或统计数据**。",
            "- 不要从对话历史中提取数字来拼凑表格或列表。",
            "- 如果当前没有真实数据，只描述已解析的参数，不要生成带有数值的表格。",
            "- 不要使用 xxx、待统计 等占位符来伪造数据表格。",
            "",
            f"业务上下文：{context or '无'}",
            f"当前日期：{result.current_date}",
            f"上下文模式：{history_mode_label}",
            f"问句类型：{result.query_type}",
            f"用户问题：{task}",
            f"关键词：{', '.join(result.keywords) if result.keywords else '未识别'}",
            f"指标：{result.metric or '未识别'}",
            f"店铺名称：{result.store_name or '未识别'}",
            f"开始日期：{result.start_date or '未识别'}",
            f"结束日期：{result.end_date or '未识别'}",
            f"对比方式：{result.comparison_type or '未识别'}",
            f"对比开始日期：{result.comparison_start_date or '未识别'}",
            f"对比结束日期：{result.comparison_end_date or '未识别'}",
            "",
            "## 对话摘要",
            conversation_bundle.summary or "无",
            "",
            "## 近期对话",
            _format_messages(conversation_bundle.recent_messages),
            "",
            "回答要求：",
            "- 优先结合上下文回答追问。",
            "- 对普通问题，直接回答用户问题本身。",
            "- 对零售问题，告知用户已识别到的查询参数，说明数据正在获取中。",
            "- 如果当前问句省略了店铺、指标或时间，但上下文足够明确，可以自然继承。",
            "- 如果上下文仍不足以明确零售参数，要明确指出缺失项。",
        ]
    )
