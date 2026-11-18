# Báo cáo Day 09 — Nguyễn Bình Anh, 2A202504063

## 1. Kết luận trước
Pipeline kết luận **HOLD** (tạm giữ, xuất bản nháp tại `submission/export/clean_v1` và chưa phát hành chính thức). Từ **224 ảnh** đầu vào (`data/raw/`), Bước 1 loại **19 ảnh** không đạt chuẩn (ảnh hỏng, sai kích thước, trùng lặp, rò rỉ tập test) và đưa **205 ảnh** vào dataset. Sau khi máy tự sửa lỗi cú pháp và người duyệt hết ngân sách **80 ảnh** (bao gồm 6 ảnh thiếu nhãn), dataset không còn lỗi bắt buộc (`0 error`) nhưng vẫn còn **38/205 ảnh (18.54%)** mang cảnh báo chưa được duyệt — vượt ngưỡng cho phép **10.00%** của cửa chặn.

## 2. Lỗi và phân việc
Tổng hợp từ `02_error_list_v1.csv` trên lô dữ liệu (19 ảnh loại ở Bước 1 + 36 lỗi bắt buộc và 149 cảnh báo trên 205 ảnh hợp lệ):

| Mã lỗi | Số dòng / ảnh | Ai sửa (máy/người) | Vì sao |
|---|---:|---|---|
| `DUP_IMAGE_EXACT` | 8 / 8 ảnh | Máy (Bước 1) | Trùng MD5 tuyệt đối, loại tự động để tránh lặp dữ liệu. |
| `LEAK_TEST` | 4 / 4 ảnh | Máy (Bước 1) | Trùng với tập test, bắt buộc loại để chống rò rỉ dữ liệu. |
| `BAD_SIZE` | 3 / 3 ảnh | Máy (Bước 1) | Kích thước ảnh bất thường, loại tự động ở khâu nhận dữ liệu. |
| `CORRUPT_IMAGE` | 2 / 2 ảnh | Máy (Bước 1) | File ảnh hỏng không đọc được, loại tự động. |
| `DUP_IMAGE_NEAR` | 2 / 2 ảnh | Máy (Bước 1) | Trùng gần (`phash_dist <= 4`), loại tự động bản dư. |
| `BOX_OUT_OF_IMAGE` | 8 / 8 ảnh | Máy (autofix) | Tọa độ tràn biên `[0, 1]`, có thể cắt (clip) chính xác về mép ảnh. |
| `DUP_BOX` | 7 / 7 ảnh | Máy (autofix) | Box trùng lặp cùng lớp (`IoU > 0.90`), khử trùng tự động theo quy tắc. |
| `BAD_CLASS_ID` | 6 / 6 ảnh | Máy (autofix) | ID lớp nằm ngoài `0..3`, không thể đoán lớp đúng nên xoá dòng lỗi. |
| `BOX_ZERO` | 4 / 4 ảnh | Máy (autofix) | Box có chiều rộng hoặc cao $\le 0$, vô nghĩa nên xoá dòng. |
| `BAD_FORMAT` | 3 / 3 ảnh | Máy (autofix) | Dòng sai cấu trúc 5 cột YOLO, xoá tự động để sạch file nhãn. |
| `BAD_CLASS_NAME` | 2 / 1 file (`data.yaml`) | Máy (autofix) | Sai tên lớp trong `data.yaml`, chuẩn hoá tự động theo danh sách chuẩn. |
| `MISSING_LABEL_FILE` | 6 / 6 ảnh | Người (qua hàng đợi) | Thiếu file `.txt`, máy tạo file rỗng và gắn `NEEDS_LABEL` cho người gán. |
| `POSSIBLE_MISSING` | 53 / 52 ảnh | Người | Nghi sót vật thể, cần mắt người xác nhận bối cảnh thực tế. |
| `POSSIBLE_LOOSE_BOX` | 28 / 24 ảnh | Người | Box lệch/lỏng so với model kiểm (`IoU < 0.55`), cần người căn chỉnh. |
| `POSSIBLE_FALSE_POS` | 25 / 24 ảnh | Người | Box nhãn không khớp dự đoán model, cần người kiểm tra box thừa. |
| `POSSIBLE_WRONG_CLASS` | 18 / 18 ảnh | Người | Nghi gán nhầm lớp (vd: `car` vs `truck`), cần người phân định. |
| `EMPTY_LABEL` | 12 / 12 ảnh | Người | File nhãn trống, cần người xác nhận ảnh nền thật hay bị bỏ sót. |
| `BOX_TINY` | 6 / 4 ảnh | Người | Box có cạnh ngắn `< 12 px`, cần người xem có phải nhiễu hay vật ở xa. |
| `CLASS_RARE` | 4 / 1 mức dataset | Người | Cảnh báo mất cân bằng lớp ở mức toàn tập, người dùng để cân đối bổ sung. |
| `BOX_HUGE` | 3 / 3 ảnh | Người | Box chiếm `> 90%` diện tích ảnh, cần người kiểm tra có phải gán nhầm nền. |

- **Cách xếp thứ tự `05_review_queue.csv`:** Hàng đợi ưu tiên cao nhất cho các ảnh vừa bị máy sửa/xoá dòng (`FIXED_DROP_LINE`, điểm ~11.5) để người kiểm tra lại tránh máy xoá nhầm nhãn đúng, tiếp theo là các ảnh chưa có nhãn (`NEEDS_LABEL`, điểm 10.0) nhằm triệt tiêu toàn bộ lỗi bắt buộc (`ERROR`), sau đó mới xếp các cảnh báo ngữ nghĩa theo mức độ nghiêm trọng và độ tự tin (`conf`) của model kiểm.
- **Hiệu quả ngân sách 80 ảnh:** Trong **80 ảnh** đầu hàng đợi (trên tổng 125 ảnh cần xem), người duyệt xử lý được **88 cảnh báo lỗi ngữ nghĩa** (`50 POSSIBLE_MISSING`, `18 POSSIBLE_WRONG_CLASS`, `12 POSSIBLE_FALSE_POS`, `8 POSSIBLE_LOOSE_BOX`), đồng thời hoàn tất **6/6 ảnh `NEEDS_LABEL`**, **11 ảnh `EMPTY_LABEL`** và **1 cảnh báo `BOX_TINY`**.

## 3. Calibration (2 ngưỡng)
| Tham số | Khởi đầu | Đã chọn | Precision / Recall (trước → sau) | Lý do (đánh đổi) |
|---|---|---|---|---|
| `duplicates.phash_dist` | 2 | **4** | `DUP_IMAGE_NEAR`: `1.00 / 0.50` → `1.00 / 0.67` (`F1`: `0.67` → `0.80`) | Tăng từ `2` lên `4` giúp bắt thêm ảnh trùng gần (`Recall` tăng `0.17`) mà vẫn giữ `Precision = 1.00` (`FP = 0`), tránh để autofix xoá nhầm ảnh khác nhau. |
| `second_opinion.conf` | 0.25 | **0.6** | `POSSIBLE_MISSING`: `0.50 / 1.00` → `0.57 / 1.00`; `POSSIBLE_WRONG_CLASS`: `0.56 / 0.83` → `0.62 / 0.83` | Nâng ngưỡng lên `0.6` giữ nguyên toàn bộ `Recall` bắt lỗi (`1.00` và `0.83`) nhưng giảm được 3 báo động giả trên `calib`, tiết kiệm ngân sách duyệt tay; nếu tăng tiếp lên `0.7` thì `Recall` của `POSSIBLE_MISSING` bắt đầu rơi xuống `0.88`. |

- **Một chỗ calibration có thể đánh lừa:** Trên tập `calib` (39 ảnh rời rạc), `duplicates.phash_dist = 16` cho kết quả đẹp nhất (`Precision = 1.00, Recall = 0.83, F1 = 0.91`, `FP = 0`). Tuy nhiên, nếu tin theo con số này để đặt ngưỡng `16` trên dữ liệu thật (`data/raw/`), các khung hình chụp liên tiếp trong cùng một bối cảnh giao thông có khoảng cách pHash nhỏ sẽ bị coi nhầm là trùng lặp và bị xoá vĩnh viễn ở Bước 1. Với mức an toàn `4`, Bước 1 loại hợp lý **19/224 ảnh** (gồm 8 trùng tuyệt đối, 2 trùng gần, 4 rò rỉ test, 3 sai kích thước, 2 ảnh hỏng) và giữ lại **205 ảnh** sạch.

## 4. Cửa chặn và điều pipeline KHÔNG bắt được
- **Quan sát bằng mắt trên `work/viz/` đối chiếu với kết quả pipeline:**
  1. `img_0001.png` (bỏ sót người lính mặc quân phục bên phải): Pipeline **bắt được** bằng cảnh báo `POSSIBLE_MISSING` ở Bước 6 vì model `yolo26l` nhận diện được đối tượng `person` này.
  2. `img_0004.png` (bỏ sót 2 chiếc ô tô đỗ góc dưới bên phải): Pipeline **bắt được** nhờ `POSSIBLE_MISSING` do 2 xe có kích thước đủ lớn (`> 400 px²`) và độ tự tin cao.
  3. `img_0005.png` (box `5: person` khoanh nhầm vào cột thùng rác ở rìa trái): Pipeline **bắt được** thông qua `POSSIBLE_FALSE_POS` vì box nhãn có `IoU < 0.30` so với mọi dự đoán của model kiểm.
- **Điều pipeline vẫn không bắt được:** Các vật thể bị che khuất nặng, quá nhỏ (`< 400 px²` bị lọc bởi `min_area_px` trong `second_opinion`), hoặc các ca mờ nhòe mà cả người gán lẫn model `yolo26l` đều bỏ sót/nhầm giống nhau; ngoài ra **38 ảnh** mang cảnh báo nằm ngoài top 80 của hàng đợi chưa được người xem nên cửa chặn buộc phải dừng ở **HOLD**.

## 5. Train: raw vs clean (tùy chọn, chấm riêng)
Chưa chạy (tập trung hoàn thiện pipeline QC, hiệu chỉnh ngưỡng, rà soát thủ công và kiểm thử hồi quy).

## 6. Quyết định và ghi chú AI
- **(a) Quyết định cuối & điều kiện để thành Release:** Giữ trạng thái **HOLD** cho lô `clean_v1` (205 ảnh). Để chuyển sang **Release**, cần bổ sung ngân sách duyệt tay cho tối thiểu **18 ảnh** đứng đầu phần còn lại của `05_review_queue.csv` (giảm số ảnh mang cảnh báo chưa duyệt từ `38/205` = `18.54%` xuống dưới `20/205` = `9.76% < 10.00%`).
- **(b) Ghi chú sử dụng AI:**
  - *Prompt chính:* Yêu cầu viết các hàm kiểm tra định dạng nhãn (`label_format.py`), tự động sửa lỗi bắt buộc (`autofix.py`), đối chiếu model lớn hơn (`second_opinion.py`) và logic cổng quyết định (`gate.py`) bám sát `configs/pipeline.yaml` và bộ `pytest`.
  - *Cách kiểm code AI:* Chạy toàn bộ unit test và integration test (`pytest -q`), đối chiếu chỉ số Precision/Recall trên `data/calib/` qua `pipeline.calibrate`, và trực tiếp mở ảnh kiểm tra bằng `viz_labels.py` cùng CVAT.
  - *1 lần AI sai và cách sửa:* AI ban đầu dùng `enumerate(ds.read_label_lines(stem), start=1)` khiến biến dòng nhận về kiểu `tuple` thay vì `str` (gây lỗi `AttributeError: 'tuple' object has no attribute 'strip'`), đồng thời trong `cvat/labels.json` trường `"values": []` của checkbox bị CVAT từ chối; đã sửa lại vòng lặp unpack trực tiếp `(line_no, raw_line)` và bổ sung `"values": ["false"]` cho schema CVAT.
- **(Thưởng +2) Đối chiếu lọc box nhỏ trên CVAT (`width < 20`):**
  - *Ảnh và số box khớp trên CVAT:* Lọc `width < 20` trên bộ 205 ảnh bắt được các box người đứng xa như `img_0030.jpg` (3 box `person`), `img_0053.jpg` (1 box `person` kích thước `16.5 × 36.5 px`), `img_0135.jpg` (2 box `person`) và ảnh xe buýt Metro Local (3 box `person`, kích thước `16.3 × 48.2 px`).
  - *Đối chiếu với `BOX_TINY` của pipeline:* Pipeline ghi nhận **7 dòng `BOX_TINY`** (`img_0026`, `img_0030` dòng 9, `img_0051`, `img_0069` và 3 box ở `img_0161`), trùng với CVAT tại ảnh **`img_0030`** (box có cạnh ngắn `9.8 px`). Các box như `16.3 × 48.2 px` hay `16.5 × 36.5 px` bị CVAT lọc vì dùng ngưỡng rộng `width < 20 px`, trong khi pipeline không cảnh báo `BOX_TINY` do áp dụng ngưỡng chặt hơn là `min_box_px: 12` px.
  - *Ý nghĩa của `can_review`:* Người gán nhãn bật `can_review = true` khi gặp đối tượng mờ, khuất hoặc khó phân loại để chuyển sang người kiểm duyệt xem lại; trong pipeline, cơ chế tương đương chính là các cờ cảnh báo mức `WARN` từ `second_opinion` và danh sách ưu tiên trong `05_review_queue.csv`.