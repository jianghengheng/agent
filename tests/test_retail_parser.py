from datetime import date

from ai_multi_agent.agents.retail_parser import parse_retail_query


def test_parse_today_defaults_to_year_over_year() -> None:
    result = parse_retail_query("今天星河店销售额怎么样", today=date(2026, 3, 31))

    assert result.query_type == "retail_metric_query"
    assert result.store_name == "星河店"
    assert result.start_date == "2026-03-31"
    assert result.end_date == "2026-03-31"
    assert result.comparison_type == "同比"
    assert result.comparison_start_date == "2025-03-31"
    assert result.comparison_end_date == "2025-03-31"


def test_parse_this_week_and_last_week_range_in_plain_language() -> None:
    this_week = parse_retail_query("本周星河店销售额", today=date(2026, 3, 31))
    assert this_week.start_date == "2026-03-30"
    assert this_week.end_date == "2026-04-05"
    assert this_week.comparison_type == "同比"
    assert this_week.comparison_start_date == "2025-03-30"
    assert this_week.comparison_end_date == "2025-04-05"

    last_week = parse_retail_query("上周星河店销售额", today=date(2026, 3, 31))
    assert last_week.start_date == "2026-03-23"
    assert last_week.end_date == "2026-03-29"
    assert last_week.comparison_type == "同比"
    assert last_week.comparison_start_date == "2025-03-23"
    assert last_week.comparison_end_date == "2025-03-29"


def test_follow_up_question_inherits_context_and_defaults_to_year_over_year() -> None:
    result = parse_retail_query(
        "那上周呢",
        today=date(2026, 3, 31),
        history_messages=[
            {
                "role": "user",
                "content": "星河店这周的销售额怎么样",
            },
            {
                "role": "assistant",
                "content": "我理解你在问星河店本周销售额。",
            },
        ],
    )

    assert result.query_type == "retail_metric_query"
    assert result.store_name == "星河店"
    assert result.metric == "销售额"
    assert result.start_date == "2026-03-23"
    assert result.end_date == "2026-03-29"
    assert result.comparison_type == "同比"
    assert result.comparison_start_date == "2025-03-23"
    assert result.comparison_end_date == "2025-03-29"


def test_explicit_ring_ratio_overrides_default_year_over_year() -> None:
    result = parse_retail_query("本周星河店销售额环比怎么样", today=date(2026, 3, 31))

    assert result.query_type == "retail_metric_query"
    assert result.start_date == "2026-03-30"
    assert result.end_date == "2026-04-05"
    assert result.comparison_type == "环比"
    assert result.comparison_start_date == "2026-03-23"
    assert result.comparison_end_date == "2026-03-29"
