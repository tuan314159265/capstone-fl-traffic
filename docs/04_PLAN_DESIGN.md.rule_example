## 1. Thiết kế giao diện: Single Page duy nhất

### 1.1. Bố cục tổng thể (layout)

Một trang duy nhất chia làm 3 vùng chính:

1. **Thanh trên cùng (Top Bar / Header)**  
   - Logo / Tên app: “Petri Analyzer”
   - Nút:
     - `New` (tạo net rỗng)
     - `Open` (Upload PNML/JSON)
     - `Save` (Tải về PNML/JSON)
     - `Export` (PNG/SVG)
   - Nút `Analyze` (mở panel phân tích)
   - Nút `Simulate` (mở khu vực mô phỏng)
   - Phần nhỏ `Status` (bounded/unbounded, số place/transition, cảnh báo state explosion)

2. **Khu vực trung tâm (Canvas) – React Flow**  
   - Đây là nơi:
     - Vẽ/hiển thị Petri net: place, transition, arc.
     - Tương tác drag-drop, kéo thả, pan/zoom.
     - Hiển thị token (số trên place).
   - Dựa trên React Flow:
     - Place: node hình tròn, hiển thị tên + số token.
     - Transition: node hình chữ nhật mỏng (dọc hoặc ngang).
     - Arc: edge có mũi tên, nhãn weight.
   - Click chọn node/edge để chỉnh sửa ở sidebar phải.

3. **Thanh bên phải (Right Sidebar, dạng tab)**  
   Sidebar có 3 tab (có thể dùng tab hoặc accordion):

   - **Tab 1: Properties / Editor**
     - Khi chọn Place:
       - Tên (id / label)
       - Số token (editable)
     - Khi chọn Transition:
       - Tên / label
     - Khi chọn Arc (edge):
       - From / To
       - Weight
     - Nút xóa phần tử (Delete).
   - **Tab 2: Analysis**
     - Nút chạy từng loại phân tích:
       - `Build Reachability Graph`
       - `Check Deadlock`
       - `Check Boundedness`
       - `Compute Siphons/Traps`
       - `Check Liveness`
     - Kết quả hiển thị dạng:
       - Boundedness: bounded/unbounded; nếu bounded: k-bounded cho từng place.
       - Deadlock: danh sách marking deadlock (click vào để highlight trong RG).
       - Siphons/Traps: bảng các siphon/trap tối thiểu (danh sách place).
       - Liveness:
         - Bảng transition: t1: L3-live, t2: Dead, ...
     - Nút `Show Reachability Graph`:
       - Mở modal overlay hoặc panel dưới canvas hiển thị RG (dùng Graphviz SVG).
       - Node deadlock tô đỏ.
   - **Tab 3: Simulation**
     - Hiển thị marking hiện tại (vector).
     - Danh sách transition khả kích (enabled) tại marking hiện tại:
       - Mỗi transition có button `Fire`.
     - Nút:
       - `Step` (fire từng transition đã chọn hoặc random enabled).
       - `Reset to M0`.
     - Tuỳ chọn:
       - `Auto-play` với tốc độ (slider).
     - Trong canvas:
       - Khi fire: animate token di chuyển (tối thiểu: update số token + highlight edge).

---

## 2. Tính năng cụ thể trên 1 trang

### 2.1. Vẽ, sửa, undo/redo

- Thanh công cụ nhỏ bên trái canvas:

  - Tool `Select/Move`  
  - Tool `Place` (click lên canvas để thêm place)
  - Tool `Transition`
  - Tool `Arc`:
    - Click node nguồn → click node đích → tạo edge
  - Tool `Token`:
    - Click lên place để +1 token, Shift+click để -1 (hoặc chỉnh trong Properties).

- Undo:
  - Ctrl+Z
  - Dùng state history trong React.

### 2.2. Import / Export

- **Open (Upload)**:
  - Chọn file PNML/JSON.
  - Gửi file lên backend qua API `/api/import`.
  - Backend parse → trả về JSON chuẩn nội bộ:
    ```json
    {
      "places": [{ "id": "p1", "label": "p1", "tokens": 1 }, ...],
      "transitions": [{ "id": "t1", "label": "t1" }, ...],
      "arcs": [{ "id": "a1", "source": "p1", "target": "t1", "weight": 1 }, ...],
      "initial_marking": { "p1": 1, "p2": 0, ... }
    }
    ```
  - Frontend map JSON này thành nodes/edges React Flow.

- **Save (Download PNML/JSON)**:
  - Frontend gửi model hiện tại (JSON) → backend `/api/export` với `format = pnml/json`.
  - Backend validate, sinh file & trả về (Content-Disposition download).

- **Export (PNG/SVG)**:
  - 2 tùy chọn:
    - Xuất ảnh Petri net hiện tại: frontend capture canvas (React Flow) → PNG.
    - Xuất ảnh RG: backend dùng Graphviz tạo SVG/PNG, frontend chỉ tải về.

### 2.3. Reachability Graph & Deadlock

- Nút `Build Reachability Graph`:
  - Gửi Petri net JSON + M0 → `/api/analyze/reachability`.
  - Backend chạy Algorithm 1:
    - Trả về:
      ```json
      {
        "states": [
          { "id": "M0", "marking": [1,0,0,0,0] },
          ...
        ],
        "edges": [
          { "from": "M0", "to": "M1", "transition": "t1" },
          ...
        ]
      }
      ```
- Nút `Show Reachability Graph`:
  - Gọi `/api/graphviz/rg` hoặc sử dụng dữ liệu RG ở trên để render bằng Graphviz ở backend, trả SVG string.
  - Frontend hiển thị trong modal overlay cuộn được.
  - Các marking deadlock (enabled = ∅) được tô đỏ:
    - Backend đã tính sẵn deadlock và khi sinh Graphviz set style: `fillcolor=red, style=filled`.

- Deadlock:
  - API `/api/analyze/deadlock` có thể tái sử dụng RG đã tính:
    - Trả danh sách id marking bị deadlock + giá trị marking.
  - Trong tab Analysis:
    - Table: M_id, marking vector.
    - Click → highlight node tương ứng trong RG view.

### 2.4. Boundedness (Coverability Tree)

- Nút `Check Boundedness`:
  - Gọi `/api/analyze/boundedness`.
  - Backend:
    - Xây Coverability Tree (Algorithm 4).
    - Nếu có `ω` → `unbounded` + danh sách place có thể tăng vô hạn.
    - Nếu bounded → `bounded` + k-bounded cho từng place (max token).

- Hiển thị:
  - Thông tin tổng quát trong tab Analysis:
    - “Net is BOUNDED / UNBOUNDED”
    - Nếu bounded:
      - Bảng: place – max token (k).
  - Có thêm nút `Show Coverability Tree` (tùy chọn):
    - Tương tự RG, hiển thị hình Graphviz (có ω trong label).

### 2.5. Siphons & Traps

- Nút `Compute Siphons/Traps`:
  - Gọi `/api/analyze/siphons_traps`.
  - Backend:
    - Dùng Algorithm 3:
      - Tìm tất cả siphon/trap.
      - Lọc minimal.
  - Trả JSON:
    ```json
    {
      "siphons_minimal": [
        { "places": ["p1", "p2"] },
        ...
      ],
      "traps_minimal": [
        { "places": ["p3"] },
        ...
      ]
    }
    ```

- UI:
  - Tab Analysis:
    - 2 list:
      - Minimal Siphons
      - Minimal Traps
    - Click một siphon/trap → highlight các place tương ứng trên canvas (viền màu khác, ví dụ xanh/thanh).

### 2.6. Liveness

- Nút `Check Liveness`:
  - Điều kiện: chỉ chạy nếu bounded (hoặc user chấp nhận cảnh báo nếu không).
  - Gọi `/api/analyze/liveness`.
  - Backend:
    - Tái sử dụng RG.
    - Chạy Tarjan (Algorithm 5) tìm SCC.
    - Dùng Algorithm 6 để gán mức liveness cho mỗi transition: Dead, L1, L2, L3, Live(L4).
  - Trả JSON:
    ```json
    {
      "t1": "L3",
      "t2": "Dead",
      "t3": "Live",
      ...
    }
    ```

- UI:
  - Bảng trong tab Analysis:
    - Transition – Liveness level – Mô tả ngắn (tooltip: “L3-live: xuất hiện vô hạn trong một firing sequence”).
  - Có thể tô màu transition trên canvas theo mức liveness:
    - Dead: xám
    - L1: xanh nhạt
    - L3: cam
    - Live (L4): xanh đậm

### 2.7. Simulation

- Tab Simulation:
  - Dùng marking hiện tại (state riêng, mặc định = M0).
  - Gọi backend `/api/sim/enabled` hoặc tính client-side (tối ưu hơn) dựa trên:
    - pre/post, current marking.
  - Hiển thị danh sách `enabled transitions`.
  - Khi click `Fire(t)`:
    - Gửi `/api/sim/fire` hoặc tự tính (M' = M + C(t)).
    - Cập nhật marking + redraw tokens.
    - Highlight node transition đó ngắn (animation CSS).
  - Nút `Reset to M0`: khôi phục marking ban đầu.

---

## 3. Kiến trúc kỹ thuật

### 3.1. Frontend

- **Công nghệ**:
  - React.js (SPA).
  - React Flow để vẽ graph Petri net.
  - Tailwind CSS cho style, layout, responsive.
- **State chính**:
  - `petriNetModel`: { places, transitions, arcs, initial_marking }
  - `currentMarking`: object { placeId: tokens } (cho simulation).
  - `reachabilityGraph`: { states, edges } (cache sau khi build).
  - `analysisResult`: boundedness, deadlocks, siphons/traps, liveness.
  - `uiState`: tab đang mở, phần tử đang chọn, lịch sử (undo/redo).
- **Phím tắt**:
  - Ctrl+Z → undo
  - Ctrl+S → trigger `Save` (download JSON).

### 3.2. Backend (Python)

- **Framework**: FastAPI hoặc Flask (FastAPI gọn & dễ làm API).
- **Module chính**:
  - `models.py`: cấu trúc dữ liệu Petri net (P, T, F, W, M0).
  - `reachability.py`: Algorithm 1.
  - `deadlock.py`: Algorithm 2 (+ hàm enabled).
  - `siphons_traps.py`: Algorithm 3.
  - `boundedness.py`: Coverability Tree + Algorithm 4.
  - `liveness.py`: Tarjan SCC + Algorithm 5 & 6.
  - `pnml_parser.py` / `json_parser.py`: import/export.
  - `graphviz_utils.py`: sinh DOT, gọi Graphviz để render PNG/SVG.

### 3.3. API endpoints (REST/JSON)

Ví dụ (prefix `/api`):

- Import / Export:
  - `POST /api/import` (file PNML/JSON → JSON chuẩn)
  - `POST /api/export` (JSON + format → file)
- Phân tích:
  - `POST /api/analyze/reachability`
  - `POST /api/analyze/deadlock`
  - `POST /api/analyze/boundedness`
  - `POST /api/analyze/siphons_traps`
  - `POST /api/analyze/liveness`
- Đồ thị:
  - `POST /api/graphviz/rg` (trả SVG)
  - `POST /api/graphviz/coverability` (optional)

Tất cả truyền/nhận đều ở dạng JSON (trừ khi trả file).
