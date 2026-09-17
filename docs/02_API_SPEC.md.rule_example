# **Petri Net Analyzer – API Specification**

**Version:** 1.0  
**Base URL:** `http://127.0.0.1:8000/api`  
**Backend Framework:** FastAPI  

# Danh sách Endpoint
|Nhóm chức năng|Method|Endpoint|Mô tả|
|---|---|---|---|
|Upload & Parse|`POST`|`/api/net/upload`|Upload file PNML hoặc JSON|
|Convert Format|`POST`|`/api/net/convert`|Chuyển đổi PNML ↔ JSON|
|Export Net / Image|`POST`|`/api/net/export`|Xuất PNML/JSON/ảnh Petri Net (PNG/SVG)|
|Reachability|`POST`|`/api/analyze/reachability`|Phân tích và sinh Reachability Graph|
|Siphons & Traps|`POST`|`/api/analyze/siphons-traps`|Tính toán Siphons và Traps|
|Boundedness|`POST`|`/api/analyze/boundedness`|Kiểm tra boundedness + liveness tổng quát|
|Liveness|`POST`|`/api/analyze/liveness`|Kiểm tra tính sống (liveness) chi tiết|
|Deadlock|`POST`|`/api/analyze/deadlock`|Phát hiện deadlock|
|Visualize RG|`POST`|`/api/visualize/reachability`|Trả hình Reachability Graph (PNG/SVG/SVG string)|
|Visualize Coverability|`POST`|`/api/visualize/coverability`|Trả hình Coverability Tree|
|Visualize Petri Net|`POST`|`/api/visualize/petri-net`|Trả hình cấu trúc Petri Net|
|Health Check|`GET`|`/api/health`|Kiểm tra backend đang hoạt động|

## 1. Upload Petri Net File

**POST** `/api/net/upload`

### Request
`Content-Type: multipart/form-data`

|Key|Type|Description|
|---|---|---|
|`file`|File (.pnml / .json)|File chứa Petri Net|

### Response – `200 OK`
```json
{
  "status": "success",
  "message": "File uploaded successfully",
  "data": {
    "filename": "example.pnml",
    "format": "pnml",
    "parsed_net": {
      "places": [
        {"id": "P1", "tokens": 1},
        {"id": "P2", "tokens": 0}
      ],
      "transitions": [
        {"id": "T1"}
      ],
      "arcs": [
        {"source": "P1", "target": "T1", "weight": 1},
        {"source": "T1", "target": "P2", "weight": 1}
      ]
    }
  }
}
```

## 2. Convert PNML ↔ JSON

**POST** `/api/net/convert`

### Request
```json
{
  "input_format": "pnml",
  "output_format": "json",
  "data": "<pnml>...</pnml>"
}
```
### Response
```json
{
  "status": "success",
  "converted_data": {
    "places": [...],
    "transitions": [...],
    "arcs": [...]
  }
}
```

## 3. Reachability Graph

**POST** `/api/analyze/reachability`

### Request
```json
{
  "places": [
    {"id": "P1", "tokens": 1},
    {"id": "P2", "tokens": 0}
  ],
  "transitions": [
    {"id": "T1"}
  ],
  "arcs": [
    {"source": "P1", "target": "T1", "weight": 1},
    {"source": "T1", "target": "P2", "weight": 1}
  ]
}
```
### Response
```json
{
  "type": "reachability",
  "result": {
    "nodes": [
      {"id": "M0", "marking": {"P1": 1, "P2": 0}},
      {"id": "M1", "marking": {"P1": 0, "P2": 1}}
    ],
    "edges": [
      {"source": "M0", "target": "M1", "transition": "T1"}
    ],
    "is_deadlock_free": true
  },
  "success": true
}
```

## 4. Siphons & Traps

**POST** `/api/analyze/siphons-traps`

### Request
```json
{
  "places": [...],
  "transitions": [...],
  "arcs": [...]
}
```
### Response
```json
{
  "type": "siphons-traps",
  "result": {
    "siphons": [["P1", "P2"]],
    "traps": [["P2", "P3"]],
    "minimal_siphons": [["P1"]],
    "minimal_traps": [["P3"]]
  },
  "success": true
}
```

## 5. Boundedness
**POST** `/api/analyze/boundedness`

### Request
```json
{
  "places": [...],
  "transitions": [...],
  "arcs": [...]
}
```
### Response
```json
{
  "type": "boundedness",
  "result": {
    "is_bounded": true,
    "k_value": 2,
    "unbounded_places": []
  },
  "success": true
}
```

## 6. Liveness
**POST** `/api/analyze/liveness`

### Request
```json
{
  "places": [...],
  "transitions": [...],
  "arcs": [...]
}
```
### Response
```json
{
  "type": "liveness",
  "result": {
    "is_live": true,
    "details": {
      "dead_transitions": [],
      "live_transitions": ["T1", "T2"]
    }
  },
  "success": true
}
```

## 7. Deadlock Detection

**POST** `/api/analyze/deadlock`

### Request
```json
{
  "places": [...],
  "transitions": [...],
  "arcs": [...]
}
```
### Response
```json
{
  "type": "deadlock",
  "result": {
    "is_deadlock": false,
    "deadlock_states": []
  },
  "success": true
}
```

## 8. Visualization

Hiện tại backend cung cấp 3 endpoint POST để sinh hình bằng Graphviz:

- `POST /api/visualize/reachability`
- `POST /api/visualize/coverability`
- `POST /api/visualize/petri-net`

Tùy theo `format` trong body (schema `VisualizationRequest`):

- Nếu `format = "svg"` → trả trực tiếp SVG: `Content-Type: image/svg+xml`
- Nếu `format = "png"` → trả bytes PNG: `Content-Type: image/png`
- Các định dạng khác → trả chuỗi base64: `{ "image_data": "data:image/<fmt>;base64,..." }`

## 9. Health Check

**GET** `/api/health`

### Response

```json
{
  "status": "ok",
  "message": "Petri Net Analyzer backend is running"
}
```

## Error Response Format

Các API sử dụng cơ chế lỗi mặc định của FastAPI:

- Khi xảy ra `HTTPException` (ví dụ lỗi validate JSON, định dạng file không đúng...), backend trả về dạng:

```json
{
  "detail": "Error message..."
}
```

- Các response `200 OK` trả về đúng theo các schema đã mô tả ở trên (không bọc trong `status` / `message` riêng).