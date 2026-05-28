# Clash Verge 节点自动切换指南

> 适用场景：Python 脚本批量签到时，自动切换 Clash 代理节点以规避限流。
> Clash Verge外部控制器监听地址：127.0.0.1:9090
> Clash Verge外部控制api访问密钥：zhaoguangshuai
---

## 方法一：通过 Clash API 切换（推荐）

Clash Verge 内置了 RESTful API，可以直接用 Python 控制。

**前置准备**：在 Clash Verge「设置 → 外部控制」中找到端口号（默认 `9090`）和 API Secret。

```python
import requests

CLASH_API = "http://127.0.0.1:9090"
SECRET = "your_secret"  # 在 Clash Verge 设置里查看
HEADERS = {"Authorization": f"Bearer {SECRET}"}

def get_proxies():
    """获取所有代理节点"""
    r = requests.get(f"{CLASH_API}/proxies", headers=HEADERS)
    return r.json()

def switch_proxy(group_name: str, proxy_name: str):
    """切换代理组的节点"""
    r = requests.put(
        f"{CLASH_API}/proxies/{group_name}",
        headers=HEADERS,
        json={"name": proxy_name}
    )
    return r.status_code == 204

def get_available_nodes(group_name: str = "Google"):
    """获取代理组下所有可用节点"""
    r = requests.get(f"{CLASH_API}/proxies/{group_name}", headers=HEADERS)
    data = r.json()
    return data.get("all", [])

# 示例：切换到台湾 04
switch_proxy("Google", "台灣 04")
```

---

## 方法二：签到脚本中集成自动切换

```python
import requests
import time
import itertools

CLASH_API = "http://127.0.0.1:9090"
SECRET = "your_secret"
HEADERS = {"Authorization": f"Bearer {SECRET}"}

# 优选低延迟节点（香港04=64ms、台湾04=111ms 较优）
PREFERRED_NODES = ["香港 04", "香港 05", "台灣 01", "台灣 04", "台灣 05"]

def switch_proxy(node_name: str):
    requests.put(
        f"{CLASH_API}/proxies/Google",
        headers=HEADERS,
        json={"name": node_name}
    )
    time.sleep(1)  # 等待切换生效

def get_proxy_delay(node_name: str):
    """测试节点延迟"""
    r = requests.get(
        f"{CLASH_API}/proxies/{node_name}/delay",
        headers=HEADERS,
        params={"url": "http://www.gstatic.com/generate_204", "timeout": 3000}
    )
    if r.status_code == 200:
        return r.json().get("delay", 9999)
    return 9999

def checkin_with_auto_switch(accounts: list):
    node_pool = itertools.cycle(PREFERRED_NODES)

    for i, account in enumerate(accounts):
        # 每 3 个账号切换一次节点
        if i % 3 == 0:
            next_node = next(node_pool)
            print(f"切换节点 -> {next_node}")
            switch_proxy(next_node)

        try:
            result = do_checkin(account)  # 你的签到逻辑
            print(f"账号 {account} 签到成功")
        except RateLimitError:
            # 被限流时立即切换
            print("触发限流，紧急切换节点...")
            switch_proxy(next(node_pool))
            time.sleep(3)
            do_checkin(account)  # 重试

        time.sleep(2)  # 每次签到间隔

# 运行
accounts = ["account1", "account2", "..."]  # 你的账号列表
checkin_with_auto_switch(accounts)
```

---

## 方法三：切换前先测速，选最优节点

```python
def get_best_node():
    """从候选节点中选延迟最低的"""
    candidates = PREFERRED_NODES
    delays = {}
    for node in candidates:
        delays[node] = get_proxy_delay(node)
        print(f"{node}: {delays[node]}ms")

    best = min(delays, key=delays.get)
    print(f"最优节点: {best} ({delays[best]}ms)")
    return best

# 每次运行脚本前先选最优节点
best_node = get_best_node()
switch_proxy(best_node)
```

---

## 查看 API 端口的方法

在 Clash Verge 里依次进入：**设置 → 外部控制**，即可看到端口号和 Secret。

---

## 推荐策略

| 策略 | 说明 |
|------|------|
| 分批切换 | 每签到 3~5 个账号切换一次节点 |
| 限流触发切换 | 捕获限流异常后立即切换并重试 |
| 随机延迟 | 加入 `time.sleep(random.uniform(1, 3))` 模拟人工操作 |
| 测速优选 | 每次运行前测速，优先选延迟最低的节点 |

> **提示**：以上策略可以组合使用，效果更佳。
