# 01. Backend Python Functions Reference (Audited & Verified v2.4)

> [!IMPORTANT]
> Tài liệu này là **Từ điển Kỹ thuật Chi tiết (Comprehensive Function Dictionary)** đã được kiểm toán đối chiếu từng dòng (line-by-line audit) với toàn bộ **10 file mã nguồn Python** thuộc Backend của dự án. Mọi hàm đều được đặc tả chính xác tọa độ dòng, chữ ký, tham số, công thức toán học thực tế trong code, luồng rẽ nhánh, bảng dữ liệu SQLite tác động, và cây phả hệ gọi hàm (`Callers` $\leftrightarrow$ `Callees`).

---

## Mục lục Phân hệ Backend

- [1. app.py — FastAPI Gateway & Orchestrator](#1-apppy--fastapi-gateway--orchestrator)
- [2. engine/db_manager.py — SQLite Star-Schema Persistence](#2-enginedb_managerpy--sqlite-star-schema-persistence)
- [3. engine/hayinsights_client.py — Market Data & Macro API Client](#3-enginehayinsights_clientpy--market-data--macro-api-client)
- [4. engine/textbook_math.py — Markowitz & Merton Quantitative Core](#4-enginetextbook_mathpy--markowitz--merton-quantitative-core)
- [5. engine/benchmark_engine.py — Benchmark Attribution & Tail Risk](#5-enginebenchmark_enginepy--benchmark-attribution--tail-risk)
- [6. engine/data_loader.py — Excel/CSV Parser & Roundtrip Validator](#6-enginedata_loaderpy--excelcsv-parser--roundtrip-validator)
- [7. engine/data_exporter.py — Live Dataset & Matrix Exporter](#7-enginedata_exporterpy--live-dataset--matrix-exporter)
- [8. engine/excel_exporter.py — 8-Sheet Institutional Report Exporter](#8-engineexcel_exporterpy--8-sheet-institutional-report-exporter)
- [9. engine/risk_profiler.py — Investor Risk Aversion Quiz](#9-enginerisk_profilerpy--investor-risk-aversion-quiz)
- [10. engine/template_generator.py — Excel Template Generator](#10-enginetemplate_generatorpy--excel-template-generator)

---

## 1. app.py — FastAPI Gateway & Orchestrator

Đường dẫn: [`app.py`](file:///d:/Project%20Khim/portfolio-optimization-by-Khim-main/app.py) (598 dòng). Cổng tiếp nhận mọi yêu cầu từ trình duyệt, khởi tạo danh mục cơ sở dữ liệu lúc khởi động (`db_manager.seed_initial_data()` tại `L31-L34`) và điều phối luồng phân tích định lượng.

### 1.1. `add_no_cache_header(request, call_next)`
- **Tọa độ**: [L50-L57](file:///d:/Project%20Khim/portfolio-optimization-by-Khim-main/app.py#L50-L57)
- **Chữ ký**: `async def add_no_cache_header(request, call_next)`
- **Mục đích**: HTTP Middleware gắn header `Cache-Control: no-cache, no-store, must-revalidate, max-age=0` cho mọi request tới `/` và `/static/*` để trình duyệt luôn tải phiên bản JS/HTML mới nhất.

### 1.2. Pydantic Models (Schemas)
- **`QuizSubmission`** ([L64-L65](file:///d:/Project%20Khim/portfolio-optimization-by-Khim-main/app.py#L64-L65)): Chứa `scores: list[int]` (4 câu hỏi trắc nghiệm, mỗi câu điểm `1..4`).
- **`BenchmarkAttributionRequest`** ([L68-L78](file:///d:/Project%20Khim/portfolio-optimization-by-Khim-main/app.py#L68-L78)): Nhận `symbols`, `w_tangency`, `tangency_return`, `tangency_volatility`, `tangency_sharpe`, `rf`, `benchmark_symbol`, `benchmark_range`, `use_adjusted_close`, `input_mode`.
- **`OptimizeRequest`** ([L81-L100](file:///d:/Project%20Khim/portfolio-optimization-by-Khim-main/app.py#L81-L100)): Chứa 19 trường tham số toàn diện của một lượt chạy MVO (`input_mode`, `symbols`, `hayinsights_range`, `use_adjusted_close`, `expected_returns`, `std_devs`, `corr_matrix`, `latest_prices`, `rf`, `risk_aversion_A`, `allow_short`, `w_min`, `w_max`, `cash_mode`, `mandated_cash_pct`, `benchmark_symbol`, `benchmark_range`, `nav_vnd`, `n_monte_carlo`).

### 1.3. `_build_full_analysis(req: OptimizeRequest) -> dict[str, Any]`
- **Tọa độ**: [L103-L285](file:///d:/Project%20Khim/portfolio-optimization-by-Khim-main/app.py#L103-L285)
- **Chữ ký**: `def _build_full_analysis(req: OptimizeRequest) -> dict[str, Any]`
- **Vai trò**: **Core Orchestrator** trung tâm của toàn bộ hệ thống backend (Graphify God Node — 20 edges).
- **Luồng giải thuật chi tiết**:
  1. *Bước 1 (Xử lý Dữ liệu & Tính Moments)*:
     - **Nhánh Manual (`L112-L129`)**: Khi `req.input_mode == "manual"` và có đủ `expected_returns`, `std_devs`, `corr_matrix` $\rightarrow$ gọi [`textbook_math.build_moments_from_manual`](file:///d:/Project%20Khim/portfolio-optimization-by-Khim-main/engine/textbook_math.py#L57-L103). Kiểm tra thêm `data_loader.get_last_uploaded_dataset()` (`L121`); nếu danh sách mã trùng khớp với file Excel vừa tải lên thì đính kèm `prices_df`, `volumes_df`, `daily_returns_df` vào `moments` để tính Historical VaR và Benchmark Attribution thực tế.
     - **Nhánh HayInsights Live/DB (`L130-L145`)**: Gọi [`hayinsights_client.fetch_multi_equity_dataset`](file:///d:/Project%20Khim/portfolio-optimization-by-Khim-main/engine/hayinsights_client.py#L536-L663), sau đó gọi [`textbook_math.compute_moments_from_prices`](file:///d:/Project%20Khim/portfolio-optimization-by-Khim-main/engine/textbook_math.py#L22-L54) và gán `moments["latest_prices"] = live["latest_raw_prices"]` (dùng giá đóng cửa chưa điều chỉnh để chia lô chẵn 100 cổ phiếu khớp thực tế sàn HOSE/HNX).
  2. *Bước 2 (Giải bài toán Tối ưu hóa Danh mục Rủi ro — `L156-L173`)*:
     - Nếu `req.allow_short == True`: Gọi [`textbook_math.solve_merton_closed_form(mu, cov, req.rf, num_frontier=50)`](file:///d:/Project%20Khim/portfolio-optimization-by-Khim-main/engine/textbook_math.py#L119-L206).
     - Nếu `req.allow_short == False`: Gọi [`textbook_math.solve_long_only_qp(mu, cov, req.rf, allow_short=False, w_min=req.w_min, w_max=req.w_max, num_frontier=50)`](file:///d:/Project%20Khim/portfolio-optimization-by-Khim-main/engine/textbook_math.py#L209-L383).
  3. *Bước 3 (Danh mục Chia đều $1/N$ — `L174-L175`)*: Tính `w_eq = np.ones(n) / n` và gọi [`textbook_math._portfolio_stats`](file:///d:/Project%20Khim/portfolio-optimization-by-Khim-main/engine/textbook_math.py#L106-L116).
  4. *Bước 4 (Danh mục Hoàn chỉnh $C$ & Hàm Hữu dụng — `L177-L185`)*: Gọi [`textbook_math.compute_complete_portfolio`](file:///d:/Project%20Khim/portfolio-optimization-by-Khim-main/engine/textbook_math.py#L386-L458).
  5. *Bước 5 (Đối chuẩn Benchmark Attribution — `L188-L210`)*: Nếu `bm_rng != opt_rng` (và không ở chế độ manual), tải chuỗi giá theo `bm_rng`, sau đó gọi [`benchmark_engine.compute_benchmark_comparison`](file:///d:/Project%20Khim/portfolio-optimization-by-Khim-main/engine/benchmark_engine.py#L231-L341).
  6. *Bước 6 (Kiểm định Sức chịu đựng & VaR/CVaR — `L212-L220`)*: Gọi [`benchmark_engine.compute_stress_testing_and_var`](file:///d:/Project%20Khim/portfolio-optimization-by-Khim-main/engine/benchmark_engine.py#L344-L490).
  7. *Bước 7 (Mô phỏng Đám mây Monte Carlo — `L222-L228`)*: Gọi [`textbook_math.simulate_monte_carlo`](file:///d:/Project%20Khim/portfolio-optimization-by-Khim-main/engine/textbook_math.py#L461-L501) với số lượng giới hạn trong `[500, 6000]`.
- **Đầu ra**: Dictionary gồm 33 khóa JSON trả về cho Frontend hoặc bộ xuất Excel.
- **Gọi bởi (Callers)**: [`api_optimize`](file:///d:/Project%20Khim/portfolio-optimization-by-Khim-main/app.py#L411), [`api_export_matrix`](file:///d:/Project%20Khim/portfolio-optimization-by-Khim-main/app.py#L561), [`api_export_excel`](file:///d:/Project%20Khim/portfolio-optimization-by-Khim-main/app.py#L587).

### 1.4. Danh Sách 17 FastAPI Endpoints Trong `app.py`
| Endpoint | Hàm Xử Lý | Dòng | Các Hàm Engine Được Gọi Trực Tiếp |
| :--- | :--- | :---: | :--- |
| `GET /` | [`index_page`](file:///d:/Project%20Khim/portfolio-optimization-by-Khim-main/app.py#L288-L300) | `L288-L300` | Đọc `static/index.html` kèm No-Cache headers. |
| `GET /healthz` | [`health_check`](file:///d:/Project%20Khim/portfolio-optimization-by-Khim-main/app.py#L303-L305) | `L303-L305` | Trả về `{"status": "ok", "version": "2.4.4"}`. |
| `GET /api/presets` | [`api_get_presets`](file:///d:/Project%20Khim/portfolio-optimization-by-Khim-main/app.py#L308-L318) | `L308-L318` | `hayinsights_client.load_api_key()`, `VN_TICKER_DIRECTORY`, `risk_profiler.QUIZ_QUESTIONS`. |
| `GET /api/tickers` | [`api_search_tickers`](file:///d:/Project%20Khim/portfolio-optimization-by-Khim-main/app.py#L321-L326) | `L321-L326` | `hayinsights_client.search_tickers(query=q, limit=limit)`. |
| `GET /api/hayinsights/quote/{symbol}` | [`api_quote_ticker`](file:///d:/Project%20Khim/portfolio-optimization-by-Khim-main/app.py#L329-L334) | `L329-L334` | `hayinsights_client.validate_and_quote_ticker(symbol)`. |
| `GET /api/db/stats` | [`api_get_db_stats`](file:///d:/Project%20Khim/portfolio-optimization-by-Khim-main/app.py#L337-L343) | `L337-L343` | `db_manager.get_database_summary()`. |
| `POST /api/db/sync/equity/{symbol}` | [`api_sync_equity_to_db`](file:///d:/Project%20Khim/portfolio-optimization-by-Khim-main/app.py#L346-L365) | `L346-L365` | `hayinsights_client.fetch_single_equity(sym, range_str)` + `fetch_equity_profile_and_ratios(sym)`. |
| `POST /api/db/sync/index/{code}` | [`api_sync_market_index`](file:///d:/Project%20Khim/portfolio-optimization-by-Khim-main/app.py#L368-L378) | `L368-L378` | `benchmark_engine.sync_benchmark_index_to_db(sym, range_str)`. |
| `POST /api/db/sync/macro` | [`api_sync_macro_to_db`](file:///d:/Project%20Khim/portfolio-optimization-by-Khim-main/app.py#L381-L397) | `L381-L397` | `hayinsights_client.fetch_macro_data(endpoint_type, params)`. |
| `POST /api/quiz` | [`api_evaluate_quiz`](file:///d:/Project%20Khim/portfolio-optimization-by-Khim-main/app.py#L400-L405) | `L400-L405` | `risk_profiler.evaluate_risk_profile(sub.scores)`. |
| `POST /api/optimize` | [`api_optimize`](file:///d:/Project%20Khim/portfolio-optimization-by-Khim-main/app.py#L408-L413) | `L408-L413` | `_build_full_analysis(req)`. |
| `POST /api/benchmark-attribution` | [`api_benchmark_attribution`](file:///d:/Project%20Khim/portfolio-optimization-by-Khim-main/app.py#L416-L456) | `L416-L456` | `data_loader.get_last_uploaded_dataset()`, `hayinsights_client.fetch_multi_equity_dataset()`, `benchmark_engine.compute_benchmark_comparison()`. |
| `POST /api/upload-excel` | [`api_upload_excel`](file:///d:/Project%20Khim/portfolio-optimization-by-Khim-main/app.py#L459-L476) | `L459-L476` | `data_loader.parse_uploaded_file(content, file.filename)`. |
| `GET /api/template/{kind}` | [`api_download_template`](file:///d:/Project%20Khim/portfolio-optimization-by-Khim-main/app.py#L479-L488) | `L479-L488` | `template_generator.generate_input_template_xlsx(mode)`. |
| `POST /api/export-prices` | [`api_export_prices`](file:///d:/Project%20Khim/portfolio-optimization-by-Khim-main/app.py#L491-L551) | `L491-L551` | `data_loader.get_last_uploaded_dataset()`, `hayinsights_client.fetch_multi_equity_dataset()`, `textbook_math.compute_moments_from_prices()`, `data_exporter.export_live_price_dataset_xlsx()`. |
| `POST /api/export-matrix` | [`api_export_matrix`](file:///d:/Project%20Khim/portfolio-optimization-by-Khim-main/app.py#L554-L581) | `L554-L581` | `_build_full_analysis(req)` $\rightarrow$ `data_exporter.export_live_parameter_matrix_xlsx()`. |
| `POST /api/export-excel` | [`api_export_excel`](file:///d:/Project%20Khim/portfolio-optimization-by-Khim-main/app.py#L584-L598) | `L584-L598` | `_build_full_analysis(req)` $\rightarrow$ `excel_exporter.export_mvo_institutional_workbook(analysis)`. |

---

## 2. engine/db_manager.py — SQLite Star-Schema Persistence

Đường dẫn: [`engine/db_manager.py`](file:///d:/Project%20Khim/portfolio-optimization-by-Khim-main/engine/db_manager.py) (1,115 dòng). Quản lý cơ sở dữ liệu `data/hayinsights_quant.sqlite3` gồm 8 bảng và 3 Analytical Views (`vw_equity_master_dashboard`, `vw_equity_daily_returns`, `vw_macro_latest_snapshot`).

- **[`get_connection()`](file:///d:/Project%20Khim/portfolio-optimization-by-Khim-main/engine/db_manager.py#L32-L44)** (`L32-L44`): Mở kết nối SQLite với `timeout=5.0`, `row_factory = sqlite3.Row`, `PRAGMA foreign_keys = ON`, `PRAGMA journal_mode = WAL`, `PRAGMA synchronous = NORMAL`, `PRAGMA busy_timeout = 5000`.
- **[`init_db()`](file:///d:/Project%20Khim/portfolio-optimization-by-Khim-main/engine/db_manager.py#L278-L285)** (`L278-L285`): Thực thi `SCHEMA_DDL` (`L51-L275`) khởi tạo 3 bảng Dimension, 4 bảng Fact, 1 bảng System Log và 3 Views.
- **[`seed_initial_data()`](file:///d:/Project%20Khim/portfolio-optimization-by-Khim-main/engine/db_manager.py#L292-L375)** (`L292-L375`): Nạp danh mục gốc cho 159 cổ phiếu (`dim_equities`), 4 chỉ số thị trường (`dim_market_indices`), và 12 chỉ báo vĩ mô (`dim_macro_indicators`). Không nạp bất kỳ dòng dữ liệu mẫu nào vào 4 bảng Fact.
- **[`upsert_equity_prices_with_drift_check(symbol, points, formula_version)`](file:///d:/Project%20Khim/portfolio-optimization-by-Khim-main/engine/db_manager.py#L382-L474)** (`L382-L474`):
  - Truy vấn toàn bộ các ngày giao dịch trùng lặp giữa `points` từ API và `fact_equity_daily_prices`.
  - Duyệt từ ngày mới nhất trở về trước: nếu độ lệch tương đối `abs(api_adj - db_adj) / db_adj > 0.0001` (`> 0.01%`), bật cờ `drift_detected = True` báo hiệu có sự kiện chia cổ tức/tách cổ phiếu để hàm gọi (`fetch_single_equity`) tự động tải lại lịch sử `5y` đầy đủ.
  - Thực thi `executemany` với `ON CONFLICT(symbol, trading_date) DO UPDATE` và cập nhật `formula_version` trên `dim_equities`.
- **[`upsert_equity_master_and_ratios(symbol, payload, headers)`](file:///d:/Project%20Khim/portfolio-optimization-by-Khim-main/engine/db_manager.py#L477-L590)** (`L477-L590`): Bóc tách payload từ `GET /openapi/v1/market/vn/equities/{symbol}` để cập nhật `dim_equities` (`sector`, `overview.tradingUnit`, `sharesOutstanding`, `marketCap`) và nạp bộ chỉ số định giá (`pe_ratio`, `pb_ratio`, `roe`, `roa`, `eps`, `high_52w`, `low_52w`, `change_1d_pct`..`change_3y_pct`) vào `fact_equity_financial_ratios`.
- **[`record_sync_log(resource_id, sync_scope, last_synced_date, records_upserted, headers, http_status)`](file:///d:/Project%20Khim/portfolio-optimization-by-Khim-main/engine/db_manager.py#L592-L643)** (`L592-L643`): Bóc tách HTTP response headers (`x-ratelimit-remaining`, `x-ratelimit-weight-used`, `x-ratelimit-reset`) và upsert vào `sys_sync_logs`.
- **[`get_single_equity_cached_payload(symbol, range_str)`](file:///d:/Project%20Khim/portfolio-optimization-by-Khim-main/engine/db_manager.py#L650-L746)** (`L650-L746`): Đọc chuỗi giá từ `fact_equity_daily_prices`. Kiểm tra 2 điều kiện: (1) `len(rows) >= min_required` theo `min_sessions_map` (`1y: 200`, `6m: 90`, v.v.) và (2) độ tươi mới `(date.today() - latest_dt).days <= 5`.
- **[`get_cached_multi_equity_dataset(symbols, range_str, use_adjusted)`](file:///d:/Project%20Khim/portfolio-optimization-by-Khim-main/engine/db_manager.py#L749-L851)** (`L749-L851`): Truy vấn chuỗi giá cho danh sách mã, căn chỉnh ngày giao dịch chung bằng `pd.concat(..., join="inner").dropna(how="any")` và kiểm tra `len(df_aligned) >= min_required`.
- **[`upsert_market_index_daily(index_code, payload)`](file:///d:/Project%20Khim/portfolio-optimization-by-Khim-main/engine/db_manager.py#L858-L902)** (`L858-L902`): Chuyển đổi mảng Unix timestamps `t` và OHLCV `o, h, l, c, v` từ VNDirect DChart API thành các bản ghi trong `fact_market_indices_daily`.
- **[`get_benchmark_series_from_db(index_code, lookback_days)`](file:///d:/Project%20Khim/portfolio-optimization-by-Khim-main/engine/db_manager.py#L905-L929)** (`L905-L929`): Đọc chuỗi điểm đóng cửa `close_point` từ `fact_market_indices_daily` thành `pd.Series`.
- **[`upsert_macro_time_series(indicator_code, points)`](file:///d:/Project%20Khim/portfolio-optimization-by-Khim-main/engine/db_manager.py#L932-L985)** (`L932-L985`): Kiểm tra khóa ngoại trong `dim_macro_indicators` và nạp chuỗi thời gian vĩ mô (`value`, `bid_value`, `ask_value`, `previous_value`, `forecast_value`, `change_value`, `change_pct`) vào `fact_macro_time_series`.
- **[`get_macro_series_from_db(indicator_code, lookback_days)`](file:///d:/Project%20Khim/portfolio-optimization-by-Khim-main/engine/db_manager.py#L988-L1008)** (`L988-L1008`): Truy vấn chuỗi lịch sử chỉ báo vĩ mô từ `fact_macro_time_series`.
- **[`ingest_uploaded_prices_df(df_prices, df_volumes)`](file:///d:/Project%20Khim/portfolio-optimization-by-Khim-main/engine/db_manager.py#L1011-L1066)** (`L1011-L1066`): Tự động đăng ký mã cổ phiếu mới vào `dim_equities` (`exchange='UPLOADED'`) và nạp bảng giá Excel tải lên vào `fact_equity_daily_prices`.
- **[`get_database_summary()`](file:///d:/Project%20Khim/portfolio-optimization-by-Khim-main/engine/db_manager.py#L1073-L1115)** (`L1073-L1115`): Tổng hợp dung lượng file `.sqlite3`, số dòng của 8 bảng, 10 dòng `sys_sync_logs` mới nhất và 5 dòng mẫu từ `vw_equity_master_dashboard`.

---

## 3. engine/hayinsights_client.py — Market Data & Macro API Client

Đường dẫn: [`engine/hayinsights_client.py`](file:///d:/Project%20Khim/portfolio-optimization-by-Khim-main/engine/hayinsights_client.py) (877 dòng). Kết nối tới `BASE_URL = "https://api.hayinsights.com/openapi/v1"` sử dụng header xác thực `"X-API-Key": key`.

- **[`load_api_key()`](file:///d:/Project%20Khim/portfolio-optimization-by-Khim-main/engine/hayinsights_client.py#L223-L246)** (`L223-L246`): Tìm đọc API key theo thứ tự: biến môi trường `HAYINSIGHTS_API_KEY` $\rightarrow$ các file `.env`, `env`, `.API key.txt`, `API key.txt`.
- **[`search_tickers(query, limit=30)`](file:///d:/Project%20Khim/portfolio-optimization-by-Khim-main/engine/hayinsights_client.py#L249-L281)** (`L249-L281`): Tìm kiếm trên `VN_TICKER_DIRECTORY` (159 cổ phiếu HOSE/HNX/UPCoM).
- **[`_generate_calibrated_equity_payload(symbol, range_str)`](file:///d:/Project%20Khim/portfolio-optimization-by-Khim-main/engine/hayinsights_client.py#L284-L347)** (`L284-L347`): Sinh chuỗi giá dự phòng có kiểm soát trong RAM khi không thể kết nối mạng và SQLite trống. **Không ghi vào SQLite.**
- **[`fetch_single_equity(symbol, range_str="1y", api_key=None)`](file:///d:/Project%20Khim/portfolio-optimization-by-Khim-main/engine/hayinsights_client.py#L350-L473)** (`L350-L473`):
  1. Kiểm tra RAM cache `_PRICE_CACHE` (TTL 900s).
  2. Kiểm tra SQLite qua `db_manager.get_single_equity_cached_payload(sym, api_rng)`.
  3. Gọi `GET {BASE_URL}/market/vn/equities/{sym}/prices?range={api_rng}` (tối đa 2 lần thử, timeout 12s).
  4. Ghi vào SQLite qua `db_manager.upsert_equity_prices_with_drift_check`. Nếu `drift_detected == True` và `api_rng != "5y"`, tự động gọi thêm `range=5y` để làm mới toàn bộ lịch sử giá điều chỉnh.
- **[`validate_and_quote_ticker(symbol, api_key=None)`](file:///d:/Project%20Khim/portfolio-optimization-by-Khim-main/engine/hayinsights_client.py#L476-L533)** (`L476-L533`): Gọi `fetch_single_equity(sym, range_str="1m")` lấy giá đóng cửa mới nhất; nếu lỗi thì fallback đọc dòng mới nhất từ `fact_equity_daily_prices`.
- **[`fetch_multi_equity_dataset(symbols, range_str="1y", use_adjusted=True, api_key=None)`](file:///d:/Project%20Khim/portfolio-optimization-by-Khim-main/engine/hayinsights_client.py#L536-L663)** (`L536-L663`):
  1. Kiểm tra SQLite qua `db_manager.get_cached_multi_equity_dataset`.
  2. Nếu chưa đủ trong DB, dùng `ThreadPoolExecutor(max_workers=2)` gọi `fetch_single_equity` cho từng mã.
  3. Căn chỉnh ngày giao dịch chung (`pd.concat(..., join="inner").dropna(how="any")`) và cắt lát lịch cho `2y` / `ytd`.
- **[`fetch_equity_profile_and_ratios(symbol, api_key=None)`](file:///d:/Project%20Khim/portfolio-optimization-by-Khim-main/engine/hayinsights_client.py#L666-L739)** (`L666-L739`): Gọi `GET {BASE_URL}/market/vn/equities/{sym}` và lưu vào `dim_equities` + `fact_equity_financial_ratios` qua `db_manager.upsert_equity_master_and_ratios`.
- **[`fetch_macro_data(endpoint_type="rates_yields", params=None, api_key=None)`](file:///d:/Project%20Khim/portfolio-optimization-by-Khim-main/engine/hayinsights_client.py#L742-L877)** (`L742-L877`): Gọi `GET {BASE_URL}/macro/{sub_path}`, phân giải `indicator_code` (`VN_BOND_10Y`, `FX_USD_VND`, `VN_POLICY_RATE`, v.v.), chuẩn hóa mảng điểm dữ liệu và nạp vào `fact_macro_time_series` qua `db_manager.upsert_macro_time_series`.

---

## 4. engine/textbook_math.py — Markowitz & Merton Quantitative Core

Đường dẫn: [`engine/textbook_math.py`](file:///d:/Project%20Khim/portfolio-optimization-by-Khim-main/engine/textbook_math.py) (501 dòng).

- **[`compute_moments_from_prices(df_prices, trading_days=252)`](file:///d:/Project%20Khim/portfolio-optimization-by-Khim-main/engine/textbook_math.py#L22-L54)** (`L22-L54`):
  - Tính lợi suất phần trăm ngày: `rets = df_clean.pct_change().dropna(how="any")`.
  - Kỳ vọng lợi suất năm hóa: $\boldsymbol{\mu} = \bar{\mathbf{r}} \times 252$.
  - Ma trận hiệp phương sai mẫu năm hóa (Bessel `ddof=1`): $\boldsymbol{\Sigma} = \text{Cov}(\mathbf{r}) \times 252$.
  - Độ lệch chuẩn $\boldsymbol{\sigma} = \sqrt{\text{diag}(\boldsymbol{\Sigma})}$ và ma trận tương quan $\mathbf{C}$.
- **[`build_moments_from_manual(symbols, expected_returns, std_devs, corr_matrix, latest_prices)`](file:///d:/Project%20Khim/portfolio-optimization-by-Khim-main/engine/textbook_math.py#L57-L103)** (`L57-L103`): Đối xứng hóa $\mathbf{C} \leftarrow \frac{1}{2}(\mathbf{C} + \mathbf{C}^\top)$, tính $\boldsymbol{\Sigma} = \text{diag}(\boldsymbol{\sigma}) \mathbf{C} \text{diag}(\boldsymbol{\sigma})$ và hiệu chỉnh trị riêng dương nếu $\lambda_{\min} \le 10^{-8}$.
- **[`_portfolio_stats(weights, mu, cov, rf)`](file:///d:/Project%20Khim/portfolio-optimization-by-Khim-main/engine/textbook_math.py#L106-L116)** (`L106-L116`): Tính `expected_return`, `variance`, `volatility`, `sharpe_ratio`.
- **[`solve_merton_closed_form(mu, cov, rf, num_frontier=50)`](file:///d:/Project%20Khim/portfolio-optimization-by-Khim-main/engine/textbook_math.py#L119-L206)** (`L119-L206`): Giải nghiệm giải tích Merton (1972) với 4 vô hướng $A, B, C, D$, $\mathbf{w}_{\text{GMV}} = \frac{\boldsymbol{\Sigma}^{-1}\mathbf{1}}{C}$, $\mathbf{w}_T = \frac{\boldsymbol{\Sigma}^{-1}(\boldsymbol{\mu} - R_f\mathbf{1})}{\mathbf{1}^\top \boldsymbol{\Sigma}^{-1}(\boldsymbol{\mu} - R_f\mathbf{1})}$ và đường biên $\mathbf{w}(E) = \mathbf{g} + \mathbf{h}E$. Nếu điểm tiếp tuyến giải tích rơi xuống nhánh dưới của hyperbol, tự động chuyển sang giải số trên nhánh trên (`L158-L161`).
- **[`solve_long_only_qp(mu, cov, rf, allow_short=False, w_min=0.0, w_max=1.0, num_frontier=50)`](file:///d:/Project%20Khim/portfolio-optimization-by-Khim-main/engine/textbook_math.py#L209-L383)** (`L209-L383`): Giải quy hoạch bậc hai SLSQP với ràng buộc hộp $w_{\min} \le w_i \le w_{\max}$ và $\sum w_i = 1$. Tự động điều chỉnh biên khả thi nếu $w_{\min} > 1/N$ hoặc $w_{\max} < 1/N$ (`L234-L250`).
- **[`compute_complete_portfolio(tangency_stats, w_tangency, rf, risk_aversion_A, allow_leverage, cash_mode, mandated_cash_weight)`](file:///d:/Project%20Khim/portfolio-optimization-by-Khim-main/engine/textbook_math.py#L386-L458)** (`L386-L458`): Tính tỷ trọng tài sản rủi ro $y^*$ theo chế độ `bkm` ($y^* = \frac{E(R_T)-R_f}{A\sigma_T^2}$) hoặc `mandated` ($y^* = 1 - w_{\text{cash}}$), điểm hữu dụng $U^*$, tọa độ đường `cal_line` và `indifference_curve`.
- **[`simulate_monte_carlo(mu, cov, rf, n_portfolios=3000, allow_short=False, seed=42)`](file:///d:/Project%20Khim/portfolio-optimization-by-Khim-main/engine/textbook_math.py#L461-L501)** (`L461-L501`): Sinh đám mây danh mục ngẫu nhiên bằng kết hợp 2 phân phối Dirichlet ($\alpha=1.0$ và $\alpha=0.35$) và tính phương sai vector hóa bằng `np.einsum("ij,jk,ik->i", weights_mat, cov, weights_mat)`.

---

## 5. engine/benchmark_engine.py — Benchmark Attribution & Tail Risk

Đường dẫn: [`engine/benchmark_engine.py`](file:///d:/Project%20Khim/portfolio-optimization-by-Khim-main/engine/benchmark_engine.py) (490 dòng).

- **[`_generate_fallback_benchmark_series(symbol, n_days)`](file:///d:/Project%20Khim/portfolio-optimization-by-Khim-main/engine/benchmark_engine.py#L47-L66)** (`L47-L66`): Sinh chuỗi chỉ số dự phòng trong RAM khi mất kết nối.
- **[`_slice_series_by_horizon(s, rng_key)`](file:///d:/Project%20Khim/portfolio-optimization-by-Khim-main/engine/benchmark_engine.py#L69-L90)** (`L69-L90`): Cắt lát `pd.Series` hoặc `pd.DataFrame` theo kỳ hạn (`6m`, `1y`, `2y`, `3y`, `5y`, `ytd`, `max`).
- **[`fetch_benchmark_series(symbol="VNINDEX", range_str="1y")`](file:///d:/Project%20Khim/portfolio-optimization-by-Khim-main/engine/benchmark_engine.py#L93-L176)** (`L93-L176`): Kiểm tra `_BENCHMARK_CACHE` $\rightarrow$ đọc SQLite qua `db_manager.get_benchmark_series_from_db` $\rightarrow$ gọi VNDirect DChart API (`https://dchart-api.vndirect.com.vn/dchart/history`) và lưu Write-Through qua `db_manager.upsert_market_index_daily`.
- **[`sync_benchmark_index_to_db(symbol="VNINDEX", range_str="1y")`](file:///d:/Project%20Khim/portfolio-optimization-by-Khim-main/engine/benchmark_engine.py#L179-L228)** (`L179-L228`): Tải trực tiếp OHLCV của `VNINDEX`, `VN30`, `HNX`, `UPCOM` từ VNDirect DChart API và lưu vào `fact_market_indices_daily`.
- **[`compute_benchmark_comparison(df_asset_returns, w_tangency, tangency_stats, rf, benchmark_symbol, range_str)`](file:///d:/Project%20Khim/portfolio-optimization-by-Khim-main/engine/benchmark_engine.py#L231-L341)** (`L231-L341`): Căn chỉnh ngày giao dịch chung giữa danh mục và chỉ số, tính Beta ($\beta$), Jensen's Alpha ($\alpha$), Tracking Error, Information Ratio, $R^2$ và chuỗi tài sản tích lũy gốc 100 (`portfolio_base100`, `benchmark_base100`).
- **[`compute_stress_testing_and_var(df_asset_returns, w_tangency, tangency_stats, complete_stats, beta, nav_vnd, rf)`](file:///d:/Project%20Khim/portfolio-optimization-by-Khim-main/engine/benchmark_engine.py#L344-L490)** (`L344-L490`): Tính Historical / Parametric VaR & CVaR (95%, 99%) cho 1 ngày và 21 ngày, Maximum Drawdown (MDD), và mô phỏng 4 kịch bản khủng hoảng (`covid_2020`, `bond_crisis_2022`, `fx_sbv_2024`, `stress_15pct`).

---

## 6–10. Các Module Nhập/Xuất Excel & Khẩu Vị Rủi Ro

- **[`engine/data_loader.py`](file:///d:/Project%20Khim/portfolio-optimization-by-Khim-main/engine/data_loader.py)** (`L1-L180`):
  - [`get_last_uploaded_dataset()`](file:///d:/Project%20Khim/portfolio-optimization-by-Khim-main/engine/data_loader.py#L23-L25) (`L23-L25`): Trả về `_LAST_UPLOADED_DATASET`.
  - [`parse_uploaded_file(file_bytes, filename)`](file:///d:/Project%20Khim/portfolio-optimization-by-Khim-main/engine/data_loader.py#L28-L180) (`L28-L180`): Tự động phát hiện Mode A (`Parameters`) hoặc Mode B (`Historical_Prices` + `Trading_Volume`) và nạp vào SQLite qua `db_manager.ingest_uploaded_prices_df`.
- **[`engine/data_exporter.py`](file:///d:/Project%20Khim/portfolio-optimization-by-Khim-main/engine/data_exporter.py)** (`L1-L425`):
  - [`_common_styles()`](file:///d:/Project%20Khim/portfolio-optimization-by-Khim-main/engine/data_exporter.py#L26-L74) (`L26-L74`), [`export_live_price_dataset_xlsx(...)`](file:///d:/Project%20Khim/portfolio-optimization-by-Khim-main/engine/data_exporter.py#L77-L263) (`L77-L263`), [`export_live_parameter_matrix_xlsx(...)`](file:///d:/Project%20Khim/portfolio-optimization-by-Khim-main/engine/data_exporter.py#L266-L425) (`L266-L425`).
- **[`engine/excel_exporter.py`](file:///d:/Project%20Khim/portfolio-optimization-by-Khim-main/engine/excel_exporter.py)** (`L1-L716`):
  - [`export_mvo_institutional_workbook(data)`](file:///d:/Project%20Khim/portfolio-optimization-by-Khim-main/engine/excel_exporter.py#L22-L716) (`L22-L716`): Kết xuất workbook 8 sheets với công thức Excel sống.
- **[`engine/risk_profiler.py`](file:///d:/Project%20Khim/portfolio-optimization-by-Khim-main/engine/risk_profiler.py)** (`L1-L104`):
  - [`evaluate_risk_profile(scores)`](file:///d:/Project%20Khim/portfolio-optimization-by-Khim-main/engine/risk_profiler.py#L64-L104) (`L64-L104`): Nội suy hệ số ngại rủi ro $A \in [1.2, 8.0]$ từ 4 câu hỏi khảo sát.
- **[`engine/template_generator.py`](file:///d:/Project%20Khim/portfolio-optimization-by-Khim-main/engine/template_generator.py)** (`L1-L82`):
  - [`generate_input_template_xlsx(mode)`](file:///d:/Project%20Khim/portfolio-optimization-by-Khim-main/engine/template_generator.py#L14-L82) (`L14-L82`): Tạo file Excel mẫu chuẩn.
