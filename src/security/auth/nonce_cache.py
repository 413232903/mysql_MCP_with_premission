"""Nonce 防重放缓存

单实例内存实现（TTL 淘汰 + 容量上限）。多实例部署时应替换为 Redis
等共享存储（接口保持 check_and_add 语义即可）。
"""
import threading
import time
from collections import OrderedDict
from typing import Optional


class NonceCache:
    """带 TTL 的一次性 Nonce 登记表"""

    def __init__(self, ttl: int = 600, maxsize: int = 100_000):
        self._ttl = ttl
        self._maxsize = maxsize
        # nonce -> 过期时刻（unix 秒）。TTL 恒定，过期时刻随插入顺序单调递增，
        # 因此从队首惰性淘汰即可
        self._seen: "OrderedDict[str, float]" = OrderedDict()
        self._lock = threading.Lock()

    def check_and_add(self, nonce: str, now: Optional[float] = None) -> bool:
        """nonce 未出现过则登记并返回 True；已存在（重放）返回 False"""
        now = time.time() if now is None else now
        with self._lock:
            self._evict_expired(now)
            if nonce in self._seen:
                return False
            if len(self._seen) >= self._maxsize:
                # 容量保护：丢弃最早登记的条目（极小概率缩短其防重放窗口）
                self._seen.popitem(last=False)
            self._seen[nonce] = now + self._ttl
            return True

    def _evict_expired(self, now: float) -> None:
        while self._seen:
            _, expires_at = next(iter(self._seen.items()))
            if expires_at > now:
                break
            self._seen.popitem(last=False)

    def __len__(self) -> int:
        with self._lock:
            return len(self._seen)
