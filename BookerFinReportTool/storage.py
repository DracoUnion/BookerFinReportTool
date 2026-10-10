"""纯文件存储层：YAML/JSON 读写研报、观点、预测、事件。

所有数据默认放在 `data_dir` 下（默认 `./data`）。
列表接口返回 `List`，通过 `parse_obj_as` 做类型转换；
单份研报存于 `reports/{id}.yaml`，抽取结果存于 `extracted/{id}.yaml`。
"""
import os
import hashlib
import json
import logging
from typing import List, Optional, Dict, Any
from pydantic import parse_obj_as
from os import path
from .util import read_yaml_model, write_yaml_model, read_text, write_text
from .models import (
    Report, View, Prediction, Event, ExtractedBundle,
)

logger = logging.getLogger(__name__)


class FileStore:
    """纯文件系统实现的数据仓库。"""

    def __init__(self, data_dir: str = './data'):
        self.data_dir = data_dir
        self.reports_dir = path.join(data_dir, 'reports')
        self.extracted_dir = path.join(data_dir, 'extracted')
        self.index_dir = path.join(data_dir, 'index')
        for d in (self.data_dir, self.reports_dir, self.extracted_dir, self.index_dir):
            os.makedirs(d, exist_ok=True)

    # ── 通用读写 ─────────────────────────────────────────

    def report_fname(self, report_id: str) -> str:
        return path.join(self.reports_dir, f'{report_id}.yaml')

    def extracted_fname(self, report_id: str) -> str:
        return path.join(self.extracted_dir, f'{report_id}.yaml')

    def save_report(self, rep: Report) -> None:
        write_yaml_model(self.report_fname(rep.id), rep)

    def load_report(self, report_id: str) -> Optional[Report]:
        return read_yaml_model(self.report_fname(report_id), Report)

    def save_extracted(self, bundle: ExtractedBundle) -> None:
        write_yaml_model(self.extracted_fname(bundle.report.id), bundle)

    def load_extracted(self, report_id: str) -> Optional[ExtractedBundle]:
        return read_yaml_model(self.extracted_fname(report_id), ExtractedBundle)

    def list_report_ids(self) -> List[str]:
        """返回已入库的研报 ID 列表。"""
        return sorted(
            f[:-5] for f in os.listdir(self.reports_dir)
            if f.endswith('.yaml')
        )

    def all_reports(self) -> List[Report]:
        return [
            rep for rid in self.list_report_ids()
            if (rep := self.load_report(rid))
        ]

    def all_extracted(self) -> List[ExtractedBundle]:
        return [
            b for rid in self.list_report_ids()
            if (b := self.load_extracted(rid))
        ]

    # ── 关键词检索（简易 FTS 替代）────────────────────────

    def _report_text(self, rid: str) -> str:
        """收集研报的可搜索文本：report + views/predictions/events。"""
        parts = []
        rep = self.load_report(rid)
        if rep:
            parts += [rep.title, rep.institution, rep.summary, rep.industry,
                      ' '.join(rep.tickers), ' '.join(rep.analysts)]
        b = self.load_extracted(rid)
        if b:
            for v in b.views:
                parts += [v.subject, v.thesis, ' '.join(v.catalysts), ' '.join(v.risks)]
            for p in b.predictions:
                parts += [p.metric, p.rationale, p.ticker or '']
            for e in b.events:
                parts += [e.event_type, e.description]
        return ' '.join(str(x) for x in parts if x)

    def keyword_search(self, keywords: List[str]) -> List[str]:
        """返回命中任意关键词的研报 ID。"""
        res = []
        for rid in self.list_report_ids():
            text = self._report_text(rid)
            if any(k.lower() in text.lower() for k in keywords if k):
                res.append(rid)
        return res

    # ── 时间过滤 ─────────────────────────────────────────

    @staticmethod
    def filter_by_time(
        reps: List[Report],
        as_of: Optional[str] = None,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
    ) -> List[Report]:
        """按 `published_at` 过滤，支持防前视（`as_of`）。"""
        def ok(d: str) -> bool:
            if as_of and d > as_of:
                return False
            if from_date and d < from_date:
                return False
            if to_date and d > to_date:
                return False
            return True
        return [r for r in reps if ok(r.published_at)]

    # ── 幂等：hash 校验 ──────────────────────────────────

    @staticmethod
    def content_hash(text: str) -> str:
        return hashlib.sha256(text.encode('utf8')).hexdigest()
