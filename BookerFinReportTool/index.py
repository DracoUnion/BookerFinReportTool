"""子命令 index：构建关键词/向量索引（纯文件版）。

输出：
- `index/keyword.json`：`{keyword: [report_id, ...]}`
- `index/summaries.yaml`：`List[Report]`（已排序）
- `index/graph.yaml`：主题 -> 关联研报
"""
import json
import logging
import re
from os import path
from typing import Dict, List
from .util import write_yaml_model, write_text, read_text
from .models import Report, View
from .storage import FileStore

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s][%(name)s][%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)

def _index_words(text: str) -> List[str]:
    """简易分词：英文按 \\w+，中文按单字。"""
    toks = re.findall(r'[a-zA-Z]+', text.lower())
    toks += re.findall(r'[一-龥]', text)
    return [t for t in toks if len(t) > 1 or (len(t) == 1 and '一' <= t <= '鿿')]

def index(args):
    """重建索引。"""
    store = FileStore(args.data_dir)
    rids = store.list_report_ids()
    if not rids:
        logger.warning('没有研报可索引，先运行 ingest/extract')
        return

    # 关键词倒排
    kw_map: Dict[str, List[str]] = {}
    theme_map: Dict[str, List[str]] = {}

    for rid in rids:
        rep = store.load_report(rid)
        if rep is None:
            continue
        text = rep.title + ' ' + rep.institution + ' ' + ' '.join(rep.industry) + ' ' + ' '.join(rep.tickers) + ' ' + rep.summary
        for tok in _index_words(text):
            kw_map.setdefault(tok, [])
            if rid not in kw_map[tok]:
                kw_map[tok].append(rid)

        # 主题：行业 + 观点 subject 前缀
        bundle = store.load_extracted(rid)
        if bundle:
            for v in bundle.views:
                key = v.subject[:8]
                theme_map.setdefault(key, [])
                if rid not in theme_map[key]:
                    theme_map[key].append(rid)

    write_text(
        path.join(store.index_dir, 'keyword.json'),
        json.dumps(kw_map, ensure_ascii=False, indent=2),
    )
    write_yaml_model(
        path.join(store.index_dir, 'themes.yaml'),
        theme_map,
    )
    logger.info(f'[*] 关键词 {len(kw_map)} 个，主题 {len(theme_map)} 个')

def reg_subparser(subparsers):
    p = subparsers.add_parser('index', help='重建关键词/主题索引')
    p.add_argument('-d', '--data-dir', default='./data', help='数据存储目录')
    p.add_argument('--rebuild', action='store_true', help='强制重建（默认即全量）')
    p.set_defaults(func=index)
