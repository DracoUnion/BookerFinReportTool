"""子命令 leaderboard：分析师/机构排行榜。

读取 `data/backtest/result.yaml` + 全部 `extracted/*.yaml`，
按 `--metric` 聚合 → 贝叶斯收缩 + 置信区间 → 排名 → LLM 评语。
"""
import json
import logging
import json_repair
from os import path
from typing import List
from .util import render_prompt, ext_code_block, json_dump_model, write_yaml_model
from .openai import OpenAIClient
from .models import Prediction, LeaderboardEntry
from .storage import FileStore

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s][%(name)s][%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)

LEADER_COMMENT_PMT = """\
你是一位资深投研总监。根据下面一行排行榜数据，写一句 20~40 字的评语，
放入 JSON：{{"comment": "..."}}。

```
{entry}
```
"""


def _bayes_shrink(x: float, n: int, m: float = 0.5, k: float = 10) -> float:
    """贝叶斯收缩：`weight = n / (n + k)`，把小样本向先验 `m` 收缩。"""
    w = n / (n + k)
    return w * x + (1 - w) * m


def leaderboard(args):
    store = FileStore(args.data_dir)
    llm = OpenAIClient.from_args(args)
    by = args.by
    key_of = lambda p: (p.analyst if by == 'analyst' else p.institution)
    groups: dict = {}
    for rid in store.list_report_ids():
        b = store.load_extracted(rid)
        if not b:
            continue
        for p in b.predictions:
            if not p.actual_value:
                continue
            groups.setdefault(key_of(p), []).append(p)

    entries: List[LeaderboardEntry] = []
    for name, ps in groups.items():
        if len(ps) < args.min_samples:
            continue
        hit = sum(
            1 for p in ps
            if (p.direction == 'up' and _to_f(p.actual_value) > _to_f(p.value)) or
               (p.direction == 'down' and _to_f(p.actual_value) < _to_f(p.value))
        )
        x = hit / len(ps)
        val = _bayes_shrink(x, len(ps))
        # 简单 95% CI：正态近似
        z = 1.96
        ci = z * (val * (1 - val) / len(ps)) ** 0.5
        entry = LeaderboardEntry(
            name=name,
            metric=args.metric,
            value=round(val, 4),
            ci_low=max(0.0, round(val - ci, 4)),
            ci_high=min(1.0, round(val + ci, 4)),
            samples=len(ps),
            comment='',
        )
        try:
            ans = json_repair.loads(ext_code_block(llm.ask_chatgpt_retry(
                render_prompt(LEADER_COMMENT_PMT, entry=json_dump_model(entry)),
                args.model, args,
                parse_output=lambda s: ext_code_block(s),
            )))
            entry.comment = ans.get('comment', '')
        except Exception as ex:
            logger.debug(f'LLM 评语失败：{ex}')
        entries.append(entry)

    entries.sort(key=lambda e: -e.value)
    top = entries[:args.top]
    write_yaml_model(
        path.join(store.data_dir, 'leaderboard', f'{args.metric}.yaml'),
        top,
    )
    print(json_dump_model(top))
    logger.info('[*] 完成')


def _to_f(x):
    try:
        return float(str(x).replace('%', '').replace(',', '').split(' ')[0])
    except Exception:
        return None


def reg_subparser(subparsers):
    p = subparsers.add_parser('leaderboard', help='分析师/机构排行榜')
    p.add_argument('--metric', default='direction_accuracy',
                   help='排序指标（默认：方向准确率）')
    p.add_argument('--by', default='analyst',
                   choices=['analyst', 'institution'],
                   help='聚合维度')
    p.add_argument('-m', '--min-samples', type=int, default=10,
                   dest='min_samples', help='最少样本数')
    p.add_argument('--top', type=int, default=50, help='展示前 N')
    p.add_argument('-d', '--data-dir', default='./data', help='数据存储目录')
    p.set_defaults(func=leaderboard)
