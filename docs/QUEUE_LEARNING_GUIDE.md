# 🎮 Enhanced Installation Queue — Guided Learning Plan

> **You are the developer.** I'm your mentor. This plan breaks the feature into bite-sized Python lessons. You'll write every line — I'll explain the concepts, review your code, and guide you through tricky spots.

---

## 📋 Feature Overview

| Feature | Description |
|---------|-------------|
| **Installation Queue** | Add PKGs to a queue and install them one-by-one automatically |
| **Patch Chaining** | Auto-order: Base Game → Patch → DLC (grouped by `title_id`) |
| **Select All + Batch Add** | Checkbox-based multi-select with "Add Selected to Queue" button |
| **Dashboard Sorting** | Sort packages by Name, File Size, Type/Category, or Title ID (Asc/Desc) |

---

## 🗺️ Roadmap (6 Lessons)

```
Lesson 1 ──► Lesson 2 ──► Lesson 3 ──► Lesson 4 ──► Lesson 5 ──► Lesson 6
Data Model   Wire to App  API Routes   Auto-Advance  Patch Chain  UI (Queue & Sort)
```

---

## 🔀 Git Setup (Do This First!)

Before writing any code, create your feature branch:

```fish
cd ~/Projects/"PS4 PKG Sender"
git checkout develop
git checkout -b feature/installation-queue
```

Each lesson ends with a commit. This way you can always go back if something breaks.

---

## 📖 Lesson 1: The Queue Data Model

### 🧠 Concept: Python `collections.deque`

Right now, your app tracks **one task** with `self.active_task` (a single `dict`). A queue needs an **ordered list** of items where you:
- **Append** to the end (enqueue)
- **Pop** from the front (dequeue)
- **Remove** from anywhere (cancel)

Python has the perfect data structure for this: **`collections.deque`** (double-ended queue).

```python
from collections import deque

# deque is like a list, but optimized for append/pop from both ends
q = deque()
q.append("game1")    # Add to back  → deque(['game1'])
q.append("game2")    # Add to back  → deque(['game1', 'game2'])
q.popleft()          # Remove front  → 'game1',  deque(['game2'])
q.appendleft("game0") # Add to front → deque(['game0', 'game2'])
```

### ✏️ Exercise: Create `core/queue_manager.py`

Create a new file `core/queue_manager.py`. Here's what you need to build:

1. A `QueueItem` dataclass to represent one queued package
2. An `InstallQueue` class that wraps a `deque`

**Skeleton to fill in:**

```python
"""
Installation Queue Manager for OrbiSend.
Manages an ordered queue of PKG installations with thread-safe operations.
"""
import threading
from collections import deque
from dataclasses import dataclass, field
from typing import Optional
import time

@dataclass
class QueueItem:
    """Represents a single package in the installation queue."""
    file_path: str          # Full path to the .pkg file
    file_id: str            # MD5-based file ID for the streaming server
    title: str              # Game title from param.sfo
    title_id: str           # e.g., "CUSA03173"
    category: str           # "Base Game", "Update / Patch", "Add-on / DLC"
    version: str            # Package version
    file_size: int          # Size in bytes
    icon_base64: Optional[str] = None  # Base64-encoded icon
    status: str = "pending" # "pending", "installing", "completed", "failed"
    added_at: float = field(default_factory=time.time)

    # YOUR TASK: Add a method called `to_dict` that converts this
    # dataclass to a regular dictionary (for JSON serialization).
    # Hint: Look up `dataclasses.asdict()` or write it manually.


class InstallQueue:
    """Thread-safe installation queue with ordering support."""

    def __init__(self):
        self._queue: deque[QueueItem] = deque()
        self._lock = threading.Lock()

    # YOUR TASK: Implement these methods:

    def add(self, item: QueueItem) -> None:
        """Add an item to the end of the queue."""
        # Hint: Use self._lock to make it thread-safe
        # Hint: Use self._queue.append()
        pass

    def remove(self, file_id: str) -> bool:
        """Remove an item by file_id. Returns True if found and removed."""
        # Hint: deque doesn't have .remove() by value easily.
        # Strategy: rebuild the deque without that item.
        pass

    def peek(self) -> Optional[QueueItem]:
        """Look at the next item WITHOUT removing it."""
        # Hint: self._queue[0] if queue is not empty
        pass

    def pop_next(self) -> Optional[QueueItem]:
        """Remove and return the next item from the front."""
        # Hint: self._queue.popleft()
        pass

    def reorder(self, file_id: str, new_index: int) -> bool:
        """Move an item to a new position in the queue."""
        # Advanced! Strategy: remove it, then insert at new_index
        pass

    def get_all(self) -> list[dict]:
        """Return all items as a list of dicts (for the API)."""
        pass

    def size(self) -> int:
        """Return the number of items in the queue."""
        pass

    def clear(self) -> None:
        """Remove all items from the queue."""
        pass
```

### 🧪 Test Yourself

After implementing, you should be able to run this in a Python shell:

```python
from core.queue_manager import QueueItem, InstallQueue

q = InstallQueue()
item = QueueItem(
    file_path="/home/abde/Documents/PKG/game.pkg",
    file_id="abc123",
    title="Bloodborne",
    title_id="CUSA03173",
    category="Base Game",
    version="01.00",
    file_size=1024*1024*100
)
q.add(item)
print(q.size())       # Should print: 1
print(q.peek().title)  # Should print: Bloodborne
```

### 💾 Commit When Done

```fish
git add core/queue_manager.py
git commit -m "feat(queue): add QueueItem dataclass and InstallQueue data structure"
```

---

## 📖 Lesson 2: Wire the Queue into AppState

### 🧠 Concept: Composition

Your `AppState` class in `app.py` (lines 45-62) currently has `self.active_task = None` (a single dict). You'll **keep** `active_task` (it tracks the *currently installing* package), but **add** the queue as a new attribute.

### ✏️ Exercise: Modify `app.py`

1. **Import** your new module at the top of `app.py`:
   ```python
   from core.queue_manager import QueueItem, InstallQueue
   ```

2. **Add** the queue to `AppState.__init__`:
   ```python
   self.install_queue = InstallQueue()
   ```

3. **Add a helper method** to `AppState` that creates a `QueueItem` from a file path:
   ```python
   def make_queue_item(self, file_path: str) -> QueueItem:
       """Parse a PKG and create a QueueItem from it."""
       # YOUR TASK:
       # 1. Parse the PKG metadata using PKGParser.parse_pkg()
       # 2. Generate the file_id using hashlib.md5()
       # 3. Register the package with self.stream_server
       # 4. Create and return a QueueItem with all the metadata
       pass
   ```

**Why a helper method?** The same "parse + hash + register" logic is already in your `/api/install` endpoint (lines 316-340 of app.py). By extracting it to a method, you follow the **DRY principle** (Don't Repeat Yourself). Later, both "install now" and "add to queue" will use this.

### 💾 Commit

```fish
git add app.py
git commit -m "feat(queue): integrate InstallQueue into AppState"
```

---

## 📖 Lesson 3: Queue API Endpoints

### 🧠 Concept: REST API Design

You need new HTTP endpoints for the frontend to interact with the queue:

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/api/queue/add` | Add one or more packages to queue |
| `POST` | `/api/queue/remove` | Remove a package from queue |
| `GET` | `/api/queue` | Get current queue contents |
| `POST` | `/api/queue/clear` | Clear the entire queue |
| `POST` | `/api/queue/reorder` | Move an item to new position |
| `POST` | `/api/queue/start` | Begin processing the queue |

### ✏️ Exercise: Add Endpoints to `WebDashboardHandler`

In `app.py`, add these routes. Here's the first one as an example — **you implement the rest**:

```python
# In do_POST(), add BEFORE the final 404 response:

if path == "/api/queue/add":
    paths = payload.get("paths", [])
    if not paths:
        # Single file fallback
        p = payload.get("path")
        if p:
            paths = [p]

    added = []
    for p in paths:
        if not os.path.isfile(p):
            continue
        item = state.make_queue_item(p)
        state.install_queue.add(item)
        added.append(item.to_dict())

    self.send_json({"status": "success", "added": added, "queue_size": state.install_queue.size()})
    return

# YOUR TASK: Implement these endpoints:
# - POST /api/queue/remove  (expects {"file_id": "..."})
# - GET  /api/queue         (returns all queue items — goes in do_GET!)
# - POST /api/queue/clear
# - POST /api/queue/reorder (expects {"file_id": "...", "new_index": 2})
# - POST /api/queue/start   (triggers queue processing — we'll wire this in Lesson 4)
```

**IMPORTANT:** Don't forget to add the `GET /api/queue` handler in the `do_GET` method, not `do_POST`!

### 💾 Commit

```fish
git add app.py
git commit -m "feat(queue): add REST API endpoints for queue management"
```

---

## 📖 Lesson 4: Auto-Advance (The Queue Engine)

### 🧠 Concept: State Machine + Threading

This is the **brain** of the queue. When one installation finishes, the queue should automatically start the next one. This is a **state machine**:

```
┌─────────┐    start     ┌────────────┐   complete   ┌──────────┐
│  IDLE   │ ──────────►  │ INSTALLING │ ──────────►  │ ADVANCE  │
└─────────┘              └────────────┘              └──────┬───┘
                              ▲                            │
                              │       next item            │
                              └────────────────────────────┘
                                     (if queue not empty)
```

### ✏️ Exercise: Add `_queue_worker` to `AppState`

```python
def start_queue_processing(self):
    """Start processing the installation queue."""
    # YOUR TASK:
    # 1. Check if queue is empty → return early
    # 2. Check if already processing → return early  (add self._queue_running flag)
    # 3. Set self._queue_running = True
    # 4. Start a daemon thread that runs self._queue_worker
    pass

def _queue_worker(self):
    """Background worker that processes the queue one item at a time."""
    # YOUR TASK (pseudocode to guide you):
    #
    # while self._queue_running:
    #     item = self.install_queue.peek()
    #     if item is None:
    #         self._queue_running = False
    #         break
    #
    #     # Mark item as "installing"
    #     item.status = "installing"
    #
    #     # Build the install URL (same logic as /api/install):
    #     server_ip = self.config.get("server_ip") or NetworkManager.get_local_ip_for_target(...)
    #     port = self.config.get("server_port", 8080)
    #     url = f"http://{server_ip}:{port}/pkg/{item.file_id}.pkg"
    #
    #     # Call self.ps4.install([url]), start_task(), resume_task()
    #     # Set self.active_task (same dict structure as /api/install builds)
    #     # Start PS4 polling: self.start_ps4_polling(task_id)
    #
    #     # WAIT for completion (poll until done)
    #     while item.status == "installing":
    #         if self.active_task and not self.active_task.get("running", True):
    #             item.status = "completed"
    #             self.install_queue.pop_next()  # remove completed item
    #         time.sleep(2.0)
    #
    #     # Loop continues → picks up next item from queue
    pass

def stop_queue_processing(self):
    """Stop the queue after current item finishes."""
    self._queue_running = False
```

### Key Python Concepts Here:
- **Daemon threads**: `daemon=True` means the thread dies when the main program exits
- **Polling loop**: We check every 2 seconds if the current install is done
- **Thread-safe flags**: `self._queue_running` is a simple bool (safe for single-writer scenarios)

**WARNING:** The tricky part is detecting completion. Your existing progress endpoint already sets `state.active_task["running"] = False` when done (line 257 of app.py). Your worker can check this flag.

### 💾 Commit

```fish
git add app.py
git commit -m "feat(queue): add background queue worker with auto-advance"
```

---

## 📖 Lesson 5: Patch Chaining (Smart Ordering)

### 🧠 Concept: Sorting with Custom Keys

PS4 games have a strict install order:
1. **Base Game** (`category = "gd"` → "Base Game") — must install first
2. **Update / Patch** (`category = "gp"` → "Update / Patch") — install second, sorted by version
3. **Add-on / DLC** (`category = "ac"` → "Add-on / DLC") — install last

All parts of the same game share the same `title_id` (e.g., `CUSA03173`).

### ✏️ Exercise: Add `chain_packages` to `InstallQueue`

```python
@staticmethod
def chain_packages(items: list[QueueItem]) -> list[QueueItem]:
    """
    Sort a list of QueueItems so that for each title_id:
    Base Game comes first, then Patches (sorted by version), then DLC.
    """
    # YOUR TASK:
    #
    # Step 1: Group items by title_id
    #   from collections import defaultdict
    #   groups = defaultdict(list)
    #   for item in items:
    #       groups[item.title_id].append(item)
    #
    # Step 2: For each group, sort by priority:
    #   PRIORITY = {"Base Game": 0, "Update / Patch": 1, "Add-on / DLC": 2}
    #   sorted_group = sorted(group, key=lambda x: (PRIORITY.get(x.category, 9), x.version))
    #
    # Step 3: Flatten all groups back into a single list
    #   result = []
    #   for title_id, group in groups.items():
    #       result.extend(sorted_group)
    #
    # Return the sorted list
    pass
```

### Python Concepts:
- **`defaultdict`**: A dict that auto-creates a default value for missing keys
- **`sorted()` with `key`**: Custom sort using a lambda function
- **Tuple sorting**: `(0, "01.00")` < `(1, "01.05")` — Python compares tuples element by element

### 🧪 Test

```python
items = [
    QueueItem(..., title="BB DLC", title_id="CUSA03173", category="Add-on / DLC", version="01.00", ...),
    QueueItem(..., title="BB Patch", title_id="CUSA03173", category="Update / Patch", version="01.09", ...),
    QueueItem(..., title="Bloodborne", title_id="CUSA03173", category="Base Game", version="01.00", ...),
]
ordered = InstallQueue.chain_packages(items)
# Should be: [Bloodborne (Base), BB Patch (Update), BB DLC (DLC)]
```

### Wire It Up

In the `/api/queue/add` endpoint, when adding multiple items at once, apply chaining:

```python
if len(added) > 1:
    if payload.get("auto_chain", True):
        # Re-sort the queue using chain_packages
        pass
```

### 💾 Commit

```fish
git add core/queue_manager.py app.py
git commit -m "feat(queue): add automatic patch chaining by title_id and category"
```

---

## 📖 Lesson 6: Frontend UI (Select All, Queue Panel & Dashboard Sorting)

### 🧠 Concept: Alpine.js Reactivity & Client-Side vs Server-Side Sorting

Your dashboard uses **Alpine.js** for reactivity. Key patterns:
- `x-data` → defines reactive state
- `x-model` → two-way binding (checkboxes, dropdowns!)
- `x-for` → loop rendering
- `@click` → event handlers

In this lesson, you'll build the full UI experience: batch selection, the queue panel, and **interactive sorting** by Name, Size, Type, or Title ID!

---

### ✏️ Exercise: Add to `web/index.html`

#### **Part A: Add Selection & Sorting State**

In your `app()` function, add these new reactive state variables and methods:

```javascript
// Selection state
selectedPkgs: [],      // Array of file paths currently checked
selectAll: false,      // Select all toggle

// Sorting state
sortBy: 'title',       // 'title', 'file_size', 'category', 'title_id'
sortAsc: true,         // true = Ascending (A-Z, Small-to-Large), false = Descending

// Queue state
queue: [],             // Queue items from API
queueRunning: false,   // Is queue currently installing?
showQueue: false,      // Show/hide queue sidebar panel

// Methods:
toggleSelectAll() {
    // YOUR TASK:
    // If selectAll is true → this.selectedPkgs = this.filteredPackages().map(p => p.file_path)
    // If false → this.selectedPkgs = []
},

toggleSortDirection() {
    this.sortAsc = !this.sortAsc;
},

addSelectedToQueue() {
    // YOUR TASK:
    // POST /api/queue/add with {paths: this.selectedPkgs, auto_chain: true}
    // Then refresh queue: await this.fetchQueue()
    // Clear selection: this.selectedPkgs = []; this.selectAll = false;
},

async fetchQueue() {
    // YOUR TASK:
    // GET /api/queue → update this.queue
},

async startQueue() {
    // YOUR TASK:
    // POST /api/queue/start
}
```

---

#### **Part B: Update `filteredPackages()` to Support Sorting**

Right now, `filteredPackages()` only filters by search query and category. Enhance it to sort the filtered list!

```javascript
filteredPackages() {
    // 1. Filter packages (your existing logic)
    let list = this.packages.filter(p => {
        const matchesSearch = !this.searchQuery ||
            (p.title && p.title.toLowerCase().includes(this.searchQuery.toLowerCase())) ||
            (p.title_id && p.title_id.toLowerCase().includes(this.searchQuery.toLowerCase())) ||
            (p.filename && p.filename.toLowerCase().includes(this.searchQuery.toLowerCase()));
        const matchesCategory = this.categoryFilter === 'all' || p.category === this.categoryFilter;
        return matchesSearch && matchesCategory;
    });

    // 2. YOUR TASK: Sort the filtered list
    return list.sort((a, b) => {
        let valA = a[this.sortBy] ?? '';
        let valB = b[this.sortBy] ?? '';

        let cmp = 0;
        if (typeof valA === 'string') {
            cmp = valA.localeCompare(valB, undefined, { numeric: true, sensitivity: 'base' });
        } else {
            // Numbers (e.g., file_size)
            cmp = valA - valB;
        }

        return this.sortAsc ? cmp : -cmp;
    });
}
```

> [!TIP]
> **JavaScript vs Python Sorting Comparison:**
> - In Python: `list.sort(key=lambda x: x['title'], reverse=not sort_asc)`
> - In JavaScript: `array.sort((a, b) => cmp)` where negative means `a < b`, positive means `a > b`.
> - Notice how `localeCompare()` handles string sorting cleanly in JS just like `<` does in Python!

---

#### **Part C: Add Sort Controls to the Dashboard**

In `web/index.html` (inside the Search & Filters container, around line 197), add the Sort By dropdown and Sort Direction toggle button:

```html
<!-- Sort By Dropdown -->
<select x-model="sortBy"
        class="bg-darkbg border border-darkborder rounded-xl px-3 py-2 text-sm text-gray-300 focus:outline-none focus:border-brand-500 font-medium">
  <option value="title">Sort by Name</option>
  <option value="file_size">Sort by Size</option>
  <option value="category">Sort by Type</option>
  <option value="title_id">Sort by Title ID</option>
</select>

<!-- Sort Direction Toggle Button -->
<button @click="toggleSortDirection()"
        class="p-2 bg-darkbg border border-darkborder hover:border-brand-500 rounded-xl text-gray-300 transition flex items-center justify-center"
        :title="sortAsc ? 'Ascending (click for Descending)' : 'Descending (click for Ascending)'">
  <span x-text="sortAsc ? '▲' : '▼'" class="text-xs font-mono text-brand-400"></span>
</button>
```

---

#### **Part D: Add Checkboxes & Select All Bar**

1. **In the directory/filter bar or above the package grid**, add the "Select All" checkbox and "Add Selected to Queue" action button:

```html
<div x-show="packages.length > 0" class="flex items-center justify-between bg-darkcard/50 border border-darkborder px-4 py-2.5 rounded-xl">
  <label class="flex items-center space-x-2 cursor-pointer text-sm text-gray-300">
    <input type="checkbox" x-model="selectAll" @change="toggleSelectAll()" class="w-4 h-4 rounded border-gray-600 bg-gray-800 text-brand-500">
    <span>Select All (<span x-text="selectedPkgs.length"></span> selected)</span>
  </label>

  <div class="flex items-center space-x-3">
    <button @click="addSelectedToQueue()" :disabled="selectedPkgs.length === 0"
            class="px-3 py-1.5 rounded-lg bg-brand-600 hover:bg-brand-500 disabled:opacity-50 disabled:cursor-not-allowed text-xs font-semibold text-white transition flex items-center space-x-1.5">
      <i data-lucide="list-plus" class="w-3.5 h-3.5"></i>
      <span>Add Selected to Queue</span>
    </button>
    <button @click="showQueue = !showQueue" class="px-3 py-1.5 rounded-lg bg-gray-800 hover:bg-gray-700 text-xs font-semibold text-gray-200 transition">
      Queue (<span x-text="queue.length"></span>)
    </button>
  </div>
</div>
```

2. **In each package card template**, add a checkbox:

```html
<input type="checkbox"
       :value="pkg.file_path"
       x-model="selectedPkgs"
       class="w-4 h-4 rounded border-gray-600 bg-gray-800 text-brand-500 cursor-pointer">
```

---

#### **Part E: Add Queue Sidebar Panel**

Add a flyout panel to inspect, reorder, or trigger the queue:

```html
<!-- Queue Panel -->
<div x-show="showQueue" x-cloak
     class="fixed right-0 top-16 bottom-0 w-96 bg-darkcard border-l border-darkborder p-4 overflow-y-auto z-30 shadow-2xl">
  <div class="flex items-center justify-between mb-4">
    <h3 class="text-lg font-bold">Installation Queue (<span x-text="queue.length"></span>)</h3>
    <button @click="showQueue = false" class="text-gray-400 hover:text-white">✕</button>
  </div>

  <template x-for="(item, index) in queue" :key="item.file_id">
    <div class="flex items-center justify-between p-3 rounded-lg bg-gray-800/60 mb-2 border border-darkborder">
      <div class="flex-1 min-w-0 mr-2">
        <p class="text-xs font-bold truncate text-white" x-text="item.title"></p>
        <span class="text-[10px] text-gray-400" x-text="item.category"></span>
      </div>
      <span class="text-[10px] px-2 py-0.5 rounded uppercase font-mono"
            :class="item.status === 'installing' ? 'bg-amber-500/20 text-amber-400' : 'bg-gray-700 text-gray-300'"
            x-text="item.status"></span>
    </div>
  </template>

  <button @click="startQueue()"
          class="w-full mt-4 px-4 py-2.5 rounded-xl bg-brand-600 hover:bg-brand-500 text-white font-medium shadow-lg transition">
    Start Queue
  </button>
</div>
```

---

### 🐍 Bonus Python Exercise: Server-Side Sorting in `app.py`

Want to make the backend also support sorting via the `/api/scan` endpoint?
In `app.py` under `if path == "/api/scan":`:

```python
# Try adding this before sending the response:
sort_by = payload.get("sort_by", "title")    # "title", "file_size", "category"
reverse = payload.get("reverse", False)

packages.sort(key=lambda p: (p.get(sort_by) or 0) if sort_by == "file_size" else str(p.get(sort_by) or "").lower(), reverse=reverse)
```
This teaches you how Python's `list.sort()` works in place with custom lambdas and type handling!

### 💾 Commit

```fish
git add web/index.html app.py
git commit -m "feat(ui): add queue panel, select-all batch controls, and dashboard sorting"
```

---

## 🏁 Final Steps

### Merge to develop

```fish
git checkout develop
git merge --no-ff feature/installation-queue -m "merge: merge branch 'feature/installation-queue' into develop"
```

### Tag the release

```fish
git checkout main
git merge --no-ff develop -m "merge: merge branch 'develop' into main"
git tag -a v1.2.0 -m "feat: enhanced installation queue, auto-chaining, and dashboard sorting"
```

### Push

```fish
git push origin main develop feature/installation-queue --tags
```

---

## 📚 Python Concepts You'll Learn

| Concept | Where |
|---------|-------|
| `dataclasses` & `@dataclass` | Lesson 1 (QueueItem) |
| `collections.deque` | Lesson 1 (InstallQueue) |
| `threading.Lock` | Lesson 1–4 (thread safety) |
| `typing.Optional`, type hints | Lesson 1 (method signatures) |
| Composition pattern | Lesson 2 (AppState + InstallQueue) |
| DRY principle | Lesson 2 (make_queue_item) |
| REST API design | Lesson 3 (CRUD endpoints) |
| State machines | Lesson 4 (auto-advance) |
| Daemon threads | Lesson 4 (background worker) |
| `defaultdict` & `sorted()` | Lesson 5 (patch chaining) |
| Lambda functions & custom sort keys | Lesson 5 & Bonus (Python sorting) |
| Tuple comparison | Lesson 5 (multi-key sorting) |
| In-place list mutation (`.sort()`) | Bonus Exercise (`app.py`) |
