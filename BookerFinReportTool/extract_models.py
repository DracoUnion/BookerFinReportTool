"""extract 子命令的 Pydantic 模型。

LLM 直接输出的中间模型（`*LLMOut`），再由 orchestrator 补齐
`report_id` / `published_at` 等字段后落成 `ExtractedBundle`。
"""
from typing import List, Optional
from pydantic import BaseModel, Field
from .models import EvidenceRef, View, Prediction, Event, Report, ExtractedBundle


class ViewLLMOut(BaseModel):
    """LLM 直接输出的单条观点（缺省 report_id）。"""
    subject: str = Field(..., description="观点对象")
    stance: str = Field(..., description="bullish/bearish/neutral/mixed")
    horizon: Optional[str] = Field(None, description="时间维度")
    thesis: str = Field(..., description="核心论点")
    catalysts: List[str] = Field([], description="催化剂")
    risks: List[str] = Field([], description="风险")
    evidences: List[EvidenceRef] = Field([], description="证据引用")


class PredictionLLMOut(BaseModel):
    analyst: str = Field('', description="分析师")
    institution: str = Field('', description="机构")
    ticker: Optional[str] = Field(None, description="股票代码")
    metric: str = Field(..., description="预测指标")
    horizon: str = Field('', description="时间维度")
    value: str = Field('', description="预测值")
    direction: str = Field('unknown', description="up/down/flat/unknown")
    confidence: float = Field(0.5, description="0~1")
    rationale: str = Field('', description="依据")


class EventLLMOut(BaseModel):
    ticker: Optional[str] = Field(None, description="股票代码")
    event_type: str = Field(..., description="事件类型")
    event_date: Optional[str] = Field(None, description="YYYY-MM-DD")
    description: str = Field(..., description="事件描述")
    importance: int = Field(3, description="1~5")
    evidences: List[EvidenceRef] = Field([], description="证据")


class ExtractBundleLLMOut(BaseModel):
    """LLM 一次调用输出：views + predictions + events。"""
    views: List[ViewLLMOut] = Field([], description="观点")
    predictions: List[PredictionLLMOut] = Field([], description="预测")
    events: List[EventLLMOut] = Field([], description="事件")
