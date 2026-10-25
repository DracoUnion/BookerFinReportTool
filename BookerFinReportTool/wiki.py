"""子命令 wiki：RAG 式问答。

混合检索（关键词 + 主题）→ 取 top-K 研报 → LLM 基于证据生成答案。
"""
import json
import logging
import json_repair
from os import path
from typing import List, Optional
from .util import (
    read_yaml_model, write_yaml_model, read_text,
    render_prompt, ext_cont_block, json_dump_model,
)
from .openai import OpenAIClient
from .models import WqiAnswer, EvidenceRef, Report
from .storage import FileStore

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s][%(name)s][%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)

WQI_PMT = """\
你是一位投研助理。基于下面检索到的研报摘要，回答用户问题，并以 JSON 输出（三个反引号包裹）：

```
{
    "answer": "回答正文，必须引用下方研报证据",
    "citations": [
        {"report_id":"", "page":0, "quote":"原文", "published_at":""}
    ],
    "confidence": 0.7
}
```

要求：
- 不得编造未在研报中出现的信息；引用不足时把 confidence 调到 0.3 以下。
- 回答使用 [content]...[/content] 包裹正文（citations 用 JSON 数组表示）。

检索到的研报：

[content]
{retrieved}
[/content]

用户问题：
{question}
"""


def _retrieval(store: FileStore, question: str, top_k: int = 5) -> List[dict]:
    """简易关键词检索：对 question 分词，匹配 keyword.json。"""
    kw_fname = path.join(store.index_dir, 'keyword.json')
    kw_map = {}
    if path.isfile(kw_fname):
        kw_map = json.loads(read_text(kw_fname))
    toks = [w.lower() for w in question.replace(' ', '').split() if w]
    toks += list(question)  # 中文字符
    rid_scores = {}
    for tok in toks:
        rids = kw_map.get(tok, [])
        for rid in rids:
            rid_scores[rid] = rid_scores.get(rid, 0) + 1
    ranked = sorted(rid_scores.items(), key=lambda x: -x[1])[:top_k]

    out = []
    for rid, _ in ranked:
        rep = store.load_report(rid)
        if rep is None:
            continue
        bundle = store.load_extracted(rid)
        out.append({
            'report': rep,
            'bundle': bundle,
        })
    return out


def wiki(args):
    """`args.question` 作为自然语言问题。"""
    store = FileStore(args.data_dir)
    llm = OpenAIClient.from_args(args)
    retrieved = _retrieval(store, args.question, args.top_k)
    if not retrieved:
        logger.warning('检索结果为空，可先运行 `index` 或 `extract`')

    rep_texts = []
    for r in retrieved:
        rep: Report = r['report']
        rep_texts.append(
            f"=== {rep.id} | {rep.title} | {rep.institution} | {rep.published_at} ===\n"
            f"摘要：{rep.summary}\n"
            f"观点：{json_dump_model([v.model_dump() for v in (r['bundle'].views if r['bundle'] else [])])}"
        )
    retrieved_str = '\n\n'.join(rep_texts) if rep_texts else '（无相关研报）'

    ques = render_prompt(WQI_PMT, retrieved=retrieved_str, question=args.question)
    parse_output = lambda s: json_repair.loads(ext_cont_block(s))
    ans: dict = llm.ask_chatgpt_retry(
        ques, args.model, args,
        parse_output=parse_output,
    )
    ans_model = WqiAnswer(
        question=args.question,
        answer=ans.get('answer', ''),
        citations=[
            EvidenceRef.model_validate(c) for c in ans.get('citations', [])
        ],
        confidence=float(ans.get('confidence', 0.5)),
    )
    write_yaml_model(
        path.join(store.data_dir, 'qa', f'q_{hash(ans_model.question) & 0xFFFF}.yaml'),
        ans_model,
    )
    print(json_dump_model(ans_model))
    logger.info('[*] 完成')


def reg_subparser(subparsers):
    p = subparsers.add_parser('wiki', help='研报百科问答')
    p.add_argument('question', help='自然语言问题')
    p.add_argument('-d', '--data-dir', default='./data', help='数据存储目录')
    p.add_argument('-k', '--top-k', type=int, default=5, help='检索 top-K')
    p.set_defaults(func=wiki)
