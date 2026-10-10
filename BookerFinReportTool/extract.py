"""子命令 extract：LLM + Pydantic 抽取观点/预测/事件并入库。"""
import json
import logging
import json_repair
from os import path
from typing import Optional
from pydantic import parse_obj_as
from .util import (
    read_yaml_model, write_yaml_model, read_text,
    render_prompt, ext_code_block,
)
from .openai import ask_chatgpt_retry
from .extract_pmt import EXTRACT_BUNDLE_PMT
from .extract_models import (
    ExtractBundleLLMOut,
)
from .models import ExtractedBundle, View, Prediction, Event
from .storage import FileStore

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s][%(name)s][%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)


def _report_text(store: FileStore, rid: str) -> str:
    """优先读缓存文本，缺失时跳过。"""
    fname = path.join(store.data_dir, 'texts', f'{rid}.txt')
    if path.isfile(fname):
        return read_text(fname)
    return ''


def extract_one(
    args, store: FileStore, rid: str,
) -> Optional[ExtractedBundle]:
    """对单份研报做抽取，结果幂等写回 `extracted/{rid}.yaml`。"""
    cached = store.load_extracted(rid)
    if cached:
        return cached
    rep = store.load_report(rid)
    if rep is None:
        logger.warning(f'{rid} 未在 reports 目录中，请先 ingest')
        return None
    text = _report_text(store, rid)
    if not text.strip():
        logger.warning(f'{rid} 无正文文本，跳过')
        return None

    ques = render_prompt(EXTRACT_BUNDLE_PMT, report_text=text[:60_000])
    parse_output = lambda s: ExtractBundleLLMOut.model_validate(
        json_repair.loads(ext_code_block(s))
    )
    out: ExtractBundleLLMOut = ask_chatgpt_retry(
        ques, args.model, args,
        parse_output=parse_output,
    )

    # 补齐 LLM 缺省的上下文字段
    views = [
        View(
            report_id=rid,
            published_at=rep.published_at,
            **{k: v for k, v in vv.model_dump().items()},
        ) for vv in out.views
    ]
    preds = [
        Prediction(
            report_id=rid,
            published_at=rep.published_at,
            **{k: v for k, v in pp.model_dump().items()},
        ) for pp in out.predictions
    ]
    evts = [
        Event(
            report_id=rid,
            **{k: v for k, v in ee.model_dump().items()},
        ) for ee in out.events
    ]
    bundle = ExtractedBundle(
        report=rep, views=views, predictions=preds, events=evts,
    )
    store.save_extracted(bundle)
    logger.info(
        f'extract {rid}: views={len(views)} preds={len(preds)} evts={len(evts)}'
    )
    return bundle


def extract(args):
    """抽取 `args.report_id`，或 `--all` 抽取全部已入库研报。"""
    store = FileStore(args.data_dir)
    if args.all:
        for rid in store.list_report_ids():
            extract_one(args, store, rid)
    else:
        for rid in args.report_ids:
            extract_one(args, store, rid)
    logger.info('[*] 完成')


def reg_subparser(subparsers):
    p = subparsers.add_parser('extract', help='LLM 抽取观点/预测/事件')
    p.add_argument('report_ids', nargs='*', help='研报 ID（可多个）')
    p.add_argument('-a', '--all', action='store_true', help='抽取全部已入库研报')
    p.add_argument('-d', '--data-dir', default='./data', help='数据存储目录')
    p.set_defaults(func=extract)
