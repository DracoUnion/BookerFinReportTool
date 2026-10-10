"""核心 Pydantic 模型。

所有 LLM 输出、数据记录、CLI 输出都先过这些模型（设计文档 §4）。
每个字段带中文 `description`，便于 LLM 理解和后续校验。
"""
from datetime import datetime
from typing import *
from pydantic import BaseModel, Field
import json


def _now() -> str:
    return datetime.now().strftime('%Y-%m-%d %H:%M')


class EvidenceRef(BaseModel):
    """证据引用：指向某份研报的原文片段。"""
    report_id: str = Field(..., description="来源研报 ID")
    page: Optional[int] = Field(None, description="页码（PDF）或章节序号（MD）")
    quote: str = Field(..., description="原文片段")
    published_at: str = Field(..., description="研报发布时间，YYYY-MM-DD")


class Report(BaseModel):
    """研报元数据。"""
    id: str = Field(..., description="研报唯一 ID")
    title: str = Field('', description="标题")
    institution: str = Field('', description="研究机构")
    analysts: List[str] = Field([], description="分析师列表")
    published_at: str = Field(..., description="发布时间，YYYY-MM-DD")
    industry: List[str] = Field([], description="行业/主题标签")
    tickers: List[str] = Field([], description="涉及股票代码")
    rating: Optional[str] = Field(None, description="评级，如 买入/增持/中性")
    target_price: Optional[float] = Field(None, description="目标价")
    summary: str = Field('', description="摘要")
    raw_path: str = Field('', description="原始 PDF/MD 文件相对路径")
    content_hash: str = Field('', description="内容哈希，用于幂等")


class View(BaseModel):
    """研报观点。"""
    report_id: str = Field(..., description="来源研报 ID")
    subject: str = Field(..., description="观点对象（行业/公司/主题）")
    stance: str = Field(..., description="立场：bullish/bearish/neutral/mixed")
    horizon: Optional[str] = Field(None, description="时间维度，如 6个月")
    thesis: str = Field(..., description="核心论点")
    catalysts: List[str] = Field([], description="催化剂")
    risks: List[str] = Field([], description="风险点")
    evidence: List[EvidenceRef] = Field([], description="证据引用")


class Prediction(BaseModel):
    """研报中的可回测预测。"""
    report_id: str = Field(..., description="来源研报 ID")
    analyst: str = Field('', description="分析师")
    institution: str = Field('', description="机构")
    ticker: Optional[str] = Field(None, description="股票代码")
    metric: str = Field(..., description="预测指标，如 净利润/营收/目标价")
    horizon: str = Field('', description="预测时间维度")
    value: str = Field('', description="预测值（数字或区间）")
    direction: str = Field('unknown', description="方向：up/down/flat/unknown")
    confidence: float = Field(0.5, description="置信度 0~1")
    rationale: str = Field('', description="预测依据")
    published_at: str = Field(..., description="发布时间")
    actual_value: Optional[str] = Field(None, description="实际值（回测后填入）")
    score: Optional[float] = Field(None, description="回测得分")


class Event(BaseModel):
    """事件/催化剂。"""
    report_id: str = Field(..., description="来源研报 ID")
    ticker: Optional[str] = Field(None, description="股票代码")
    event_type: str = Field(..., description="事件类型，如 财报/政策/新品")
    event_date: Optional[str] = Field(None, description="事件日期，YYYY-MM-DD")
    description: str = Field(..., description="事件描述")
    importance: int = Field(3, description="重要性 1~5")
    evidence: List[EvidenceRef] = Field([], description="证据引用")


class ExtractedBundle(BaseModel):
    """从单份研报中抽取出的全部结构化对象。"""
    report: Report
    views: List[View] = Field([], description="观点列表")
    predictions: List[Prediction] = Field([], description="预测列表")
    events: List[Event] = Field([], description="事件列表")


# ── 索引 / 检索 ────────────────────────────────────────────

class WqiAnswer(BaseModel):
    """wiki 问答结果。"""
    question: str = Field(..., description="问题")
    answer: str = Field(..., description="答案")
    citations: List[EvidenceRef] = Field([], description="引用")
    confidence: float = Field(0.5, description="置信度 0~1")


class DebateTurn(BaseModel):
    """辩论的一轮发言。"""
    role: str = Field(..., description="角色：bull/bear/risk/judge")
    text: str = Field(..., description="发言内容")
    citations: List[EvidenceRef] = Field([], description="引用")


class DebateResult(BaseModel):
    """多智能体辩论结果。"""
    ticker: str = Field('', description="标的")
    rounds: int = Field(0, description="辩论轮数")
    turns: List[DebateTurn] = Field([], description="各轮发言")
    memo: str = Field('', description="裁判总结的投资备忘录")


class ConsensusMetric(BaseModel):
    """共识度指标。"""
    subject: str = Field(..., description="对象（行业/公司/主题）")
    window_days: int = Field(90, description="统计窗口（天）")
    count: int = Field(0, description="样本数")
    avg_stance: float = Field(0.0, description="平均立场分（-1 熊 ~ +1 牛）")
    divergence: float = Field(0.0, description="分歧度 0~1")
    revision_speed: float = Field(0.0, description="共识修正速度")
    crowdedness: float = Field(0.0, description="拥挤度 0~1")
    alert: bool = Field(False, description="是否触发分歧预警")


class NarrativeNode(BaseModel):
    """叙事图谱节点。"""
    theme: str = Field(..., description="主题名")
    first_seen: Optional[str] = Field(None, description="最早出现日期")
    report_ids: List[str] = Field([], description="涉及研报 ID")


class NarrativeEdge(BaseModel):
    """叙事传播边：A 主题催生了 B 主题。"""
    src: str = Field(..., description="源主题")
    dst: str = Field(..., description="目标主题")
    weight: float = Field(1.0, description="关联强度")


class NarrativeResult(BaseModel):
    """叙事传播图谱结果。"""
    theme: str = Field(..., description="主叙事主题")
    nodes: List[NarrativeNode] = Field([], description="节点")
    edges: List[NarrativeEdge] = Field([], description="边")
    timeline: List[str] = Field([], description="时间线（按日聚合）")
    summary: str = Field('', description="演变总结")


class QualityReport(BaseModel):
    """研报质量评分。"""
    report_id: str = Field('', description="研报 ID")
    score: float = Field(0.0, description="总分 0~100")
    dimensions: Dict[str, float] = Field(
        {}, description="各维度分数：数据支撑/逻辑链/风险提示/模板化/利益冲突/重复度")
    issues: List[str] = Field([], description="发现的异常/问题")


class FactorValue(BaseModel):
    """文本因子面板中的单条记录。"""
    ticker: str = Field(..., description="股票代码")
    date: str = Field(..., description="日期")
    factor: str = Field(..., description="因子名")
    value: float = Field(0.0, description="因子值")


class BacktestResult(BaseModel):
    """回测结果。"""
    period: str = Field('', description="回测区间")
    horizon: str = Field('', description="预测时间维度")
    by: str = Field('', description="聚合维度：analyst/institution/industry")
    direction_accuracy: float = Field(0.0, description="方向准确率")
    mae: float = Field(0.0, description="平均绝对误差")
    ic: float = Field(0.0, description="信息系数")
    excess_return: float = Field(0.0, description="超额收益")
    sample: int = Field(0, description="样本数")
    note: str = Field('', description="LLM 对偏差模式的解释")


class LeaderboardEntry(BaseModel):
    """排行榜条目。"""
    name: str = Field(..., description="分析师/机构名")
    metric: str = Field('', description="排序指标")
    value: float = Field(0.0, description="指标值")
    ci_low: float = Field(0.0, description="置信区间下界")
    ci_high: float = Field(0.0, description="置信区间上界")
    samples: int = Field(0, description="样本数")
    comment: str = Field('', description="LLM 评语")


def dump_model(obj: Any) -> str:
    """把对象（含 Pydantic 模型/列表）序列化为 JSON 字符串。"""
    if isinstance(obj, BaseModel):
        obj = obj.model_dump()
    elif isinstance(obj, list):
        obj = [it.model_dump() if isinstance(it, BaseModel) else it for it in obj]
    return json.dumps(obj, ensure_ascii=False, indent=2)
