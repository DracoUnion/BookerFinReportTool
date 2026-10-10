"""子命令 batch：批量下载 txt 中的研报。"""
import logging
from concurrent.futures import ThreadPoolExecutor
from .util import read_text
from .download import download as download_one

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s][%(name)s][%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)

def batch(args):
    """批量下载 txt 中的研报 ID。"""
    if not args.dj_key:
        logger.fatal('请通过 -dj 或 DJ_YANBAO_KEY 提供洞见研报 Bearer Key')
        return
    ids = [
        l.strip()
        for l in read_text(args.fname).splitlines()
        if l.strip()
    ]
    logger.info(f'[*] 共 {len(ids)} 个研报 ID')
    if not ids:
        logger.fatal('txt 文件中没有研报 ID')
        return

    def dl(rid):
        try:
            download_one(args, rid)
            return True
        except KeyboardInterrupt:
            raise
        except Exception as ex:
            logger.warning(f'研报 {rid} 下载失败：{ex}')
            return False

    with ThreadPoolExecutor(args.threads) as pool:
        futs = [pool.submit(dl, rid) for rid in ids]
        for f in futs:
            f.result()
    logger.info('[*] 完成')

def reg_subparser(subparsers):
    batch_parser = subparsers.add_parser("batch", help="批量下载 txt 中的研报")
    batch_parser.add_argument("fname", help="含研报 ID 的 txt 文件")
    batch_parser.add_argument("-o", "--out-dir", default='.', help="输出目录")
    batch_parser.add_argument("-t", "--threads", type=int, default=4, help="线程数")
    batch_parser.set_defaults(func=batch)
