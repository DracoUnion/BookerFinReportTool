"""子命令 debate：多智能体投研辩论。"""
import json
import logging
import json_repair
from os import path
from typing import List
from .util import render_prompt, ext_code_block, ext_cont_block, json_dump_model, write_yaml_model
from .openai import OpenAIClient
from .debate_pmt import (
    DEBATE_BULL_PMT, DEBATE_BEAR_PMT, DEBATE_REBUT_PMT, DEBATE_JUDGE_PMT,
)
from .models import DebateResult, DebateTurn
from .storage import FileStore

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s][%(name)s][%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)


def _retrieved_str(store: FileStore, ticker: str) -> str:
    """把含 ticker 的研报观点拼为文本，传给 LLM。"""
    parts = []
    for rid in store.list_report_ids():
        b = store.load_extracted(rid)
        if not b:
            continue
        reps = store.load_report(rid)
        if reps and ticker in ' '.join(reps.tickers):
            parts.append(
                f"--- {reps.id} | {reps.title} ---\n"
                + '\n'.join(v.thesis for v in b.views)
            )
    return '\n\n'.join(parts) or '（暂无相关研报，请先 ingest/extract）'


def debate(args):
    store = FileStore(args.data_dir)
    llm = OpenAIClient.from_args(args)
    retrieved = _retrieved_str(store, args.ticker)
    turns: List[DebateTurn] = []

    roles = [r.strip() for r in args.roles.split(',')]
    rounds = max(1, args.rounds)

    bull_hist: List[str] = []
    bear_hist: List[str] = []

    for rnd in range(1, rounds + 1):
        # bull
        bull_txt = llm.ask_chatgpt_retry(
            render_prompt(
                DEBATE_BULL_PMT if rnd == 1 else DEBATE_REBUT_PMT,
                ticker=args.ticker,
                role='bull',
                op_role='bear',
                retrieved=retrieved,
                opponent='\n'.join(bear_hist),
            ),
            args.model, args,
            parse_output=ext_cont_block,
        )
        bull_hist.append(bull_txt)
        turns.append(DebateTurn(role='bull', text=bull_txt))

        # bear
        bear_txt = llm.ask_chatgpt_retry(
            render_prompt(
                DEBATE_BEAR_PMT if rnd == 1 else DEBATE_REBUT_PMT,
                ticker=args.ticker,
                role='bear',
                op_role='bull',
                retrieved=retrieved,
                opponent='\n'.join(bull_hist),
            ),
            args.model, args,
            parse_output=ext_cont_block,
        )
        bear_hist.append(bear_txt)
        turns.append(DebateTurn(role='bear', text=bear_txt))

    # judge
    judge_ans = json_repair.loads(ext_code_block(llm.ask_chatgpt_retry(
        render_prompt(
            DEBATE_JUDGE_PMT,
            bull='\n\n'.join(bull_hist),
            bear='\n\n'.join(bear_hist),
        ),
        args.model, args,
        parse_output=lambda s: ext_code_block(s),
    )))

    result = DebateResult(
        ticker=args.ticker,
        rounds=rounds,
        turns=turns,
        memo=json.dumps(judge_ans, ensure_ascii=False, indent=2),
    )
    out_fname = path.join(store.data_dir, 'debates', f'{args.ticker}.yaml')
    write_yaml_model(out_fname, result)
    print(json_dump_model(result))
    logger.info(f'[*] 完成，备忘录写入 {out_fname}')


def reg_subparser(subparsers):
    p = subparsers.add_parser('debate', help='多智能体投研辩论')
    p.add_argument('ticker', help='标的代码')
    p.add_argument('-r', '--rounds', type=int, default=2, help='辩论轮数')
    p.add_argument('--roles', default='bull,bear',
                   help='角色列表（逗号分隔），如 bull,bear,risk,judge')
    p.add_argument('-d', '--data-dir', default='./data', help='数据存储目录')
    p.set_defaults(func=debate)
