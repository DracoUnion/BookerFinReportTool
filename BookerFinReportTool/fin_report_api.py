"""洞见研报 API 客户端（Bearer 鉴权）。

key 从命令行参数 `args` 获取（`args.dj_key`）。
"""
import json
import requests
import logging
from typing import *

logger = logging.getLogger(__name__)

BASE_URL = "https://api.djyanbao.com/api/"

class DjYanbaoClient:
    """洞见研报 API 客户端。

    用法::

        client = DjYanbaoClient(args)   # args.dj_key 为 Bearer key
        items = client.list_reports(page=1, limit=20)
        detail = client.report_detail(123)
        content = client.report_content(123)
        pdf_url = client.report_download_info(123)
        ids = client.favorite_report_ids()
    """

    def __init__(self, args):
        self.key = args.dj_key
        self.headers = {
            "Authorization": f"Bearer {self.key}",
            "client-ver": "v2.1.0",
            "client-type": "wx_miniprogram",
            "Content-Type": "application/json",
        }

    def _req(self, method: str, url: str, **kw) -> dict:
        """发起请求并解析响应信封。"""
        r = requests.request(
            method, BASE_URL + url,
            headers=self.headers,
            **kw,
        )
        if r.status_code in (401, 403):
            raise PermissionError(f"洞见研报鉴权失败：HTTP {r.status_code}")
        r.raise_for_status()
        resp = r.json()
        code = resp.get("code")
        message = resp.get("message", "")
        if code != 0:
            raise RuntimeError(f"洞见研报接口错误：code={code}, message={message}")
        return resp.get("data")

    def list_reports(
        self, page: int = 1, limit: int = 20,
        q: str = "", sort: str = "publish_at",
        order: str = "DESC",
        publish_at_begin: str = "",
        publish_at_end: str = "",
        **filters,
    ) -> List[dict]:
        """研报列表 / 搜索。"""
        params = {"page": page, "limit": limit, "sort": sort, "order": order}
        if q:
            params["q"] = q
        if publish_at_begin:
            params["publishAtBegin"] = publish_at_begin
        if publish_at_end:
            params["publishAtEnd"] = publish_at_end
        params.update({k: v for k, v in filters.items() if v is not None})
        data = self._req("GET", "report", params=params)
        return data.get("data", []) if isinstance(data, dict) else (data or [])

    def report_detail(self, report_id) -> dict:
        """研报详情。"""
        return self._req("GET", f"report/{report_id}")

    def report_content(self, report_id) -> str:
        """研报正文内容。"""
        data = self._req("GET", f"report/{report_id}/content")
        return (data or {}).get("content", "")

    def report_download_info(
        self, report_id, 
        action: Literal["view", "download"] = "view",
        format: Literal["pdf", "origin"] = "pdf",
    ) -> dict:
        """研报下载信息，成功时返回 `data.fileUrl`（PDF 下载地址）。"""
        return self._req(
            "GET", 
            f"report/{report_id}/download/info", 
            params={"action": action, "format": format},
        )

    def favorite_report_ids(self) -> List:
        """收藏研报 ID 列表。"""
        return self._req("GET", "favorite/reportIds") or []
