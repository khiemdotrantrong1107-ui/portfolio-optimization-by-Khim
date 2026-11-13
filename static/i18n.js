// Internationalization Dictionary & Locale Formatting (VI / EN) for Textbook MVO
(function () {
  'use strict';

  var MVO_I18N = {
    vi: {
      'app.title': 'Tối Ưu Hóa Danh Mục Markowitz',
      'app.subtitle': 'Mô hình Biên Hiệu Quả Mean-Variance • Long-Only Không Đòn Bẩy',
      'nav.export_matrix': 'Xuất Ma trận',
      'nav.export_prices': 'Xuất Dữ liệu Giá',
      'nav.export_excel': 'Xuất Excel (8 Sheet)',
      'nav.theme_toggle': 'Chuyển chế độ Sáng / Tối',
      'nav.lang_vi': 'VI',
      'nav.lang_en': 'EN',
      'nav.export_bar_mobile_label': 'Xuất báo cáo từ kết quả đã chốt:',

      'banner.stale': 'Thông số đầu vào đã thay đổi so với kết quả đang hiển thị — bấm Chạy Tối Ưu Hóa để cập nhật số liệu và mở khóa Xuất báo cáo.',
      'banner.computing': 'Đang tối ưu hóa danh mục và đồng bộ dữ liệu...',
      'banner.error_title': 'Không thể tối ưu hóa với ràng buộc hiện tại',
      'banner.no_positive_excess': 'Không có cổ phiếu nào đạt E(R) > Rf trong kỳ quan sát: mô hình giữ 100% Tiền mặt (y* = 0%) theo giả định không đòn bẩy; danh mục rủi ro lấy điểm Tham chiếu Biên hiệu quả (sharpe tối đa có ràng buộc).',
      'banner.short_mode': 'Chế độ Tham chiếu Học thuật (Bán khống / Merton 1972 không ràng buộc): bỏ qua giới hạn sàn/trần tỷ trọng và tắt Thực thi Lô 100.',
      'banner.singleton_prefix': 'Miền ràng buộc suy biến thành điểm duy nhất:',

      'kpi.max_sharpe': 'Max Sharpe (Tangency)',
      'kpi.optimal_risky': 'Rủi ro Tối ưu',
      'kpi.gmv_sr': 'Sharpe GMV',
      'kpi.exp_ret': 'Lợi suất Kỳ vọng E(R)',
      'kpi.annualized_252': 'Quy năm 252 phiên (Số học)',
      'kpi.volatility': 'Độ biến động (σ)',
      'kpi.min_risk_gmv': 'Rủi ro Tối thiểu GMV',
      'kpi.cap_alloc': 'Phân bổ Vốn Rủi ro (y*)',
      'kpi.utility_u': 'Hữu dụng U*',

      'step1.heading': '1. Chọn tài sản & Nguồn dữ liệu',
      'step2.heading': '2. Giả định & Giới hạn Danh mục',
      'step3.heading': '3. Kết quả & Diễn giải Định lượng',
      'step4.heading': '4. Thực thi Lô 100 & Xuất Báo cáo',

      'source.live_market': 'Thị trường Trực tiếp',
      'source.uploaded_prices': 'File Giá Tải lên',
      'source.manual_matrix': 'Ma trận Thủ công / Excel',
      'source.live_tag': 'HayInsights API Trực tiếp',
      'source.uploaded_tag': 'Chuỗi Giá Excel/CSV Độc lập',
      'source.manual_tag': 'Ma trận Tham số Tự nhập',

      'live.search_label': 'Tìm kiếm Mã cổ phiếu (HOSE / HNX / UPCoM)',
      'live.search_placeholder': 'Nhập 1-3 ký tự (vd: FPT, VCB, HPG)...',
      'live.browse': 'Danh sách',
      'live.selected': 'Đã chọn',
      'live.preset_core': 'Core 5',
      'live.preset_banking': 'Ngân hàng',
      'live.preset_growth': 'Tăng trưởng',
      'live.window': 'Kỳ dữ liệu:',
      'live.adj_close': 'Giá điều chỉnh (ước lượng lợi suất)',
      'live.adj_note': 'Ước lượng lợi suất dùng giá điều chỉnh; số cổ phiếu Lô 100 dùng giá đóng cửa giao dịch thực tế mới nhất.',
      'live.min_assets_alert': 'Danh mục cần tối thiểu 2 mã cổ phiếu.',
      'live.no_match': 'Không tìm thấy mã phù hợp.',
      'live.added': 'Đã chọn',
      'live.add': '+ Thêm',
      'live.direct_api': 'Tải mã này trực tiếp từ HayInsights API',

      'upload.title': 'Tải lên Chuỗi Giá Lịch sử (.xlsx / .csv)',
      'upload.subtitle': 'Khớp ngày giao dịch nghiêm ngặt, không điền khuyết giả; mỗi file tạo dataset_id độc lập.',
      'upload.choose_file': 'Chọn File Giá',
      'upload.dl_price_tpl': 'Tải Mẫu Giá (.xlsx)',
      'upload.status_empty': 'Chưa có file chuỗi giá nào được nạp trong phiên này.',
      'upload.status_loaded': 'Đã nạp {name}: {n} mã, {sessions} phiên ({from} → {to}, bỏ {dropped} ngày thiếu).',
      'upload.must_upload_first': 'Vui lòng tải lên một file chuỗi giá (.xlsx/.csv) trước khi chạy chế độ File Giá Tải lên.',

      'manual.title': 'Nhập / Tải Ma trận Tham số (252 phiên)',
      'manual.subtitle': 'Lưu ý: Chế độ Ma trận không có chuỗi lịch sử nên sẽ ẩn Wealth Index, MDD & Historical VaR.',
      'manual.dl_matrix_tpl': 'Tải Mẫu Ma trận',
      'manual.upload_matrix': 'Nạp từ Excel',
      'manual.add_row': '+ Thêm mã',
      'manual.remove_row': '- Bớt mã',
      'manual.prices_note': 'Cột Giá (VND) là tùy chọn: để trống nếu chỉ tối ưu hóa trọng số lý thuyết (Lô 100 sẽ tắt).',
      'manual.price_col': 'Giá (VND)',
      'manual.er_col': 'E(R) %',
      'manual.std_col': 'σ %',

      'prov.title': 'Nguồn gốc & Tính toàn vẹn Dữ liệu',
      'prov.source': 'Nguồn:',
      'prov.range': 'Khoảng thời gian:',
      'prov.sessions': 'Số phiên khớp:',
      'prov.dropped': 'Phiên loại bỏ do thiếu:',
      'prov.basis': 'Chuẩn giá:',
      'prov.timestamp': 'Thời điểm nạp/tính:',

      'param.rf': 'Lãi suất Phi rủi ro Rf (%)',
      'param.nav': 'Tổng vốn NAV (VND)',
      'param.buy_fee': 'Phí mua giao dịch (%)',
      'param.risk_a': 'Hệ số Ngại rủi ro (γ)',
      'param.assess_quiz': 'Khảo sát Khẩu vị Rủi ro',
      'param.aggressive': '1.0 (Ưa rủi ro)',
      'param.balanced': 'Cân bằng',
      'param.conservative': '10.0 (Thận trọng)',

      'bounds.title': 'Giới hạn Tỷ trọng Cổ phiếu (w_min, w_max)',
      'bounds.subtitle': 'Áp dụng trong nội bộ rổ cổ phiếu (tổng Σw_i = 100% rổ cổ phiếu).',
      'bounds.preset_20': 'Trần 20% (trong phần cổ phiếu)',
      'bounds.floor': 'Sàn (w_min):',
      'bounds.ceiling': 'Trần (w_max):',

      'cash.title': 'Phân bổ Tiền mặt / Tài sản Phi rủi ro',
      'cash.mode_utility': 'Theo Utility (γ), Không vay',
      'cash.mode_fixed': 'Giữ Tiền mặt Cố định (%)',
      'cash.hint_utility': 'Tỷ trọng tiền mặt nội sinh w_cash = 1 − y* từ tối ưu Utility U = E(R) − 0.5·γ·σ² trên nhánh hiệu quả (chặn 0% ≤ y* ≤ 100%).',
      'cash.target_label': 'Tỷ trọng Tiền mặt Mục tiêu (% NAV):',
      'cash.buffer_5': '5% Dự phòng',
      'cash.buffer_10': '10% Tiêu chuẩn',
      'cash.buffer_20': '20% Phòng thủ',
      'cash.buffer_30': '30% Chiến thuật',

      'bm.index': 'Chỉ số Tham chiếu (Benchmark)',
      'bm.horizon': 'Kỳ đối chiếu Benchmark',
      'short.title': 'Bán khống Không ràng buộc (Tham chiếu Học thuật)',
      'short.desc_long': 'Long-only (0 ≤ w_i ≤ 100%, Quadratic Programming)',
      'short.desc_short': 'Không ràng buộc (Công thức đóng Merton Σ⁻¹ — Tắt Lô 100)',

      'btn.run': 'Chạy Tối Ưu Hóa',
      'btn.running': 'Đang tính toán...',
      'footer.assets': 'Số tài sản:',

      'chart.frontier_title': 'Biên Hiệu Quả & Đường Phân Bổ Vốn (CAL)',
      'chart.frontier_sub': 'Tập Khả Thi (trong biên) • GMV • Tangency • Đường Bàng Quan Utility (U*)',
      'chart.weights_title': 'So sánh Tỷ trọng Tối ưu & Thực thi (Bao gồm Tiền mặt)',
      'chart.weights_sub': 'GMV • Tangency (Max Sharpe) • Complete Mục tiêu • Thực thi Lô 100 (Sau phí)',
      'chart.zoom_btn': 'Phóng to',
      'chart.x_vol': 'Độ biến động Quy năm σ (%)',
      'chart.y_ret': 'Lợi suất Kỳ vọng E(R) (%)',
      'chart.y_weight': 'Tỷ trọng (%)',
      'chart.cash_label': 'TIỀN MẶT / Rf',
      'chart.trace_mc': 'Tập Khả Thi (Monte Carlo)',
      'chart.trace_frontier': 'Biên Hiệu Quả (Nhánh trên)',
      'chart.trace_cal': 'Đường CAL',
      'chart.trace_indiff': 'Đường Bàng Quan (γ={gamma})',
      'chart.trace_assets': 'Từng cổ phiếu',
      'chart.trace_gmv': 'GMV (Phương sai Tối thiểu)',
      'chart.trace_tan': 'Tangency (Max Sharpe)',
      'chart.trace_comp': 'Danh mục Hoàn chỉnh (C)',
      'chart.trace_exec': 'Thực thi Lô 100 (Sau phí)',

      'mode.short': 'Bán khống Học thuật (Merton Σ⁻¹)',
      'mode.bounded': 'QP Có Ràng Buộc ({min}% ≤ w_i ≤ {max}%)',
      'mode.long_only': 'Long-Only (w_i ≥ 0)',

      'tab.execution': '01. Nắm giữ & Lô 100',
      'tab.benchmark': '02. Đối chiếu Benchmark',
      'tab.stress': '03. Stress Test & VaR / ES',
      'tab.moments': '04. Tham số & Hiệp phương sai',
      'tab.algebra': '05. Đại số Merton (Tham chiếu)',

      'exec.disabled_short': 'Đang bật chế độ Bán khống Học thuật — Bảng đặt lệnh Lô 100 thực tế đã tắt vì bán khống chứng khoán cơ sở không khả dụng cho danh mục Long-only.',
      'exec.disabled_no_prices': 'Thiếu giá giao dịch cho các mã ({missing}) — Chỉ hiển thị phân bổ tỷ trọng lý thuyết, bảng đặt lệnh Lô 100 đã tạm tắt.',
      'exec.nav_initial': 'NAV Ban đầu:',
      'exec.equities_val': 'Mua Cổ phiếu:',
      'exec.fees_val': 'Phí mua:',
      'exec.cash_rem': 'Tiền dư (Cash):',
      'exec.nav_post_fee': 'NAV Sau phí:',
      'exec.col_ticker': 'Mã CP',
      'exec.col_price': 'Giá khớp (VND)',
      'exec.col_wgmv': 'w GMV',
      'exec.col_wtan': 'w Tangency',
      'exec.col_w1n': 'w 1/N',
      'exec.col_wcomp': 'w Complete (NAV)',
      'exec.col_target': 'Giá trị Mục tiêu',
      'exec.col_shares': 'SL Lô 100',
      'exec.col_exec': 'Giá trị Mua',
      'exec.col_fee': 'Phí mua',
      'exec.col_actual_w': 'Tỷ trọng Sau phí',
      'exec.cash_row': 'TIỀN MẶT / Rf ({rf})',
      'exec.cash_reserve': 'Dự trữ Tiền mặt',
      'exec.total_row': 'TỔNG DANH MỤC (SAU PHÍ)',
      'exec.mobile_target': 'Mục tiêu:',
      'exec.mobile_exec': 'Thực mua:',
      'exec.mobile_shares': 'Khối lượng:',
      'exec.mobile_fee': 'Phí:',
      'exec.drift_warn': 'Cảnh báo lệch trần/sàn sau làm tròn lô (trong rổ cổ phiếu):',

      'bm.title': 'Đánh giá Hiệu suất So với Benchmark',
      'bm.recalc': '• Đang tính toán lại...',
      'bm.label': 'Tham chiếu:',
      'bm.horizon_label': 'Kỳ đối chiếu:',
      'bm.unavailable_title': 'Không khả dụng đối chiếu lịch sử Benchmark',
      'bm.methodology_note': 'Giả định: Chỉ số Price Return Index • Danh mục cổ phiếu Tái cân bằng Hàng ngày theo trọng số cố định • Đánh giá In-Sample (không phải Backtest Out-of-Sample).',
      'bm.col_metric': 'Chỉ tiêu Định lượng',
      'bm.col_port': 'Danh mục Cổ phiếu',
      'bm.col_spread': 'Chênh lệch / Ghi chú',
      'bm.wealth_title': 'Tăng trưởng Tích lũy Chuẩn hóa (Base = 100 tại ngày đầu chung)',

      'stress.basis_label': 'Cơ sở đánh giá Rủi ro:',
      'stress.basis_target': 'Danh mục Mục tiêu (Complete)',
      'stress.basis_exec': 'Danh mục Thực thi Lô 100 (Sau phí)',
      'stress.var95_1d': 'VaR 1 Ngày (95%)',
      'stress.es95_1d': 'ES / CVaR 1 Ngày (95%)',
      'stress.var95_21d': 'VaR 1 Tháng (21 phiên, 95%)',
      'stress.mdd': 'Sụt giảm Tối đa Lịch sử (MDD)',
      'stress.mdd_unavail': 'Không tính ở chế độ Ma trận',
      'stress.hist_unavailable': 'Không có dữ liệu lịch sử (Matrix Mode): chỉ hiển thị VaR/ES Tham số.',
      'stress.scenarios_title': 'Kịch bản Khủng hoảng & Cú sốc Thị trường Việt Nam',

      'moments.stats_title': 'Thống kê Lợi suất, CAGR, Biến động & Giá khớp (252 phiên)',
      'moments.corr_title': 'Ma trận Tương quan (P)',
      'moments.cov_title': 'Ma trận Hiệp phương sai Quy năm (Σ = 252 × Σ_daily)',

      'algebra.title': 'Đại số Ma trận Merton (1972) — Tham chiếu Lý thuyết (Không Ràng Buộc)',
      'algebra.applied_yes': 'Lưu ý: Danh mục hiện tại đang dùng trực tiếp nghiệm bán khống không ràng buộc này.',
      'algebra.applied_no': 'Tham chiếu lý thuyết (KHÔNG áp dụng làm danh mục chính vì hệ thống đang bật ràng buộc Long-only / Giới hạn tỷ trọng).',
      'algebra.singular': 'Ma trận Hiệp phương sai suy biến hoặc gần suy biến — Không thể tính nghịch đảo Σ⁻¹ chính xác; công thức đóng Merton không khả dụng, hệ thống sử dụng bộ giải QP có ràng buộc.',

      'quiz.title': 'Khảo sát Khẩu vị Rủi ro Nhà đầu tư',
      'quiz.subtitle': 'Trả lời đầy đủ 4 câu hỏi để quy đổi sang hệ số ngại rủi ro γ trong hàm U = E(R) − 0.5·γ·σ²',
      'quiz.close': 'Đóng',
      'quiz.prompt': 'Vui lòng chọn đáp án cho cả 4 câu hỏi rồi bấm Áp dụng.',
      'quiz.missing': 'Bạn cần chọn đầy đủ đáp án cho cả 4 câu hỏi ({answered}/4 đã chọn).',
      'quiz.apply': 'Áp dụng Khẩu vị Rủi ro',

      'modal.close': '× Đóng (Esc)',
      'modal.reset': 'Đặt lại Góc nhìn',
      'modal.subtitle': 'Phóng to tương tác với thu phóng, kéo thả, chú giải chi tiết'
    },

    en: {
      'app.title': 'Markowitz Portfolio Optimization',
      'app.subtitle': 'Mean-Variance Efficient Frontier • Unleveraged Long-Only Engine',
      'nav.export_matrix': 'Export Matrix',
      'nav.export_prices': 'Export Price Data',
      'nav.export_excel': 'Export Excel (8 Sheets)',
      'nav.theme_toggle': 'Toggle Light / Dark Mode',
      'nav.lang_vi': 'VI',
      'nav.lang_en': 'EN',
      'nav.export_bar_mobile_label': 'Export committed snapshot reports:',

      'banner.stale': 'Inputs changed since last committed optimization — click Run Optimization to update results and unlock Exports.',
      'banner.computing': 'Computing optimization and synchronizing dataset...',
      'banner.error_title': 'Cannot optimize with current constraints',
      'banner.no_positive_excess': 'No asset has E(R) > Rf over the observation window: Complete Portfolio allocates 100% Cash (y* = 0%) under no-leverage utility; Risky benchmark shown is constrained Max Sharpe.',
      'banner.short_mode': 'Academic Unconstrained Short-Sales Mode (Merton 1972): weight floor/ceiling bounds are ignored and Lot-100 order sizing is disabled.',
      'banner.singleton_prefix': 'Constraint domain collapses to a single feasible point:',

      'kpi.max_sharpe': 'Max Sharpe (Tangency)',
      'kpi.optimal_risky': 'Optimal Risky',
      'kpi.gmv_sr': 'GMV Sharpe',
      'kpi.exp_ret': 'Expected Return E(R)',
      'kpi.annualized_252': '252d Annualized (Arithmetic)',
      'kpi.volatility': 'Volatility (σ)',
      'kpi.min_risk_gmv': 'Min Risk GMV',
      'kpi.cap_alloc': 'Capital Allocation (y*)',
      'kpi.utility_u': 'Utility U*',

      'step1.heading': '1. Asset Universe & Data Source',
      'step2.heading': '2. Assumptions & Portfolio Constraints',
      'step3.heading': '3. Results & Quantitative Analytics',
      'step4.heading': '4. Lot-100 Execution & Reports',

      'source.live_market': 'Live Market',
      'source.uploaded_prices': 'Uploaded Prices',
      'source.manual_matrix': 'Manual / Excel Matrix',
      'source.live_tag': 'HayInsights Live Market API',
      'source.uploaded_tag': 'Isolated Uploaded Price File',
      'source.manual_tag': 'Manual Parameter Matrix',

      'live.search_label': 'Search Ticker (HOSE / HNX / UPCoM)',
      'live.search_placeholder': 'Type 1-3 letters (e.g. FPT, VCB, HPG)...',
      'live.browse': 'Browse',
      'live.selected': 'Selected',
      'live.preset_core': 'Core 5',
      'live.preset_banking': 'Banking',
      'live.preset_growth': 'Growth',
      'live.window': 'Lookback Window:',
      'live.adj_close': 'Adjusted Close (return estimation)',
      'live.adj_note': 'Expected returns/covariance use adjusted close; Lot-100 sizing uses latest unadjusted trade price.',
      'live.min_assets_alert': 'Portfolio requires at least 2 assets.',
      'live.no_match': 'No matching ticker found.',
      'live.added': 'Added',
      'live.add': '+ Add',
      'live.direct_api': 'Fetch directly from HayInsights API',

      'upload.title': 'Upload Historical Price Series (.xlsx / .csv)',
      'upload.subtitle': 'Strict inner date alignment, no synthetic forward-fill; isolated via unique dataset_id.',
      'upload.choose_file': 'Choose Price File',
      'upload.dl_price_tpl': 'Price Template (.xlsx)',
      'upload.status_empty': 'No price series file loaded in this session.',
      'upload.status_loaded': 'Loaded {name}: {n} assets, {sessions} sessions ({from} → {to}, {dropped} dropped).',
      'upload.must_upload_first': 'Please upload a historical price file (.xlsx/.csv) before running Uploaded Prices mode.',

      'manual.title': 'Manual / Excel Parameter Matrix (252d)',
      'manual.subtitle': 'Note: Matrix mode has no daily price history, so Wealth Index, MDD & Historical VaR are omitted.',
      'manual.dl_matrix_tpl': 'Matrix Template',
      'manual.upload_matrix': 'Load Excel',
      'manual.add_row': '+ Add Row',
      'manual.remove_row': '- Remove Row',
      'manual.prices_note': 'Price (VND) column is optional: leave blank for weight-only optimization (Lot-100 disabled).',
      'manual.price_col': 'Price (VND)',
      'manual.er_col': 'E(R) %',
      'manual.std_col': 'σ %',

      'prov.title': 'Data Provenance & Integrity',
      'prov.source': 'Source:',
      'prov.range': 'Window:',
      'prov.sessions': 'Aligned Sessions:',
      'prov.dropped': 'Dropped Dates:',
      'prov.basis': 'Price Basis:',
      'prov.timestamp': 'Timestamp:',

      'param.rf': 'Risk-Free Rate Rf (%)',
      'param.nav': 'Capital NAV (VND)',
      'param.buy_fee': 'Buy Fee Rate (%)',
      'param.risk_a': 'Risk Aversion (γ)',
      'param.assess_quiz': 'Assess Risk Profile',
      'param.aggressive': '1.0 (Aggressive)',
      'param.balanced': 'Balanced',
      'param.conservative': '10.0 (Conservative)',

      'bounds.title': 'Stock Weight Bounds (w_min, w_max)',
      'bounds.subtitle': 'Applied within the equity basket (Σw_i = 100% of risky sleeve).',
      'bounds.preset_20': '20% Cap (Within Equity Basket)',
      'bounds.floor': 'Floor (w_min):',
      'bounds.ceiling': 'Ceiling (w_max):',

      'cash.title': 'Cash / Risk-Free Allocation',
      'cash.mode_utility': 'Utility (γ), No Leverage',
      'cash.mode_fixed': 'Fixed Cash % (NAV)',
      'cash.hint_utility': 'Endogenous cash weight w_cash = 1 − y* from U = E(R) − 0.5·γ·σ² along efficient CAL (clamped to 0% ≤ y* ≤ 100%).',
      'cash.target_label': 'Target Cash Reserve (% NAV):',
      'cash.buffer_5': '5% Buffer',
      'cash.buffer_10': '10% Standard',
      'cash.buffer_20': '20% Defensive',
      'cash.buffer_30': '30% Tactical',

      'bm.index': 'Benchmark Index',
      'bm.horizon': 'Benchmark Horizon',
      'short.title': 'Unconstrained Short-Sales (Academic Reference)',
      'short.desc_long': 'Long-only (0 ≤ w_i ≤ 100%, Quadratic Programming)',
      'short.desc_short': 'Unconstrained (Merton Σ⁻¹ closed-form — Lot-100 Disabled)',

      'btn.run': 'Run Optimization',
      'btn.running': 'Computing Optimization...',
      'footer.assets': 'Assets:',

      'chart.frontier_title': 'Efficient Frontier & Capital Allocation Line (CAL)',
      'chart.frontier_sub': 'Feasible Bounded Set • GMV • Tangency • Utility Indifference Curve (U*)',
      'chart.weights_title': 'Optimal & Executed Portfolio Weights (incl. Cash)',
      'chart.weights_sub': 'GMV • Tangency (Max Sharpe) • Target Complete • Executed Lot-100 (Post-Fee)',
      'chart.zoom_btn': 'Fullscreen Zoom',
      'chart.x_vol': 'Annualized Volatility σ (%)',
      'chart.y_ret': 'Expected Return E(R) (%)',
      'chart.y_weight': 'Weight (%)',
      'chart.cash_label': 'CASH / Rf',
      'chart.trace_mc': 'Feasible Set (Monte Carlo)',
      'chart.trace_frontier': 'Efficient Frontier (Upper Branch)',
      'chart.trace_cal': 'CAL (Capital Allocation Line)',
      'chart.trace_indiff': 'Indifference Curve (γ={gamma})',
      'chart.trace_assets': 'Individual Assets',
      'chart.trace_gmv': 'GMV (Min Variance)',
      'chart.trace_tan': 'Tangency (Max Sharpe)',
      'chart.trace_comp': 'Complete Portfolio (C)',
      'chart.trace_exec': 'Executed Lot-100 (Post-Fee)',

      'mode.short': 'Short-Sales Allowed (Academic)',
      'mode.bounded': 'Bounded QP ({min}% ≤ w_i ≤ {max}%)',
      'mode.long_only': 'Long-Only (w_i ≥ 0)',

      'tab.execution': '01. Holdings & Lot 100',
      'tab.benchmark': '02. Benchmark Attribution',
      'tab.stress': '03. Stress Testing & VaR',
      'tab.moments': '04. Asset Moments & Cov',
      'tab.algebra': '05. Merton (1972) Reference',

      'exec.disabled_short': 'Academic Short-Sales mode active — Physical Lot-100 execution is disabled because short selling underlying equities is not executed in the demo order book.',
      'exec.disabled_no_prices': 'Missing trade prices for ({missing}) — Theoretical weights are shown; Lot-100 order sizing is disabled.',
      'exec.nav_initial': 'Initial NAV:',
      'exec.equities_val': 'Equities Cost:',
      'exec.fees_val': 'Buy Fees:',
      'exec.cash_rem': 'Cash Remaining:',
      'exec.nav_post_fee': 'Post-Fee NAV:',
      'exec.col_ticker': 'Ticker',
      'exec.col_price': 'Price (VND)',
      'exec.col_wgmv': 'w GMV',
      'exec.col_wtan': 'w Tangency',
      'exec.col_w1n': 'w 1/N',
      'exec.col_wcomp': 'w Complete (NAV)',
      'exec.col_target': 'Target Value',
      'exec.col_shares': 'Lot-100 Shares',
      'exec.col_exec': 'Executed Value',
      'exec.col_fee': 'Buy Fee',
      'exec.col_actual_w': 'Post-Fee Weight',
      'exec.cash_row': 'CASH / Rf ({rf})',
      'exec.cash_reserve': 'Cash Reserve',
      'exec.total_row': 'TOTAL PORTFOLIO (POST-FEE)',
      'exec.mobile_target': 'Target:',
      'exec.mobile_exec': 'Executed:',
      'exec.mobile_shares': 'Shares:',
      'exec.mobile_fee': 'Fee:',
      'exec.drift_warn': 'Post-fee Lot-100 rounding drift vs equity bounds:',

      'bm.title': 'Institutional Benchmark Attribution',
      'bm.recalc': '• Recalculating Attribution...',
      'bm.label': 'Benchmark:',
      'bm.horizon_label': 'Attribution Horizon:',
      'bm.unavailable_title': 'Historical Benchmark Attribution Unavailable',
      'bm.methodology_note': 'Conventions: Price Return Index • Daily Fixed-Weight Rebalanced Equity Portfolio • In-Sample Evaluation (not out-of-sample backtest).',
      'bm.col_metric': 'Metric',
      'bm.col_port': 'Risky Portfolio',
      'bm.col_spread': 'Active / Note',
      'bm.wealth_title': 'Cumulative Wealth Index (Normalized Base = 100 at common start)',

      'stress.basis_label': 'Risk Evaluation Basis:',
      'stress.basis_target': 'Target Complete Portfolio',
      'stress.basis_exec': 'Executed Lot-100 (Post-Fee)',
      'stress.var95_1d': '1-Day VaR (95%)',
      'stress.es95_1d': '1-Day ES / CVaR (95%)',
      'stress.var95_21d': '1-Month (21d) VaR (95%)',
      'stress.mdd': 'Max Historical Drawdown (MDD)',
      'stress.mdd_unavail': 'Unavailable in Matrix Mode',
      'stress.hist_unavailable': 'No historical price series (Matrix Mode): Parametric VaR/ES shown only.',
      'stress.scenarios_title': 'Vietnam Historical Crisis & Shock Scenarios',

      'moments.stats_title': 'Asset Return, CAGR, Volatility & Trade Price (252d)',
      'moments.corr_title': 'Correlation Matrix (P)',
      'moments.cov_title': 'Annualized Covariance Matrix (Σ = 252 × Σ_daily)',

      'algebra.title': 'Merton (1972) Matrix Algebra — Theoretical Reference (Unconstrained)',
      'algebra.applied_yes': 'Active Status: Current unconstrained short-sales portfolio directly matches these analytical identities.',
      'algebra.applied_no': 'Theoretical Reference Only (NOT active portfolio weights because Long-Only / Box Bounds QP is active).',
      'algebra.singular': 'Covariance matrix is singular or numerically ill-conditioned — Exact Σ⁻¹ unavailable; active solver uses constrained Quadratic Programming.',

      'quiz.title': 'Investor Risk Tolerance Assessment',
      'quiz.subtitle': 'Answer all 4 questions to calibrate risk aversion γ in U = E(R) − 0.5·γ·σ²',
      'quiz.close': 'Close',
      'quiz.prompt': 'Select one answer for each of the 4 questions and click Apply.',
      'quiz.missing': 'Please answer all 4 questions before applying ({answered}/4 selected).',
      'quiz.apply': 'Apply Risk Profile',

      'modal.close': '× Close (Esc)',
      'modal.reset': 'Reset View',
      'modal.subtitle': 'Interactive inspection with zoom, pan, hover tooltips, and legend filtering'
    }
  };

  function getSavedLang() {
    try {
      var saved = localStorage.getItem('mvo_lang');
      if (saved === 'vi' || saved === 'en') return saved;
    } catch (_) {}
    return 'vi';
  }

  function t(key, params, langOverride) {
    var lang = langOverride || (window.appState && window.appState.uiLang) || getSavedLang();
    var dict = MVO_I18N[lang] || MVO_I18N.vi;
    var text = dict[key];
    if (text === undefined || text === null) {
      text = MVO_I18N.en[key] !== undefined ? MVO_I18N.en[key] : key;
    }
    if (params && typeof text === 'string') {
      Object.keys(params).forEach(function (k) {
        text = text.split('{' + k + '}').join(String(params[k]));
      });
    }
    return text;
  }

  function applyStaticI18n(lang) {
    var activeLang = lang === 'en' ? 'en' : 'vi';
    document.documentElement.setAttribute('lang', activeLang);
    try {
      localStorage.setItem('mvo_lang', activeLang);
    } catch (_) {}

    var nodes = document.querySelectorAll('[data-i18n]');
    nodes.forEach(function (el) {
      var key = el.getAttribute('data-i18n');
      if (key) {
        el.textContent = t(key, null, activeLang);
      }
    });

    var phNodes = document.querySelectorAll('[data-i18n-placeholder]');
    phNodes.forEach(function (el) {
      var key = el.getAttribute('data-i18n-placeholder');
      if (key) {
        el.setAttribute('placeholder', t(key, null, activeLang));
      }
    });

    var ariaNodes = document.querySelectorAll('[data-i18n-aria]');
    ariaNodes.forEach(function (el) {
      var key = el.getAttribute('data-i18n-aria');
      if (key) {
        el.setAttribute('aria-label', t(key, null, activeLang));
      }
    });
  }

  window.MVO_I18N = MVO_I18N;
  window.getSavedLang = getSavedLang;
  window.t = t;
  window.applyStaticI18n = applyStaticI18n;
})();
