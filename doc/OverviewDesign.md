# 研报智能体 CLI 概要设计文档

版本：v0.1  
定位：把全量研报变成可查询、可回测、可辩论、可生成因子的本地命令行智能体。  
核心依赖：`pydantic>=2`、`openai>=1`。其他库可插拔。

---

## 1. 设计原则

1. **时间戳优先**：所有对象必须带 `published_at`，回测查询必须支持 `as_of`，禁止前视偏差。
2. **Pydantic 为契约**：LLM 输出、数据库记录、CLI 输出全部先过 Pydantic 模型。
3. **OpenAI API 为推理引擎**：抽取、分类、辩论、反事实、质量评审都通过 OpenAI API。
4. **结构化输出**：优先使用 OpenAI structured outputs + Pydantic schema，而不是自由文本解析。
5. **证据可追溯**：每个观点、预测、结论都必须带 `EvidenceRef`，指向研报、页码、原文片段。
6. **分层模型**：便宜模型做抽取/分类，强模型做辩论/反事实/质量评审。
7. **缓存与幂等**：LLM 调用按 `model + prompt + schema` 哈希缓存；重复 ingest 不重复入库。

---

## 2. 总体架构

```text
CLI: report-agent
  ├─ ingest / extract / index / config / doctor   # 辅助命令
  └─ 十个功能子命令
       backtest leaderboard consensus narrative debate
       wiki catalyst counterfactual quality factor

Service Layer
  IngestService ExtractService IndexService
  BacktestService LeaderboardService ConsensusService
  NarrativeService DebateService WikiService
  CatalystService CounterfactualService QualityService FactorService

Domain Layer
  Pydantic models: Report, View, Prediction, Event,
  Narrative, Factor, DebateTurn, QualityReport, ...

Infrastructure
  OpenAIClient | SQLite/DuckDB | FTS5 | Vector Index | Graph | Cache
```

数据流：

```text
原始研报 PDF/HTML
  -> Ingest 解析文本与元数据
  -> Extract 用 LLM + Pydantic 抽取观点/预测/事件
  -> Normalize 实体对齐：机构、分析师、公司、主题
  -> Index 全文/向量/图索引
  -> Analyze 各子命令
  -> Output JSON / Markdown / CSV / Parquet / GraphML
```

---

## 3. 目录结构建议

```text
report_agent/
  __main__.py
  cli.py
  config.py
  models/
    report.py
    prediction.py
    event.py
    narrative.py
    debate.py
    quality.py
    factor.py
    common.py
  llm/
    client.py
    prompts.py
    cache.py
  services/
    ingest.py
    extract.py
    backtest.py
    leaderboard.py
    consensus.py
    narrative.py
    debate.py
    wiki.py
    catalyst.py
    counterfactual.py
    quality.py
    factor.py
  storage/
    sqlite.py
    vector.py
    graph.py
  utils/
    time.py
    text.py
    metrics.py
  tests/
```

---

## 4. 核心 Pydantic 模型

```python
from datetime import datetime
from typing import Literal
from pydantic import BaseModel, Field

class EvidenceRef(BaseModel):
    report_id: str
    page: int | None = None
    quote: str
    published_at: datetime

class Report(BaseModel):
    id: str
    title: str
    institution: str
    analysts: list[str] = []
    published_at: datetime
    industry: list[str] = []
    tickers: list[str] = []
    rating: str | None = None
    target_price: float | None = None
    summary: str
    raw_path: str
    content_hash: str

class View(BaseModel):
    report_id: str
    subject: str
    stance: Literal["bullish", "bearish", "neutral", "mixed"]
    horizon: str | None = None
    thesis: str
    catalysts: list[str] = []
    risks: list[str] = []
    evidence: list[EvidenceRef] = []

class Prediction(BaseModel):
    report_id: str
    analyst: str
    institution: str
    ticker: str | None = None
    metric: str
    horizon: str
    value: float | str | None = None
    direction: Literal["up", "down", "flat", "unknown"]
    confidence: float = Field(ge=0, le=1)
    rationale: str
    published_at: datetime
    actual_value: float | None = None
    score: float | None = None

class Event(BaseModel):
    report_id: str
    ticker: str | None = None
    event_type: str
    event_date: datetime | None = None
    description: str
    importance: int = Field(ge=1, le=5)
    evidence: list[EvidenceRef] = []
```

其他模型：`ConsensusMetric`、`NarrativeNode`、`NarrativeEdge`、`DebateTurn`、`QAResponse`、`CatalystEvent`、`CounterfactualReport`、`QualityReport`、`FactorValue`、`BacktestResult`、`LeaderboardEntry`。

---

## 5. LLM 层设计

```python
from openai import OpenAI
from pydantic import BaseModel

class LLMClient:
    def __init__(self, api_key: str, model: str, strong_model: str | None = None):
        self.client = OpenAI(api_key=api_key)
        self.model = model
        self.strong_model = strong_model or model

    def parse(self, *, prompt: str, schema: type[BaseModel], strong: bool = False) -> BaseModel:
        model = self.strong_model if strong else self.model
        resp = self.client.beta.chat.completions.parse(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            response_format=schema,
        )
        return resp.choices[0].message.parsed
```

要点：
- 所有抽取任务定义 Pydantic schema，直接作为 `response_format`。
- 校验失败时自动修复重试，最多 2 次。
- 缓存键：`sha256(model + prompt + schema_json)`。
- 并发控制：`asyncio.Semaphore`。
- 模型分层：抽取用 `gpt-4.1-mini`，辩论/反事实/质量用 `gpt-4.1`。
- 嵌入用 `text-embedding-3-large`，用于 wiki 和 narrative。

---

## 6. 存储与索引

- **结构化存储**：SQLite 或 DuckDB。表：`reports`、`views`、`predictions`、`events`、`narratives`、`factors`、`backtest_results`、`debates`、`qa`、`quality`、`counterfactual`。
- **全文索引**：SQLite FTS5。
- **向量索引**：sqlite-vec、FAISS 或 Chroma 可选。
- **图索引**：NetworkX，导出 GraphML/JSON。
- **文件存储**：原始 PDF、解析文本、LLM 缓存、报告输出。

---

## 7. CLI 总览

```bash
report-agent --data-dir ./data --db ./data/agent.db --model gpt-4.1-mini
```

辅助命令：

```bash
report-agent ingest ./reports --recursive
report-agent extract --all
report-agent index --rebuild
report-agent config show
report-agent doctor
```

十个功能子命令：

```bash
report-agent backtest ...
report-agent leaderboard ...
report-agent consensus ...
report-agent narrative ...
report-agent debate ...
report-agent wiki ...
report-agent catalyst ...
report-agent counterfactual ...
report-agent quality ...
report-agent factor ...
```

统一输出参数：`--output json|md|csv|parquet|graphml`。

---

## 8. 十个功能子命令详设

| 子命令 | 功能 | 核心输入 | 核心输出 | LLM 用途 |
|---|---|---|---|---|
| `backtest` | 研报观点回测 | 时间、分析师、行业、horizon | 命中率、MAE、IC、超额收益 | 解释偏差模式 |
| `leaderboard` | 分析师/机构排行榜 | 指标、样本阈值 | 排行榜、置信区间 | 生成评语与案例 |
| `consensus` | 共识拥挤度与分歧预警 | ticker/行业/主题、窗口 | 共识强度、分歧度、修正速度 | 解释共识变化 |
| `narrative` | 叙事传播图谱 | 主题、时间范围 | 时间线、传播图、股价反应 | 命名叙事、总结演变 |
| `debate` | 多智能体投研辩论 | 标的、角色、轮数 | 辩论记录、投资备忘录 | 核心生成 |
| `wiki` | 个股/行业研报百科 | 自然语言问题 | 答案、引用、置信度 | RAG 生成 |
| `catalyst` | 催化剂日历与事件驱动 | ticker/行业、时间 | 日历、事件研究 | 抽取分类事件 |
| `counterfactual` | 反事实研报生成 | 历史时期、假设条件 | 反事实研报、牛熊情景 | 生成与对比 |
| `quality` | 研报质量与合规检测 | 研报/机构/分析师 | 质量评分、雷达、异常 | 评审打分 |
| `factor` | 文本因子工厂 | 因子定义、频率 | 因子面板、IC、分层回测 | 抽取文本信号 |

### 8.1 `backtest`
流程：查询 `Prediction` -> 对齐实际价格/财务数据 -> 计算方向准确率、MAE、IC -> 按机构/分析师/行业聚合 -> LLM 解释。

### 8.2 `leaderboard`
流程：读取 `backtest_results` -> 贝叶斯收缩 + 置信区间 -> 排名 -> LLM 生成典型预测案例。

### 8.3 `consensus`
流程：抽取评级、目标价、盈利预测 -> 时间序列化 -> 计算共识强度、分歧度、修正速度、拥挤度 -> 触发预警。

### 8.4 `narrative`
流程：主题嵌入聚类 -> 找最早出现研报 -> 构建传播图 -> 关联股价阶段 -> 输出 GraphML + 时间线。

### 8.5 `debate`
流程：检索相关研报 -> 创建 `bull`、`bear`、`risk`、`judge` 等 Agent -> 轮流发言并引用证据 -> 裁判总结。

### 8.6 `wiki`
流程：问题解析 -> 混合检索（FTS + 向量）-> 重排 -> 基于证据生成答案 -> 返回引用和置信度。

### 8.7 `catalyst`
流程：抽取事件/催化剂 -> 规范化日期 -> 建日历 -> 关联股价异动 -> 事件研究。

### 8.8 `counterfactual`
流程：检索当时研报 -> 注入反事实条件 -> LLM 重写观点 -> 生成牛/熊/基准情景 -> 差异对比。

### 8.9 `quality`
流程：规则检测 + LLM 评审 -> 数据支撑、逻辑链、风险提示、模板化、利益冲突、重复度 -> 雷达图数据。

### 8.10 `factor`
流程：从研报生成文本因子：情绪、分歧、修正、主题集中度 -> 构建面板 -> 计算 IC、分层回测 -> 输出 CSV/Parquet。

---

## 9. 公共流水线

```text
ingest: PDF/HTML -> text + metadata
extract: LLM + Pydantic -> Report/View/Prediction/Event
normalize: 机构、分析师、公司、主题实体对齐
index: FTS + 向量 + 图
analyze: 各子命令
report: JSON / Markdown / CSV / Parquet / GraphML
```

关键约束：
- 回测查询必须传 `as_of`，只允许 `published_at <= as_of`。
- 每个 LLM 输出必须带 `EvidenceRef`。
- 所有服务返回 Pydantic 模型，CLI 负责序列化。

---

## 10. 配置

`.env` 示例：

```bash
OPENAI_API_KEY=...
OPENAI_BASE_URL=...
REPORT_AGENT_MODEL=gpt-4.1-mini
REPORT_AGENT_STRONG_MODEL=gpt-4.1
REPORT_AGENT_EMBEDDING_MODEL=text-embedding-3-large
REPORT_AGENT_DATA_DIR=./data
REPORT_AGENT_DB_URL=sqlite:///./data/agent.db
REPORT_AGENT_MAX_CONCURRENCY=8
```

可用 `pydantic-settings` 或 `pydantic.BaseModel + os.environ` 实现配置类。

---

## 11. 错误处理、测试与合规

- **错误处理**：LLM 调用重试、Pydantic 校验失败修复、数据库事务、幂等写入。
- **日志**：记录 prompt hash、token、延迟、模型、缓存命中。
- **测试**：Pydantic 模型单测、LLM mock、小样本 fixture、防前视回测测试。
- **合规**：研报版权注意，不输出投资建议，保留审计日志。

---

## 12. MVP 实施顺序

1. `models` + `ingest` + `extract`
2. `wiki` + `backtest`
3. `leaderboard` + `consensus` + `catalyst`
4. `narrative` + `factor`
5. `debate` + `counterfactual` + `quality`

---

## 13. 示例使用

```bash
report-agent ingest ./reports --recursive
report-agent extract --all
report-agent backtest --from 2020-01-01 --to 2025-01-01 --horizon 12m --by analyst --output md
report-agent leaderboard --metric direction_accuracy --min-samples 20 --top 50
report-agent consensus --ticker 300750.SZ --window 90d --alert
report-agent narrative --theme "AI算力" --from 2023-01-01 --output graphml
report-agent debate --ticker 300750.SZ --rounds 3 --roles bull,bear,risk,judge
report-agent wiki "2020年谁最先看多新能源车？"
report-agent catalyst --ticker 300750.SZ --from 2024-01-01 --to 2025-01-01
report-agent counterfactual --period 2022 --condition "美联储不加息" --ticker 300750.SZ
report-agent quality --institution "某券商" --from 2023-01-01
report-agent factor build --name report_sentiment --freq M --output parquet
```

这个设计的核心是：**Pydantic 管数据契约，OpenAI API 管非结构化推理，SQLite/DuckDB + 向量 + 图管记忆，CLI 管十个功能入口**。先做通 `ingest -> extract -> wiki/backtest`，其余功能都能快速长出来。