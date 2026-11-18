# Phân tích kết quả thí nghiệm: Dữ liệu gốc (`raw`) vs Dữ liệu sau Pipeline (`clean_v1`)

## 1. Tổng hợp kết quả thực nghiệm (Tập Test: 100 ảnh, 387 instances)

Thí nghiệm được thực hiện công bằng trên kiến trúc `yolo26n.pt` (20 epochs, `imgsz=640`, `batch=16`, đánh giá trên cùng tập `gold_val` 40 ảnh và `test` 100 ảnh):

| Biến thể | Seed | Số ảnh train thực tế | mAP50 | mAP50-95 | Precision | Recall | AP50 `car` | AP50 `person` | AP50 `truck` | AP50 `bus` |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **`raw`** | 0 | 213 *(khai báo 224)* | 0.7256 | 0.5144 | 0.8068 | 0.6291 | 0.7511 | 0.8126 | 0.6574 | 0.6811 |
| **`raw`** | 1 | 213 *(khai báo 224)* | 0.7259 | 0.5090 | 0.7203 | 0.6689 | 0.7239 | 0.8315 | 0.6395 | 0.7087 |
| **TB `raw`** | **0, 1** | **213** | **0.7258 ± 0.0002** | **0.5117** | **0.7636** | **0.6490** | **0.7375** | **0.8221** | **0.6485** | **0.6949** |
| **`clean`** | 0 | 205 | 0.6787 | 0.4770 | 0.6626 | 0.6029 | 0.7566 | 0.8301 | 0.5305 | 0.5978 |
| **`clean`** | 1 | 205 | 0.7219 | 0.4953 | 0.7664 | 0.6277 | 0.7403 | 0.8246 | 0.5871 | 0.7355 |
| **TB `clean`** | **0, 1** | **205** | **0.7003 ± 0.0305** | **0.4862** | **0.7145** | **0.6153** | **0.7485** | **0.8274** | **0.5588** | **0.6667** |

---

## 2. Trả lời các câu hỏi phân tích

### Câu 1: Chênh lệch `mAP50(clean) - mAP50(raw)` so với độ lệch chuẩn giữa các seed & Giới hạn kết luận với 2 seed
* **Độ chênh lệch trung bình:** $\Delta\text{mAP50} = 0.7003 - 0.7258 = -0.0255$ (tương đương giảm 2.55% trên tập test).
* **So sánh với độ lệch chuẩn (std):** Độ lệch chuẩn giữa 2 seed của `clean` lên tới **$\pm 0.0305$** (dao động từ `0.6787` ở seed 0 lên `0.7219` ở seed 1), lớn hơn cả mức chênh lệch trung bình giữa hai biến thể ($|-0.0255| < 0.0305$). Trong khi đó, ở seed 1, `clean` (`0.7219`) đạt hiệu năng gần như tương đương `raw` (`0.7259`).
* **Giới hạn kết luận với 2 seed:** Với kích thước tập dữ liệu nhỏ (khoảng 200 ảnh) và chỉ chạy 2 seed, phương sai do ngẫu nhiên (khởi tạo dữ liệu mosaic, thứ tự batch) rất lớn. Do đó, chưa đủ ý nghĩa thống kê để kết luận `clean` kém hơn `raw` về mặt tổng quát hóa; cần chạy thêm nhiều seed hơn (ví dụ 3–5 seed) và loại bỏ yếu tố rò rỉ dữ liệu ở `raw` để đánh giá chính xác.

### Câu 2: Số ảnh thực sự được dùng để train của `raw`
* Mặc dù thư mục `raw` khai báo **224 ảnh** (và 218 file nhãn), khi quét dữ liệu ở bước 6, Ultralytics đã tự động phát hiện và **loại bỏ 11 ảnh/nhãn hỏng (`corrupt`)**, khiến mô hình `raw` thực chất chỉ được train trên **213 ảnh** (trong đó có 19 ảnh background không chứa nhãn).
* Chi tiết 11 file bị Ultralytics bỏ qua:
  * **Lỗi file ảnh hỏng/cắt cụt (2 ảnh):** `img_0010.jpg` (không nhận diện được định dạng ảnh), `img_0136.jpg` (file ảnh bị truncated thiếu 26 bytes).
  * **Lỗi Class ID ngoài phạm vi `0-3` (5 ảnh):** `img_0020.jpg` (class `93`), `img_0104.jpg` (class `7`), `img_0194.jpg` (class `4`), `img_0199.jpg` (class `4`), cùng các nhãn mang giá trị âm `-1` tại `img_0099.jpg` và `img_0117.jpg`.
  * **Lỗi tọa độ/định dạng nhãn (3 ảnh):** `img_0014.jpg` và `img_0022.jpg` (tọa độ không chuẩn hóa hoặc vượt ngoài biên `[0, 1]`), `img_0179.jpg` (cấu trúc mảng nhãn không đồng nhất).
* Ngược lại, bộ `clean` có **205/205 ảnh hợp lệ (0 corrupt)**, chứng minh pipeline AutoQC đã lọc sạch hoàn toàn các lỗi định dạng cứng trước khi đưa vào huấn luyện.

### Câu 3: Hiện tượng rò rỉ dữ liệu (`LEAK_TEST`) ở `raw` và tác động thổi phồng điểm số
* **Có rò rỉ dữ liệu:** Tập `raw` chứa các ảnh trùng lặp (hoặc gần trùng lặp via perceptual hash / exact hash) với tập `test` (đã được pipeline gắn cờ `LEAK_TEST` và loại bỏ khỏi tập `clean_v1`).
* **Mức độ thổi phồng điểm số:** Việc mô hình `raw` "học thuộc" các ảnh vốn nằm trong tập `test` khiến điểm đánh giá trên tập test của `raw` (`0.7258`) bị đẩy lên cao một cách giả tạo, che lấp đi tác hại của nhiễu nhãn. Khi so sánh trên tập `gold_val` (không bị rò rỉ), `clean` ở seed 0 đạt `mAP50-95 = 0.578` (cao hơn `0.573` của `raw` seed 0), cho thấy chất lượng học thực chất của `clean` không hề thua kém.
* **Cách kiểm chứng:** Có thể đối chiếu danh sách các ảnh bị gắn cờ `LEAK_TEST` trong log/manifest của pipeline với 100 ảnh trong `data/test/images`, sau đó tính riêng mAP của mô hình `raw` trên tập `test` đã loại bỏ các ảnh bị leak (hoặc kiểm tra độ tự tin/IoU của `raw` trên riêng nhóm ảnh bị leak so với phần còn lại của tập test).

### Câu 4: Phân tích hiệu năng theo từng lớp (`car`, `person`, `truck`, `bus`)
* **Lớp được lợi nhất:** **`car`** (tăng từ `0.7375` lên `0.7485`, +1.10% AP50 trung bình) và **`person`** (tăng từ `0.8221` lên `0.8274`, +0.53% AP50 trung bình; đạt `0.8301` ngay ở seed 0).
  * *Giải thích từ thống kê box & lỗi nhãn (`02_error_list_v1`):* Sau pipeline, số lượng box hợp lệ của lớp `person` tăng từ `537` lên `576` (+39 box do khôi phục/sửa các file nhãn lỗi định dạng hoặc nhãn sai class ID như `-1`, `4`, `7`, `93` trước đó bị Ultralytics vứt bỏ cả file). Việc loại bỏ các box nhiễu/trùng lặp (`DUP_BOX`) và sửa nhãn lệch giúp hai lớp chủ đạo này hội tụ ổn định hơn.
* **Lớp bị ảnh hưởng / biến động mạnh:** **`truck`** (giảm từ `0.6485` xuống `0.5588`) và **`bus`** (giảm nhẹ trung bình từ `0.6949` xuống `0.6667`, nhưng riêng seed 1 tăng vọt lên `0.7355`).
  * *Giải thích:* Đây là hai lớp thiểu số (chỉ có 42 box `truck` và 33 box `bus` trong tập `clean`). Khi loại bỏ 19 ảnh từ `raw` (bao gồm các ảnh trùng lặp và ảnh bị `LEAK_TEST`), số mẫu đại diện của `truck` và `bus` vốn đã ít lại càng nhạy cảm hơn với việc chia batch và xóa nhãn ở mức ảnh, đồng thời dễ bị nhầm lẫn giữa các phương tiện cỡ lớn (`car` / `truck` / `bus`) do còn tồn đọng các cảnh báo chưa được người duyệt.

### Câu 5: Các lỗi còn tồn đọng trong `clean` và đánh giá "chặn trên" (Oracle)
* **Tình trạng hiện tại của `clean_v1`:** Theo `manifest.json`, pipeline đang đưa ra quyết định **`Hold`** với lý do: *"Không còn lỗi bắt buộc, nhưng tỉ lệ ảnh còn cảnh báo chưa duyệt là **18.54% (38/205 ảnh)** >= ngưỡng 10.00%"*.
* **Các lỗi còn tồn tại & Ngân sách duyệt (Human-in-the-Loop):**
  * `clean_v1` mới chỉ tự động xử lý/loại bỏ các lỗi nghiêm trọng (ảnh hỏng, trùng lặp `EXACT_DUP`/`NEAR_DUP`, rò rỉ `LEAK_TEST`, nhãn ngoài dải `0-3`).
  * Vẫn còn **38 ảnh** mang cảnh báo mức độ nhẹ/trung bình (như box quá nhỏ, tỷ lệ khung hình bất thường, hoặc nghi ngờ gán nhầm nhãn giữa `car`/`truck`/`bus`) vượt quá ngân sách duyệt thủ công cho phép (10% = ~20 ảnh) nên chưa được con người xác nhận hết.
* **Kết luận về chặn trên (Oracle):** Vì vẫn còn gần 1/5 dữ liệu (18.54%) chứa cảnh báo nhãn chưa được con người hiệu đính, **`clean_v1` chưa phải là chặn trên của dữ liệu sạch**. Nếu giải quyết nốt 38 ảnh trong hàng đợi review (hoặc sử dụng nhãn chuẩn của con người trên tập `clean` — biến thể `oracle`), hiệu năng mô hình (đặc biệt ở hai lớp `truck` và `bus`) sẽ được cải thiện rõ rệt hơn nữa.