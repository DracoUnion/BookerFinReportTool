"""子命令 quality：研报质量与合规检测。"""
import json
import logging
import json_repair
from os import path
from .util import render_prompt, ext_code_block, json_dump_model, write_yaml_model, read_text
from .openai import ask_chatgpt_retry
from .models import QualityReport
from .storage import FileStore

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s][%(name)s][%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)

QUALITY_PMT = """\
你是一位严格的研报质量评审员。对下面的研报进行合规与质量评审，按 6 个维度打分（0~10），
并列出发现的问题。以 JSON 输出（三个反引号包裹）：

```
{{
    "dimensions": {{
        "数据支撑": 0.0,
        "逻辑链": 0.0,
        "风险提示": 0.0,
        "模板化": 0.0,
        "利益冲突": 0.0,
        "重复度": 0.0
    }},
    "issues": ["...", "..."],
    "score": 0.0
}}
```

研报全文：
[content]
{text}
[/content]
"""


def quality(args):
    store = FileStore(args.data_dir)
    reps = store.all_reports()
    if args.institution:
        reps = [r for r in reps if args.institution in r.institution]
    if args.from_date:
        reps = [r for r in reps if r.published_at >= args.from_date]

    reports: list = []
    for rep in reps:
        text = ''
        txt_fname = path.join(store.data_dir, 'texts', f'{rep.id}.txt')
        if path.isfile(txt_fname):
            text = read_text(txt_fname)
        if not text:
            reports.append(QualityReport(report_id=rep.id))
            continue
        ques = render_prompt(QUALITY_PMT, text=text[:40_000])
        ans = json_repair.loads(ext_code_block(ask_chatgpt_retry(
            ques, args.model, args,
            parse_output=lambda s: ext_code_block(s),
        )))
        rep_q = QualityReport(
            report_id=rep.id,
            score=ans.get('score', 0.0),
            dimensions=ans.get('dimensions', {}),
            issues=ans.get('issues', []),
        )
        reports.append(rep_q)

    out = path.join(store.data_dir, 'quality', 'reports.yaml')
    write_yaml_model(out, reports)
    print(json_dump_model(reports))
    logger.info(f'[*] 完成，共 {len(reports)} 份')


def reg_subparser(subparsers):
    p = subparsers.add_parser('quality', help='研报质量与合规检测')
    p.add_argument('--institution', default='', help='按机构过滤')
    p.add_argument('--from', dest='from_date', default='', help='起始日期')
    p.add_argument('-d', '--data-dir', default='./data', help='数据存储目录')
    p.set_defaults(func=quality)
