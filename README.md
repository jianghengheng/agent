# AI Multi-Agent Starter

基于 `Python + uv + FastAPI + LangGraph` 的多智能体 AI 应用工程骨架，目标是直接作为业务项目起点，而不是只展示一个 Demo。

## 技术栈

- `uv` 管理依赖与运行环境
- `FastAPI` 提供 HTTP 服务
- `LangGraph` 负责编排多智能体工作流
- `langchain-openai` 连接 OpenAI 兼容模型
- `pytest + ruff + mypy + GitHub Actions` 提供基础工程化能力

## 项目结构

```text
.
├── .github/workflows/ci.yml
├── src/ai_multi_agent
│   ├── api
│   ├── agents
│   ├── core
│   ├── graph
│   ├── llm
│   ├── schemas
│   ├── services
│   └── main.py
├── tests
├── .env.example
├── Makefile
└── pyproject.toml
```

## 多智能体流程

当前内置了一个可运行的标准链路：

1. `PlannerAgent` 拆解任务，生成执行计划
2. `ResearchAgent` 补充信息与方案细节
3. `CriticAgent` 审核结果，决定是否返工
4. `SynthesizerAgent` 产出最终答案

`CriticAgent` 可以把工作流重新路由回 `ResearchAgent`，形成“智能体间互相评审和迭代”的交互模式。

## 快速开始

```bash
cp .env.example .env
uv sync --dev
uv run uvicorn ai_multi_agent.main:app --factory --reload
```

如果没有配置 `OPENAI_API_KEY`，系统会自动回退到内置 `mock` 模型，方便本地联调和测试。

## API 示例

### 健康检查

```bash
curl http://127.0.0.1:8000/api/v1/health
```

### 触发多智能体工作流

```bash
curl -X POST http://127.0.0.1:8000/api/v1/workflows/multi-agent \
  -H "Content-Type: application/json" \
  -d '{
    "task": "设计一个企业内部知识库问答系统的 MVP 方案",
    "context": "需要兼顾权限、检索质量和交付速度",
    "max_revisions": 1
  }'
```

## 工程化建议

- 在 `services` 层接入真实业务工具，例如数据库、搜索、RAG、工单系统
- 在 `agents` 层继续拆分角色，例如 Router、Executor、Reviewer、Supervisor
- 为 `llm/providers.py` 增加 Anthropic、Azure OpenAI 或私有模型适配器
- 为关键流程接入 tracing、metrics、审计日志和鉴权

