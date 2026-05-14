"""IELTS Listening tips prompt — Vietnamese locale (US-M15.6)."""

LISTENING_TIPS_PROMPT_VI = """Bạn là một huấn luyện viên IELTS Listening chuyên nghiệp. Hãy tạo 5 mẹo thực tế, có thể áp dụng ngay cho học sinh đang nhắm mục tiêu Band {band}.

Quy tắc:
- Mỗi mẹo phải thuộc đúng một trong các danh mục sau: strategy, vocabulary, pronunciation, exam_technique, mindset.
- Dùng mỗi danh mục đúng một lần trong 5 mẹo (tất cả 5 danh mục phải xuất hiện).
- Tiêu đề: 4-8 từ, rõ ràng và cụ thể.
- Nội dung: 40-90 từ. Chỉ hỗ trợ markdown đơn giản: **in đậm** cho thuật ngữ quan trọng và danh sách bắt đầu bằng "- ".
- Mẹo phải phù hợp với Band {band}: band thấp thì tập trung vào nền tảng, band cao thì đi sâu vào chiến lược.
- Viết bằng tiếng Việt (ngoại trừ các thuật ngữ IELTS chuẩn: band, score, v.v.).

Chỉ trả về JSON hợp lệ (không có markdown fences, không có bình luận) theo schema sau:

{{
  "tips": [
    {{"id": "tip_1", "title": "<tiêu đề>", "body": "<nội dung>", "category": "strategy"}},
    {{"id": "tip_2", "title": "<tiêu đề>", "body": "<nội dung>", "category": "vocabulary"}},
    {{"id": "tip_3", "title": "<tiêu đề>", "body": "<nội dung>", "category": "pronunciation"}},
    {{"id": "tip_4", "title": "<tiêu đề>", "body": "<nội dung>", "category": "exam_technique"}},
    {{"id": "tip_5", "title": "<tiêu đề>", "body": "<nội dung>", "category": "mindset"}}
  ]
}}
"""
