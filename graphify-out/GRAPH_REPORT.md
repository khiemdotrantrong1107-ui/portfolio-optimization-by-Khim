# Graph Report - portfolio-optimization-by-Khim-main  (2026-11-10)

## Corpus Check
- 23 files · ~51,029 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 7 file(s) not represented in the graph (top: (none) 2, .bat 2, .example 1)

## Summary
- 413 nodes · 1001 edges · 24 communities (21 shown, 3 thin omitted)
- Extraction: 81% EXTRACTED · 19% INFERRED · 0% AMBIGUOUS · INFERRED: 186 edges (avg confidence: 0.95)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- textbook_mvo.js
- get_connection
- test_textbook_engine.py
- hayinsights_client.py
- data_exporter.py
- numpy
- services
- Portfolio Optimization by Khim (v2.4 Institutional Edition)
- 01. Backend Python Functions Reference (Audited & Verified v2.4)
- db_manager.py
- app.py
- ingest_uploaded_prices_df
- 3. Kịch Bản Kiểm Thử Đầu-Cuối (End-to-End Testing Playbook)
- 00. Master Architecture & Graphify Knowledge Graph Map
- get_database_summary
- upsert_equity_prices_with_drift_check
- Portfolio Optimization by Khim — Technical Documentation Hub
- upsert_macro_time_series
- api_export_prices
- fetch_single_equity
- 1.4. Danh Sách 17 FastAPI Endpoints Trong `app.py`
- api_benchmark_attribution
- 4A. Quy Trình 7 Bước Tích Hợp Một Function Từ Backend Lên Frontend UI
- evaluate_risk_profile

## God Nodes (most connected - your core abstractions)
1. `get_connection()` - 31 edges
2. `4B. Ma Trận Chỉnh Sửa Song Song Khi Thêm / Sửa / Xóa Tính Năng Ở Backend (Change-Impact Matrix)` - 27 edges
3. `_build_full_analysis()` - 27 edges
4. `1.4. Danh Sách 17 FastAPI Endpoints Trong `app.py`` - 26 edges
5. `runMVOOptimization()` - 25 edges
6. `fetch_single_equity()` - 20 edges
7. `OptimizeRequest` - 18 edges
8. `compute_benchmark_comparison()` - 18 edges
9. `fetch_multi_equity_dataset()` - 17 edges
10. `solve_long_only_qp()` - 16 edges

## Surprising Connections (you probably didn't know these)
- `Bước 1: Xây dựng Hàm Tính toán tại Tầng `engine/*.py`` --references--> `_build_full_analysis()`  [INFERRED]
  docs/04_SYSTEM_AUDIT_OPTIMIZATION_AND_ENGINEERING_GUIDELINES.md → app.py
- `Bước 2: Kết nối Tầng Lưu trữ tại `engine/db_manager.py` (Nếu có lưu DB)` --references--> `record_sync_log()`  [INFERRED]
  docs/04_SYSTEM_AUDIT_OPTIMIZATION_AND_ENGINEERING_GUIDELINES.md → engine/db_manager.py
- `Bước 3: Mở Cổng Giao tiếp tại `app.py`` --references--> `OptimizeRequest`  [INFERRED]
  docs/04_SYSTEM_AUDIT_OPTIMIZATION_AND_ENGINEERING_GUIDELINES.md → app.py
- `Ca 4: Kiểm thử Khảo sát Khẩu vị Rủi ro & Tự Động Tái Tối Ưu Hóa` --references--> `runMVOOptimization()`  [INFERRED]
  docs/03_FRONTEND_UI_SYNC_AND_TEST_PLAYBOOK.md → static/textbook_mvo.js
- `1. app.py — FastAPI Gateway & Orchestrator` --references--> `seed_initial_data()`  [INFERRED]
  docs/01_BACKEND_PYTHON_FUNCTIONS_REFERENCE.md → engine/db_manager.py

## Import Cycles
- None detected.

## Communities (24 total, 3 thin omitted)

### Community 0 - "textbook_mvo.js"
Cohesion: 0.06
Nodes (83): 1. Danh Mục Toàn Bộ 48 Hàm JavaScript Theo 8 Cụm Chức Năng, Cụm 1: Quản lý Giao diện Sáng/Tối & Chuyển Tab (5 hàm), Cụm 2: Ràng buộc Trọng số TT98 & Chế độ Tiền mặt (5 hàm), Cụm 3: Quản lý Giỏ Cổ phiếu & Tìm kiếm Autocomplete (14 hàm), Cụm 4: Chế độ Nhập liệu Thủ công & Upload File Excel (9 hàm), Cụm 5: Trắc nghiệm Khẩu vị Rủi ro (3 hàm), Cụm 6: Điều khiển Chuẩn So sánh Bloomberg-Style (5 hàm), Cụm 7: Thực thi Tối ưu hóa & 8 Bộ Render Giao diện (10 hàm) (+75 more)

### Community 1 - "get_connection"
Cohesion: 0.12
Nodes (8): get_connection(), test_analytical_views_precision_and_computation(), test_date_format_and_referential_integrity(), test_market_index_ingestion_and_upsert(), test_no_duplicate_records_and_composite_pks(), test_positive_and_non_negative_values(), test_required_fields_not_null(), test_schema_tables_and_views_existence()

### Community 2 - "test_textbook_engine.py"
Cohesion: 0.19
Nodes (11): api_export_excel(), api_export_matrix(), api_optimize(), OptimizeRequest, 1.4. Redundancy #4: Chạy lại toàn bộ `_build_full_analysis` khi xuất Ma trận Tham số & Báo cáo Excel, test_benchmark_and_stress_testing_engine(), test_bounded_qp_and_mandated_cash(), test_frontend_dom_and_json_contract() (+3 more)

### Community 3 - "hayinsights_client.py"
Cohesion: 0.09
Nodes (12): Top 10 "God Nodes" (Các Nút Trung Tâm Có Độ Kết Nối Cao Nhất), compute_benchmark_comparison(), compute_stress_testing_and_var(), fetch_benchmark_series(), _generate_fallback_benchmark_series(), _slice_series_by_horizon(), sync_benchmark_index_to_db(), fetch_equity_profile_and_ratios() (+4 more)

### Community 4 - "data_exporter.py"
Cohesion: 0.12
Nodes (4): generate_input_template_xlsx(), Completed Modules (`[DONE]`), PROJECT STATE CHECKPOINT — Pure Textbook MVO v2.2 (Live HayInsights API), test_template_and_upload_roundtrip()

### Community 5 - "numpy"
Cohesion: 0.12
Nodes (18): _build_full_analysis(), 1.3. `_build_full_analysis(req: OptimizeRequest) -> dict[str, Any]`, 1.1. Redundancy #1: Tính lặp `inv_cov` + Vô hướng Merton và chạy thừa 50 bài toán SLSQP khi Fallback, 1.2. Inefficiency #2: Thiếu cơ chế Khởi tạo Nóng (Continuation Warm-Start) trong vòng lặp 50 điểm Frontier, 1.5. Redundancy #5: Tải lặp dữ liệu giá khi `benchmark_range` ngắn hơn `hayinsights_range`, 1.7. Logic Gap #7: Đám mây Monte Carlo chưa tuân thủ biên `[w_min, w_max]`, 3.3. Rủi ro Luồng #3: Ma trận Hiệp phương sai Gần Suy biến ($\kappa(\boldsymbol{\Sigma}) > 10^{10}$) trong Chế độ Bán khống, Phần 1: Kiểm Toán Liên Kết Các Functions Backend — Phát Hiện Dư Thừa (Redundancy) & Phương Án Tối Ưu Hóa (+10 more)

### Community 6 - "services"
Cohesion: 0.14
Nodes (13): key, sync, value, services, buildCommand, envVars, healthCheckPath, name (+5 more)

### Community 7 - "Portfolio Optimization by Khim (v2.4 Institutional Edition)"
Cohesion: 0.29
Nodes (6): 1. Overview, 2. Project Structure, 3. Local Development & Testing, 4. Cloud Deployment (Render.com), Key Institutional Capabilities, Portfolio Optimization by Khim (v2.4 Institutional Edition)

### Community 8 - "01. Backend Python Functions Reference (Audited & Verified v2.4)"
Cohesion: 0.20
Nodes (6): 01. Backend Python Functions Reference (Audited & Verified v2.4), 4. engine/textbook_math.py — Markowitz & Merton Quantitative Core, 5. engine/benchmark_engine.py — Benchmark Attribution & Tail Risk, Mục lục Phân hệ Backend, get_benchmark_series_from_db(), upsert_market_index_daily()

### Community 9 - "db_manager.py"
Cohesion: 0.27
Nodes (3): get_macro_series_from_db(), record_sync_log(), upsert_equity_master_and_ratios()

### Community 10 - "app.py"
Cohesion: 0.13
Nodes (5): add_no_cache_header(), api_sync_equity_to_db(), api_sync_macro_to_db(), api_sync_market_index(), api_upload_excel()

### Community 12 - "3. Kịch Bản Kiểm Thử Đầu-Cuối (End-to-End Testing Playbook)"
Cohesion: 0.17
Nodes (11): 03. Frontend UI Sync & Test Playbook, 2. Bản Đồ Ánh Xạ JSON Backend $\rightarrow$ DOM ID / Plotly Trace, 3. Kịch Bản Kiểm Thử Đầu-Cuối (End-to-End Testing Playbook), Ca 1: Kiểm thử Đồng bộ Dữ liệu Thực từ API vào Database & Báo giá Live Pill, Ca 2: Kiểm thử Chạy Tối ưu hóa Markowitz & Render Plotly, Ca 3: Kiểm thử Đổi Kỳ hạn Benchmark Tức thời (Bloomberg Strip), Ca 4: Kiểm thử Khảo sát Khẩu vị Rủi ro & Tự Động Tái Tối Ưu Hóa, Ca 5: Kiểm thử Khống chế Trần Tỷ trọng Thông tư 98 (TT98 Cap) (+3 more)

### Community 13 - "00. Master Architecture & Graphify Knowledge Graph Map"
Cohesion: 0.29
Nodes (6): 00. Master Architecture & Graphify Knowledge Graph Map, 1. Tổng Quan Kiến Trúc Hệ Thống (Master System Architecture), 2. Số Liệu Đồ Thị Tri Thức Graphify (Graphify Knowledge Graph Metrics), 3. Ma Trận Phụ Thuộc Giữa Các File Backend (Inter-Module Dependency Matrix), 4. Sơ Đồ Thực Thể Liên Kết Cơ Sở Dữ Liệu SQLite V2.1 (Star-Schema ERD), 5. Đồ Thị Luồng Gọi Hàm Master (Master Call Graph)

### Community 14 - "get_database_summary"
Cohesion: 0.36
Nodes (5): 2. engine/db_manager.py — SQLite Star-Schema Persistence, 1.6. Redundancy #6: Gọi `init_db()` (chứa `DROP VIEW IF EXISTS`) ở mọi lệnh đọc `get_database_summary()`, get_database_summary(), init_db(), seed_initial_data()

### Community 15 - "upsert_equity_prices_with_drift_check"
Cohesion: 0.20
Nodes (7): 02. Database & External API Flows (Audited & Verified v2.4), 1. Kiến Trúc Lưu Trữ SQLite V2.1 (Storage Architecture), 2. Cơ Chế Phát Hiện Lệch Giá Cổ Tức / Chia Tách (Corporate-Action Drift Guard), 4. Hướng Dẫn Sử Dụng 4 Endpoints Đồng Bộ & Kiểm Tra Database, Danh Mục Chính Xác 8 Bảng & 3 Analytical Views (`SCHEMA_DDL`), upsert_equity_prices_with_drift_check(), test_corporate_action_drift_detection()

### Community 16 - "Portfolio Optimization by Khim — Technical Documentation Hub"
Cohesion: 0.50
Nodes (3): 🌐 Các Trình Duyệt Đồ Thị Tương Tác Trực Quan (Interactive Graph Viewers), 📚 Mục Lục Tài Liệu Kỹ Thuật, Portfolio Optimization by Khim — Technical Documentation Hub

### Community 18 - "api_export_prices"
Cohesion: 0.16
Nodes (7): api_export_prices(), 6–10. Các Module Nhập/Xuất Excel & Khẩu Vị Rủi Ro, 3.1. Rủi ro Luồng #1: Xung đột Trạng thái Toàn cục `_LAST_UPLOADED_DATASET` (`engine/data_loader.py:L20`), _common_styles(), export_live_parameter_matrix_xlsx(), export_live_price_dataset_xlsx(), get_last_uploaded_dataset()

### Community 19 - "fetch_single_equity"
Cohesion: 0.22
Nodes (9): 3. engine/hayinsights_client.py — Market Data & Macro API Client, 3. Luồng Bộ Đệm 3 Tầng & Quy Tắc Kiểm Tra Độ Tươi Mới (`min_sessions_map`), 1.3. Inefficiency #3: Truy vấn $N+1$, Tải lại toàn bộ khi thiếu 1 mã & Lệch chuẩn Freshness Check giữa Single và Multi-Equity, 3.2. Rủi ro Luồng #2: Hiệu ứng "Cắt cụt Lịch sử" (`Inner-Join Truncation`) khi giỏ có mã mới niêm yết hoặc mất thanh khoản, get_cached_multi_equity_dataset(), get_single_equity_cached_payload(), fetch_multi_equity_dataset(), fetch_single_equity() (+1 more)

### Community 20 - "1.4. Danh Sách 17 FastAPI Endpoints Trong `app.py`"
Cohesion: 0.29
Nodes (9): api_download_template(), api_get_db_stats(), api_get_presets(), api_quote_ticker(), api_search_tickers(), health_check(), index_page(), 1.4. Danh Sách 17 FastAPI Endpoints Trong `app.py` (+1 more)

### Community 21 - "api_benchmark_attribution"
Cohesion: 0.22
Nodes (8): api_benchmark_attribution(), api_evaluate_quiz(), BenchmarkAttributionRequest, QuizSubmission, 1.1. `add_no_cache_header(request, call_next)`, 1.2. Pydantic Models (Schemas), 1. app.py — FastAPI Gateway & Orchestrator, test_bloomberg_benchmark_attribution_and_fullscreen_ux()

### Community 22 - "4A. Quy Trình 7 Bước Tích Hợp Một Function Từ Backend Lên Frontend UI"
Cohesion: 0.18
Nodes (10): 04. Kiểm Toán Kiến Trúc Chuyên Sâu, Tối Ưu Hóa & Quy Trình Chuẩn Phát Triển Hệ Thống (System Audit & Engineering SOP), 4A. Quy Trình 7 Bước Tích Hợp Một Function Từ Backend Lên Frontend UI, 4C. 5 Quy Tắc Bất Biến ("5 Golden Invariants") Cần Tuân Thủ Tuyệt Đối, Bước 1: Xây dựng Hàm Tính toán tại Tầng `engine/*.py`, Bước 2: Kết nối Tầng Lưu trữ tại `engine/db_manager.py` (Nếu có lưu DB), Bước 3: Mở Cổng Giao tiếp tại `app.py`, Bước 5: Lưu Trạng thái & Viết Hàm Render tại `static/textbook_mvo.js`, Bước 6: Khai báo Phần tử Giao diện tại `static/index.html` (+2 more)

## Knowledge Gaps
- **3 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `4B. Ma Trận Chỉnh Sửa Song Song Khi Thêm / Sửa / Xóa Tính Năng Ở Backend (Change-Impact Matrix)` connect `textbook_mvo.js` to `hayinsights_client.py`, `data_exporter.py`, `numpy`, `get_database_summary`, `api_export_prices`, `1.4. Danh Sách 17 FastAPI Endpoints Trong `app.py``, `api_benchmark_attribution`, `4A. Quy Trình 7 Bước Tích Hợp Một Function Từ Backend Lên Frontend UI`, `evaluate_risk_profile`?**
  _High betweenness centrality (0.130) - this node is a cross-community bridge._
- **Are the 3 inferred relationships involving `get_connection()` (e.g. with `Top 10 "God Nodes" (Các Nút Trung Tâm Có Độ Kết Nối Cao Nhất)` and `2. engine/db_manager.py — SQLite Star-Schema Persistence`) actually correct?**
  _`get_connection()` has 3 INFERRED edges - model-reasoned connections that need verification._
- **Should `textbook_mvo.js` be split into smaller, more focused modules?**
  _Cohesion score 0.05757286192068801 - nodes in this community are weakly interconnected._
- **Why does `Top 10 "God Nodes" (Các Nút Trung Tâm Có Độ Kết Nối Cao Nhất)` connect `hayinsights_client.py` to `textbook_mvo.js`, `get_connection`, `test_textbook_engine.py`, `numpy`, `00. Master Architecture & Graphify Knowledge Graph Map`, `fetch_single_equity`?**
  _High betweenness centrality (0.115) - this node is a cross-community bridge._
- **Are the 26 inferred relationships involving `4B. Ma Trận Chỉnh Sửa Song Song Khi Thêm / Sửa / Xóa Tính Năng Ở Backend (Change-Impact Matrix)` (e.g. with `api_benchmark_attribution()` and `api_get_presets()`) actually correct?**
  _`4B. Ma Trận Chỉnh Sửa Song Song Khi Thêm / Sửa / Xóa Tính Năng Ở Backend (Change-Impact Matrix)` has 26 INFERRED edges - model-reasoned connections that need verification._
- **Should `get_connection` be split into smaller, more focused modules?**
  _Cohesion score 0.12121212121212122 - nodes in this community are weakly interconnected._
- **Why does `runMVOOptimization()` connect `textbook_mvo.js` to `hayinsights_client.py`, `3. Kịch Bản Kiểm Thử Đầu-Cuối (End-to-End Testing Playbook)`, `4A. Quy Trình 7 Bước Tích Hợp Một Function Từ Backend Lên Frontend UI`?**
  _High betweenness centrality (0.107) - this node is a cross-community bridge._