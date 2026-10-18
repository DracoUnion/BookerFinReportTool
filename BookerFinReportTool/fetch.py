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

    f = open(args.fname, 'a', encoding='utf8')
    if args.source == 'favorite':
        ids = client.favorite_report_ids()
        print(f'[+] {ids}')
        for id in ids:
            f.write(id + '\n')
    else:
        page = args.start_page
        while not args.end_page or page <= args.end_page:
            print(f'[*] 抓取第 {page} 页')
            items = client.list_reports(
                page=page,
                limit=args.limit,
                q=args.query,
                publish_at_begin=args.begin,
                publish_at_end=args.end,
            )
            if not items:
                break
            ids = [str(it.get('id')) for it in items if it.get('id')]
            print(f'[+] {ids}')
            for id in ids:
                f.write(id + '\n')
            f.flush()
            page += 1

    f.close()
    logger.info(f'[*] 共 ??? 个研报 ID，已写入 {args.fname}')

def reg_subparser(subparsers):
    fetch_parser = subparsers.add_parser("fetch", help="抓取研报 ID 到 txt")
    fetch_parser.add_argument("fname", help="输出 txt 文件（每行一个研报 ID）")
    fetch_parser.add_argument(
        "-s", "--source",
        choices=['favorite', 'list'],
        default='list',
        help="抓取来源：收藏列表或研报列表",
    )
    fetch_parser.add_argument("-q", "--query", default='', help="研报搜索词（仅 source=list）")
    fetch_parser.add_argument("-l", "--limit", type=int, default=20, help="每页条数（仅 source=list）")
    fetch_parser.add_argument("-sp", "--start-page", type=int, default=1, help="起始抓取页数，0 表示不限（仅 source=list）")
    fetch_parser.add_argument("-ep", "--end-page", type=int, default=0, help="终止抓取页数，0 表示不限（仅 source=list）")
    fetch_parser.add_argument("-b", "--begin", default='', help="起始日期 YYYY-MM-DD（仅 source=list）")
    fetch_parser.add_argument("-e", "--end", default='', help="截止日期 YYYY-MM-DD（仅 source=list）")
    fetch_parser.set_defaults(func=fetch)
