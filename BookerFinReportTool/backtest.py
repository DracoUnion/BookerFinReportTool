"""子命令 backtest：研报观点回测。

输入：`--from` / `--to` 时间范围 + `--horizon` 预测维度 + `--by` 聚合维度。
输出：`BacktestResult` + 命中/偏差的 LLM 解释。
"""
import json
import logging
import json_repair
from os import path
from typing import List, Optional
from .util import render_prompt, ext_code_block, json_dump_model, write_yaml_model
from .openai import OpenAIClient
from .models import (
    Report, Prediction, BacktestResult, ExtractedBundle,
)
from .storage import FileStore

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s][%(name)s][%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)

BACKTEST_NOTE_PMT = """\
你是一位量化回测分析师。下面是在指定区间内、按 {by} 维度聚合的回测统计。
请解释可能出现的偏差模式（过拟合、幸存者偏差、前视偏差、行业周期错配等），
用 3~5 句话以 JSON 输出，包在三个反引号中：

```
{{"note": "..."}}
```

统计：
```
{stats}
```
"""


def backtest(args):
    store = FileStore(args.data_dir)
    llm = OpenAIClient.from_args(args)
    as_of = args.to or args.as_of
    preds: List[Prediction] = []
    for rid in store.list_report_ids():
        b = store.load_extracted(rid)
        if not b:
            continue
        rep = store.load_report(rid)
        if rep is None:
            continue
        if as_of and rep.published_at > as_of:
            continue
        if args.from_date and rep.published_at < args.from_date:
            continue
        if args.horizon and args.horizon not in [p.horizon for p in b.predictions]:
            continue
        preds += [p for p in b.predictions]

    if not preds:
        logger.warning('未找到匹配的回测样本，请检查时间范围/horizon/数据')
        return

    # 简单命中率：方向=up/down 且 value 非空视为可回测
    known = [p for p in preds if p.direction in ('up', 'down') and p.value]
    hit = sum(1 for p in known if p.actual_value and str(p.direction) in p.actual_value)
    direction_acc = (hit / len(known)) if known else 0.0

    # MAE：把 value/actual_value 转 float 比较
    def _to_f(x):
        try:
            return float(str(x).replace('%', '').replace(',', '').split(' ')[0])
        except Exception:
            return None
    diffs = []
    for p in known:
        a, b2 = _to_f(p.value), _to_f(p.actual_value or '')
        if a is not None and b2 is not None:
            diffs.append(abs(a - b2))
    mae = sum(diffs) / len(diffs) if diffs else 0.0

    result = BacktestResult(
        period=f'{args.from_date or "…"} → {as_of or "…"}',
        horizon=args.horizon,
        by=args.by,
        direction_accuracy=round(direction_acc, 4),
        mae=round(mae, 4),
        sample=len(preds),
        note='',
    )

    # LLM 解释偏差模式
    ques = render_prompt(
        BACKTEST_NOTE_PMT,
        by=args.by,
        stats=json_dump_model(result.model_dump()),
    )
    try:
        ans = json_repair.loads(ext_code_block(llm.ask_chatgpt_retry(
            ques, args.model, args,
            parse_output=lambda s: ext_code_block(s),
        )))
        result.note = ans.get('note', '')
    except Exception as ex:
        logger.warning(f'LLM 解释失败：{ex}')

    write_yaml_model(
        path.join(store.data_dir, 'backtest', f'result.yaml'),
        result,
    )
    print(json_dump_model(result))
    logger.info('[*] 完成')


def reg_subparser(subparsers):
    p = subparsers.add_parser('backtest', help='研报观点回测')
    p.add_argument('--from', dest='from_date', default='', help='起始日期')
    p.add_argument('--to', default='', help='截止日期')
    p.add_argument('--as-of', dest='as_of', default='', help='防前视时间戳')
    p.add_argument('--horizon', default='', help='预测时间维度过滤')
    p.add_argument('--by', default='analyst',
                   choices=['analyst', 'institution', 'industry'],
                   help='聚合维度')
    p.add_argument('-d', '--data-dir', default='./data', help='数据存储目录')
    p.set_defaults(func=backtest)
