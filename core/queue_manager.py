"""
Installation Queue Manager for OrbiSend.
Manages an ordered queue of PKG installations with thread-safe operations,
reordering, and automatic patch chaining (Base Game -> Patch -> DLC).
"""
import threading
import time
from collections import deque, defaultdict
from dataclasses import dataclass, field, asdict
from typing import Optional, List, Dict, Any


@dataclass
class QueueItem:
    """Represents a single package in the installation queue."""
    file_path: str
    file_id: str
    title: str
    title_id: str
    category: str
    version: str
    file_size: int
    icon_base64: Optional[str] = None
    status: str = "pending"  # "pending", "installing", "completed", "failed"
    added_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        """Converts the QueueItem to a serializable dictionary."""
        return asdict(self)


class InstallQueue:
    """Thread-safe installation queue with ordering and chaining support."""

    CATEGORY_PRIORITY = {
        "Base Game": 0,
        "gd": 0,
        "Update / Patch": 1,
        "gp": 1,
        "Add-on / DLC": 2,
        "ac": 2,
        "System App": 3,
        "gda": 3,
        "Digital Edition": 4,
        "gde": 4,
    }

    def __init__(self):
        self._queue: deque[QueueItem] = deque()
        self._lock = threading.Lock()

    def add(self, item: QueueItem) -> None:
        """Add an item to the end of the queue."""
        with self._lock:
            self._queue.append(item)

    def add_many(self, items: List[QueueItem]) -> None:
        """Add multiple items to the queue."""
        with self._lock:
            for item in items:
                self._queue.append(item)

    def remove(self, file_id: str) -> bool:
        """Remove an item by file_id. Returns True if found and removed."""
        with self._lock:
            for item in self._queue:
                if item.file_id == file_id:
                    self._queue.remove(item)
                    return True
            return False

    def peek(self) -> Optional[QueueItem]:
        """Look at the next item without removing it."""
        with self._lock:
            if self._queue:
                return self._queue[0]
            return None

    def pop_next(self) -> Optional[QueueItem]:
        """Remove and return the next item from the front of the queue."""
        with self._lock:
            if self._queue:
                return self._queue.popleft()
            return None

    def reorder(self, file_id: str, new_index: int) -> bool:
        """
        Move an item with file_id to new_index (0-based).
        Returns True if successful, False if item not found.
        """
        with self._lock:
            target_item = None
            for item in self._queue:
                if item.file_id == file_id:
                    target_item = item
                    break

            if target_item is None:
                return False

            self._queue.remove(target_item)
            # Bound index safely
            idx = max(0, min(new_index, len(self._queue)))
            self._queue.insert(idx, target_item)
            return True

    def get_item(self, file_id: str) -> Optional[QueueItem]:
        """Find and return an item by file_id without removing it."""
        with self._lock:
            for item in self._queue:
                if item.file_id == file_id:
                    return item
            return None

    def contains(self, file_id: str) -> bool:
        """Check if an item with file_id is in the queue."""
        with self._lock:
            return any(item.file_id == file_id for item in self._queue)

    def get_all(self) -> List[Dict[str, Any]]:
        """Return all items as a list of dicts (for JSON API)."""
        with self._lock:
            return [item.to_dict() for item in self._queue]

    def size(self) -> int:
        """Return the number of items in the queue."""
        with self._lock:
            return len(self._queue)

    def clear(self) -> None:
        """Remove all items from the queue."""
        with self._lock:
            self._queue.clear()

    @staticmethod
    def chain_packages(items: List[QueueItem]) -> List[QueueItem]:
        """
        Sort a list of QueueItems so that for each game (title_id):
        1. Base Game comes first (priority 0)
        2. Updates / Patches come next, sorted ascending by version (priority 1)
        3. Add-ons / DLCs come last (priority 2)

        Items sharing the same title_id are clustered together in discovery order.
        Items without a title_id are kept at the end.
        """
        if not items:
            return []

        # Step 1: Cluster items by title_id while preserving title discovery order
        groups: Dict[str, List[QueueItem]] = defaultdict(list)
        order_of_titles: List[str] = []

        for item in items:
            tid = (item.title_id or "").strip().upper()
            if not tid:
                tid = f"__NO_TITLE_ID_{item.file_id}__"
            if tid not in groups:
                order_of_titles.append(tid)
            groups[tid].append(item)

        # Step 2: Sort each group by priority and version
        result: List[QueueItem] = []

        for tid in order_of_titles:
            group = groups[tid]

            def sort_key(q_item: QueueItem):
                prio = InstallQueue.CATEGORY_PRIORITY.get(q_item.category, 9)
                # Parse version like "01.00" or fallback to string
                ver = q_item.version or "00.00"
                return (prio, ver, q_item.title)

            sorted_group = sorted(group, key=sort_key)
            result.extend(sorted_group)

        return result