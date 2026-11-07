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
        "options": [
            {"score": 1, "label": "Dưới 1 năm (Ngắn hạn, cần thanh khoản sớm)"},
            {"score": 2, "label": "Từ 1 đến 3 năm (Trung hạn)"},
            {"score": 3, "label": "Từ 3 đến 5 năm (Dài hạn)"},
            {"score": 4, "label": "Trên 5 năm (Tích lũy tài sản dài hạn)"},
        ],
    },
    {
        "id": "q2_drawdown_reaction",
        "question": "2. Nếu thị trường biến động mạnh làm danh mục sụt giảm 20% trong 1 tháng, bạn sẽ làm gì?",
        "options": [
            {"score": 1, "label": "Bán cắt lỗ toàn bộ ngay lập tức để bảo toàn phần vốn còn lại"},
            {"score": 2, "label": "Bán giảm 50% tỷ trọng cổ phiếu để giảm áp lực tâm lý"},
            {"score": 3, "label": "Bình tĩnh nắm giữ nguyên danh mục, chờ thị trường phục hồi"},
            {"score": 4, "label": "Xem đây là cơ hội chiết khấu tốt, giải ngân mua thêm cổ phiếu"},
        ],
    },
    {
        "id": "q3_objective",
        "question": "3. Mục tiêu ưu tiên lớn nhất của bạn khi đầu tư là gì?",
        "options": [
            {"score": 1, "label": "Bảo toàn vốn tuyệt đối, ưu tiên an toàn hơn lợi nhuận"},
            {"score": 2, "label": "Thu nhập ổn định cao hơn lãi suất tiết kiệm 2-3%/năm, ít biến động"},
            {"score": 3, "label": "Tăng trưởng tài sản bền vững, chấp nhận biến động vừa phải"},
            {"score": 4, "label": "Tối đa hóa lợi nhuận đột phá, sẵn sàng chấp nhận rủi ro cao"},
        ],
    },
    {
        "id": "q4_financial_cushion",
        "question": "4. Nguồn vốn đầu tư này chiếm tỷ trọng thế nào trong tổng tài sản và thu nhập của bạn?",
        "options": [
            {"score": 1, "label": "Chiếm phần lớn tích lũy, chưa có quỹ dự phòng khẩn cấp riêng"},
            {"score": 2, "label": "Chiếm 30% - 50% tài sản, có thu nhập hàng tháng ổn định"},
            {"score": 3, "label": "Chiếm dưới 30% tài sản, dòng tiền thặng dư hàng tháng dồi dào"},
            {"score": 4, "label": "Vốn nhàn rỗi hoàn toàn chuyên biệt cho đầu tư, đã có quỹ dự phòng > 12 tháng"},
        ],
    },
]


def evaluate_risk_profile(scores: list[int]) -> dict[str, Any]:
    """
    Evaluate 4 quiz scores (each 1..4) and map to Risk Aversion coefficient A.
    Total score ranges from 4 to 16.
    """
    if not scores or len(scores) != 4:
        raise ValueError("Cần trả lời đủ 4 câu hỏi khảo sát khẩu vị rủi ro.")

    clean_scores = [max(1, min(4, int(s))) for s in scores]
    total_score = sum(clean_scores)

    # Precise mapping from total_score (4..16) to A (8.0..1.2)
    # Score 4 -> A = 8.0, Score 16 -> A = 1.2
    score_map = {
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
    risk_aversion_A = score_map.get(total_score, 3.0)

    if total_score <= 6:
        tier = "Rất thận trọng (Ultra-Conservative)"
        desc = "Ưu tiên bảo toàn vốn tối đa. Danh mục hoàn chỉnh phân bổ tỷ trọng lớn vào tài sản phi rủi ro (Tiền gửi/Trái phiếu)."
    elif total_score <= 9:
        tier = "Thận trọng (Conservative)"
        desc = "Ưu tiên sự ổn định, kết hợp hài hòa giữa tài sản phi rủi ro và danh mục cổ phiếu tiếp tuyến."
    elif total_score <= 12:
        tier = "Cân bằng (Moderate / Balanced)"
        desc = "Khẩu vị rủi ro tiêu chuẩn trong giáo trình (A ≈ 2.5 - 3.5), chấp nhận biến động hợp lý để tối ưu hóa hàm hữu dụng."
    else:
        tier = "Tăng trưởng Mạnh (Aggressive Growth)"
        desc = "Khẩu vị rủi ro cao, tập trung tối đa vào danh mục tài sản rủi ro tối ưu (Tangency Portfolio) để tối đa hóa tăng trưởng."

    return {
        "scores": clean_scores,
        "total_score": total_score,
        "max_possible_score": 16,
        "risk_aversion_A": risk_aversion_A,
        "profile_tier": tier,
        "description": desc,
    }
