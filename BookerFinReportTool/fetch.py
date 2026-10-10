"""子命令 fetch：抓取研报 ID 到 txt。"""
import logging
from os import path
from .util import write_text, read_text
from .fin_report_api import DjYanbaoClient

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s][%(name)s][%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)

def fetch(args):
    """抓取研报 ID 列表并写入 args.fname（txt，每行一个 ID）。"""
    if not args.dj_key:
        logger.fatal('请通过 -dj 或 DJ_YANBAO_KEY 提供洞见研报 Bearer Key')
        return
    client = DjYanbaoClient(args)

    ids = []
    if args.source == 'favorite':
        ids = client.favorite_report_ids()
    else:
        page = 1
        while True:
            items = client.list_reports(
                page=page,
                limit=args.limit,
                q=args.query,
            )
            if not items:
                break
            ids += [str(it.get('id')) for it in items if it.get('id')]
            if len(items) < args.limit:
                break
            page += 1
            if args.pages and page > args.pages:
                break
    ids = [str(i) for i in ids]

    # 追加模式：与已有 txt 内容合并去重
    if path.isfile(args.fname):
        old = [l.strip() for l in read_text(args.fname).splitlines() if l.strip()]
        ids = old + [i for i in ids if i not in set(old)]

    write_text(args.fname, '\n'.join(ids) + ('\n' if ids else ''))
    logger.info(f'[*] 共 {len(ids)} 个研报 ID，已写入 {args.fname}')

def reg_subparser(subparsers):
    fetch_parser = subparsers.add_parser("fetch", help="抓取研报 ID 到 txt")
    fetch_parser.add_argument("fname", help="输出 txt 文件（每行一个研报 ID）")
    fetch_parser.add_argument(
        "-s", "--source",
        choices=['favorite', 'list'],
        default='favorite',
        help="抓取来源：收藏列表或研报列表",
    )
    fetch_parser.add_argument("-q", "--query", default='', help="研报搜索词（仅 source=list）")
    fetch_parser.add_argument("-l", "--limit", type=int, default=20, help="每页条数（仅 source=list）")
    fetch_parser.add_argument("-p", "--pages", type=int, default=0, help="最大抓取页数，0 表示不限（仅 source=list）")
    fetch_parser.set_defaults(func=fetch)
