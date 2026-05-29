# login-sign

批量自动登录签到工具，基于 Playwright 浏览器自动化 + Clash Verge 代理节点轮换，实现多账号自动登录、每日签到以及令牌自动管理。

## 功能特性

- **批量登录签到**：从 Excel 读取账号密码，自动逐个登录并签到
- **Turnstile 验证**：自动等待 Cloudflare Turnstile 人机验证通过
- **智能检测**：同时检测页面跳转和 Toast 消息，精准判断登录/失败/限流状态
- **限流自动重试**：检测到「请求次数过多」时自动切换代理节点并重试（最多 2 次）
- **令牌自动管理**：签到后自动检测用户令牌列表，为空时自动创建并写入 Excel
  - 自动创建 `特价-Codex-plus` 和 `awsq` 两个分组的令牌
  - 获取完整 key 并拼接 `sk-` 前缀后写入 Excel
- **Clash Verge 代理轮换**：
  - 按地区轮询切换节点（香港 → 台灣 → 獅城 → 日本 → 美國 → 澳門 → 英國 → 德國）
  - 同一地区内随机选取，不重复使用同一节点
  - 所有节点用完后自动重置池重新轮换
- **失败记录导出**：失败账号自动保存到带时间戳的 Excel 文件

## 项目结构

```
login-sign/
├── login.py              # 主脚本：批量登录签到 + 令牌管理
├── clash_proxy.py        # Clash Verge 代理节点切换工具
├── login-info.xlsx       # 账号数据文件
├── login-info1.xlsx      # 账号数据文件
├── .gitignore
└── README.md
```

## 环境要求

- Python 3.10+
- [Clash Verge](https://github.com/clash-verge-rev/clash-verge-rev) 已安装并运行
- Clash Verge API 已开启（默认 `http://127.0.0.1:9090`）

### Python 依赖

```bash
pip install playwright pandas requests openpyxl
playwright install chromium
```

## 快速开始

### 1. 准备账号 Excel

创建 `login-info.xlsx`，包含以下列：

| 账号 | 密码 | awsq-key-claude | codex-plus-key-gpt | 维护人 |
|------|------|-----------------|--------------------|--------|
| your_username | your_password | （留空，脚本自动填充） | （留空，脚本自动填充） | |

- **账号 / 密码**：必填
- **awsq-key-claude**：脚本自动写入 `awsq` 分组令牌 key（带 `sk-` 前缀）
- **codex-plus-key-gpt**：脚本自动写入 `特价-Codex-plus` 分组令牌 key（带 `sk-` 前缀）
- **维护人**：可选

### 2. 配置 Clash Verge

确保 Clash Verge 已启动，且 API 设置如下：

- **API 地址**：`http://127.0.0.1:9090`
- **Secret**：在 `clash_proxy.py` 中修改 `SECRET` 变量
- **代理模式**：切换到「全局」模式

在 Clash Verge 的「设置 → Clash API」中确认以上配置。

### 3. 运行脚本

```bash
python3 login.py
```

## 配置说明

### login.py 配置项

```python
USE_CLASH_AUTO_SWITCH = True          # 是否启用 Clash 代理自动切换
CLASH_SWITCH_INTERVAL = 10            # 每处理 N 个账号切换一次节点
CLASH_NODE_CANDIDATES = [             # 可用代理节点列表
    "🇭🇰 香港 01", "🇭🇰 香港 02", ...
]
```

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| `USE_CLASH_AUTO_SWITCH` | 启用/关闭代理切换 | `True` |
| `CLASH_SWITCH_INTERVAL` | 定期切换间隔（账号数） | `10` |
| `CLASH_NODE_CANDIDATES` | 候选节点列表 | 29 个节点 |
| `EXCEL_PATH` | 账号 Excel 路径 | `login-info.xlsx` |

### clash_proxy.py 配置项

```python
CLASH_API = "http://127.0.0.1:9090"   # Clash Verge API 地址
SECRET = "your_secret"                 # API 鉴权密钥
DEFAULT_GROUP = "GLOBAL"               # 代理组名称
```

## 令牌管理机制

签到成功后（无论是新签到还是今日已签到），脚本会自动执行令牌管理流程：

```
签到成功
  └─ 获取用户令牌列表
       ├─ 已有令牌 → 跳过（处理下一个用户）
       └─ 无令牌 → 创建两个令牌
            ├─ 特价-Codex-plus（name=随机4字母）
            ├─ awsq（name=随机4字母）
            ├─ 重新获取令牌列表获取 ID
            ├─ 获取每个令牌的完整 key
            └─ 写入 Excel：
                 特价-Codex-plus → codex-plus-key-gpt 列 (sk-xxx)
                 awsq           → awsq-key-claude 列 (sk-xxx)
```

## 代理节点轮换策略

脚本采用**按地区轮询**策略，避免同一地区的 IP 被频繁使用：

```
香港 03 → 台灣 02 → 獅城 05 → 日本 01 → 美國 04 → 澳門 01 → 英國 01 → 德國 01
→ 香港 02 → 台灣 05 → 獅城 01 → 日本 04 → 美國 02 → ...
```

**规则：**

1. 按固定地区顺序轮转：香港 → 台灣 → 獅城 → 日本 → 美國 → 澳門 → 英國 → 德國
2. 每次到达某地区时，从该地区**未使用过**的节点中随机选取一个
3. 同一轮内同一节点不会被重复使用
4. 所有 29 个节点用完后自动重置，重新开始轮换

**触发切换的时机：**

| 触发条件 | 行为 |
|----------|------|
| 每处理 10 个账号 | 切换到下一个地区的未使用节点 |
| 登录时检测到「请求次数过多」 | 紧急切换到另一个未使用节点，等待 5 秒后重试 |
| 签到请求 HTTP 错误 | 紧急切换节点 |

## 完整流程

```
启动
 ├── 读取 Excel 账号列表
 ├── 初始化 Clash 代理（随机选取第一个节点）
 └── 逐个处理账号
      ├── 打开 Chromium 浏览器
      ├── 访问 https://cdn.xiavier.com/login
      ├── 填写账号密码
      ├── 等待 Cloudflare Turnstile 验证通过
      ├── 点击「继续」按钮
      ├── 轮询检测结果（最多 20 秒）
      │   ├── URL 跳转到 /console → 登录成功
      │   ├── Toast 显示「登录成功」→ 继续等待跳转
      │   └── Toast 显示错误信息 → 判断是否限流
      ├── 限流时切换节点重试（最多 2 次）
      ├── 获取 Session Cookie
      ├── 调用签到 API
      ├── 令牌管理
      │   ├── 获取令牌列表
      │   ├── 无令牌时自动创建并进行写入 Excel
      │   └── 已有令牌则跳过
      ├── 关闭浏览器
      └── 等待 1 秒后处理下一个
```

## clash_proxy.py 命令行用法

```bash
# 列出所有节点
python3 clash_proxy.py list

# 切换到指定节点
python3 clash_proxy.py switch "🇭🇰 香港 03"

# 测速后切换到最优节点
python3 clash_proxy.py best

# 切换到下一个节点
python3 clash_proxy.py next

# 测试节点延迟
python3 clash_proxy.py delay "🇭🇰 香港 01"
```

## 输出示例

```
共读取到 4 个账号
[Clash] 代理节点自动切换已启用（随机不重复）
[Clash] 初始节点: 🇭🇰 香港 05

==================================================
处理账号 [1/4]: zhoujiabao
==================================================
正在通过浏览器登录...
正在加载登录页面...
正在填写账号: zhoujiabao
正在填写密码...
正在等待 Turnstile 验证...
验证完成！
正在点击继续按钮...
找到提交按钮: 继续
等待登录响应...
检测到已进入控制台，登录成功！
用户ID: 2558
✅ 登录成功
⚠️ 签到结果: 今日已签到
正在获取令牌列表...
✅ 已有 3 个令牌，跳过创建
等待 1 秒后处理下一个账号...

==================================================
处理账号 [2/4]: 一路向北
==================================================
正在通过浏览器登录...
✅ 登录成功
用户ID: 3030
✅ 签到成功: 签到成功
正在获取令牌列表...
令牌列表为空，正在创建令牌...
正在创建 特价-Codex-plus 令牌 (name=xzrn)...
✅ 特价-Codex-plus 令牌创建成功
正在创建 awsq 令牌 (name=tacw)...
✅ awsq 令牌创建成功
正在获取最新令牌列表...
正在获取令牌 key (ID=4656, group=awsq)...
获取到 key: 3oMVd... 写入: sk-3oMVd...
✅ 已将 awsq 令牌 key 保存到 awsq-key-claude 列
正在获取令牌 key (ID=4655, group=特价-Codex-plus)...
获取到 key: 012ij... 写入: sk-012ij...
✅ 已将 特价-Codex-plus 令牌 key 保存到 codex-plus-key-gpt 列
等待 1 秒后处理下一个账号...
```

## 失败处理

- 失败账号自动保存到 `failed_accounts_YYYYMMDD_HHMMSS.xlsx`
- 包含字段：账号、密码、失败类型（登录失败/签到失败）、失败原因
- 所有账号处理完毕后在终端输出汇总信息

## License

MIT
