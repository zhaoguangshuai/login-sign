# login-sign

批量自动登录签到工具，基于 Playwright 浏览器自动化 + Clash Verge 代理节点轮换，实现多账号自动登录、每日签到以及令牌自动管理。

目标网站：[https://cdn.xiavier.com](https://cdn.xiavier.com)（使用 Cloudflare Turnstile 验证）

---

## 目录

- [功能特性](#功能特性)
- [移交维护必改项](#移交维护必改项)
- [项目结构](#项目结构)
- [环境要求](#环境要求)
- [快速开始](#快速开始)
- [配置说明](#配置说明)
- [Excel 文件格式](#excel-文件格式)
- [令牌管理机制](#令牌管理机制)
- [代理节点轮换策略](#代理节点轮换策略)
- [完整执行流程](#完整执行流程)
- [失败处理](#失败处理)
- [clash_proxy.py 命令行用法](#clash_proxypy-命令行用法)
- [输出示例](#输出示例)
- [常见问题](#常见问题)

---

## 功能特性

- **批量登录签到**：从 Excel 读取账号密码，自动逐个登录并签到
- **Turnstile 验证**：自动等待 Cloudflare Turnstile 人机验证通过（最长 120 秒）
- **智能检测**：同时检测页面跳转和 Toast 消息，精准判断登录/失败/限流状态
- **限流自动重试**：检测到「请求次数过多」时自动切换代理节点并重试（最多 2 次）
- **令牌自动管理**：签到后检测用户令牌列表，为空时自动创建并将 key 写入 Excel
  - 自动创建 `特价-Codex-plus` 和 `awsq` 两个分组的令牌
  - 获取完整 key 并拼接 `sk-` 前缀后写入 Excel
- **余额查询统计**：每个账号签到后自动查询余额，最终汇总输出（含特殊账号单独统计）
- **Clash Verge 代理轮换**：
  - 执行前自动切换到「全局」模式，执行完后恢复「规则」模式
  - 按地区轮询切换节点（香港 → 台灣 → 獅城 → 日本 → 美國 → 澳門 → 英國 → 德國）
  - 同一地区内随机选取，不重复使用同一节点，所有节点用完后自动重置
- **失败记录导出**：失败账号（含失败原因）自动保存到带时间戳的 Excel 文件

---

## 移交维护必改项

> 如果将此脚本交给其他人维护，以下是**必须修改**的内容，其余均可保持默认。

### 1. 账号 Excel 文件路径（`login.py` 第 696 行）

```python
# login.py 底部 __main__ 块
EXCEL_PATH = "/Users/zhaoguangshuai/py/login-sign/login-info.xlsx"
```

修改为新机器上的实际路径，例如：

```python
EXCEL_PATH = "/home/yourname/login-sign/login-info.xlsx"
```

### 2. 失败记录输出路径（`login.py` 第 660 行）

```python
failed_excel_path = f"/Users/zhaoguangshuai/py/login-sign/failed_accounts_{timestamp}.xlsx"
```

同样需要改为新机器的实际路径：

```python
failed_excel_path = f"/home/yourname/login-sign/failed_accounts_{timestamp}.xlsx"
```

### 3. Clash API 密钥（`clash_proxy.py` 第 29 行）

```python
SECRET = "zhaoguangshuai"
```

改为新机器 Clash Verge 中配置的 API Secret：

```python
SECRET = "your_clash_secret"
```

在 Clash Verge 中查看路径：设置 → Clash 核心 → External Controller Secret。

### 4. Clash API 地址和代理组名（`clash_proxy.py` 第 28、33 行）

```python
CLASH_API = "http://127.0.0.1:9090"   # 如果 Clash Verge 改过端口，需同步修改
DEFAULT_GROUP = "GLOBAL"               # 代理组名称，需与 Clash 中一致
```

### 5. 可用节点列表（`login.py` 第 15-22 行，`clash_proxy.py` 第 36-43 行）

```python
CLASH_NODE_CANDIDATES = [
    "🇭🇰 香港 01", "🇭🇰 香港 02", ...
]
```

节点名称需与 Clash Verge 订阅中**完全一致**（包括 Emoji 旗帜和空格），否则切换会静默失败。可运行以下命令查看当前机器实际可用节点：

```bash
python3 clash_proxy.py list
```

### 6. 特殊账号余额统计（`login.py` 第 677 行）

```python
special_account = "tniub.cc@gmail.com"
```

这是余额统计中单独输出的账号，按需修改为你的主账号。

### 7. 账号 Excel 文件本身

`.gitignore` 已将 `*.xlsx` 排除在 Git 之外，文件**不会随代码一起同步**。需要手动将 `login-info.xlsx` 复制到新机器对应路径。

---

## 项目结构

```
login-sign/
├── login.py              # 主脚本：批量登录签到 + 令牌管理
├── clash_proxy.py        # Clash Verge 代理节点切换工具（可独立使用）
├── login-info.xlsx       # 账号数据文件（已被 .gitignore 忽略，不入库）
├── login-info1.xlsx      # 备用账号数据文件（已被 .gitignore 忽略，不入库）
├── .gitignore            # 忽略所有 .xlsx 文件
└── README.md
```

运行后还会在同目录生成：

```
failed_accounts_YYYYMMDD_HHMMSS.xlsx   # 有失败时自动生成，记录失败账号和原因
```

---

## 环境要求

- Python 3.10+
- [Clash Verge](https://github.com/clash-verge-rev/clash-verge-rev) 已安装并在后台运行
- Clash Verge External Controller（API）已开启，默认地址 `http://127.0.0.1:9090`

### 安装 Python 依赖

```bash
pip install playwright pandas requests openpyxl
playwright install chromium
```

### 验证 Clash API 是否可用

```bash
curl http://127.0.0.1:9090/version -H "Authorization: Bearer your_secret"
```

返回 JSON 表示 API 正常，否则检查 Clash Verge 的 External Controller 设置。

---

## 快速开始

### 1. 准备账号 Excel

创建 `login-info.xlsx`，第一行为表头，至少包含以下列：

| 账号 | 密码 | awsq-key-claude | codex-plus-key-gpt |
|------|------|-----------------|---------------------|
| user@example.com | password123 | （留空，脚本自动填充） | （留空，脚本自动填充） |

- **账号 / 密码**：必填
- **awsq-key-claude**：脚本自动写入 `awsq` 分组令牌 key（格式：`sk-xxx`）
- **codex-plus-key-gpt**：脚本自动写入 `特价-Codex-plus` 分组令牌 key（格式：`sk-xxx`）

其他列（如维护人、备注等）不影响脚本运行，可按需添加。

### 2. 确认 Clash Verge 配置

- Clash Verge 已在后台运行
- External Controller 已开启（设置 → Clash 核心 → External Controller）
- `clash_proxy.py` 中 `SECRET` 与 Clash 中配置的 Secret 一致
- 节点名称与订阅中实际节点名一致（用 `python3 clash_proxy.py list` 验证）

### 3. 运行脚本

```bash
python3 login.py
```

脚本会自动：
1. 将 Clash 切换到全局模式
2. 逐个处理 Excel 中的账号（登录 → 签到 → 令牌管理 → 查询余额）
3. 完成后将 Clash 恢复为规则模式
4. 输出余额统计汇总

---

## 配置说明

### login.py 顶部配置项

```python
USE_CLASH_AUTO_SWITCH = True    # 是否启用 Clash 代理自动切换（False = 完全不切换节点）
USE_CLASH_MODE_SWITCH = True    # 执行前切全局、执行后切回规则（False = 不修改 Clash 模式）
CLASH_SWITCH_INTERVAL = 10      # 每处理 N 个账号定期切换一次节点
CLASH_NODE_CANDIDATES = [...]   # 参与轮换的候选节点列表（名称需与 Clash 完全一致）
```

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| `USE_CLASH_AUTO_SWITCH` | 启用/关闭代理节点自动轮换 | `True` |
| `USE_CLASH_MODE_SWITCH` | 启用/关闭运行前后模式切换 | `True` |
| `CLASH_SWITCH_INTERVAL` | 按账号数量定期切换间隔 | `10` |
| `CLASH_NODE_CANDIDATES` | 候选节点列表 | 29 个节点 |
| `EXCEL_PATH`（`__main__`）| 账号 Excel 文件绝对路径 | 硬编码路径，**必须按机器修改** |

### clash_proxy.py 顶部配置项

```python
CLASH_API = "http://127.0.0.1:9090"   # Clash Verge API 地址（含端口）
SECRET = "zhaoguangshuai"              # API 鉴权密钥，必须与 Clash 配置一致
DEFAULT_GROUP = "GLOBAL"               # 切换节点时操作的代理组名称
```

---

## Excel 文件格式

脚本读写的列名为**中文表头**，大小写和空格需严格匹配：

| 列名 | 读/写 | 说明 |
|------|-------|------|
| `账号` | 读 | 登录用户名（邮箱或用户名） |
| `密码` | 读 | 登录密码 |
| `awsq-key-claude` | 写 | `awsq` 分组令牌，脚本自动填入 |
| `codex-plus-key-gpt` | 写 | `特价-Codex-plus` 分组令牌，脚本自动填入 |

> 如果需要增加令牌分组，修改 `login.py` 中的 `save_token_to_excel` 函数（第 404 行）和 `create_token` 的调用处（第 546、555 行）。

---

## 令牌管理机制

签到成功后（无论是首次签到还是今日已签到），脚本均会执行令牌管理流程：

```
签到完成
  └─ 获取用户令牌列表
       ├─ 已有令牌（≥1 个） → 跳过，处理下一个账号
       └─ 无令牌 → 自动创建
            ├─ 创建 特价-Codex-plus 令牌（name = 随机 4 位小写字母）
            ├─ 创建 awsq 令牌（name = 随机 4 位小写字母）
            ├─ 重新获取令牌列表以取得令牌 ID
            ├─ 逐个获取完整 key 值
            └─ 写入 Excel（带 sk- 前缀）：
                 特价-Codex-plus → codex-plus-key-gpt 列
                 awsq            → awsq-key-claude 列
```

---

## 代理节点轮换策略

采用**按地区轮询**策略，避免同一地区 IP 被频繁使用触发限流：

```
第1次切换：香港（随机选未用节点）→ 台灣 → 獅城 → 日本 → 美國 → 澳門 → 英國 → 德國
第2轮：    香港（排除已用节点再随机）→ 台灣 → ...
全部 29 个节点用完后自动重置池，重新开始
```

**触发切换的时机：**

| 触发条件 | 行为 |
|----------|------|
| 每处理 `CLASH_SWITCH_INTERVAL`（默认10）个账号 | 按地区顺序切换到下一个未使用节点 |
| 检测到「请求次数过多」限流 | 紧急切换节点，等待 5 秒后重试登录 |
| 签到 HTTP 请求失败 | 紧急切换节点 |

---

## 完整执行流程

```
启动
 ├── [可选] 切换 Clash 到全局模式
 ├── 读取 Excel 账号列表
 ├── 初始化 Clash NodeCycler，随机切换到第一个节点
 └── 逐个处理账号（最多 3 次登录重试）
      ├── 打开 Chromium 浏览器（非无痕，禁用 webdriver 特征）
      ├── 访问 https://cdn.xiavier.com/login
      ├── 填写账号 + 密码
      ├── 等待 Cloudflare Turnstile 自动验证通过（最长 120 秒）
      ├── 点击「继续」提交按钮
      ├── 轮询检测登录结果（最多 20 秒）
      │   ├── URL 跳转到 /console 或 /dashboard → 登录成功，提取 user_id 和 session cookie
      │   ├── Toast 含「成功」关键词 → 继续等待
      │   └── Toast 含错误信息 → 判断是否是限流，决定重试或直接失败
      ├── 调用签到 API（POST /api/user/checkin）
      ├── 令牌管理（见上节）
      ├── 查询账户余额（GET /api/user/self，quota / 500000 = 美元）
      ├── 关闭浏览器
      └── 等待 1 秒后处理下一个账号
 ├── 输出余额统计汇总
 ├── 失败账号保存到 failed_accounts_YYYYMMDD_HHMMSS.xlsx
 └── [可选] 切换 Clash 回规则模式
```

---

## 失败处理

- 以下情况会被记录为失败：
  - 登录失败（密码错误、账号封禁、Turnstile 超时等）
  - 签到请求 HTTP 错误
  - 查询余额失败
- 失败记录保存到 `failed_accounts_YYYYMMDD_HHMMSS.xlsx`，包含字段：

| 字段 | 说明 |
|------|------|
| 账号 | 用户名 |
| 密码 | 原始密码（便于排查） |
| 失败类型 | 登录失败 / 签到失败 / 查询余额失败 |
| 失败原因 | 具体错误信息或页面返回的错误文本 |

- 「今日已签到」**不会**被记录为失败

---

## clash_proxy.py 命令行用法

`clash_proxy.py` 可独立作为命令行工具使用：

```bash
# 列出当前代理组所有节点及当前选中节点
python3 clash_proxy.py list

# 切换到指定节点（节点名需加引号）
python3 clash_proxy.py switch "🇭🇰 香港 03"

# 测速后自动切换到延迟最低的节点
python3 clash_proxy.py best

# 切换到优选列表中的下一个节点
python3 clash_proxy.py next

# 测试指定节点的延迟（毫秒）
python3 clash_proxy.py delay "🇭🇰 香港 01"

# 查看当前代理模式（rule / global / direct）
python3 clash_proxy.py mode

# 切换到全局模式
python3 clash_proxy.py global

# 切换到规则模式
python3 clash_proxy.py rule
```

无参数运行时，自动执行：列出节点 → 测速 → 切换到最优节点。

---

## 输出示例

```
共读取到 4 个账号
[Clash] 代理节点自动切换已启用（随机不重复）
[Clash] 初始节点: 🇭🇰 香港 05

==================================================
处理账号 [1/4]: user@example.com
==================================================
正在通过浏览器登录...
正在加载登录页面...
正在填写账号: user@example.com
正在填写密码...
正在等待 Turnstile 验证...
验证完成！
正在点击继续按钮...
等待登录响应...
检测到已进入控制台，登录成功！
用户ID: 2558
✅ 登录成功
⚠️ 签到结果: 今日已签到
正在获取令牌列表...
✅ 已有 3 个令牌，跳过创建
💰 账号 user@example.com 当前余额: $3.14
等待 1 秒后处理下一个账号...

==================================================
处理完成！所有账号均登录并签到成功
==================================================

📊 账户余额统计（统计时间: 2026-06-07 10:30:00）
==================================================
🔑 tniub.cc@gmail.com 余额: $12.50
💰 其他 3 个账号总余额: $8.20
==================================================
```

---

## 常见问题

**Q: Turnstile 验证一直超时（120 秒后报错）**

Cloudflare 人机验证需要真实浏览器环境，确认：
- 使用了代理节点（开启了 `USE_CLASH_AUTO_SWITCH` 且 Clash 处于全局模式）
- 没有在虚拟机或 Docker 中运行（容器环境可能被识别）

**Q: 切换节点时提示「切换失败（可忽略）」**

这是非致命错误，通常是因为节点名称与订阅中的实际名称不完全匹配。运行 `python3 clash_proxy.py list` 核对节点名称后，更新 `CLASH_NODE_CANDIDATES` 列表。

**Q: 运行完成后 Clash 模式没有恢复为规则**

脚本在 `finally` 块中执行模式恢复，即使中途报错也会触发。如果恢复失败，手动在 Clash Verge 界面切换回「规则」模式即可。

**Q: Excel 文件中的 key 列没有写入**

检查 Excel 表头列名是否与代码中一致（区分大小写和空格）：`awsq-key-claude` 和 `codex-plus-key-gpt`。另外，Excel 文件不能在 WPS 或 Excel 中处于打开状态，否则写入会失败。

**Q: `failed_accounts_xxx.xlsx` 找不到**

文件生成路径硬编码在 `login.py` 第 660 行，请确认该路径在当前机器上存在且有写权限。

---

## License

MIT
