"""辅助子命令 config：展示当前配置。"""
import logging
from .util import json_dump_model

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s][%(name)s][%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)


def config_show(args):
    """打印当前生效的 OpenAI 与数据目录配置。"""
    print(json_dump_model({
        'model': args.model,
        'host': args.host,
        'stream': args.stream,
        'data_dir': getattr(args, 'data_dir', './data'),
        'retry': args.retry,
    }))


def reg_subparser(subparsers):
    p = subparsers.add_parser('config', help='展示配置')
    p.add_argument('action', nargs='?', default='show', choices=['show'])
    p.set_defaults(func=config_show)
