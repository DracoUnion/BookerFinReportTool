"""子命令 download：下载单份研报正文（Markdown）。"""
import re
import logging
from datetime import datetime
from os import path
import pyturndown
from .util import write_text
from .fin_report_api import DjYanbaoClient

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s][%(name)s][%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)

def _publish_date_str(detail) -> str:
    """从研报详情中提取发布日期，格式化为 `YYYY-MM-DD`；缺省返回空串。"""
    if not detail:
        return ''
    d = detail.get('publishAt')
    if isinstance(d, str):
        m = re.match(r'\d{4}-\d{2}-\d{2}', d)
        return m.group(0) if m else d[:10]
    try:
        return datetime.fromtimestamp(d).strftime('%Y-%m-%d')
    except Exception:
        return str(d)[:10]

def _safe_name(text: str) -> str:
    """过滤路径非法字符，保留中文标点。"""
    text = re.sub(r'[\\/:*?"<>\\|]', '', text) if text else ''
    text = text.replace('\x20', '-')
    return text

def _html_to_md(content: str) -> str:
    """将研报正文 HTML 转为 Markdown；非 HTML 纯文本原样返回。"""
    if not content:
        return content
    if re.search(r'<[a-zA-Z]', content):
        return pyturndown.TurndownService().turndown(content)
    return content

def download(args, report_id=None):
    """下载单份研报正文（Markdown），文件名格式 `【日期】【机构】标题.md`。"""
    if not args.dj_key:
        logger.fatal('请通过 -dj 或 DJ_YANBAO_KEY 提供洞见研报 Bearer Key')
        return
    client = DjYanbaoClient(args)
    rid = report_id or args.report_id
    out_dir = getattr(args, 'out_dir', '.')

    content = client.report_content(rid)
    if not content:
        logger.fatal(f'研报 {rid} 正文内容为空：{content!r}')
        return
    logger.info(f'研报正文长度：{len(content)}')

    try:
        detail = client.report_detail(rid) or {}
    except Exception:
        detail = {}

    title = _safe_name(detail.get('title', '未知标题'))
    institution = _safe_name(detail.get('orgName', '未知机构'))

    date_str = _publish_date_str(detail)
    base = f'【{date_str}】【{institution}】{title}.md'
    fname = path.join(out_dir, base)

    md = _html_to_md(content)
    write_text(fname, md)
    logger.info(f'[done] 已下载 {fname}（{len(md)} chars）')

def reg_subparser(subparsers):
    download_parser = subparsers.add_parser("download", help="下载单份研报正文（Markdown）")
    download_parser.add_argument("report_id", help="研报 ID")
    download_parser.add_argument("-o", "--out-dir", default='.', help="输出目录")
    download_parser.set_defaults(func=download)
