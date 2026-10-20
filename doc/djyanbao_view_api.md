# 洞见研报（djyanbao）文档预览接口分析

> 分析对象：`https://www.djyanbao.com/report/4514132`（研报详情 / 预览页）
> 方法：Chrome DevTools 网络抓包 + 前端打包产物（`index-DXu3nb2A.js`、`services-D2mwzmR1.js`、`reportDetail-*.js`、`PdfViewer-*.js`）逆向 + 浏览器环境实测请求
> 日期：2026-10-20
> 结论速览：网页端为 **React SPA + pdf.js**；预览 PDF 不是页面嵌入的静态文件，而是先调 `download/info` 接口换取一张**带签名、5 分钟有效**的 `storage.djyanbao.com` 直链，再由 pdf.js 整体拉取渲染。

---

## 1. 页面技术栈

| 项 | 值 |
| --- | --- |
| 前端框架 | React SPA（React 19.3.0，懒加载 chunk） |
| PDF 渲染 | pdf.js（`pdfjs-dist@6.1.200`，CDN 加载） |
| 主 bundle | `/assets/index-DXu3nb2A.js`（含 axios、pdf.js workerSrc） |
| 懒加载 chunk | `/assets/reportDetail--g-hKu_x.js`、`/assets/PdfViewer-gVfTryqH.js`、`/assets/services-D2mwzmR1.js`（API 封装） |
| API 网关 | `https://api.djyanbao.com/api`（axios `baseURL`） |
| 文件存储 | `https://storage.djyanbao.com`（对象存储，经 `u`/`t`/`token` 参数签名鉴权） |
| 统计 | `https://umami.djyanbao.com/api/collect`（umami） |

`PdfViewer` 组件加载 PDF（`PdfViewer-gVfTryqH.js`）：

```js
getDocument({
  url: fileUrl,
  cMapUrl: "https://cdn.jsdelivr.net/npm/pdfjs-dist@6.1.200/cmaps/",
  cMapPacked: true,
  standardFontDataUrl: "https://cdn.jsdelivr.net/npm/pdfjs-dist@6.1.200/standard_fonts/",
  disableRange: true,   // 禁用分片，整体下载
  disableStream: true,
  verbosity: 5 /* ERRORS */
});
```

> 注意 `disableRange:true` / `disableStream:true`：PDF 文件被**一次性整体**拉取，不支持（也不依赖）Range 分段请求。

---

## 2. 预览核心流程

```
前端打开 /report/{id}
        │
        ├─ ① GET  /api/report/{id}                                              → 报告详情（元数据，fileUrl 无签名）
        │
        ├─ ② GET  /api/report/{id}/download/info?action=view&format=pdf         → ★ 预览换取【签名直链】
        │         返回 { fileUrl: "https://storage.djyanbao.com/....pdf?u=..&t=..&token=..", validSeconds: 300 }
        │
        └─ ③ fetch fileUrl                                                     → pdf.js 渲染
           Content-Type: application/pdf, 约 1.4 MB, magic "%PDF-1.5"
```

前端代码原文（`reportDetail--g-hKu_x.js`）：

```js
let [e, n] = await Promise.all([m(t), i(t, { action: 'view', format: 'pdf' })]);
setDetail(e);
setFileUrl(n.fileUrl);   // fileUrl 即签名直链
```

---

## 3. 预览接口（核心）

### 3.1 获取预览直链

```
GET https://api.djyanbao.com/api/report/{id}/download/info
```

**Query 参数：**

| 参数 | 取值 | 必填 | 说明 |
| --- | --- | --- | --- |
| `action` | `view` \| `download` | 是 | `view`=在线预览；`download`=下载 |
| `format` | `pdf` \| `original` | 是 | `pdf`=转 PDF 预览；`original`=原格式 |

**成功响应（`action=view&format=pdf`）：**

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "fileUrl": "https://storage.djyanbao.com/<base64文件名>.pdf?u=<签名>&t=<时间戳>&token=<令牌>",
    "validSeconds": 300
  }
}
```

| 字段 | 说明 |
| --- | --- |
| `data.fileUrl` | PDF 签名直链，`https://storage.djyanbao.com/xxx.pdf?u=..&t=..&token=..`。**签名绑定有效时间，过期失效**，URL 不做明文 token 展示的落盘使用前需即时换取 |
| `data.validSeconds` | 签名有效期（秒）。实测为 `300`（5 分钟）。到期后再次访问 fileUrl 返回 401/403，需重新调本接口换取 |

**fileUrl 的存储签名参数（storage.djyanbao.com 直链）：**

| 参数 | 含义（推测） |
| --- | --- |
| `u` | 用户标识 / 权限上下文 |
| `t` | 时间戳（签名签发时间） |
| `token` | 一次性访问令牌（HMAC/CDN 签名） |

**直链下载响应特征（实测）：**

| 项 | 值 |
| --- | --- |
| HTTP Status | `200` |
| `Content-Type` | `application/pdf` |
| 文件头 | `%PDF-1.5` |
| 大小 | 1,466,163 B（与页面展示「1.4MB」一致） |

### 3.2 接口变体（实测行为）

| 请求 | 响应 | 说明 |
| --- | --- | --- |
| `action=view&format=pdf` | `code:0` + 签名直链 | 预览用 |
| `action=download&format=pdf` | `code:10002`「用户vip限额不足」（未购买/无配额时） | 下载入口，受 VIP 配额限制 |
| `action=view&format=original` | 400 Bad Request「非pdf格式仅支持action=download」 | 仅 PDF 支持在线预览，其他格式只能下载 |

> 结论：**网页端预览只看 PDF**。若报告原始为 Word/PPT，前端请求的是服务端转换后的 PDF 直链（对应 `POST /api/report/convert` 转换接口）。`original` 格式只能走 `action=download`。

---

## 4. 报告详情接口

```
GET https://api.djyanbao.com/api/report/{id}
```

**响应 `data` 主要字段：**

| 字段 | 说明 |
| --- | --- |
| `id` | 报告 ID（4514132） |
| `title` | 标题 |
| `orgName` | 机构名（开源证券） |
| `authors` | 作者数组 |
| `publishAt` | 发布时间（ISO 8601，UTC） |
| `fileSize` | 源文件字节数 |
| `pageTotal` | 总页数（12） |
| `fileUrl` | **无签名**的 storage 直链（与 §3.1 签名直链不同，仅元数据展示，`queryKeys=[]`） |
| `indexImageUrl` | 封面图 |
| `orgIds` | 机构 ID 数组（列表查询用） |
| `aiStatus` | AI 解读状态位（`&4` 表示有 AI 解读） |
| `canConvert` | 是否可转换 |
| `hasDownloaded` | 是否已下载 |
| `typeId` / `businessId` / `labelIds` / `targetIds` / `cards` | 分类 / 专题 / 标签 / 卡片等元数据 |

---

## 5. 鉴权与公共请求头

所有 `/api/*` 请求经 axios 实例统一注入（`services-D2mwzmR1.js`）：

```js
class Axios, headers: { "Content-Type": "application/json" }
axiosRequestHeaders: {
  "client-ver": "v2.0.14",
  "client-type": "pc",
  "client-id": <uuid | "scan_"+uuid>,   // localStorage 'uuid'；手机扫码登录时为 scan_ 前缀
  "Authorization": "Bearer <token>"     // localStorage 'token'，未登录不带
}
```

| Header | 来源 | 说明 |
| --- | --- | --- |
| `Authorization: Bearer <token>` | `localStorage['token']` | 登录令牌；USER 未登录时该 Header 缺失，预览接口返回 401 并触发「请先登录」弹窗 |
| `client-ver: v2.0.14` | 硬编码 | 客户端版本号（抓包看到 Vary 依赖该头，升级可能改变行为） |
| `client-type: pc` | 硬编码 | 平台标识 |
| `client-id` | `localStorage['uuid']`（一次生成并持久化） | 设备/访客 ID；扫码登录时为 `scan_<uuid>` |

> 未登录（无 `Authorization`）时，`download/info?action=view` 返回 401。预览本身需要**登录态**，即使报告免费，换取签名直链这一步也强制鉴权。

---

## 6. 错误码

前端统一错误码（`services-D2mwzmR1.js` 常量 `h`）：

| code | 常量名 | 含义 |
| --- | --- | --- |
| `0` | `SUCCESS` | 成功 |
| `10002` | `QUOTA_EXCEEDED` | 用户 VIP 限额不足（实测：`action=download` 未购买返回「用户vip限额不足」） |
| `10112` | `CONVERT_NO_QUOTA` | 转换无配额 |
| `10113` | `DOWNLOAD_LIMIT` | 下载达上限 |

HTTP 侧错误：401（未登录/令牌失效，触发登出并打开登录框）、403、429、500 等。前端 axios 响应拦截器对 `code!==0` 统一处理；`action=download` 的错误会联动打开支付/购买弹窗。

---

## 7. 报告详情页相关辅助接口

详情页同时会调用（分析时抓包实测）：

| 接口 | 方法 | 用途 |
| --- | --- | --- |
| `/api/auth/me` | GET | 当前用户信息 |
| `/api/report/view` | POST | 浏览上报，body `{ reportId }` |
| `/api/report/recommend` | POST | 相似推荐，body `{ userId, curReportId }` |
| `/api/report` | GET | 机构报告列表，params `{ orgIds, page, limit, sort, order }` |
| `/api/report/{id}/report-ai-analysis` | GET | AI 解读，params `{ all: true }`（`aiStatus & 4` 时拉取） |
| `/api/favorite/{id}` | GET | 收藏状态 |
| `/api/favorite/dictory/{dictId}/report/{reportId}` | POST | 加入收藏 |
| `/api/ad` | GET | 广告，params `{ position: 'report_detail_popup' \| 'report_detail' }` |

---

## 8. 其他（上传 / 转换 / 下载相关接口）

从 services 模块中可见的其余报告相关端点（供后续扩展下载工具参考）：

| 接口 | 方法 | 用途 |
| --- | --- | --- |
| `/api/report/convert` | GET | 转换，params 含 `reportId`（Word/PPT 转 PDF 等） |
| `/api/report/downloaded` | POST | 标记已下载 |
| `/api/report/downloaded` | GET | 已下载列表 |
| `/api/report/uploaded` | GET | 已上传列表 |
| `/api/report/hot/search` | GET | 热搜 |
| `/api/report` | POST | 上传报告（`name`、`ndbarchCode` 等） |
| `/api/oss/signature` | POST | 获取 OSS 直传签名（阿里云 OSS postObject） |
| `/api/vip/quota` | GET | VIP 配额 |

---

## 9. 分析备注

- 本次分析对象 `#4514132` 为开源证券研报，12 页、1.4 MB，实测签名直链 `storage.djyanbao.com` 下载一次约 0.4 s。
- `fileUrl` 有效期极短（`validSeconds=300`），**不可缓存落库后长期使用**；下载工具应在发起下载前即时换取并立即拉取。
- 预览 PDF 是服务端按需生成/转码后的产物，`pdfjs` 通过一次性 GET 完整取回；若需在工具中解析，直接 `GET fileUrl` 即得标准 PDF。
- 接口路径相对 `api.djyanbao.com/api`，全部为 JSON 封装：`{ code, message, data }`，axios 拦截器解包后业务只拿 `data`。