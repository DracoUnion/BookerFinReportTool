# BookerFinReportTool

基于 OpenAI 兼容 API 的财务报告命令行工具。

## 安装

```bash
pip install git+https://github.com/DracoUnion/BookerFinReportTool.git
```

安装后提供两个等价的命令：`fin-report` 和 `BookerFinReportTool`。

## 配置 API

```bash
export OPENAI_API_KEY="sk-..."
export OPENAI_BASE_URL="https://api.openai.com/v1"
export OPENAI_CHAT_MODEL="gpt-4o-mini"
```

## 用法

```bash
fin-report -h
fin-report report.pdf
```

本工具没有子命令，所有参数均为全局参数，参见 `fin-report -h`。

项目主页：<https://github.com/DracoUnion/BookerFinReportTool>
