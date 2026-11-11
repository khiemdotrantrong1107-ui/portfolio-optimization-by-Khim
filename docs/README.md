# Portfolio Optimization by Khim — Technical Documentation Hub

Chào mừng bạn đến với Trung tâm Tài liệu Kỹ thuật Toàn diện của hệ thống **Portfolio Optimization by Khim (v2.4 Institutional Edition)**.

Bộ tài liệu này được xây dựng theo phương pháp kết hợp giữa **Đồ thị Tri thức Mã nguồn AST (Graphify Knowledge Graph)** và **Đặc tả Định lượng Chuyên sâu (Quantitative Specification)**, bao quát 100% logic của 10 file Python Backend, Cơ sở dữ liệu SQLite V2.1, và 48 hàm JavaScript Frontend.

---

## 📚 Mục Lục Tài Liệu Kỹ Thuật

| Tài liệu | Đường dẫn tệp | Nội dung cốt lõi |
| :--- | :--- | :--- |
| **00. Master Architecture & Graphify Map** | [`docs/00_MASTER_ARCHITECTURE_AND_GRAPHIFY_MAP.md`](file:///d:/Project%20Khim/portfolio-optimization-by-Khim-main/docs/00_MASTER_ARCHITECTURE_AND_GRAPHIFY_MAP.md) | Tổng quan kiến trúc hệ thống, Phân tích nodes & edges Graphify, Phân tích God Nodes, Ma trận phụ thuộc liên file `.py`, Sơ đồ ERD SQLite V2.1, và Sơ đồ Master Call Graph. |
| **01. Backend Python Functions Reference** | [`docs/01_BACKEND_PYTHON_FUNCTIONS_REFERENCE.md`](file:///d:/Project%20Khim/portfolio-optimization-by-Khim-main/docs/01_BACKEND_PYTHON_FUNCTIONS_REFERENCE.md) | Từ điển kỹ thuật chi tiết đã kiểm toán từng dòng cho **10 file Python Backend (51 hàm & 3 Pydantic schemas)**. Chi tiết tọa độ dòng, chữ ký, giải thuật toán học, cơ chế rẽ nhánh và liên kết gọi hàm. |
| **02. Database & External API Flows** | [`docs/02_DATABASE_AND_EXTERNAL_API_FLOWS.md`](file:///d:/Project%20Khim/portfolio-optimization-by-Khim-main/docs/02_DATABASE_AND_EXTERNAL_API_FLOWS.md) | Cơ chế vận hành SQLite V2.1, Thuật toán phát hiện lệch giá cổ tức/chia tách (`rel_diff > 0.01%` + `5y` refetch), Luồng bộ đệm 3 tầng, Hướng dẫn 4 API sync thủ công, và Câu lệnh SQL kiểm thử toàn vẹn. |
| **03. Frontend UI Sync & Test Playbook** | [`docs/03_FRONTEND_UI_SYNC_AND_TEST_PLAYBOOK.md`](file:///d:/Project%20Khim/portfolio-optimization-by-Khim-main/docs/03_FRONTEND_UI_SYNC_AND_TEST_PLAYBOOK.md) | Đặc tả **48 hàm JavaScript** (`textbook_mvo.js`), Bản đồ ánh xạ **JSON Backend $\rightarrow$ DOM Element ID / Plotly Trace**, và **Kịch bản kiểm thử 8 ca (E2E Test Playbook)** từ DB lên UI. |
| **04. System Audit, Optimization & Engineering Guidelines** | [`docs/04_SYSTEM_AUDIT_OPTIMIZATION_AND_ENGINEERING_GUIDELINES.md`](file:///d:/Project%20Khim/portfolio-optimization-by-Khim-main/docs/04_SYSTEM_AUDIT_OPTIMIZATION_AND_ENGINEERING_GUIDELINES.md) | **Kiểm toán chuyên sâu**: 7 điểm nghẽn/dư thừa trong Backend, 6 rủi ro đường truyền Backend $\leftrightarrow$ Frontend, phân tích Blast Radius khi nâng cấp, và **Quy trình SOP 7 bước tích hợp & Ma trận chỉnh sửa song song** cho tương lai. |

---

## 🌐 Các Trình Duyệt Đồ Thị Tương Tác Trực Quan (Interactive Graph Viewers)

Bạn có thể mở trực tiếp các tệp HTML sau trên trình duyệt (Chrome / Edge / Firefox) để tương tác trực quan với đồ thị kiến trúc của dự án:

1. **[Graphify Interactive 2D/3D Knowledge Graph](file:///d:/Project%20Khim/portfolio-optimization-by-Khim-main/graphify-out/graph.html)**:
   - Đường dẫn tệp: `graphify-out/graph.html`
   - Tính năng: Tra cứu trực quan toàn bộ nodes và liên kết, zoom/pan tự do, tìm kiếm hàm nhanh, kiểm tra mức độ liên kết (centrality) và các phân cụm nghiệp vụ.
2. **[Graphify Multi-Section Call-Flow Architecture](file:///d:/Project%20Khim/portfolio-optimization-by-Khim-main/graphify-out/portfolio-optimization-by-Khim-main-callflow.html)**:
   - Đường dẫn tệp: `graphify-out/portfolio-optimization-by-Khim-main-callflow.html`
   - Tính năng: Phân tích kiến trúc gọi hàm theo 7 phân đoạn với 6 sơ đồ Mermaid động có thanh điều khiển zoom/pan tương tác.
3. **[Graphify Knowledge Report](file:///d:/Project%20Khim/portfolio-optimization-by-Khim-main/graphify-out/GRAPH_REPORT.md)**:
   - Đường dẫn tệp: `graphify-out/GRAPH_REPORT.md`
   - Báo cáo chi tiết về mức độ kết nối, chỉ số cohesion và các kết nối ngầm giữa các module.
