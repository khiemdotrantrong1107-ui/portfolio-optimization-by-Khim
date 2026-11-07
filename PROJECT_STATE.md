# PROJECT STATE CHECKPOINT — Pure Textbook MVO v2.2 (Live HayInsights API)

- **Last Updated:** 2026-11-06
- **Status:** COMPLETED (100% Modules Built & Verified — 6/6 Test Suites Passing)

## Completed Modules (`[DONE]`)
- `[DONE]` [`engine/hayinsights_client.py`](./engine/hayinsights_client.py): Kết nối trực tiếp HayInsights OpenAPI (`api-v2.hayinsights.com/openapi/v1/market/vn/equities/{symbol}/prices`) sử dụng `HAYINSIGHTS_API_KEY` từ `.env`. Kéo song song đa luồng (`ThreadPoolExecutor`), tích hợp bộ nhớ đệm TTL 15 phút, dùng `adjustedClose` (`vnsc-adjusted-close-v1`) cho tính toán lợi suất & ma trận hiệp phương sai $\boldsymbol{\Sigma}$, và dùng `close` thực tế cho bảng chia lô chẵn 100 cổ phiếu.
- `[DONE]` [`engine/textbook_math.py`](./engine/textbook_math.py): Đại số ma trận kinh điển Markowitz (1952) & Merton (1972), chuẩn hóa 252 phiên, giải tích đóng $\boldsymbol{\Sigma}^{-1}$ (Scalars $A, B, C, D$) khi cho phép bán khống và Quadratic Programming (SLSQP) khi không bán khống, định lý tách 2 quỹ $y^*$, đường CAL, đường bàng quan và mô phỏng Monte Carlo.
- `[DONE]` [`engine/risk_profiler.py`](./engine/risk_profiler.py): Khảo sát khẩu vị rủi ro 4 câu hỏi trắc nghiệm khách hàng, quy đổi điểm số (4..16) sang hệ số ngại rủi ro $A \in [1.2, 8.0]$.
- `[DONE]` [`engine/data_loader.py`](./engine/data_loader.py): Nạp dữ liệu 252 phiên cổ phiếu HOSE, nhập tay ma trận giáo trình và đọc file `.xlsx` / `.csv` tải lên.
- `[DONE]` [`engine/template_generator.py`](./engine/template_generator.py): Xuất file Excel mẫu (`Parameters` & `Historical_Prices`) cho người dùng tải về điền dữ liệu.
- `[DONE]` [`engine/excel_exporter.py`](./engine/excel_exporter.py): Xuất báo cáo Excel chuẩn công ty quản lý quỹ chuyên nghiệp gồm 6 sheet từ A-Z kèm công thức sống (`=SUM()`, `=MMULT()`, `=MINVERSE()`) và biểu đồ Scatter Chart nhúng sẵn.
- `[DONE]` [`app.py`](./app.py) & [`static/index.html`](./static/index.html) & [`static/textbook_mvo.js`](./static/textbook_mvo.js): Backend FastAPI + Giao diện Web tương tác Plotly.js kèm Tab **⚡ Live HayInsights API**.
- `[DONE]` [`tests/test_textbook_engine.py`](./tests/test_textbook_engine.py): Toàn bộ 6 bộ kiểm thử tự động đạt 100% PASS.
