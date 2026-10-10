"""子命令 ingest：将 PDF/MD 研报解析为 `Report` 记录并入库。

支持递归目录扫描，只处理 `.pdf` / `.md` 文件；
通过 `content_hash` 幂等，重复 ingest 不重复入库。
"""
import os
import re
import logging
from os import path
from concurrent.futures import ThreadPoolExecutor
from .util import read_pdf_text, read_text, extname, gen_objs_md5, write_text
from .models import Report
from .storage import FileStore

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s][%(name)s][%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)


def _extract_meta(fname: str, text: str) -> dict:
    """从文件名/首行启发式提取报告元数据。

    规则（从保守到激进）：
    - `id`：文件名主干 + 内容 hash 前 8 位，避免重复。
    - `title`：MD 首个 `# ` 标题；PDF 取文件名主干。
    - `published_at`：文件名/正文中首个 `YYYY-MM-DD`。
    - `institution`：正文中首个 "XX证券/XX研究"。
    """
    stem = path.splitext(path.basename(fname))[0]
    rid = gen_objs_md5(stem, text)[:8]

    title = stem
    m = re.search(r'^#\x20+(.+)$', text, flags=re.M)
    if m:
        title = m.group(1).strip()

    m = re.search(r'(\d{4}-\d{2}-\d{2})', fname + ' ' + text[:500])
    published_at = m.group(1) if m else ''

    m = re.search(r'([一-龥A-Za-z\.\s]{1,12}(证券|研究|基金|银行|保险))', text[:2000])
    institution = m.group(1).strip() if m else ''

    return {
        'id': rid,
        'title': title,
        'institution': institution,
        'published_at': published_at,
        'summary': text[:300].replace('\n', ' ').strip(),
    }


def ingest(args):
    """解析 `args.fname`（文件或目录）下的 PDF/MD，写入 `data_dir`。"""
    store = FileStore(args.data_dir)

    if path.isfile(args.fname):
        fnames = [args.fname]
    elif path.isdir(args.fname):
        fnames = [
            path.join(rt, f)
            for rt, _, fs in os.walk(args.fname)
            for f in fs
            if extname(f) in ('pdf', 'md')
        ]
    else:
        logger.fatal(f'路径不存在：{args.fname}')
        return

    logger.info(f'[*] 共 {len(fnames)} 个文件')

    def _one(fname: str):
        try:
            data = open(fname, 'rb').read()
        except Exception as ex:
            logger.warning(f'读取失败 {fname}：{ex}')
            return
        text = read_pdf_text(data) if fname.endswith('.pdf') else \
            read_text(fname)
        if not text.strip():
            logger.warning(f'内容为空，跳过 {fname}')
            return
        h = FileStore.content_hash(text)
        meta = _extract_meta(fname, text)
        meta['raw_path'] = fname
        meta['content_hash'] = h
        rep = Report(**meta)
        store.save_report(rep)
        # 同时缓存原始文本，供 extract 复用
        write_text(
            path.join(store.data_dir, 'texts', f'{rep.id}.txt'),
            text,
        )
        logger.info(f'ingest {rep.id}: {rep.title}')

    if args.threads > 1:
        with ThreadPoolExecutor(args.threads) as pool:
            list(pool.map(_one, fnames))
    else:
        for f in fnames:
            _one(f)

    logger.info(f'[*] 完成，入库研报：{store.list_report_ids()}')


def reg_subparser(subparsers):
    p = subparsers.add_parser('ingest', help='解析 PDF/MD 研报入库')
    p.add_argument('fname', help='PDF/MD 文件或目录')
    p.add_argument('-d', '--data-dir', default='./data', help='数据存储目录')
    p.add_argument('-t', '--threads', type=int, default=1, help='并发线程数')
    p.set_defaults(func=ingest)
