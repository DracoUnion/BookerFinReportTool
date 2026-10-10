"""子命令 catalyst：催化剂日历与事件驱动。"""
import json
import logging
from os import path
from typing import List
from .util import json_dump_model, write_yaml_model
from .models import Event
from .storage import FileStore

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s][%(name)s][%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)


def catalyst(args):
    """汇总 `event_date` 落在 [from, to] 内的事件，按日期排序输出日历。"""
    store = FileStore(args.data_dir)
    events: List[Event] = []
    for rid in store.list_report_ids():
        b = store.load_extracted(rid)
        if not b:
            continue
        if args.ticker and not any(
            args.ticker in ((e.ticker or '') + ' ' + e.description)
            for e in b.events
        ):
            continue
        events += b.events

    if args.from_date or args.to_date:
        events = [
            e for e in events
            if e.event_date
            and (not args.from_date or e.event_date >= args.from_date)
            and (not args.to_date or e.event_date <= args.to_date)
        ]

    events.sort(key=lambda e: e.event_date or '')
    calendar = {
        date: [
            {'type': e.event_type, 'desc': e.description, 'importance': e.importance}
            for e in events if e.event_date == date
        ]
        for date in {e.event_date for e in events if e.event_date}
    }
    write_yaml_model(
        path.join(store.data_dir, 'catalyst', 'calendar.yaml'),
        calendar,
    )
    print(json_dump_model(calendar))
    logger.info(f'[*] 共 {len(events)} 个事件')


def reg_subparser(subparsers):
    p = subparsers.add_parser('catalyst', help='催化剂日历与事件驱动')
    p.add_argument('--ticker', default='', help='按代码过滤')
    p.add_argument('--from', dest='from_date', default='', help='起始日期')
    p.add_argument('--to', dest='to_date', default='', help='截止日期')
    p.add_argument('-d', '--data-dir', default='./data', help='数据存储目录')
    p.set_defaults(func=catalyst)
