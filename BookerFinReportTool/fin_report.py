import os
import logging
from os import path
from .util import *
from .openai import *

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s][%(name)s][%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)

OVERALL_PMT = """\
[content]...[/content]\
"""

class FinReportOrchestrator:
    """财务报告编排器。"""

    def __init__(self, args):
        self.args = args
        self.pj_dir = (
            args.fname[:-4] + '_fin_report'
            if path.isfile(args.fname)
            else path.abspath(args.fname) + '_fin_report'
        )
        os.makedirs(self.pj_dir, exist_ok=True)

    def run(self):
        """主流程。"""
        logger.info(f'[*] 输出目录：{self.pj_dir}')
        call_llm_with_toolcall_retry(
            OVERALL_PMT, self.args.model,
            [], {},
            history_fname=path.join(self.pj_dir, 'history.yaml'),
            retry=self.args.retry,
            temp=self.args.temp,
            top_p=self.args.top_p,
            frequency_penalty=self.args.frequency_penalty,
            presence_penalty=self.args.presence_penalty,
            max_tokens=self.args.max_tokens,
            extra_body=self.args.extra_body,
        )
        logger.info(f'[*] 已完成，目标文件已写入 {self.pj_dir}')
