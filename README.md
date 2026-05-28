# login-sign

批量自动登录签到工具，基于 Playwright 浏览器自动化 + Clash Verge 代理节点轮换，实现多账号自动登录并完成每日签到。

## 功能特性

- **批量登录签到**：从 Excel 读取账号密码，自动逐个登录并签到
- **Turnstile 验证**：自动等待 Cloudflare Turnstile 人机验证通过
- **智能检测**：同时检测页面跳转和 Toast 消息，精准判断登录/失败/限流状态
- **限流自动重试**：检测到「请求次数过多」时自动切换代理节点并重试（最多 2 次）
- **Clash Verge 代理轮换**：
  - 按地区轮询切换节点（香港 → 台灣 → 獅城 → 日本 → 美國 → 澳門 → 英國 → 德國）
  - 同一地区内随机选取，不重复使用同一节点
  - 所有节点用完后自动重置池重新轮换
- **失败记录导出**：失败账号自动保存到带时间戳的 Excel 文件

## 项目结构

```
login-sign/
├── login.py              # 主脚本：批量登录签到
├── clash_proxy.py        # Clash Verge 代理节点切换工具
├── login-info.xlsx       # 账号数据（需自行准备）
├── old-login.py          # 旧版脚本备份（不使用代理）
├── README.md
└── proxy_pool/           # 备用免费代理池项目（已弃用）
```

## 环境要求

- Python 3.10+
- [Clash Verge](https://github.com/clash-verge-rev/clash-verge-rev) 已安装并运行
- Clash Verge API 已开启（默认 `http://127.0.0.1:9090`）

### Python 依赖

```bash
pip install playwright pandas requests
playwright install chromium
```

## 快速开始

### 1. 准备账号 Excel

创建 `login-info.xlsx`，包含以下列：

| 账号 | 密码 |
|------|------|
| your_username | your_password |

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

## 登录流程

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
共读取到 36 个账号
[Clash] 代理节点自动切换已启用（随机不重复）
[Clash] 初始节点: 🇭🇰 香港 02

==================================================
处理账号 [1/36]: zhoujiabao
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
用户ID: 2558
⚠️ 签到结果: 今日已签到
等待 1 秒后处理下一个账号...
```

## 失败处理

- 失败账号自动保存到 `failed_accounts_YYYYMMDD_HHMMSS.xlsx`
- 包含字段：账号、密码、失败类型（登录失败/签到失败）、失败原因
- 所有账号处理完毕后在终端输出汇总信息

## License

MIT
