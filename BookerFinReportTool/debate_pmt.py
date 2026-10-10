"""debate 子命令的提示词模板。"""

DEBATE_BULL_PMT = """\
你是一位乐观的买方基金经理。基于提供的 {ticker} 研报摘要与观点，生成 {role} 立场。

输入研报：
[content]
{retrieved}
[/content]

请输出"多方论点"，包含：
1. 核心结论（一句话）
2. 三条支撑论据（每条引用研报证据 quote）
3. 对主要风险的反驳（说明为何可控或已 price-in）

正文用 [content]...[/content] 包裹。
"""

DEBATE_BEAR_PMT = """\
你是一位谨慎的风险分析师。基于提供的 {ticker} 研报摘要与观点，生成 {role} 立场。

输入研报：
[content]
{retrieved}
[/content]

请输出"空方论点"，包含：
1. 核心顾虑（一句话）
2. 三条风险论据（每条引用研报证据 quote）
3. 对乐观预期的质疑（假设脆弱性、数据片面性）

正文用 [content]...[/content] 包裹。
"""

DEBATE_REBUT_PMT = """\
你扮演 {role}。对手（{op_role}）已经发言：

[content]
{opponent}
[/content]

请基于研报证据逐条反驳，加强 {role} 立场。正文用 [content]...[/content] 包裹。
"""

DEBATE_JUDGE_PMT = """\
你是一位客观、理性的首席投资官。基于多方与空方全部发言，给出最终投资备忘录，
用 JSON 输出（三个反引号包裹）：

多方：
[content]
{bull}
[/content]

空方：
[content]
{bear}
[/content]

```
{{
    "recommendation": "overweight|neutral|underweight",
    "key_drivers": ["...", "..."],
    "key_risks": ["...", "..."],
    "conclusion": "5~8 句结论综述",
    "conclusion_evidences": ["引用具体数据或辩论结论", "..."]
}}
```
"""
