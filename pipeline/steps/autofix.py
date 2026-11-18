"""BƯỚC 2/4 — Sửa tự động những lỗi bắt buộc mà máy sửa được AN TOÀN.   ★★

Test:  pytest tests/test_autofix.py -q

`fix(ds, issues, cfg) -> list[dict]`: duyệt `issues` (chỉ lỗi severity ERROR), sửa thẳng vào thư mục `ds`,
và trả về danh sách thay đổi; mỗi phần tử có khoá: image, line, action, before, after
(đây chính là file `03_fixes.csv` — bằng chứng pipeline đã làm gì, người có thể kiểm lại).

| code lỗi                                       | cách sửa                                    | action           |
|------------------------------------------------|---------------------------------------------|------------------|
| BAD_FORMAT, BAD_CLASS_ID, BOX_ZERO, DUP_BOX    | xoá dòng đó khỏi file nhãn                  | "drop_line"      |
| BOX_OUT_OF_IMAGE                               | cắt box về trong [0,1] (giữ nguyên lớp)     | "clip_box"       |
| MISSING_LABEL_FILE                             | KHÔNG sửa file (máy không thể bịa nhãn): ghi 1 dòng fix, before="(không có file)", after="chuyển người gán" | "needs_label" |
| BAD_CLASS_NAME                                 | ghi lại `names` trong data.yaml đúng `cfg["classes"]` | "rename_classes" |
| DUP_IMAGE_*, LEAK_TEST, CORRUPT_IMAGE, BAD_SIZE| xoá ảnh + nhãn khỏi `ds`                    | "remove_image"   |

Bẫy cần nghĩ tới (có test cho từng cái)
- Một file có NHIỀU dòng lỗi: số dòng trong `issues` là số dòng GỐC. Nếu xoá từng dòng một thì số dòng lệch.
  Gom theo file, rồi ghi lại MỘT lần.
- Sau khi cắt, box có thể không còn diện tích (nằm hẳn ngoài ảnh): lúc đó xoá dòng thay vì ghi box rỗng.
- Một dòng có 2 lỗi (vd. BOX_OUT_OF_IMAGE + DUP_BOX): xoá dòng thắng, chỉ ghi 1 fix `drop_line`, không ghi thêm `clip_box`. Dòng trống ở giữa file vẫn đếm vào số dòng gốc.
- Ảnh vừa bị xoá (DUP_IMAGE_*...) mà còn issue dòng của chính nó: bỏ qua êm, không được báo lỗi/chết.
- Không động tới lỗi WARN (cảnh báo là việc của người). Không sửa file ở `data/raw/` — chỉ sửa `ds`.
- Chạy lần 2 trên dữ liệu đã sửa phải không làm gì thêm (idempotent) — NGOẠI LỆ duy nhất: `needs_label` được ghi lại mỗi lần còn lỗi `MISSING_LABEL_FILE` (vì ảnh vẫn chưa có nhãn).

- `needs_label` KHÔNG tạo file nhãn rỗng (rỗng = "ảnh nền", khác với "chưa gán"). `review_queue` sẽ đẩy ảnh này lên đầu hàng đợi cho người.

Gợi ý: `yaml.safe_load / safe_dump`.
"""

from collections import defaultdict
from pathlib import Path

import yaml

from ..common import ERROR, parse_yolo_line

DROP_CODES = {"BAD_FORMAT", "BAD_CLASS_ID", "BOX_ZERO", "DUP_BOX"}
REMOVE_IMAGE_CODES = {"DUP_IMAGE_EXACT", "DUP_IMAGE_NEAR", "LEAK_TEST", "CORRUPT_IMAGE", "BAD_SIZE"}


def _find_yaml_path(ds):
    for attr in ("yaml_path", "data_yaml", "yaml_file"):
        p = getattr(ds, attr, None)
        if p is not None:
            return Path(p)
    root = getattr(ds, "root", None) or getattr(ds, "dir", None)
    if root is not None:
        return Path(root) / "data.yaml"
    return Path(ds.labels_dir).parent / "data.yaml"


def fix(ds, issues, cfg):
    err_issues = [i for i in issues if i.severity == ERROR]
    fixes = []
    removed_images = set()

    # 1. Xoá ảnh lỗi / trùng / rò rỉ
    for iss in err_issues:
        if iss.code in REMOVE_IMAGE_CODES or iss.code.startswith("DUP_IMAGE_"):
            stem = iss.image
            if stem in removed_images:
                continue
            removed_images.add(stem)
            for img_p in list(ds.image_files()):
                if img_p.stem == stem:
                    img_p.unlink(missing_ok=True)
            lp = ds.label_path(stem)
            if lp.exists():
                lp.unlink(missing_ok=True)
            fixes.append(
                {
                    "image": stem,
                    "line": None,
                    "action": "remove_image",
                    "before": stem,
                    "after": "(đã xoá)",
                }
            )

    # 2. Sửa tên lớp trong data.yaml
    if any(i.code == "BAD_CLASS_NAME" for i in err_issues):
        yp = _find_yaml_path(ds)
        if yp.exists():
            data = yaml.safe_load(yp.read_text(encoding="utf-8")) or {}
            old_names = data.get("names")
            target_classes = list(cfg["classes"])
            if isinstance(old_names, list):
                data["names"] = target_classes
            else:
                data["names"] = {idx: name for idx, name in enumerate(target_classes)}
            if "nc" in data:
                data["nc"] = len(target_classes)
            yp.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")
            fixes.append(
                {
                    "image": "data.yaml",
                    "line": None,
                    "action": "rename_classes",
                    "before": str(old_names),
                    "after": str(target_classes),
                }
            )

    # 3. Ghi nhận ảnh thiếu file nhãn để đẩy cho người duyệt (không tạo file rỗng)
    seen_missing = set()
    for iss in err_issues:
        if iss.code == "MISSING_LABEL_FILE" and iss.image not in removed_images and iss.image not in seen_missing:
            seen_missing.add(iss.image)
            fixes.append(
                {
                    "image": iss.image,
                    "line": None,
                    "action": "needs_label",
                    "before": "(không có file)",
                    "after": "chuyển người gán",
                }
            )

    # 4. Gom lỗi theo (ảnh, dòng) để sửa một lần, giữ đúng số dòng gốc
    line_codes = defaultdict(lambda: defaultdict(set))
    for iss in err_issues:
        if iss.image in removed_images or iss.line is None:
            continue
        if iss.code in DROP_CODES or iss.code == "BOX_OUT_OF_IMAGE":
            line_codes[iss.image][iss.line].add(iss.code)

    for stem, per_line in line_codes.items():
        lp = ds.label_path(stem)
        if not lp.exists():
            continue

        orig_lines = lp.read_text(encoding="utf-8").splitlines()
        new_lines = []

        for line_no, orig_line in enumerate(orig_lines, start=1):
            codes = per_line.get(line_no)
            if not codes:
                new_lines.append(orig_line)
                continue

            # Xoá dòng được ưu tiên cao hơn cắt box nếu cùng 1 dòng dính 2 lỗi
            if codes & DROP_CODES:
                fixes.append(
                    {
                        "image": stem,
                        "line": line_no,
                        "action": "drop_line",
                        "before": orig_line,
                        "after": "(đã xoá)",
                    }
                )
                continue

            if "BOX_OUT_OF_IMAGE" in codes:
                try:
                    cls_id, cx, cy, w, h = parse_yolo_line(orig_line)
                except ValueError:
                    fixes.append(
                        {
                            "image": stem,
                            "line": line_no,
                            "action": "drop_line",
                            "before": orig_line,
                            "after": "(đã xoá)",
                        }
                    )
                    continue

                x1 = max(0.0, cx - w / 2.0)
                y1 = max(0.0, cy - h / 2.0)
                x2 = min(1.0, cx + w / 2.0)
                y2 = min(1.0, cy + h / 2.0)
                nw, nh = x2 - x1, y2 - y1

                # Nếu box nằm hẳn ngoài ảnh (sau khi cắt diện tích <= 0) thì xoá dòng
                if nw <= 0.0 or nh <= 0.0:
                    fixes.append(
                        {
                            "image": stem,
                            "line": line_no,
                            "action": "drop_line",
                            "before": orig_line,
                            "after": "(đã xoá)",
                        }
                    )
                    continue

                ncx, ncy = (x1 + x2) / 2.0, (y1 + y2) / 2.0
                clipped_line = f"{cls_id} {ncx:.6f} {ncy:.6f} {nw:.6f} {nh:.6f}"
                new_lines.append(clipped_line)
                fixes.append(
                    {
                        "image": stem,
                        "line": line_no,
                        "action": "clip_box",
                        "before": orig_line,
                        "after": clipped_line,
                    }
                )

        lp.write_text("\n".join(new_lines) + ("\n" if new_lines else ""), encoding="utf-8")

    return fixes