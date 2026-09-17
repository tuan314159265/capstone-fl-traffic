# Petri Net Analyzer – Hướng dẫn sử dụng và kiểm thử

## 1. Giới thiệu

Petri Net Analyzer là công cụ hỗ trợ **mô hình hóa** và **phân tích** mạng Petri với giao diện đồ họa, bao gồm:

- Vẽ và chỉnh sửa Petri net.
- Mô phỏng (simulation) quá trình bắn transition.
- Phân tích các thuộc tính: reachability, deadlock, boundedness, liveness, siphons & traps.
- Xuất file mô hình và trace thực thi.

---

## 2. Giao diện chính

Giao diện gồm 4 vùng chính:

1. **Top Bar**
   - Nút tạo mới, mở file, lưu, export.
   - Hiển thị trạng thái net: BOUNDED/UNBOUNDED, số places/transitions, số states.

2. **Left Toolbar**
   - Chọn công cụ: Select, Place, Transition, Arc, Token.
   - Một số phím tắt tương ứng.

3. **Canvas (Editor)**
   - Khu vực vẽ mạng Petri: node Place/Transition, các Arc.
   - Có thể kéo/thả (drag) để thay đổi vị trí node.

4. **Right Sidebar – Properties**
   - Thông tin chi tiết của phần tử đang chọn (place/transition/arc).
   - Chỉnh sửa label, token, weight, v.v.

---

## 3. Các công cụ chính

### 3.1. Công cụ Select

- Dùng để **chọn** phần tử trên canvas.
- Có thể:
  - Click vào Place/Transition/Arc để chọn.
  - Kéo (drag) node để thay đổi vị trí.
- Khi chọn phần tử, thông tin chi tiết hiện ở **Properties Tab** bên phải.

### 3.2. Công cụ Place

- Dùng để tạo **Place** mới.
- Cách dùng:
  - Chọn tool `Place`.
  - Click lên canvas để tạo node Place mới (với ID mặc định `pX`).
- Sau khi tạo:
  - Chỉnh sửa `Label` và `Tokens` trong Properties.

### 3.3. Công cụ Transition

- Dùng để tạo **Transition** mới.
- Cách dùng:
  - Chọn tool `Transition`.
  - Click lên canvas để tạo node Transition mới (ID mặc định `tX`).
- Có thể chỉnh `Label` trong Properties.

### 3.4. Công cụ Arc

- Dùng để tạo **cung** (Arc) nối giữa Place và Transition.
- Quy tắc:
  - Chỉ cho phép nối **Place → Transition** hoặc **Transition → Place**.
  - Không cho phép Place → Place hoặc Transition → Transition.
- Cách dùng:
  - Chọn tool `Arc`.
  - Click vào phần tử nguồn, sau đó click vào phần tử đích.
- Sau khi tạo:
  - Chỉnh sửa `Weight` trong Properties (mặc định là 1).

### 3.5. Công cụ Token

- Dùng để chỉnh nhanh số **token** trong Place.
- Cách dùng (tùy cách cài đặt trong UI):
  - Chọn tool `Token`.
  - Click vào Place để tăng/giảm token (hoặc dùng Properties Tab để nhập số cụ thể).

---

## 4. Bảng thuộc tính (Properties)

Khi chọn một element, bên phải sẽ hiển thị:

### 4.1. Place

- **ID**: mã định danh (không sửa được).
- **Label**: tên hiển thị (có thể sửa, cho phép xóa/chỉnh hoàn toàn).
- **Tokens**:
  - Nhập số token ban đầu.
  - Có nút `+` / `-` để tăng/giảm nhanh.
- **Connections**:
  - Danh sách Arc vào/ra Place đó.

### 4.2. Transition

- **ID**: mã định danh (không sửa được).
- **Label**: tên hiển thị.
- **Thông tin thêm**:
  - Số `Preconditions` (cung vào).
  - Số `Postconditions` (cung ra).
  - `Status`: Enabled/Disabled tại marking hiện tại.
  - `Liveness` (nếu có kết quả phân tích).

### 4.3. Arc

- **Source / Target**: nguồn và đích của cung (chỉ xem).
- **Weight**: trọng số của cung (>= 1).

---

## 5. File operations

### 5.1. Tạo mới mô hình

- Nút **New** (Top Bar).
- Hệ thống có thể hiển thị hộp thoại xác nhận (mất các thay đổi chưa lưu).

### 5.2. Mở file

- Nút **Open**:
- Khi load:
  - Mạng Petri trên canvas được thay thế bằng dữ liệu trong file.

### 5.3. Lưu (Save)

- Nút **Save** hoặc `Ctrl+S`.
- Xuất file **JSON** chứa:
  - Danh sách places, transitions, arcs.
  - Vị trí node trên canvas.
  - Marking ban đầu.

### 5.4. Export

- Nút **Export** trên Top Bar:
  - **PNG / SVG**: xuất hình ảnh mạng Petri.
  - **PNML**: export dưới dạng chuẩn PNML.
  - **JSON**: export cấu trúc mạng.

---

## 6. Mô phỏng (Simulation)

### 6.1. Marking hiện tại

- `currentMarking` là số token hiện tại tại mỗi Place.
- Có thể **Reset to initial marking**.

### 6.2. Firing Transition (bắn chuyển tiếp)

- Click vào Transition (hoặc dùng nút “Fire” nếu có).
- Hệ thống sẽ:
  - Kiểm tra điều kiện enabled:
    - Mỗi cung đầu vào phải có đủ token theo weight.
  - Nếu enabled:
    - Trừ token ở places đầu vào.
    - Cộng token ở places đầu ra.
    - Lưu lại bước này vào `simulationHistory`.

### 6.3. Auto Play

- Chế độ tự động bắn transition sau mỗi khoảng thời gian cố định.
- Hệ thống:
  - Lấy danh sách transitions enabled.
  - Chọn 1 transition (ví dụ random) để bắn.
  - Dừng khi không còn transition nào enabled.

### 6.4. Export Trace

- Chức năng **Export Trace**:
  - Export ra `JSON` hoặc `TXT`:
    - Danh sách marking theo từng bước.
    - Transition được bắn ở mỗi bước.
    - Marking hiện tại.

---

## 7. Phân tích (Analysis)

Các chức năng phân tích sử dụng backend FastAPI, kết quả hiển thị lại trên frontend.

### 7.1. Reachability

- Xây dựng **Reachability Graph**.
- Cho biết các marking có thể đạt được từ marking ban đầu.

### 7.2. Deadlock

- Phát hiện các marking **deadlock**:
  - Không còn transition nào enabled.
- Có thể hiển thị danh sách marking deadlock hoặc đánh dấu trong graph.

### 7.3. Boundedness

- Kiểm tra mạng Petri:
  - **BOUNDED**: số token tại mọi place luôn hữu hạn.
  - **UNBOUNDED**: có place có thể tăng token vô hạn.
- Kết quả hiển thị ở **Top Bar** (Net: BOUNDED/UNBOUNDED).

### 7.4. Liveness

- Đánh giá **Liveness** của từng transition.
- Có thể hiển thị mức liveness trong Properties của Transition.

### 7.5. Siphons & Traps

- Phân tích **siphons** và **traps**:
  - Hỗ trợ đánh giá tính ổn định của net.
- Kết quả có thể hiển thị trong zone Analysis hoặc trong bảng properties.

---

## 8. Undo

- **Undo (Ctrl+Z)**:
  - Hoàn tác thao tác chỉnh sửa mô hình (thêm/xoá/sửa place, transition, arc, load, reset).
- Hệ thống chỉ undo các thao tác **mô hình**, không undo bước mô phỏng (firing).

---
## 9. Phím tắt

Một số phím tắt mặc định:

- `Ctrl+Z`: Undo.
- `Ctrl+S`: Save.
- `S`: chọn tool **Select**.
- `P`: chọn tool **Place**.
- `T`: chọn tool **Transition**.
- `A`: chọn tool **Arc**.
- `K`: chọn tool **Token**.

---

## 10. Gợi ý quy trình sử dụng

1. **Vẽ mô hình**:
   - Chọn Place/Transition để vẽ các node.
   - Dùng Arc để nối theo logic hệ thống.
   - Thiết lập weight cho cung.

2. **Thiết lập marking ban đầu**:
   - Chỉnh số token cho mỗi Place.

3. **Mô phỏng**:
   - Bắn thủ công từng transition hoặc dùng Auto Play.
   - Quan sát marking thay đổi theo thời gian.

4. **Phân tích**:
   - Chạy các thuật toán phân tích: reachability, deadlock, boundedness, liveness, siphons/traps.
   - Đọc kết quả ở khu vực phân tích và Properties.

5. **Lưu/Export**:
   - Lưu file JSON để chỉnh sửa sau.
   - Export PNG/SVG để đưa vào báo cáo.
   - Export trace để phân tích thêm hoặc báo cáo.

---

### Lưu ý về cấu trúc file JSON
Các file JSON của dự án tuân thủ schema:
``` json
{
  "places": [
    {
      "id": "p1",
      "label": "p1",
      "position": { "x": 200, "y": 200 }
    }
  ],
  "transitions": [
    {
      "id": "t1",
      "label": "t1",
      "position": { "x": 400, "y": 200 }
    }
  ],
  "arcs": [
    { "source": "p1", "target": "t1" },
    { "source": "t1", "target": "p2" }
  ],
  "weights": {
    "[\"p1\",\"t1\"]": 1,
    "[\"t1\",\"p2\"]": 1
  },
  "initial_marking": {
    "p1": 1,
    "p2": 0
  }
}
```
* **places**: danh sách place
  * **id**: định danh duy nhất (ví dụ `p1`, `p2`)
  * **label**: nhãn hiển thị (nếu thiếu, UI sẽ dùng `id`)
  * **position**: toạ độ hiển thị `{ "x": number, "y": number }`
* **transitions**: danh sách transition (cùng cấu trúc với `places`, nhưng là transition)
* **arcs**: danh sách cung
  * **source**: id place/transition đầu
  * **target**: id place/transition cuối
* **weights**:
  * Key: chuỗi JSON `["source","target"]`, ví dụ `"[\"p1\",\"t1\"]"`
  * Value: trọng số (mặc định 1 nếu không khai báo)
* **initial_marking**: map `{ placeId: số_token_ban_đầu }`

Nếu người dùng tự tạo file JSON mới để dùng tính năng Import JSON, đảm bảo tuân thủ theo schema trên. Tham khảo thư mục test/ để xem các ví dụ minh họa nhóm đã tạo sẵn