"""子命令 consensus：共识拥挤度与分歧预警。"""
import json
import logging
import json_repair
from os import path
from typing import List, Dict
from .util import render_prompt, ext_code_block, json_dump_model, write_yaml_model
from .openai import ask_chatgpt_retry
from .models import ConsensusMetric, View
from .storage import FileStore

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s][%(name)s][%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)

STANCE_SCORE = {
    'bullish': 1.0, 'bearish': -1.0, 'neutral': 0.0, 'mixed': 0.0,
}

CONSENSUS_NOTE_PMT = """\
你是一位市场情绪分析师。基于下面的共识统计，解释共识变化的可能原因（3~5 句话），
JSON 输出：{{"note":"..."}}。

```
{stats}
```
"""


def consensus(args):
    store = FileStore(args.data_dir)
    views: List[View] = []
    for rid in store.list_report_ids():
        b = store.load_extracted(rid)
        if not b:
            continue
        if args.ticker and not any(args.ticker in (v.subject) for v in b.views):
            continue
        if args.industry:
            rep = store.load_report(rid)
            if rep and args.industry not in rep.industry:
                continue
        views += b.views

    # 按 subject 分组
    groups: Dict[str, List[View]] = {}
    for v in views:
        groups.setdefault(v.subject, []).append(v)

    res: List[ConsensusMetric] = []
    for subject, vs in groups.items():
        scores = [STANCE_SCORE.get(v.stance, 0.0) for v in vs]
        avg = sum(scores) / len(scores)
        div = (max(scores) - min(scores)) / 2 if scores else 0.0
        m = ConsensusMetric(
            subject=subject,
            window_days=args.window_days,
            count=len(vs),
            avg_stance=round(avg, 4),
            divergence=round(div, 4),
            alert=(div > 0.5 and len(vs) >= 5),
        )
        res.append(m)

    res.sort(key=lambda x: -x.count)
    top = res[:args.top]
    write_yaml_model(
        path.join(store.data_dir, 'consensus', 'metrics.yaml'),
        top,
    )
    print(json_dump_model(top))

    # LLM 解释最强的一条
    if top:
        m = top[0]
        ans = json_repair.loads(ext_code_block(ask_chatgpt_retry(
            render_prompt(
                CONSENSUS_NOTE_PMT,
                stats=json_dump_model(m.model_dump()),
            ),
            args.model, args,
            parse_output=lambda s: ext_code_block(s),
        )))
        print(f'\n共识说明：{ans.get("note", "")}')
    logger.info('[*] 完成')


def reg_subparser(subparsers):
    p = subparsers.add_parser('consensus', help='共识拥挤度与分歧预警')
    p.add_argument('--ticker', default='', help='按代码过滤')
    p.add_argument('--industry', default='', help='按行业过滤')
    p.add_argument('-w', '--window-days', type=int, default=90,
                   dest='window_days', help='统计窗口（天）')
    p.add_argument('--top', type=int, default=20, help='展示前 N 个主题')
    p.add_argument('-d', '--data-dir', default='./data', help='数据存储目录')
    p.set_defaults(func=consensus)
