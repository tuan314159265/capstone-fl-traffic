# Naming & Coding Convention

## Environment Setup Guideline
- File: `/backend/.env` hoặc `/frontend/.env`
- Luôn có bản mẫu `.env.example`
- Không commit `.env` thật (chỉ `.env.example`)
- Khi deploy, chỉ cần copy `.env.example` thành `.env` và điền giá trị thật
  
## Python (Backend)
- File: snake_case (`pnml_parser.py`)
- Function: snake_case (`def analyze_reachability()`)
- Class: PascalCase (`class PetriNetAnalyzer`)
- Constant: UPPER_CASE (`MAX_TOKENS`)
- Commit message:
	- [feat] add boundedness analyzer
	- [fix] bug in PNML parser
	- [refactor] improve API response format
	- [style] update Tailwind theme
	- [docs] add API spec

## JavaScript (Frontend)
- Component: PascalCase (`CanvasEditor.jsx`)
- Function/hook: camelCase (`useFetchAPI()`)
- Folder: lowercase (`components`, `services`)

## Git Branch Convention
- `main` → bản ổn định
- `dev` → nhánh phát triển chung, tạo PR vào dev
- `feat/<module>` → thêm tính năng (vd: `feat/reachability`)