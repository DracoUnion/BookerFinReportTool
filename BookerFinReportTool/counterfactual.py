"""子命令 counterfactual：反事实研报生成。"""
import json
import logging
import json_repair
from os import path
from .util import render_prompt, ext_code_block, json_dump_model, write_yaml_model
from .openai import OpenAIClient
from .storage import FileStore

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s][%(name)s][%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)

COUNTERFCTUAL_PMT = """\
你是一位宏观策略分析师。请基于 {period} 期的真实研报，注入反事实假设条件：

    {condition}

生成一份反事实情景研报，对比牛/熊/基准三种路径。以 JSON 输出（三个反引号包裹）：

```
{{
    "benchmark": "基准情景要点",
    "bull": "牛市情景要点",
    "bear": "熊市情景要点",
    "diff": "相对基准的关键差异（3~5 条）"
}}
```

{period} 期研报：
[content]
{retrieved}
[/content]
"""


def counterfactual(args):
    store = FileStore(args.data_dir)
    llm = OpenAIClient.from_args(args)
    # 检索 period 内的研报
    parts = []
    for rid in store.list_report_ids():
        rep = store.load_report(rid)
        if rep and args.period and args.period in rep.published_at[:7]:
            parts.append(f"--- {rep.title} ---\n{rep.summary}")
        elif not args.period:
            parts.append(f"--- {rep.title} ---\n{rep.summary}")
    retrieved = '\n\n'.join(parts)[:40_000] or '（无匹配研报）'

    ques = render_prompt(
        COUNTERFCTUAL_PMT,
        period=args.period,
        condition=args.condition,
        retrieved=retrieved,
    )
    ans = json_repair.loads(ext_code_block(llm.ask_chatgpt_retry(
        ques, args.model, args,
        parse_output=lambda s: ext_code_block(s),
    )))
    write_yaml_model(
        path.join(store.data_dir, 'counterfactual', f'{args.period}.yaml'),
        ans,
    )
    print(json_dump_model(ans))
    logger.info('[*] 完成')


def reg_subparser(subparsers):
    p = subparsers.add_parser('counterfactual', help='反事实研报生成')
    p.add_argument('--period', required=True, help='历史时期，如 2022 / 2022-06')
    p.add_argument('--condition', required=True, help='反事实假设条件')
    p.add_argument('--ticker', default='', help='相关标的（可选）')
    p.add_argument('-d', '--data-dir', default='./data', help='数据存储目录')
    p.set_defaults(func=counterfactual)
