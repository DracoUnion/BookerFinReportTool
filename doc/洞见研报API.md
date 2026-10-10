# 洞见研报小程序 · HTTP 接口文档

> 本文档通过分析小程序编译产物（`app-service.js` 及各页面 JS）中所有 `this.request(...)` 调用自动梳理生成。

## 通用说明

### 请求封装

所有业务接口通过 Vue 混入 `requestAjax` 调用：

```js
this.request(path, method, params, success, fail)
```

- **Base URL**：`https://api.djyanbao.com/api/`（普通用户）或 `https://api-wxaplus.djyanbao.com/api/`（plus 用户，依据 appId 判断）
- 完整 URL = Base URL + `path`
- `params` 以 JSON 放入请求体（`Content-Type: application/json`）
- **请求头**：
  - `Authorization: Bearer <token>`（token 取自本地 storage）
  - `client-ver: v2.1.0`
  - `client-type: <clientType>`

### 响应信封

后端统一返回对象：

```json
{
  "code": 0,        // 0 = 成功；非 0 = 失败
  "message": "ok",  // 错误时为提示文案；成功时通常为 "ok"
  "data": { ... }   // 业务数据
}
```

- 客户端判成功通常依据 `code === 0`（或 `message === "ok"`），失败时弹 `message`。
- 特殊错误码（示例）：`30001`（余额不足/支付失败），`10002`（未购买/无权限）。
- HTTP 状态码：`200/201` 成功；`401` 未授权跳转登录；`403` 账号注销或禁用。

### 分页参数约定

列表接口普遍支持：`page`（页码，从 1 起）、`limit`（每页条数）。

### 方法枚举

`method` 取值：`GET`、`POST`、`PUT`、`DELETE`（源码小写 `get/post/put/delete`，运行时不区分大小写）。

---

## 接口清单

### 认证 · auth

#### 1. 获取当前用户信息
- **URL**：`/api/auth/me`
- **方法**：`GET`
- **请求参数**：无
- **返回**：`data` 含用户信息（如 `userLevel`，取值 `NONE`/`VIP`/`SVIP`/`SHARED_VIP`）
- **用途**：登录后拉取用户信息，判断 VIP 等级并写入 storage。

#### 2. 微信登录
- **URL**：`/api/auth/login/wechat`
- **方法**：`POST`
- **请求参数**：
  | 字段 | 类型 | 说明 |
  |---|---|---|
  | `type` | string | `wx_miniprogram` 或 `wechat_miniprogram` |
  | `oauthType` | string | `wx_miniprogram`（部分调用） |
  | `code` | string | 微信授权 code |
  | `encryptedData` | string | 加密数据（可为 `""`） |
  | `encryptIv` | string | 加密向量（可为 `""`） |
  | `inviteCode` | string | 邀请码 |
  | `channel` | string | 渠道 |
- **返回**：`data` 含登录结果（token 等）。

#### 3. 手机验证码登录
- **URL**：`/api/auth/login/mobile`
- **方法**：`POST`
- **请求参数**：`channel`、`inviteCode`、`code`（验证码）、`mobile`
- **返回**：登录结果。

#### 4. 密码登录
- **URL**：`/api/auth/login`
- **方法**：`POST`
- **请求参数**：`channel`、`inviteCode`、`password`、`phone`
- **返回**：登录结果。

#### 5. Apple 登录
- **URL**：`/api/auth/login/apple`
- **方法**：`POST`
- **请求参数**：`state`、`email`、`scope`（默认空），并合并用户身份字段
- **返回**：登录结果。

#### 6. 微信 App 登录（内嵌 App）
- **URL**：`/api/auth/login/wechatapp`
- **方法**：`POST`
- **请求参数**：合并 `authResult`（授权结果对象）
- **返回**：登录结果。

#### 7. 百度小程序登录
- **URL**：`/api/auth/login/baidu`
- **方法**：`POST`
- **请求参数**：`oauthType`(`baidu_miniprogram`)、`code`、`encryptedData`、`encryptIv`、`inviteCode`、`channel`
- **返回**：登录结果。

#### 8. 扫码登录
- **URL**：`/api/auth/login/scan`
- **方法**：`POST`
- **请求参数**：`scene`、`redirect`
- **返回**：扫码登录结果。

#### 9. 绑定手机号
- **URL**：`/api/auth/wechat/bind/phone`
- **方法**：`POST`
- **请求参数**：`t`（含 code/encryptedData/iv 等授权数据）
- **返回**：绑定结果。

#### 10. 更新授权信息
- **URL**：`/api/auth/{oauthType}/update/info`（`oauthType` 动态）
- **方法**：`POST`
- **请求参数**：`code`、`encryptedData`、`encryptIv`
- **返回**：更新结果。

#### 11. 修改密码
- **URL**：`/api/auth/password`
- **方法**：`PUT`
- **请求参数**：`password`
- **返回**：`code`/`message`。

#### 12. 退出登录
- **URL**：`/api/auth/logout`
- **方法**：`POST`
- **请求参数**：无
- **返回**：`code`/`message`。

#### 13. 生成 MA 活码（二维码）
- **URL**：`/api/auth/ma/qrcode`
- **方法**：`GET`
- **请求参数**：`page`（如 `pages/index/shareMiddle`）、`scene`（如 `id={reportId}&inviteCode={code}`）
- **返回**：二维码内容。

#### 14. MA H5 支付短信下发
- **URL**：`/api/auth/ma/pay/h5/send`
- **方法**：`POST`
- **请求参数**：`orderNo`
- **返回**：`code`/`message`。

---

### 研报 · report

> 列表/详情接口的查询参数由筛选器（`filter`/`popupFilter`）动态拼装，可能包含以下字段的组合：`q`（搜索词）、`title`（仅标题搜索）、`matchPhrase`（关键词不分词）、`typeIds`（行业/机构）、`orgIds`、`labelIds`、`businessIds`、`sort`（如 `publish_at`）、`order`（`DESC`）、`page`、`limit`、`paid`。

#### 15. 研报列表 / 搜索
- **URL**：`/api/report`
- **方法**：`GET`
- **请求参数**：上述组合参数（`page`、`limit`、`q`、`sort`、`order` 等）
- **返回**：`data` 为研报数组（含 `id`、`title`、`img`、`cards` 等）；`data.data` 为列表本体。

#### 16. 研报详情
- **URL**：`/api/report/{reportId}`
- **方法**：`GET`
- **请求参数**：路径参数 `reportId`
- **返回**：`data` 含 `title`、`cards`、`indexImageUrl` 等。

#### 17. 研报正文内容
- **URL**：`/api/report/{reportId}/content`
- **方法**：`GET`
- **请求参数**：路径参数 `reportId`
- **返回**：`data.content`（正文文本）。

#### 18. 研报下载信息
- **URL**：`/api/report/{reportId}/download/info`
- **方法**：`GET`
- **请求参数**：路径参数 `reportId`；`action`（如 `view`）
- **返回**：`code`、`message`；成功时 `data.fileUrl` 为 PDF 下载地址。错误码 `10002` 表示无权限。

#### 19. 浏览记录（读/写）
- **URL**：`/api/report/view`
- **方法**：`GET`（历史浏览列表）/ `POST`（上报浏览进度）
- **请求参数**：
  - GET：`page`、`limit`
  - POST：`reportId`、`progress`（初始为 `0`）
- **返回**：GET 返回浏览记录列表；POST 返回 `code`/`message`。

#### 20. 浏览记录条数
- **URL**：`/api/report/view/count`
- **方法**：`GET`
- **请求参数**：无
- **返回**：`data` 为条数。

#### 21. 已下载报告列表
- **URL**：`/api/report/downloaded`
- **方法**：`GET`
- **请求参数**：`page`、`limit`
- **返回**：`data` 为已下载研报列表。

#### 22. 已下载研报条数
- **URL**：`/api/report/downloaded/count`
- **方法**：`GET`
- **请求参数**：无
- **返回**：`data` 为条数。

#### 23. 周排行榜
- **URL**：`/api/report/rank/week`
- **方法**：`GET`
- **请求参数**：无
- **返回**：`data` 为排行榜列表。

#### 24. 月排行榜
- **URL**：`/api/report/rank/month`
- **方法**：`GET`
- **请求参数**：无
- **返回**：`data` 为排行榜列表。

---

### 图表 / 资讯 · chart & article & analyst & organization

#### 25. 图表研报列表
- **URL**：`/api/chart`
- **方法**：`GET`
- **请求参数**：筛选器拼装的组合参数（`page`、`limit` 及筛选字段）
- **返回**：`data` 为列表；VIP 限制下 `page>=10` 触发升级提示。

#### 26. 资讯（新闻）列表
- **URL**：`/api/article`
- **方法**：`GET`
- **请求参数**：`page`、`limit`
- **返回**：`data` 为资讯列表。

#### 27. 资讯详情
- **URL**：`/api/article/{articleId}`
- **方法**：`GET`
- **请求参数**：路径参数 `articleId`
- **返回**：`data.content`（正文）。

#### 28. 分析师列表
- **URL**：`/api/analyst`
- **方法**：`GET`
- **请求参数**：`limit`（金研/普通研分别为 10/20）、`isGolden`（是否金牌，可选）、`q`（分析师名搜索，可选）
- **返回**：`data.data` 为分析师列表。

#### 29. 机构列表
- **URL**：`/api/organization`
- **方法**：`GET`
- **请求参数**：`hot`（热门机构）或 `q`、`page`、`limit`、`order`、`paid`、`reportQuery`（可选）
- **返回**：`data` / `data.data` 为机构列表。

#### 30. 分类（全部）
- **URL**：`/api/category/all`
- **方法**：`GET`
- **请求参数**：无
- **返回**：`data` 含 `DOC_TYPE`、`KEYWORD_BUSINESS`、`KEYWORD_HOT` 等分类字典。

#### 31. 一级分类
- **URL**：`/api/category/l1`
- **方法**：`GET`
- **请求参数**：`type`（如 `DOC_BUSINESS`）
- **返回**：`data` 为一级分类列表。

---

### 收藏 · favorite

#### 32. 收藏目录（文件夹）树
- **URL**：`/api/favorite/dictory`
- **方法**：`GET`（查询）/ `POST`（新建文件夹）
- **请求参数**：
  - GET：`level`（层级 1/2/3…）、`parentId`（可选）
  - POST：`level`、`name`（文件夹名）、`parentId`
- **返回**：`data` 为目录列表或新建结果。

#### 33. 目录下的研报列表
- **URL**：`/api/favorite/dictory/{dictoryId}/report`
- **方法**：`GET`
- **请求参数**：`limit`、`page`
- **返回**：`data.data` 为该目录下收藏的研报（`data.report.title` 等）。

#### 34. 收藏研报到目录
- **URL**：`/api/favorite/dictory/{dictoryId}/report/{reportId}`
- **方法**：`POST`（收藏）/ `DELETE`（取消收藏）
- **请求参数**：POST 可带 `rating`；DELETE 无
- **返回**：`message`（`ok` 成功）/ `code`。

#### 35. 目录操作
- **URL**：`/api/favorite/dictory/{dictoryId}`
- **方法**：`DELETE`（删除文件夹）/ `PUT`（重命名，`{ name }`）
- **返回**：`code`（`0` 成功）。

#### 36. 收藏研报（快捷）
- **URL**：`/api/favorite/report/{reportId}`
- **方法**：`DELETE`（取消收藏）
- **返回**：`code`/`message`。

#### 37. 收藏条数
- **URL**：`/api/favorite/report/count`
- **方法**：`GET`
- **请求参数**：无
- **返回**：`data` 为条数。

#### 38. 收藏研报 ID 列表
- **URL**：`/api/favorite/reportIds`
- **方法**：`GET`
- **请求参数**：无
- **返回**：`data` 为 reportId 数组。

---

### 订单 / 支付 · order & paid-report & commodity

#### 39. 创建订单
- **URL**：`/api/order/create`
- **方法**：`POST`
- **请求参数**：`commodityType`（如 `dj_report`、`dj_vip`、`dj_svip`、`dj_vip0`）、`commodityId`、`couponId`（可选）
- **返回**：`data.orderNo`（订单号）、`data.id`（Apple 渠道）。

#### 40. 发起支付
- **URL**：`/api/order/{orderNo}/pay`
- **方法**：`POST`
- **请求参数**：`payType`（如 `balance`、`wxpay`）、`payChannel`（如 `NATIVE`、`JSAPI`）
- **返回**：`code`（`30001` = 余额/支付异常）、`message`、`data`（微信支付参数）。

#### 41. 查询订单
- **URL**：`/api/order/{orderNo}`
- **方法**：`GET`
- **请求参数**：路径参数 `orderNo`
- **返回**：`data.orderStatus`（如 `paid`）等，用于轮询支付结果。

#### 42. 商品列表
- **URL**：`/api/commodity`
- **方法**：`GET`
- **请求参数**：`types`（如 `dj_vip,dj_svip,dj_vip0`）
- **返回**：`data` 为商品列表（含 `type`、`id`、价格等）。

#### 43. 付费研报列表
- **URL**：`/api/paid-report`
- **方法**：`GET`
- **请求参数**：筛选器组合参数（`page`、`limit` 及筛选字段）
- **返回**：`data` 为付费研报列表。

#### 44. 付费研报详情
- **URL**：`/api/paid-report/{reportId}`
- **方法**：`GET`
- **请求参数**：路径参数 `reportId`
- **返回**：`data` 含标题、信息等。

#### 45. 创建付费研报订单
- **URL**：`/api/paid-report/order`
- **方法**：`POST`
- **请求参数**：`deliveryType`（`电子版`）、`reportId`
- **返回**：`data` 含 `reportOrderId`。

#### 46. 更新付费订单收件信息
- **URL**：`/api/paid-report/order/{reportOrderId}`
- **方法**：`PUT`
- **请求参数**：`email`、`phone`
- **返回**：`code`/`message`。

---

### 钱包 / VIP · wallet & vip

#### 47. 钱包余额
- **URL**：`/api/wallet/balance`
- **方法**：`GET`
- **请求参数**：无
- **返回**：`data` 为余额信息。

#### 48. 余额流水
- **URL**：`/api/wallet/balance/log`
- **方法**：`GET`
- **请求参数**：`order`（`DESC`）、`page`、`limit`
- **返回**：`data` 为流水列表。

#### 49. VIP 额度
- **URL**：`/api/vip/quota`
- **方法**：`GET`
- **请求参数**：无
- **返回**：`data` 为 VIP 下载/查看额度信息。

---

### 社区 / 活动 · community & task

#### 50. 社区活动列表
- **URL**：`/api/community`
- **方法**：`GET`
- **请求参数**：无
- **返回**：`data` 为活动列表。

#### 51. 社区活动详情
- **URL**：`/api/community/{activityId}`
- **方法**：`GET`
- **请求参数**：路径参数 `activityId`
- **返回**：`data` 含 `hasBuy`、商品信息等。

#### 52. 社区活动购买状态
- **URL**：`/api/community/{activityId}/me`
- **方法**：`GET`
- **请求参数**：路径参数 `activityId`
- **返回**：`data.groupCode` 等购买凭证。

#### 53. 任务列表
- **URL**：`/api/task`
- **方法**：`GET`
- **请求参数**：`platform`（`mobile`）
- **返回**：`data` 为任务列表。

---

### 用户 / 画像 / 邀请 · user

#### 54. 用户额外信息
- **URL**：`/api/user/extra`
- **方法**：`GET`
- **请求参数**：`field`（如 `wxwork_added`）
- **返回**：`data` 为对应字段值。

#### 55. 事件上报
- **URL**：`/api/user/event`
- **方法**：`POST`
- **请求参数**：`event`
- **返回**：`code`/`message`。

#### 56. 提交用户画像（问卷）
- **URL**：`/api/user/portrait`
- **方法**：`POST`
- **请求参数**：`profession`（职业）、`organization`（机构）、`job`、`education`（学历）、`email`
- **返回**：`code`/`message`。

#### 57. 画像填写状态
- **URL**：`/api/user/portrait/status`
- **方法**：`GET`
- **请求参数**：无
- **返回**：`data` 为是否已填写。

#### 58. 邀请码
- **URL**：`/api/user/invite/code`
- **方法**：`GET`
- **请求参数**：无
- **返回**：`data` 为邀请码。

#### 59. 被邀请人列表
- **URL**：`/api/user/invited`
- **方法**：`GET`
- **请求参数**：`page`、`limit`
- **返回**：`data` 为被邀请人列表。

#### 60. 注销账号
- **URL**：`/api/user/logoff`
- **方法**：`POST`
- **请求参数**：`reason`
- **返回**：`code`/`message`。

#### 61. 公众号关注状态
- **URL**：`/api/user/mp/follow/status`
- **方法**：`GET`
- **请求参数**：无
- **返回**：`data` 为关注状态布尔。

---

### 广告 / 短信 / 远程配置 / 企微 · ad & sms & remote_config & qx

#### 62. 广告位（单条）
- **URL**：`/api/ad`
- **方法**：`GET`
- **请求参数**：`position`（如 `mobile_report_list`）
- **返回**：`data` 为广告素材。

#### 63. 广告位（批量）
- **URL**：`/api/ad/batch`
- **方法**：`GET`
- **请求参数**：`position`（如 `miniprogram_home`）
- **返回**：`data` 为广告素材列表。

#### 64. 短信验证码
- **URL**：`/api/sms/verifyCode`
- **方法**：`POST`
- **请求参数**：`mobile`
- **返回**：`code`/`message`。

#### 65. 远程配置
- **URL**：`/api/remote_config`
- **方法**：`GET`
- **请求参数**：无
- **返回**：`data` 为配置键值。

#### 66. 企业微信活码
- **URL**：`/api/qx/wxwork/qrcode`
- **方法**：`GET`
- **请求参数**：无
- **返回**：`data` 为企微二维码。

---

### 订阅消息 · subscribe

#### 67. 订阅模板
- **URL**：`/api/subscribe`
- **方法**：`GET`（查询可用模板）/ `POST`（选择订阅）
- **请求参数**：
  - GET：`type`（`mp_template`）
  - POST：`type`（`mp_template`）、`businessIds`
- **返回**：`data` 为模板列表或订阅结果。

---

## 附录：非业务直连 URL

以下请求绕过 `requestAjax`，直接调用 `wx.request`（非业务接口，此处仅作记录）：

| URL | 方法 | 说明 |
|---|---|---|
| `https://storage.djyanbao.com/dj-static/wxma/case_list.json` | GET | 案例列表静态 JSON |
| `https://storage.djyanbao.com/dj-static/app-pkgs/app_stores.config` | GET | App 商店配置 |
| `this.protocolUrl` | GET | 用户协议全文 |
| `this.privacyUrl` | GET | 隐私政策全文 |

> 另有微信开放能力链接 `https://mp.weixin.qq.com/s/...`（公众号文章外链），非业务 API。

---

*文档基于编译产物静态分析生成，参数标注为源码中出现的字段；动态拼装参数（列表筛选类）已合并列示。*
