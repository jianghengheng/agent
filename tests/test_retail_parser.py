from datetime import date

from ai_multi_agent.agents.retail_parser import parse_retail_query


def test_parse_extracts_store_name_and_metric() -> None:
    result = parse_retail_query("今天星河店销售额怎么样", today=date(2026, 3, 31))

    assert result.query_type == "retail_metric_query"
    assert result.store_name == "星河店"
    assert result.metric == "销售额"
    assert result.store_flag is True
    assert result.current_date == "2026-03-31"


def test_parse_no_specific_metric_returns_none() -> None:
    result = parse_retail_query("这个月情况怎么样", today=date(2026, 3, 31))

    assert result.query_type == "retail_metric_query"
    assert result.metric is None


def test_follow_up_inherits_store_and_metric_from_history() -> None:
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


def test_family_keyword_sets_store_flag_false() -> None:
    result = parse_retail_query("所有家族3月份的情况", today=date(2026, 4, 4))

    assert result.query_type == "retail_metric_query"
    assert result.store_flag is False


def test_normal_chat_excluded_by_non_retail_hints() -> None:
    result = parse_retail_query("今天天气怎么样", today=date(2026, 3, 31))

    assert result.query_type == "normal_chat"


def test_dates_are_none_before_llm_resolution() -> None:
    result = parse_retail_query("1月份情况怎么样", today=date(2026, 4, 4))

    assert result.query_type == "retail_metric_query"
    assert result.start_date is None
    assert result.end_date is None
    assert result.comparison_type is None
