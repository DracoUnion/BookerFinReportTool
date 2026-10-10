"""辅助子命令 doctor：环境自检。

检查依赖、环境变量、目录可写性。
"""
import os
import logging
from os import path

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s][%(name)s][%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)

CHECKS = ['openai', 'pydantic', 'yaml', 'requests', 'pymupdf', 'json_repair']


def doctor(args):
    ok = True
    # 依赖
    for m in CHECKS:
        try:
            __import__(m)
            logger.info(f'[ok] 依赖 {m}')
        except Exception as ex:
            ok = False
            logger.warning(f'[x] 依赖 {m} 缺失：{ex}')
    # 环境变量
    key = os.environ.get('OPENAI_API_KEY') or args.key
    if not key:
        ok = False
        logger.warning('[x] 未配置 OPENAI_API_KEY / -k')
    else:
        logger.info('[ok] API Key 已配置')
    # 目录
    d = getattr(args, 'data_dir', './data')
    try:
        os.makedirs(d, exist_ok=True)
        logger.info(f'[ok] 数据目录 {d}')
    except Exception as ex:
        ok = False
        logger.warning(f'[x] 数据目录不可写 {d}：{ex}')
    logger.info('[*] 自检通过' if ok else '[*] 自检存在问题')


def reg_subparser(subparsers):
    p = subparsers.add_parser('doctor', help='环境自检')
    p.add_argument('-d', '--data-dir', default='./data', help='数据存储目录')
    p.set_defaults(func=doctor)
