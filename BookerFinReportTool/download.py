"""子命令 download：下载单份研报。"""
import re
import logging
from datetime import datetime
from os import path
import requests
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
    d = detail.get('publishAt') or detail.get('publish_at') or detail.get('publishDate') or ''
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

def download(args, report_id=None):
    """下载单份研报 PDF，文件名格式 `【日期】【机构】标题.pdf`。"""
    if not args.dj_key:
        logger.fatal('请通过 -dj 或 DJ_YANBAO_KEY 提供洞见研报 Bearer Key')
        return
    client = DjYanbaoClient(args)
    rid = report_id or args.report_id
    out_dir = getattr(args, 'out_dir', '.')

    info = client.report_download_info(rid)
    file_url = info.get('fileUrl') if isinstance(info, dict) else None
    if not file_url:
        logger.fatal(f'研报 {rid} 无法获取下载地址：{info}')
        return
    logger.info(f'PDF 下载地址：{file_url}')

    try:
        detail = client.report_detail(rid) or {}
    except Exception:
        detail = {}

    title = _safe_name(detail.get('title', ''))
    # 机构名：优先 detail.institution，其次 cards/organization 字段
    institution = (
        detail.get('institution')
        or detail.get('organization')
        or (detail.get('cards') or {}).get('institution', '')
        or ''
    )
    institution = _safe_name(str(institution))

    date_str = _publish_date_str(detail)
    parts = [f'【{date_str}】']
    if institution:
        parts.append(f'【{institution}】')
    parts.append(title if title else str(rid))
    fname = path.join(out_dir, ''.join(parts) + '.pdf')

    r = requests.get(file_url)
    r.raise_for_status()
    with open(fname, 'wb') as f:
        f.write(r.content)
    logger.info(f'[done] 已下载 {fname}（{len(r.content)} bytes）')

def reg_subparser(subparsers):
    download_parser = subparsers.add_parser("download", help="下载单份研报 PDF")
    download_parser.add_argument("report_id", help="研报 ID")
    download_parser.add_argument("-o", "--out-dir", default='.', help="输出目录")
    download_parser.set_defaults(func=download)
