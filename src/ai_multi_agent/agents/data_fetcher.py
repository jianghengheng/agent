from __future__ import annotations

import json
import logging
from dataclasses import dataclass

import httpx

from ai_multi_agent.agents.base import BaseAgent
from ai_multi_agent.agents.retail_parser import RetailParserExecution
from ai_multi_agent.graph.state import WorkflowState

logger = logging.getLogger(__name__)

DEFAULT_API_BASE_URL = "https://staging.retail-digit-api.e-zhong.com"
DEFAULT_API_PATH = "/web/dashboard/stat"
DEFAULT_COLUMN_ID = 105
DEFAULT_TOKEN = "904117b81e4b7b79fc10bd40ac9c7b61"
HTTP_TIMEOUT_SECONDS = 30


@dataclass(slots=True)
class DataFetcherAgent(BaseAgent):
    api_base_url: str = DEFAULT_API_BASE_URL
    api_path: str = DEFAULT_API_PATH
    token: str = DEFAULT_TOKEN
    column_id: int = DEFAULT_COLUMN_ID

    async def run(self, state: WorkflowState, execution: RetailParserExecution) -> dict[str, object]:
        result = execution.result

        if result.query_type != "retail_metric_query":
            return {}

        if not result.start_date or not result.comparison_start_date:
            return {
                "trace": [f"{self.name}: skipped - missing date params"],
            }

        store_flag = result.store_flag

        request_info = self._build_request_info(
            start_date=result.start_date,
            end_date=result.end_date,
            comparison_start_date=result.comparison_start_date,
            comparison_end_date=result.comparison_end_date,
            store_flag=store_flag,
        )

        api_data = await self._fetch_data(
            start_date=result.start_date,
            end_date=result.end_date,
            comparison_start_date=result.comparison_start_date,
            comparison_end_date=result.comparison_end_date,
            store_flag=store_flag,
        )

        if api_data is None:
            return {
                "api_request": request_info,
                "api_response": None,
                "trace": [f"{self.name}: api call failed"],
            }

        data_summary = _summarize_api_data(api_data, metric=result.metric)

        return {
            "research": data_summary,
            "api_request": request_info,
            "api_response": api_data,
            "trace": [f"{self.name}: data fetched"],
        }

    def _build_request_info(
        self,
        *,
        start_date: str,
        end_date: str | None,
        comparison_start_date: str,
        comparison_end_date: str | None,
        store_flag: bool,
    ) -> dict[str, object]:
        params = self._build_params(
            start_date=start_date,
            end_date=end_date,
            comparison_start_date=comparison_start_date,
            comparison_end_date=comparison_end_date,
            store_flag=store_flag,
        )
        return {
            "url": f"{self.api_base_url}{self.api_path}",
            "method": "GET",
            "headers": {"token": self.token, "Content-Type": "application/json"},
            "params": params,
        }

    @staticmethod
    def _build_params(
        *,
        start_date: str,
        end_date: str | None,
        comparison_start_date: str,
        comparison_end_date: str | None,
        store_flag: bool,
        column_id: int | None = None,
    ) -> dict[str, str | int | bool]:
        params: dict[str, str | int | bool] = {
            "columnId": column_id if column_id is not None else DEFAULT_COLUMN_ID,
            "storeFlag": store_flag,
            "startDate": start_date,
            "comparisonStartDate": comparison_start_date,
        }
        if end_date:
            params["endDate"] = end_date
        if comparison_end_date:
            params["comparisonEndDate"] = comparison_end_date
        return params

    async def _fetch_data(
        self,
        *,
        start_date: str,
        end_date: str | None,
        comparison_start_date: str,
        comparison_end_date: str | None,
        store_flag: bool,
    ) -> list[dict] | None:
        params = self._build_params(
            start_date=start_date,
            end_date=end_date,
            comparison_start_date=comparison_start_date,
            comparison_end_date=comparison_end_date,
            store_flag=store_flag,
            column_id=self.column_id,
        )

        url = f"{self.api_base_url}{self.api_path}"
        headers = {
            "token": self.token,
            "Content-Type": "application/json",
        }

        print("\n" + "=" * 60)
        print("📡 API 请求")
        print("=" * 60)
        print(f"  URL:     {url}")
        print(f"  Method:  GET")
        print(f"  Headers: {json.dumps(headers, ensure_ascii=False)}")
        print(f"  Params:  {json.dumps(params, ensure_ascii=False)}")
        print("=" * 60)

        try:
            async with httpx.AsyncClient(timeout=HTTP_TIMEOUT_SECONDS) as client:
                response = await client.get(url, params=params, headers=headers)
                response.raise_for_status()
                body = response.json()

                print("\n" + "=" * 60)
                print("📦 API 响应")
                print("=" * 60)
                print(f"  Status:  {response.status_code}")
                print(f"  Code:    {body.get('code')}")
                print(f"  Msg:     {body.get('msg')}")
                print(f"  TraceId: {body.get('traceId')}")

                data = body.get("data", [])
                print(f"  数据条数: {len(data)}")
                print("-" * 60)

                for i, item in enumerate(data):
                    print(f"\n  [{i + 1}] {item.get('columnName', '未知')} ({item.get('columnType', '')})")
                    print(f"      销售额: {item.get('salesAmount', '-')}"
                          f"  增长率: {_format_rate(item.get('salesAmountGrowthRate'))}")
                    print(f"      毛利:   {item.get('netProfit', '-')}"
                          f"  增长率: {_format_rate(item.get('netProfitGrowthRate'))}")
                    print(f"      会员销额: {item.get('salesAmountMember', '-')}"
                          f"  活跃会员: {item.get('activeMemberCount', '-')}"
                          f"  新增会员: {item.get('newMemberCount', '-')}")
                    print(f"      人效: {item.get('salesAmountPerStaff', '-')}"
                          f"  过店人数: {item.get('passByCount', '-')}")

                print("\n" + "=" * 60)

                if body.get("code") != 0:
                    logger.warning(
                        "API returned non-zero code: %s, msg: %s",
                        body.get("code"),
                        body.get("msg"),
                    )
                    return None

                return data
        except Exception:
            print("\n❌ API 调用失败")
            logger.exception("Failed to fetch data from %s", url)
            return None


def _summarize_api_data(api_data: list[dict], *, metric: str | None) -> str:
    if not api_data:
        return "无数据"

    header = (
        "名称|类型|销售额|销售增长|毛利|毛利增长|会员销额|会员销额增长"
        "|活跃会员|新增会员|过店人数|进店率|成交率|人效"
        "|蛋糕销额|现烤销额|线上销额|门店费用|门店贡献"
    )
    lines: list[str] = [f"共 {len(api_data)} 条记录", "", header]

    for item in api_data:
        row = "|".join([
            str(item.get("columnName", "")),
            str(item.get("columnType", "")),
            str(item.get("salesAmount", 0)),
            _format_rate(item.get("salesAmountGrowthRate")),
            str(item.get("netProfit", 0)),
            _format_rate(item.get("netProfitGrowthRate")),
            str(item.get("salesAmountMember", 0)),
            _format_rate(item.get("salesAmountMemberGrowthRate")),
            str(item.get("activeMemberCount", 0)),
            str(item.get("newMemberCount", 0)),
            str(item.get("passByCount", 0)),
            _format_rate(item.get("enterRate")),
            _format_rate(item.get("buyRate")),
            str(item.get("salesAmountPerStaff", 0)),
            str(item.get("salesAmountCake", 0)),
            str(item.get("salesAmountBaked", 0)),
            str(item.get("salesAmountOnline", 0)),
            str(item.get("storeCost", "")),
            str(item.get("netIncome", "")),
        ])
        lines.append(row)

    return "\n".join(lines)


def _format_rate(value: object) -> str:
    if value is None:
        return "暂无"
    if isinstance(value, (int, float)):
        return f"{value}%"
    return str(value)
