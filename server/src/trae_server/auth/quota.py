"""滑动窗口限流与配额。"""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque


class QuotaTracker:
    """线程安全的滑动窗口配额跟踪。"""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        # user_id -> deque[timestamp]
        self._requests: dict[str, deque[float]] = defaultdict(deque)
        # user_id -> tokens consumed today
        self._tokens_today: dict[str, float] = defaultdict(float)
        self._day_marker: dict[str, int] = {}

    def _current_day(self) -> int:
        return int(time.time() // 86400)

    def check_request(self, user_id: str, rpm: int) -> bool:
        """检查过去 60 秒内是否超过 rpm。"""
        now = time.time()
        with self._lock:
            window = self._requests[user_id]
            while window and now - window[0] > 60:
                window.popleft()
            if len(window) >= rpm:
                return False
            window.append(now)
            return True

    def record_tokens(self, user_id: str, tokens: int, daily_limit: int) -> bool:
        """记录 token 消耗；若超限返回 False。"""
        if daily_limit <= 0:
            return True
        with self._lock:
            day = self._current_day()
            if self._day_marker.get(user_id) != day:
                self._day_marker[user_id] = day
                self._tokens_today[user_id] = 0
            if self._tokens_today[user_id] + tokens > daily_limit:
                return False
            self._tokens_today[user_id] += tokens
            return True


_tracker = QuotaTracker()


def check_quota(user_id: str, quota: dict) -> tuple[bool, str]:
    """统一配额入口：(ok, reason)。"""
    rpm = int(quota.get("requests_per_minute", 0))
    if rpm and not _tracker.check_request(user_id, rpm):
        return False, "rate_limited"

    tpd = int(quota.get("tokens_per_day", 0))
    # 这里只做配额记录判断；实际 token 消耗在调用完成后 record
    if tpd:
        # 乐观通过；具体 token 计量在 record_tokens
        pass
    return True, ""


def record_token_usage(user_id: str, tokens: int, quota: dict) -> bool:
    tpd = int(quota.get("tokens_per_day", 0))
    return _tracker.record_tokens(user_id, tokens, tpd)