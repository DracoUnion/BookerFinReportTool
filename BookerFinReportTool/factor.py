"""子命令 factor：文本因子工厂。

从研报中抽取文本信号（情绪/分歧/修正/主题集中度）→ 构建面板 →
计算 IC、分层回测 → 输出 CSV/JSON。
"""
import json
import logging
import json_repair
from os import path
from typing import List
from .util import render_prompt, ext_code_block, json_dump_model, write_yaml_model
from .openai import ask_chatgpt_retry
from .models import FactorValue
from .storage import FileStore

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s][%(name)s][%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)

FACTOR_EXTRACT_PMT = """\
你是一位量化研究员。请基于研报中所有涉及 {ticker} 的观点，抽取文本因子 {factor}，
归一化到 0~1，以 JSON 输出（三个反引号包裹）：

```
{{"value": 0.0, "reason": "简要说明"}}
```

可用观点：
[content]
{views}
[/content]
"""

FACTOR_NAMES = [
    'report_sentiment', 'disagreement', 'revision', 'theme_concentration',
]


def factor_build(args):
    """构建指定因子的面板。"""
    store = FileStore(args.data_dir)
    panel: List[FactorValue] = []
    tickers = args.tickers.split(',') if args.tickers else _all_tickers(store)
    for t in tickers:
        t = t.strip()
        if not t:
            continue
        views_str = _views_for(store, t)
        if not views_str:
            continue
        ques = render_prompt(
            FACTOR_EXTRACT_PMT,
            ticker=t, factor=args.name, views=views_str,
        )
        ans = json_repair.loads(ext_code_block(ask_chatgpt_retry(
            ques, args.model, args,
            parse_output=lambda s: ext_code_block(s),
        )))
        for rid in _rids_for(store, t):
            rep = store.load_report(rid)
            panel.append(FactorValue(
                ticker=t,
                date=rep.published_at if rep else '',
                factor=args.name,
                value=float(ans.get('value', 0.0)),
            ))
    out = path.join(store.data_dir, 'factors', f'{args.name}.json')
    write_yaml_model(out, panel)
    print(json_dump_model(panel[:5]))
    logger.info(f'[*] 因子 {args.name} 面板共 {len(panel)} 行，写入 {out}')


def factor_run(args):
    """对面板计算 IC 与分层回测（简化版：按值分组比较）。"""
    store = FileStore(args.data_dir)
    fname = path.join(store.data_dir, 'factors', f'{args.name}.json')
    if not path.isfile(fname):
        logger.warning(f'{fname} 不存在，先运行 factor build')
        return
    import yaml
    panel = yaml.safe_load(open(fname, encoding='utf8').read())
    if not panel:
        return
    # 按 factor value 分 3 层，比较"命中方向"的比例（简化 IC）
    vals = sorted(panel, key=lambda p: p.value)
    n = len(vals)
    lo = vals[:n // 3]
    hi = vals[-(n // 3):]
    ic = (sum(p.value for p in hi) - sum(p.value for p in lo)) / max(1, len(hi) + len(lo))
    print(json_dump_model({
        'factor': args.name,
        'rows': n,
        'ic_proxy': round(ic, 4),
    }))


def _all_tickers(store: FileStore) -> List[str]:
    ts = set()
    for rep in store.all_reports():
        ts.update(rep.tickers)
    return sorted(ts)


def _rids_for(store: FileStore, ticker: str) -> List[str]:
    rids = []
    for rid in store.list_report_ids():
        rep = store.load_report(rid)
        if rep and ticker in rep.tickers:
            rids.append(rid)
    return rids


def _views_for(store: FileStore, ticker: str) -> str:
    parts = []
    for rid in _rids_for(store, ticker):
        b = store.load_extracted(rid)
        if not b:
            continue
        parts += [f'({v.stance}) {v.thesis}' for v in b.views]
    return '\n'.join(parts)[:30_000]


def factor(args):
    if args.action == 'build':
        factor_build(args)
    else:
        factor_run(args)


def reg_subparser(subparsers):
    p = subparsers.add_parser('factor', help='文本因子工厂')
    sub = p.add_subparsers(dest='action')

    b = sub.add_parser('build', help='构建因子面板')
    b.add_argument('--name', default='report_sentiment', choices=FACTOR_NAMES,
                   help='因子名')
    b.add_argument('--tickers', default='', help='逗号分隔的代码列表，缺省为全部')
    b.add_argument('-d', '--data-dir', default='./data', help='数据存储目录')

    r = sub.add_parser('run', help='IC / 分层回测')
    r.add_argument('--name', default='report_sentiment', choices=FACTOR_NAMES,
                   help='因子名')
    r.add_argument('-d', '--data-dir', default='./data', help='数据存储目录')

    p.set_defaults(func=factor)
