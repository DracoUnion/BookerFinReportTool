"""子命令 download：下载单份研报。"""
import re
import logging
from os import path
import requests
from .fin_report_api import DjYanbaoClient

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s][%(name)s][%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)

def download(args, report_id=None):
    """下载单份研报 PDF，保存到 args.out_dir 目录。"""
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
        detail = client.report_detail(rid)
        title = (detail or {}).get('title', '')
    except Exception:
        title = ''
    safe_title = re.sub(r'[^\\w\\u4e00-\\u9fff]', '_', title) if title else ''
    fname = path.join(out_dir, f'{rid}_{safe_title}.pdf' if safe_title else f'{rid}.pdf')

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
