"""
Investor Risk Profiling & Risk Aversion (A) Assessment Engine.
Maps a 4-question behavioral and financial questionnaire (score 4..16)
to the textbook utility risk aversion parameter A in U = E(R) - 0.5 * A * sigma^2.
"""
from __future__ import annotations

from typing import Any

QUIZ_QUESTIONS = [
    {
        "id": "q1_horizon",
        "question": "1. Thời gian đầu tư dự kiến của bạn cho danh mục này là bao lâu?",
        "question_en": "1. What is your expected investment horizon for this portfolio?",
        "options": [
            {"score": 1, "label": "Dưới 1 năm (Ngắn hạn, cần thanh khoản sớm)", "label_en": "Under 1 year (Short-term, early liquidity need)"},
            {"score": 2, "label": "Từ 1 đến 3 năm (Trung hạn)", "label_en": "1 to 3 years (Medium-term)"},
            {"score": 3, "label": "Từ 3 đến 5 năm (Dài hạn)", "label_en": "3 to 5 years (Long-term)"},
            {"score": 4, "label": "Trên 5 năm (Tích lũy tài sản dài hạn)", "label_en": "Over 5 years (Long-term wealth compounding)"},
        ],
    },
    {
        "id": "q2_drawdown_reaction",
        "question": "2. Nếu thị trường biến động mạnh làm danh mục sụt giảm 20% trong 1 tháng, bạn sẽ làm gì?",
        "question_en": "2. If severe market volatility drops your portfolio by 20% in 1 month, what will you do?",
        "options": [
            {"score": 1, "label": "Bán cắt lỗ toàn bộ ngay lập tức để bảo toàn phần vốn còn lại", "label_en": "Sell everything immediately to preserve remaining capital"},
            {"score": 2, "label": "Bán giảm 50% tỷ trọng cổ phiếu để giảm áp lực tâm lý", "label_en": "Trim equity allocation by 50% to ease psychological pressure"},
            {"score": 3, "label": "Bình tĩnh nắm giữ nguyên danh mục, chờ thị trường phục hồi", "label_en": "Stay calm and hold the portfolio awaiting recovery"},
            {"score": 4, "label": "Xem đây là cơ hội chiết khấu tốt, giải ngân mua thêm cổ phiếu", "label_en": "Treat it as an attractive discount and allocate more capital"},
        ],
    },
    {
        "id": "q3_objective",
        "question": "3. Mục tiêu ưu tiên lớn nhất của bạn khi đầu tư là gì?",
        "question_en": "3. What is your primary investment objective?",
        "options": [
            {"score": 1, "label": "Bảo toàn vốn tuyệt đối, ưu tiên an toàn hơn lợi nhuận", "label_en": "Capital preservation above return"},
            {"score": 2, "label": "Thu nhập ổn định cao hơn lãi suất tiết kiệm 2-3%/năm, ít biến động", "label_en": "Steady income 2-3% above deposit rate with low volatility"},
            {"score": 3, "label": "Tăng trưởng tài sản bền vững, chấp nhận biến động vừa phải", "label_en": "Sustainable capital growth with moderate volatility"},
            {"score": 4, "label": "Tối đa hóa lợi nhuận đột phá, sẵn sàng chấp nhận rủi ro cao", "label_en": "Maximize long-run returns with high risk tolerance"},
        ],
    },
    {
        "id": "q4_financial_cushion",
        "question": "4. Nguồn vốn đầu tư này chiếm tỷ trọng thế nào trong tổng tài sản và thu nhập của bạn?",
        "question_en": "4. How much of your net worth and liquidity does this investment capital represent?",
        "options": [
            {"score": 1, "label": "Chiếm phần lớn tích lũy, chưa có quỹ dự phòng khẩn cấp riêng", "label_en": "Majority of savings with no separate emergency fund"},
            {"score": 2, "label": "Chiếm 30% - 50% tài sản, có thu nhập hàng tháng ổn định", "label_en": "30% - 50% of assets, backed by stable monthly income"},
            {"score": 3, "label": "Chiếm dưới 30% tài sản, dòng tiền thặng dư hàng tháng dồi dào", "label_en": "Under 30% of assets, strong monthly surplus cash flow"},
            {"score": 4, "label": "Vốn nhàn rỗi hoàn toàn chuyên biệt cho đầu tư, đã có quỹ dự phòng > 12 tháng", "label_en": "100% idle investment capital with >12 months emergency reserve"},
        ],
    },
]


SCORE_TO_GAMMA_MAP = {
    4: 8.0,
    5: 7.0,
    6: 6.0,
    7: 5.2,
    8: 4.5,
    9: 4.0,
    10: 3.5,
    11: 3.0,
    12: 2.6,
    13: 2.2,
    14: 1.8,
    15: 1.5,
    16: 1.2,
}


def evaluate_risk_profile(scores: list[int]) -> dict[str, Any]:
    """
    Evaluate 4 quiz scores (each 1..4) and map to Risk Aversion coefficient gamma (alias A).
    Total score ranges from 4 to 16.
    """
    if not scores or len(scores) != 4:
        raise ValueError("Cần trả lời đủ 4 câu hỏi khảo sát khẩu vị rủi ro.")

    clean_scores = []
    for s in scores:
        val = int(s)
        if val < 1 or val > 4:
            raise ValueError("Mỗi câu trả lời khẩu vị rủi ro phải có điểm từ 1 đến 4.")
        clean_scores.append(val)

    total_score = sum(clean_scores)
    gamma = SCORE_TO_GAMMA_MAP.get(total_score, 3.0)

    if total_score <= 6:
        tier = "Rất thận trọng (Ultra-Conservative)"
        tier_en = "Ultra-Conservative"
        desc = "Ưu tiên bảo toàn vốn tối đa. Danh mục hoàn chỉnh phân bổ tỷ trọng lớn vào tài sản phi rủi ro (Tiền mặt / Rf)."
        desc_en = "Prioritizes capital preservation with heavy allocation to risk-free Cash."
    elif total_score <= 9:
        tier = "Thận trọng (Conservative)"
        tier_en = "Conservative"
        desc = "Ưu tiên sự ổn định, kết hợp hài hòa giữa tiền mặt phi rủi ro và danh mục cổ phiếu tham chiếu."
        desc_en = "Prioritizes stability by balancing risk-free Cash with the risky equity portfolio."
    elif total_score <= 12:
        tier = "Cân bằng (Moderate / Balanced)"
        tier_en = "Moderate / Balanced"
        desc = "Khẩu vị rủi ro cân bằng (γ ≈ 2.6 - 3.5), chấp nhận biến động hợp lý để tối ưu hóa hàm hữu dụng U = E(R) - 0.5·γ·σ²."
        desc_en = "Balanced risk tolerance (γ ≈ 2.6 - 3.5), optimizing utility U = E(R) - 0.5·γ·σ² with moderate risk."
    else:
        tier = "Tăng trưởng Mạnh (Aggressive Growth)"
        tier_en = "Aggressive Growth"
        desc = "Khẩu vị rủi ro cao, chấp nhận biến động lớn để tối đa hóa kỳ vọng sinh lời trong giới hạn không đòn bẩy."
        desc_en = "High risk tolerance targeting growth within long-only, unleveraged portfolio bounds."

    return {
        "scores": clean_scores,
        "total_score": total_score,
        "max_possible_score": 16,
        "risk_aversion_gamma": gamma,
        "risk_aversion_A": gamma,
        "profile_tier": tier,
        "profile_tier_en": tier_en,
        "description": desc,
        "description_en": desc_en,
        "score_mapping_table": SCORE_TO_GAMMA_MAP,
        "academic_disclaimer": "Công cụ minh họa quy đổi điểm hành vi sang hệ số ngại rủi ro γ (4→8.0 ... 16→1.2) phục vụ học thuật, không phải tư vấn đầu tư cá nhân hóa.",
        "academic_disclaimer_en": "Educational calibration mapping behavioral score 4..16 to risk aversion γ (8.0..1.2); not personalized financial advice.",
    }
