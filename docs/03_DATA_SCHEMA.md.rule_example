# DATA SCHEMA – Petri Net Analyzer

## Mục tiêu
Chuẩn hóa dữ liệu vào/ra cho toàn bộ hệ thống, giúp các module (frontend, backend, thuật toán, visualization) giao tiếp thống nhất và dễ mở rộng.

---

## 1️⃣ Tổng quan

Hệ thống Petri Net Analyzer nhận dữ liệu Petri Net ở hai dạng:

| **Nguồn**       | **Định dạng** | **Mô tả**                                      |
|------------------|--------------|------------------------------------------------|
| File nhập       | .pnml, .json | Người dùng upload từ máy hoặc nhập tay trên giao diện |
| Dữ liệu chuẩn hóa | JSON thống nhất | Dạng JSON dùng chung cho tất cả thuật toán         |

Mọi thuật toán (Reachability, Deadlock, Liveness, Boundedness, Siphons-Traps) đều nhận cùng một JSON input chuẩn hóa.

---

## 2️⃣ Cấu trúc Input (chuẩn hóa sau khi đọc PNML)

### Mẫu JSON Input
```json
{
  "places": ["p1", "p2", "p3"],
  "transitions": ["t1", "t2"],
  "arcs": [
    ["p1", "t1"],
    ["t1", "p2"],
    ["p2", "t2"],
    ["t2", "p3"]
  ],
  "weights": {
    "[\"p1\",\"t1\"]": 1,
    "[\"t1\",\"p2\"]": 1,
    "[\"p2\",\"t2\"]": 1,
    "[\"t2\",\"p3\"]": 1
  },
  "initial_marking": {
    "p1": 1,
    "p2": 0,
    "p3": 0
  }
}
```

### Giải thích các trường
| **Trường**         | **Kiểu**         | **Mô tả**                                                                 |
|---------------------|------------------|---------------------------------------------------------------------------|
| `places`           | List[str]        | Danh sách các place                                                      |
| `transitions`      | List[str]        | Danh sách các transition                                                 |
| `arcs`             | List[List[str]]  | Các cung nối `[source, target]`, có thể từ place → transition hoặc transition → place |
| `weights`          | Dict[str, int]   | Trọng số trên các cung, key là chuỗi `["source","target"]`               |
| `initial_marking`  | Dict[str, int]   | Số lượng token ban đầu của từng place                                    |

Dữ liệu này có thể được sinh ra bằng tay (vẽ trên UI) hoặc chuyển đổi tự động từ file `.pnml`.

---

## 3️⃣ Chuyển đổi PNML → JSON (Backend xử lý)

**File:** `app/utils/pnml_parser.py`

Ví dụ JSON:
```json
{
  "places": ["p1", "p2"],
  "transitions": ["t1"],
  "arcs": [["p1", "t1"], ["t1", "p2"]],
  "weights": { "[\"p1\",\"t1\"]": 1, "[\"t1\",\"p2\"]": 1 },
  "initial_marking": {"p1": 1, "p2": 0}
}
```

Parser sẽ đọc XML PNML và sinh JSON theo đúng format trên. Đây là định dạng chuẩn nội bộ cho toàn bộ backend.

---

## 4️⃣ Chuẩn Output của các thuật toán

### a. Reachability Graph
```json
{
  "states": [
    {"p1": 1, "p2": 0, "p3": 0},
    {"p1": 0, "p2": 1, "p3": 0},
    {"p1": 0, "p2": 0, "p3": 1}
  ],
  "initial_marking": {"p1": 1, "p2": 0, "p3": 0},
  "deadlocks": [[2]],
  "edges": [
    {"from": 0, "to": 1, "transition": "t1"},
    {"from": 1, "to": 2, "transition": "t2"}
  ],
  "graph_image": null
}
```

| **Trường**        | **Kiểu**             | **Mô tả**                                      |
|--------------------|----------------------|-----------------------------------------------|
| `states`          | List[Dict[str, int]] | Các marking (trạng thái)                      |
| `initial_marking` | Dict[str, int]       | Marking ban đầu                               |
| `deadlocks`       | List[List[int]]      | Danh sách các tập chỉ số state là deadlock    |
| `edges`           | List[Dict[str, Any]] | Các cạnh tương ứng với firing transition      |
| `graph_image`     | Optional[str]        | Ảnh đồ thị dạng base64 (hiện tại thường để `null`) |

---

### b. Deadlock Detection
```json
{
  "total_states": 3,
  "total_deadlocks": 1,
  "deadlock_markings": [
    {"p1": 0, "p2": 0, "p3": 1}
  ]
}
```

| **Trường**           | **Kiểu**         | **Mô tả**                                      |
|-----------------------|------------------|-----------------------------------------------|
| `total_states`       | int              | Tổng số marking có thể đạt được               |
| `total_deadlocks`    | int              | Số lượng marking bị deadlock                  |
| `deadlock_markings`  | List[Dict[str,int]] | Danh sách các marking deadlock               |

---

### c. Boundedness & Liveness
```json
{
  "is_bounded": true,
  "bound": 3,
  "unbounded_places": [],
  "is_live": true,
  "liveness_level": 4,
  "unreachable_transitions": [],
  "transition_liveness_levels": {
    "t1": 4,
    "t2": 3
  }
}
```

| **Trường**                   | **Kiểu**           | **Mô tả**                                      |
|-------------------------------|--------------------|-----------------------------------------------|
| `is_bounded`                 | bool               | Petri Net có bị unbounded hay không           |
| `bound`                      | Optional[int]      | Giá trị k-bounded toàn mạng (None nếu unbounded) |
| `unbounded_places`           | List[str]          | Danh sách place có token tăng vô hạn          |
| `is_live`                    | bool               | Petri Net có đảm bảo liveness không (tổng quát) |
| `liveness_level`             | int                | Mức liveness tổng thể (0-4)                   |
| `unreachable_transitions`    | List[str]          | Danh sách transition không bao giờ firing được|
| `transition_liveness_levels` | Dict[str, int]     | Mức liveness của từng transition (0-4)        |

---

### d. Siphons & Traps
```json
{
  "siphons": [["p1", "p2"], ["p3"]],
  "minimal_siphons": [["p1", "p2"]],
  "traps": [["p2"], ["p3"]],
  "minimal_traps": [["p2"]]
}
```

| **Trường**         | **Kiểu**         | **Mô tả**                                      |
|---------------------|------------------|-----------------------------------------------|
| `siphons`          | List[List[str]]  | Danh sách siphon tìm được                     |
| `minimal_siphons`  | List[List[str]]  | Các siphon tối thiểu                          |
| `traps`            | List[List[str]]  | Danh sách trap tìm được                       |
| `minimal_traps`    | List[List[str]]  | Các trap tối thiểu                            |

---

## 5️⃣ Chuẩn API Input/Output (Pydantic Schemas)

**File:** `app/core/schemas.py`

| **Model**            | **Dùng cho** | **Miêu tả**                                   |
|-----------------------|--------------|-----------------------------------------------|
| `PetriNetRequest`    | Input        | Mô tả cấu trúc Petri Net chuẩn                |
| `DeadlockResult`     | Output       | Kết quả phát hiện deadlock                    |
| `ReachabilityResult` | Output       | Kết quả xây dựng đồ thị reachability          |
| `BoundednessResult`  | Output       | Kết quả boundedness/liveness                  |
| `SiphonTrapResult`   | Output       | Kết quả siphon & trap                         |

---

## 6️⃣ Đồ thị Reachability (Graphviz)

**Input:** danh sách states (V) và edges (E)  
**Output:** ảnh SVG hoặc PNG mã hóa base64.

```python
image_data = render_reachability_graph(V, E, output_format="svg")
```

Trả về chuỗi: `"data:image/svg+xml;base64,..."`

Frontend chỉ cần:
```html
<img src={graph_image} alt="Reachability Graph" />
```

---

## 7️⃣ Tích hợp tổng quát

| **Bước** | **API**                        | **Input**       | **Output**                     |
|----------|---------------------------------|-----------------|--------------------------------|
| 1️⃣      | `/api/net/convert`             | PNML/JSON       | JSON chuẩn                    |
| 2️⃣      | `/api/analyze/reachability`    | JSON chuẩn      | States, edges, deadlocks...   |
| 3️⃣      | `/api/analyze/deadlock`        | JSON chuẩn      | Deadlock markings             |
| 4️⃣      | `/api/analyze/liveness`        | JSON chuẩn      | Liveness, unreachable transitions |
| 5️⃣      | `/api/analyze/boundedness`     | JSON chuẩn      | Boundedness + liveness info   |
| 6️⃣      | `/api/analyze/siphons-traps`   | JSON chuẩn      | Siphons & traps               |

---

## 🧾 8️⃣ Quy ước mở rộng (nếu có)

- Tất cả dữ liệu trao đổi đều là `application/json`.
- Mọi response nên có thêm trường `"status": "ok" | "error"` và `"message"` để dễ debug.
- Các thuật toán mới (nếu thêm) phải tuân theo input chuẩn này để đảm bảo frontend không cần sửa.