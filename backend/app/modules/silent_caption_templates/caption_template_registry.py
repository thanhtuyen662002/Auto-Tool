from __future__ import annotations

from app.modules.silent_caption_templates.caption_template_schema import (
    SilentCaptionIndustry,
    SilentCaptionIntent,
    SilentCaptionTemplate,
)


def _templates(
    industry: SilentCaptionIndustry,
    rows: list[tuple[SilentCaptionIntent, str]],
) -> list[SilentCaptionTemplate]:
    counts: dict[SilentCaptionIntent, int] = {}
    result: list[SilentCaptionTemplate] = []
    for intent, text in rows:
        counts[intent] = counts.get(intent, 0) + 1
        tone = "chill" if any(word in text.casefold() for word in ("nhẹ nhàng", "thư giãn", "dễ chịu")) else "natural"
        tags = [tone]
        if intent in {SilentCaptionIntent.demo, SilentCaptionIntent.result}:
            tags.append("clean_review")
        if intent == SilentCaptionIntent.cta:
            tags.append("sales_light")
        result.append(
            SilentCaptionTemplate(
                id=f"{industry.value}.{intent.value}.{counts[intent]:02d}",
                industry=industry,
                intent=intent,
                text=text,
                tone=tone,
                tags=tags,
            )
        )
    return result


_I = SilentCaptionIntent
_D = SilentCaptionIndustry

_GENERAL = [
    (_I.hook, "Món này nhìn đơn giản mà khá tiện"),
    (_I.hook, "Ban đầu không kỳ vọng nhiều, nhưng dùng lại ổn"),
    (_I.hook, "Một món nhỏ giúp mọi thứ gọn hơn"),
    (_I.product_reveal, "Thiết kế gọn, nhìn khá sạch mắt"),
    (_I.product_reveal, "Cầm trên tay thấy nhỏ gọn hơn tưởng tượng"),
    (_I.unboxing, "Mở hộp ra là có thể xem ngay từng chi tiết"),
    (_I.unboxing, "Phần đóng gói nhìn gọn và khá chỉn chu"),
    (_I.closeup, "Nhìn gần mới thấy phần hoàn thiện khá ổn"),
    (_I.closeup, "Các chi tiết được làm theo kiểu đơn giản"),
    (_I.demo, "Thao tác dùng khá đơn giản"),
    (_I.demo, "Chỉ vài bước là dùng được ngay"),
    (_I.benefit, "Dùng hằng ngày sẽ tiện hơn khá nhiều"),
    (_I.benefit, "Nhỏ vậy thôi nhưng giúp tiết kiệm thời gian"),
    (_I.result, "Sắp xếp xong nhìn gọn hơn thấy rõ"),
    (_I.result, "Kết quả sau khi dùng nhìn khá sạch mắt"),
    (_I.cta, "Lưu lại để tham khảo khi cần nha"),
    (_I.cta, "Xem kỹ rồi hãy chọn mẫu phù hợp nhé"),
]

_HOME = [
    (_I.hook, "Góc nhà nhìn gọn hơn hẳn"),
    (_I.hook, "Nhà gọn hơn từ những chi tiết nhỏ thế này"),
    (_I.product_reveal, "Một món gia dụng nhìn khá thực tế"),
    (_I.product_reveal, "Kiểu dáng đơn giản, dễ hợp nhiều không gian"),
    (_I.unboxing, "Mở hộp món đồ cho góc nhà nhỏ"),
    (_I.unboxing, "Đóng gói gọn, lấy ra sắp xếp khá nhanh"),
    (_I.closeup, "Bề mặt và chi tiết nhìn khá sạch mắt"),
    (_I.closeup, "Nhìn gần thấy thiết kế thiên về tối giản"),
    (_I.demo, "Đặt ở phòng khách hay phòng ngủ đều ổn"),
    (_I.demo, "Dùng cho sinh hoạt hằng ngày khá tiện"),
    (_I.benefit, "Một món nhỏ giúp không gian dễ chịu hơn"),
    (_I.benefit, "Hợp với ai thích góc nhà ngăn nắp"),
    (_I.result, "Không gian sạch mắt hơn một chút"),
    (_I.result, "Cảm giác nhà cửa ngăn nắp hơn hẳn"),
    (_I.cta, "Lưu lại cho lần sắp xếp nhà tới nha"),
    (_I.cta, "Một món đáng cân nhắc cho góc nhà nhỏ"),
]

_KITCHEN = [
    (_I.hook, "Góc bếp gọn hơn thấy rõ"),
    (_I.hook, "Bếp nhỏ mà biết sắp xếp là khác liền"),
    (_I.product_reveal, "Món này hợp với căn bếp nhỏ"),
    (_I.product_reveal, "Không chiếm nhiều chỗ trên bàn bếp"),
    (_I.unboxing, "Mở hộp món tiện ích cho căn bếp"),
    (_I.unboxing, "Lấy ra là thấy kiểu dáng khá gọn"),
    (_I.closeup, "Nhìn gần các chi tiết khá dễ vệ sinh"),
    (_I.closeup, "Thiết kế gọn, đặt trong bếp khá hợp"),
    (_I.demo, "Nhìn thao tác khá nhanh và gọn"),
    (_I.demo, "Ai hay vào bếp chắc sẽ thấy tiện"),
    (_I.benefit, "Một món nhỏ giúp bếp dễ dùng hơn"),
    (_I.benefit, "Cất đồ kiểu này đỡ rối hơn hẳn"),
    (_I.result, "Nấu xong dọn cũng nhẹ hơn"),
    (_I.result, "Đặt trong bếp nhìn khá ngăn nắp"),
    (_I.cta, "Lưu lại cho góc bếp nhà mình nha"),
    (_I.cta, "Xem kích thước trước khi chọn cho bếp nhé"),
]

_STORAGE = [
    (_I.hook, "Nhìn cảnh sắp xếp này rất đã mắt"),
    (_I.hook, "Càng nhìn càng muốn dọn lại phòng"),
    (_I.product_reveal, "Món này hợp cho ai thích sắp xếp"),
    (_I.product_reveal, "Thiết kế dành cho những góc nhỏ dễ rối"),
    (_I.unboxing, "Mở ra là có thể chia đồ theo từng nhóm"),
    (_I.unboxing, "Từng ngăn nhìn đơn giản mà dễ dùng"),
    (_I.closeup, "Nhìn gần thấy các ngăn chia khá rõ"),
    (_I.closeup, "Kích thước gọn cho nhiều món đồ nhỏ"),
    (_I.demo, "Từng món nhỏ vào đúng chỗ rất gọn"),
    (_I.demo, "Dọn kiểu này nhìn thư giãn thật"),
    (_I.benefit, "Đồ đạc vào đúng chỗ là thấy nhẹ người"),
    (_I.benefit, "Không gian bớt rối hơn khá nhiều"),
    (_I.result, "Góc nhỏ gọn lại nhìn thích thật"),
    (_I.result, "Dọn xong sạch mắt hơn hẳn"),
    (_I.cta, "Lưu lại để có động lực dọn phòng"),
    (_I.cta, "Tham khảo cách chia đồ theo từng nhóm nha"),
]

_DESK = [
    (_I.hook, "Góc bàn nhìn gọn hơn hẳn"),
    (_I.hook, "Nhìn xong muốn dọn lại bàn luôn"),
    (_I.product_reveal, "Setup đơn giản mà sạch mắt"),
    (_I.product_reveal, "Đặt trên bàn khá hợp vibe tối giản"),
    (_I.unboxing, "Mở hộp món nhỏ cho góc làm việc"),
    (_I.unboxing, "Phụ kiện gọn, lấy ra setup khá nhanh"),
    (_I.closeup, "Nhìn gần thấy thiết kế khá tối giản"),
    (_I.closeup, "Chi tiết nhỏ nhưng hợp với mặt bàn gọn"),
    (_I.demo, "Sắp lên bàn chỉ mất vài thao tác"),
    (_I.demo, "Bàn làm việc đỡ rối hơn khá nhiều"),
    (_I.benefit, "Góc làm việc nhìn dễ chịu hơn hẳn"),
    (_I.benefit, "Bàn gọn thì làm việc cũng dễ tập trung hơn"),
    (_I.result, "Không gian nhỏ vẫn có thể gọn đẹp"),
    (_I.result, "Setup xong mặt bàn thoáng hơn thấy rõ"),
    (_I.cta, "Lưu lại cho lần setup bàn tiếp theo"),
    (_I.cta, "Ai thích setup bàn có thể tham khảo"),
]

_DORM = [
    (_I.hook, "Phòng nhỏ dùng mấy món này khá tiện"),
    (_I.hook, "Ký túc xá mà gọn được vậy là ổn"),
    (_I.product_reveal, "Một món tiện ích cho không gian nhỏ"),
    (_I.product_reveal, "Món này khá hợp với sinh viên"),
    (_I.unboxing, "Mở hộp món nhỏ dành cho phòng bé"),
    (_I.unboxing, "Đồ gọn nên cất trong phòng khá dễ"),
    (_I.closeup, "Nhìn gần thấy kích thước khá vừa vặn"),
    (_I.closeup, "Thiết kế nhỏ gọn, không tốn nhiều diện tích"),
    (_I.demo, "Dùng hằng ngày khá nhanh và đơn giản"),
    (_I.demo, "Hợp cho phòng nhỏ hoặc góc học tập"),
    (_I.benefit, "Đồ trong phòng đỡ lộn xộn hơn"),
    (_I.benefit, "Nhỏ gọn nhưng dùng hằng ngày ổn"),
    (_I.result, "Phòng bé vẫn có thể sắp xếp gọn"),
    (_I.result, "Góc học tập nhìn thoáng hơn một chút"),
    (_I.cta, "Lưu lại cho góc phòng nhỏ nha"),
    (_I.cta, "Nhớ xem kích thước trước khi chọn nhé"),
]

_BEAUTY = [
    (_I.hook, "Nhìn thao tác khá nhẹ nhàng"),
    (_I.hook, "Một món nhỏ cho routine cá nhân"),
    (_I.product_reveal, "Thiết kế nhỏ gọn, dễ cầm"),
    (_I.product_reveal, "Nhìn packaging khá sạch mắt"),
    (_I.unboxing, "Mở hộp từng lớp nhìn khá chỉn chu"),
    (_I.unboxing, "Lấy sản phẩm ra khá gọn và sạch"),
    (_I.closeup, "Nhìn gần thiết kế khá tinh gọn"),
    (_I.closeup, "Để trên bàn cũng khá xinh"),
    (_I.demo, "Dùng đơn giản, không quá cầu kỳ"),
    (_I.demo, "Thao tác phù hợp cho routine hằng ngày"),
    (_I.benefit, "Góc bàn trang điểm nhìn gọn hơn"),
    (_I.benefit, "Hợp với ai thích chăm chút bản thân"),
    (_I.result, "Sắp xếp xong góc cá nhân sạch mắt hơn"),
    (_I.result, "Routine nhìn gọn và dễ theo dõi hơn"),
    (_I.cta, "Lưu lại cho routine cá nhân khi cần nha"),
    (_I.cta, "Xem kỹ thông tin trước khi chọn nhé"),
]

_CLEANING = [
    (_I.hook, "Dọn kiểu này nhìn đã thật"),
    (_I.hook, "Góc nhỏ sạch hơn thấy rõ"),
    (_I.product_reveal, "Một món nhỏ cho việc vệ sinh hằng ngày"),
    (_I.product_reveal, "Thiết kế gọn cho những chỗ khó lau"),
    (_I.unboxing, "Mở hộp bộ dụng cụ dọn dẹp nhỏ gọn"),
    (_I.unboxing, "Các phần được xếp khá gọn trong hộp"),
    (_I.closeup, "Nhìn gần đầu dụng cụ khá dễ thao tác"),
    (_I.closeup, "Chi tiết nhỏ nhưng cầm khá vừa tay"),
    (_I.demo, "Nhìn thao tác khá gọn và nhanh"),
    (_I.demo, "Dùng cho việc lau dọn hằng ngày khá tiện"),
    (_I.benefit, "Món này giúp việc lau dọn nhẹ hơn"),
    (_I.benefit, "Mấy chi tiết nhỏ làm nhà gọn hơn"),
    (_I.result, "Dọn xong nhìn dễ chịu hơn hẳn"),
    (_I.result, "Không gian sạch mắt hơn khá nhiều"),
    (_I.cta, "Lưu lại cho lần dọn nhà tới"),
    (_I.cta, "Tham khảo cho góc cần vệ sinh thường xuyên"),
]


SILENT_CAPTION_TEMPLATES: list[SilentCaptionTemplate] = [
    *_templates(_D.general_product, _GENERAL),
    *_templates(_D.home_goods, _HOME),
    *_templates(_D.kitchen_goods, _KITCHEN),
    *_templates(_D.storage_organization, _STORAGE),
    *_templates(_D.desk_setup, _DESK),
    *_templates(_D.dorm_goods, _DORM),
    *_templates(_D.beauty_goods, _BEAUTY),
    *_templates(_D.cleaning_goods, _CLEANING),
]
