``` bash
petri-analyzer/
│
├── backend/                        # Phần xử lý logic & thuật toán
|   |── .env.example                # File mẫu để chia sẻ công khai
│   ├── app/
│   │   ├── main.py                 # Entry point: Khởi tạo FastAPI, mount routers
│   │   │
│   │   ├── api/                    # Các API endpoint nhóm theo chức năng
│   │   │   ├── endpoints/
│   │   │   │   ├── net_upload.py   # Upload file PNML/JSON
│   │   │   │   ├── analyze.py      # Gọi các thuật toán phân tích
│   │   │   │   └── visualize.py    # Trả về hình ảnh Graphviz (PNG/SVG)
│   │   │   └── __init__.py
│   │   │
│   │   ├── core/                   # Cấu hình hệ thống (settings, constants)
│   │   │   ├── config.py           # Cấu hình app, CORS, logging, path
│   │   │   └── schemas.py          # Định nghĩa Pydantic models cho input/output JSON
│   │   │
│   │   ├── algorithms/             # Các thuật toán Petri Net
│   │   │   ├── reachability.py
│   │   │   ├── siphons_traps.py
│   │   │   ├── boundedness.py
│   │   │   ├── liveness.py
│   │   │   ├── deadlock.py
│   │   │   └── __init__.py
│   │   │
│   │   ├── utils/                  # Tiện ích hỗ trợ
│   │   │   ├── pnml_parser.py      # Parse PNML <-> JSON
│   │   │   ├── json_converter.py   # Chuẩn hóa input/output thuật toán
│   │   │   ├── graphviz_helper.py  # Sinh hình ảnh Reachability graph
│   │   │   └── __init__.py
│   │   │
│   │   └── tests/                  # Unit test
│   │       ├── test_pnml_parser.py
│   │       ├── test_reachability.py
│   │       └── ...
│   │
│   ├── requirements.txt            # Danh sách thư viện FastAPI, Graphviz, SNAKES
│   └── README.md                   # Hướng dẫn setup & chạy backend
│
│
├── frontend/                       # React + React Flow + Tailwind
|   |── .env.example                # File mẫu để chia sẻ công khai
│   ├── src/
│   │   ├── components/
│   │   │   ├── CanvasEditor.jsx
│   │   │   ├── Toolbar.jsx
│   │   │   ├── FileMenu.jsx
│   │   │   ├── SimulationPanel.jsx
│   │   │   └── AnalysisPanel.jsx
│   │   │
│   │   ├── pages/
│   │   │   ├── HomePage.jsx
│   │   │   └── AboutPage.jsx
│   │   │
│   │   ├── services/
│   │   │   ├── api.js              # axios call tới backend
│   │   │   └── netUtils.js
│   │   │
│   │   ├── App.jsx
│   │   └── index.js
│   │
│   ├── public/
│   │   └── index.html
│   │
│   ├── package.json
│   └── README.md
│
│
├── docs/                           # Tài liệu nhóm
│   ├── 00_PROJECT_STRUCTURE.md     # Giải thích cấu trúc project
│   ├── 01_NAMING_CONVENTION.md     # Quy tắc đặt tên, Git commit rule
│   ├── 02_API_SPEC.md              # Mô tả các endpoint FastAPI
│   ├── 03_DATA_SCHEMA.md           # Chuẩn hóa cấu trúc dữ liệu Petri Net
│   ├── 04_PLAN_DESIGN.md           # Thiết kế tổng quan kiến trúc & luồng
│   └── USER_GUIDE.md               # Hướng dẫn sử dụng ứng dụng
│
│
├── assets/
│   ├── examples/
│   │   ├── sample_net.pnml
│   │   ├── sample_net.json
│   │   └── sample_graph.svg
│   └── screenshots/
│       ├── ui_mockup.png
│       └── reachability_demo.png
│
├── .gitignore
├── README.md                       # Tổng quan toàn dự án + hướng dẫn cài đặt
└── LICENSE

```