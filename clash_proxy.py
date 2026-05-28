"""
Clash Verge 代理节点切换工具
============================
用于 Clash Verge 的代理节点自动切换，支持：
- 获取所有代理组和节点
- 切换到指定节点
- 测速并选择最优节点
- 节点轮换策略

可被 login.py 等签到脚本导入使用。

用法:
  python clash_proxy.py list          # 列出所有节点
  python clash_proxy.py switch <节点名> # 切换到指定节点
  python clash_proxy.py best           # 测速后切换到最优节点
  python clash_proxy.py next           # 切换到下一个优选节点
  python clash_proxy.py delay <节点名>  # 测试节点延迟
"""

import time
import random
import itertools
from typing import Optional, List

import requests

# ============ 配置（根据你的 Clash Verge 设置修改） ============
CLASH_API = "http://127.0.0.1:9090"
SECRET = "zhaoguangshuai"
HEADERS = {"Authorization": f"Bearer {SECRET}"}

# 默认代理组名称（在 Clash Verge 中查看你的代理组名）
DEFAULT_GROUP = "GLOBAL"

# 优选低延迟节点（按偏好排序）
PREFERRED_NODES = [
    "🇭🇰 香港 01", "🇭🇰 香港 02", "🇭🇰 香港 03", "🇭🇰 香港 04", "🇭🇰 香港 05",
    "🇹🇼 台灣 01", "🇹🇼 台灣 02", "🇹🇼 台灣 03", "🇹🇼 台灣 04", "🇹🇼 台灣 05",
    "🇸🇬 獅城 01", "🇸🇬 獅城 02", "🇸🇬 獅城 03", "🇸🇬 獅城 04", "🇸🇬 獅城 05",
    "🇯🇵 日本 01", "🇯🇵 日本 02", "🇯🇵 日本 03", "🇯🇵 日本 04", "🇯🇵 日本 05",
    "🇺🇸 美國 01", "🇺🇸 美國 02", "🇺🇸 美國 03", "🇺🇸 美國 04", "🇺🇸 美國 05",
    "🇲🇴 澳門 01", "🇬🇧 英國 01", "🇩🇪 德國 01", "🇺🇸 美國 001",
]


# ============ API 基础函数 ============

def get_proxies() -> dict:
    """获取所有代理节点信息"""
    r = requests.get(f"{CLASH_API}/proxies", headers=HEADERS, timeout=5)
    r.raise_for_status()
    return r.json()


def get_group_proxies(group_name: str = DEFAULT_GROUP) -> dict:
    """获取指定代理组的详细信息（含 all/now 等字段）"""
    r = requests.get(f"{CLASH_API}/proxies/{group_name}", headers=HEADERS, timeout=5)
    r.raise_for_status()
    return r.json()


def get_available_nodes(group_name: str = DEFAULT_GROUP) -> List[str]:
    """获取代理组下所有可用节点名称"""
    data = get_group_proxies(group_name)
    return data.get("all", [])


def get_current_node(group_name: str = DEFAULT_GROUP) -> Optional[str]:
    """获取当前正在使用的节点名称"""
    data = get_group_proxies(group_name)
    return data.get("now")


def switch_proxy(proxy_name: str, group_name: str = DEFAULT_GROUP) -> bool:
    """切换代理组的节点，成功返回 True"""
    r = requests.put(
        f"{CLASH_API}/proxies/{group_name}",
        headers=HEADERS,
        json={"name": proxy_name},
        timeout=5,
    )
    return r.status_code == 204


def get_proxy_delay(node_name: str, timeout_ms: int = 3000) -> int:
    """测试节点延迟（毫秒），超时或失败返回 9999"""
    try:
        r = requests.get(
            f"{CLASH_API}/proxies/{node_name}/delay",
            headers=HEADERS,
            params={
                "url": "http://www.gstatic.com/generate_204",
                "timeout": timeout_ms,
            },
            timeout=timeout_ms // 1000 + 1,
        )
        if r.status_code == 200:
            return r.json().get("delay", 9999)
    except requests.RequestException:
        pass
    return 9999


# ============ 高阶策略函数 ============

def switch_to_preferred(
    nodes: Optional[List[str]] = None, group: str = DEFAULT_GROUP
) -> str:
    """切换到优选节点列表中的下一个节点（轮换）"""
    if nodes is None:
        nodes = PREFERRED_NODES
    current = get_current_node(group)
    if current in nodes:
        idx = (nodes.index(current) + 1) % len(nodes)
        target = nodes[idx]
    else:
        target = nodes[0]
    switch_proxy(target, group)
    time.sleep(1)
    print(f"[Clash] 切换节点: {target}")
    return target


def get_best_node(
    candidates: Optional[List[str]] = None, group: str = DEFAULT_GROUP
) -> str:
    """从候选节点中选延迟最低的"""
    if candidates is None:
        candidates = PREFERRED_NODES
    delays = {}
    for node in candidates:
        delay = get_proxy_delay(node)
        delays[node] = delay
        print(f"[Clash] {node}: {delay}ms")
    best = min(delays, key=delays.get)
    print(f"[Clash] 最优节点: {best} ({delays[best]}ms)")
    return best


def switch_to_best(
    candidates: Optional[List[str]] = None, group: str = DEFAULT_GROUP
) -> str:
    """测速后切换到最优节点"""
    best = get_best_node(candidates, group)
    switch_proxy(best, group)
    time.sleep(1)
    return best


def list_nodes(group: str = DEFAULT_GROUP):
    """打印代理组的所有节点和当前选中节点"""
    data = get_group_proxies(group)
    all_nodes = data.get("all", [])
    now = data.get("now")
    print(f"\n代理组: {group}")
    print(f"当前节点: {now}")
    print(f"可用节点 ({len(all_nodes)}):")
    for node in all_nodes:
        marker = " ← 当前" if node == now else ""
        print(f"  - {node}{marker}")


# ============ 签到集成辅助类 ============

class NodeCycler:
    """节点循环器 —— 按地区轮询，每个地区内随机选取不重复节点。

    例如：香港 03 → 台灣 02 → 獅城 05 → 日本 01 → 美國 04 → ...
    同一地区内不会重复选同一个节点，所有地区轮完后重置。

    用法:
        cycler = NodeCycler(switch_interval=3)
        for i, account in enumerate(accounts):
            cycler.tick()
            cycler.maybe_switch()
            if rate_limited:
                cycler.emergency_switch()
    """

    REGION_ORDER = ["香港", "台灣", "獅城", "日本", "美國", "澳門", "英國", "德國"]

    def __init__(
        self,
        nodes: Optional[List[str]] = None,
        switch_interval: int = 3,
        group: str = DEFAULT_GROUP,
    ):
        self.switch_interval = switch_interval
        self.group = group
        self._counter = 0
        self._current_node: Optional[str] = None
        self._region_nodes: dict[str, list[str]] = self._build_region_map(nodes)
        self._used: dict[str, set] = {r: set() for r in self._region_nodes}
        self._region_cycle = itertools.cycle(self._region_nodes.keys())

    @staticmethod
    def _build_region_map(nodes: Optional[List[str]]) -> dict[str, list[str]]:
        raw = nodes or PREFERRED_NODES
        region_map: dict[str, list[str]] = {}
        for node in raw:
            region = None
            for key in NodeCycler.REGION_ORDER:
                if key in node:
                    region = key
                    break
            if region is None:
                region = "其他"
            region_map.setdefault(region, []).append(node)
        ordered = {r: region_map[r] for r in NodeCycler.REGION_ORDER if r in region_map}
        if "其他" in region_map:
            ordered["其他"] = region_map["其他"]
        return ordered

    def _pick_next(self) -> str:
        for _ in range(len(self._region_nodes)):
            region = next(self._region_cycle)
            nodes = self._region_nodes[region]
            unused = [n for n in nodes if n not in self._used[region]]
            if unused:
                node = random.choice(unused)
                self._used[region].add(node)
                return node
        self._used = {r: set() for r in self._region_nodes}
        return self._pick_next()

    def tick(self):
        self._counter += 1

    def maybe_switch(self) -> Optional[str]:
        if self._counter > 0 and self._counter % self.switch_interval == 0:
            return self._do_switch("[Clash] 切换节点")
        return None

    def emergency_switch(self) -> str:
        return self._do_switch("[Clash] 限流切换节点")

    def _do_switch(self, label: str) -> str:
        self._current_node = self._pick_next()
        print(f"{label} -> {self._current_node}")
        switch_proxy(self._current_node, self.group)
        time.sleep(random.uniform(1, 2))
        return self._current_node


# ============ 命令行入口 ============

if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        cmd = sys.argv[1]
        if cmd == "list":
            list_nodes()
        elif cmd == "switch" and len(sys.argv) > 2:
            node_name = sys.argv[2]
            ok = switch_proxy(node_name)
            print(f"{'✅' if ok else '❌'} 切换{'成功' if ok else '失败'}")
            if ok:
                print(f"当前节点: {get_current_node()}")
        elif cmd == "best":
            switch_to_best()
            print(f"当前节点: {get_current_node()}")
        elif cmd == "next":
            switch_to_preferred()
            print(f"当前节点: {get_current_node()}")
        elif cmd == "delay" and len(sys.argv) > 2:
            delay = get_proxy_delay(sys.argv[2])
            print(f"{sys.argv[2]}: {delay}ms")
        else:
            print("用法:")
            print("  python clash_proxy.py list              # 列出所有节点")
            print("  python clash_proxy.py switch <节点名>    # 切换到指定节点")
            print("  python clash_proxy.py best              # 测速后切换到最优节点")
            print("  python clash_proxy.py next              # 切换到下一个优选节点")
            print("  python clash_proxy.py delay <节点名>     # 测试节点延迟")
    else:
        # 无参数：列出节点 → 测速 → 切换到最优
        print("=== Clash 节点自动切换 ===")
        list_nodes()
        print("\n正在测速选择最优节点...")
        switch_to_best()
        print(f"\n已切换到最优节点: {get_current_node()}")
