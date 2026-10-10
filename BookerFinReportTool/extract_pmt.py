"""extract 子命令的提示词模板。"""

EXTRACT_BUNDLE_PMT = """\
你是一位资深卖方研究员。请通读下面的研报全文，抽取其中所有的**观点(View)**、**可回测预测(Prediction)**与**事件/催化剂(Event)**，以 JSON 输出，放在三个反引号（```）中。

要求：
- 每个观点/预测/事件都必须给出至少一条 `evidence`，`quote` 直接引用研报原文（保持原样，不要改写）。
- `stance` 取值：bullish/bearish/neutral/mixed。
- 预测的 `direction` 取值：up/down/flat/unknown；`confidence` 为 0~1 小数。
- 事件日期统一 `YYYY-MM-DD`；不确定则置空。
- 不要编造研报没有的内容；找不到就返回空列表。
- 输出 JSON 结构：

```
{
    "views": [
        {"subject":"", "stance":"", "horizon":"", "thesis":"",
         "catalysts":[], "risks":[],
         "evidences":[{"page":0,"quote":"","published_at":""}]},
        ...
    ],
    "predictions": [
        {"analyst":"", "institution":"", "ticker":"", "metric":"", "horizon":"",
         "value":"", "direction":"", "confidence":0.5, "rationale":""},
        ...
    ],
    "events": [
        {"ticker":"", "event_type":"", "event_date":"", "description":"",
         "importance":3, "evidences":[{"page":0,"quote":"","published_at":""}]},
        ...
    ]
}
```

研报全文：

[content]
{report_text}
[/content]
"""
