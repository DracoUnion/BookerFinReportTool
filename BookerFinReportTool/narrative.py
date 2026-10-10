"""子命令 narrative：叙事传播图谱。

主题嵌入聚类（简化为关键词分组）→ 找最早出现研报 → 构建传播图 →
关联时间线 → LLM 总结 → 输出 GraphML/YAML + 时间线。
"""
import json
import logging
import json_repair
from os import path
from collections import defaultdict
from .util import render_prompt, ext_code_block, ext_cont_block, json_dump_model, write_yaml_model
from .openai import ask_chatgpt_retry
from .models import NarrativeResult, NarrativeNode, NarrativeEdge
from .storage import FileStore

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s][%(name)s][%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)

NARRATIVE_SUM_PMT = """\
你是一位策略研究员。基于主题 "{theme}" 的研报时间线，总结其叙事演变
（谁最早提出、如何扩散、主流观点如何变化），3~5 句话，正文用 [content]...[/content] 包裹。

时间线：
[content]
{timeline}
[/content]
"""


def narrative(args):
    store = FileStore(args.data_dir)

    # 1. 按主题（观点 subject 前 8 字）分组
    theme_map: dict = defaultdict(list)
    for rid in store.list_report_ids():
        rep = store.load_report(rid)
        b = store.load_extracted(rid)
        if rep is None or b is None:
            continue
        if args.theme and args.theme not in ' '.join(
            [v.subject for v in b.views] + rep.industry
        ):
            continue
        for v in b.views:
            key = v.subject[:8]
            theme_map[key].append((rep, v))

    nodes, edges, timeline = [], [], []
    for theme, items in theme_map.items():
        items.sort(key=lambda x: x[0].published_at)
        first = items[0]
        rep_ids = sorted({r.id for r, _ in items})
        nodes.append(NarrativeNode(
            theme=theme,
            first_seen=first[0].published_at,
            report_ids=rep_ids,
        ))
        timeline += [
            f'{r.published_at} | {v.stance} | {v.thesis}'
            for r, v in items
        ]
        # 传播边：把出现过的主题两两连接（简化）
    themes = [n.theme for n in nodes]
    for i in range(len(themes)):
        for j in range(i + 1, len(themes)):
            edges.append(NarrativeEdge(src=themes[i], dst=themes[j], weight=1.0))

    timeline.sort()
    summary = ''
    if timeline:
        summary = ask_chatgpt_retry(
            render_prompt(
                NARRATIVE_SUM_PMT,
                theme=args.theme or '多主题',
                timeline='\n'.join(timeline)[:30_000],
            ),
            args.model, args,
            parse_output=ext_cont_block,
        )

    result = NarrativeResult(
        theme=args.theme or '多主题',
        nodes=nodes, edges=edges,
        timeline=timeline,
        summary=summary,
    )
    out = path.join(store.data_dir, 'narrative', f'{args.theme or "all"}.yaml')
    write_yaml_model(out, result)

    # 可选导出 GraphML
    if args.output == 'graphml':
        _write_graphml(out[:-5] + '.graphml', nodes, edges)

    print(json_dump_model(result))
    logger.info(f'[*] 完成，写入 {out}')


def _write_graphml(fname: str, nodes, edges):
    import xml.etree.ElementTree as ET
    g = ET.Element('graphml')
    ET.SubElement(g, 'graph', edgedefault='directed')
    for n in nodes:
        ET.SubElement(g[0], 'node', id=n.theme, label=n.theme)
    for e in edges:
        ET.SubElement(g[0], 'edge', source=e.src, target=e.dst)
    ET.ElementTree(g).write(fname, encoding='utf8', xml_declaration=True)


def reg_subparser(subparsers):
    p = subparsers.add_parser('narrative', help='叙事传播图谱')
    p.add_argument('--theme', default='', help='主叙事主题')
    p.add_argument('--from', dest='from_date', default='', help='起始日期')
    p.add_argument('-o', '--output', default='yaml',
                   choices=['yaml', 'graphml'], help='输出格式')
    p.add_argument('-d', '--data-dir', default='./data', help='数据存储目录')
    p.set_defaults(func=narrative)
