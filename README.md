# stardew-moon

Công cụ và dữ liệu để kéo **Harvest Moon: Friends of Mineral Town** (GBA) về phía cân bằng kiểu
**Stardew Valley**: giá nông sản, số ngày sinh trưởng, thể lực khởi đầu.

Repo này **không chứa ROM, không chứa mã nguồn decompile**. Bạn tự cung cấp ROM mình sở hữu và
clone [StanHash/fomt](https://github.com/StanHash/fomt) — hai thứ đó không được phép phân phối ở đây.

## Nội dung

| Đường dẫn | Nội dung |
|---|---|
| `scripts/extract_crop_data.py` | Đọc bảng cây trồng, bảng thời tiết và bảng ánh xạ vật phẩm trực tiếp từ ROM |
| `scripts/patch_stardew.py` | Patch giá bán, số ngày sinh trưởng, thể lực khởi đầu vào repo decompile |
| `scripts/verify_patch.py` | So sánh ROM gốc với ROM đã patch, in ra các vùng byte bị đổi |
| `data/farm_data.json` | Kết quả trích: 21 cây, ngày chín, ngày tái sinh, giá, xác suất thời tiết |
| `docs/FOMT-NOTES.md` | Phân tích engine FoMT: cấu trúc ô đất, vòng ngày, event script, số liệu cân bằng |
| `docs/PATCH-NOTES.md` | Quy trình build, nội dung từng patch, kiểm chứng, và giới hạn kỹ thuật |
| `patches/0001-stardew-balance.patch` | Diff tham chiếu của patch hiện tại |

## Vì sao chỉ patch được dữ liệu

Repo decompile mới dịch ngược khoảng **2%** game thành C++ (9.697 dòng), phần còn lại là
**434.464 dòng assembly** gọi hàm bằng địa chỉ tuyệt đối. `fomt.lds` xếp các object tuần tự, nên
chỉ cần một hàm dài thêm vài byte là mọi địa chỉ phía sau lệch và ROM hỏng.

Vì vậy patch ở đây chỉ sửa **giá trị dữ liệu** và **immediate cùng cỡ lệnh**. Sprinkler, kỹ năng
nghề có XP, hầm mỏ nhiều tầng, crafting — đều cần thêm code, sprite và mục shop, tức loại thay đổi
bị chặn bởi ràng buộc trên.

## Quy trình

```bash
# 1. Lấy bộ decompile và ROM của bạn
git clone https://github.com/StanHash/fomt
cp /duong/dan/rom-cua-ban.gba fomt/baserom.gba

# 2. Toolchain: arm-none-eabi (Arm GNU 13.2) + agbcc branch cp, cài vào fomt/tools/agbcc
#    Chi tiết từng lệnh ở docs/PATCH-NOTES.md mục 1

# 3. Xác nhận build khớp bản gốc trước khi patch
cd fomt && make compare        # phải ra: fomt.gba: OK

# 4. Patch và build lại
python3 ../scripts/patch_stardew.py .
make

# 5. Kiểm chứng: chỉ vài chục byte đổi, kích thước không đổi
python3 ../scripts/verify_patch.py baserom.gba fomt.gba

# Hoàn nguyên
git checkout -- .
```

## Patch hiện tại

| Hạng mục | FoMT gốc | Sau patch |
|---|---|---|
| Giá 15 nông sản | 60/80/60/250/30/... | 35/80/60/175/120/60/50/80/320/250/60/120/160/110/40 |
| Potato | 7 ngày | 6 |
| Cabbage | 14 ngày | 12 |
| Pumpkin | 14 ngày | 13 |
| Spinach | 5 ngày | 6 |
| Thể lực khởi đầu | 150 | 250 |

8 cây tái sinh giữ nguyên số ngày: hàm harvest đặt cứng cặp `(stage, counter)` theo bảng gốc, rút
ngắn ngày sẽ làm counter vượt bảng và cây biến mất sau khi hái.

Kết quả kiểm chứng của lần patch hiện tại: ROM cùng kích thước, **64 byte khác trong 3 vùng** —
2 byte immediate thể lực, bảng sinh trưởng `0xE8D14`, bảng giá `0xF0348`.

## Ghi công

- [StanHash/fomt](https://github.com/StanHash/fomt) — decompilation của FoMT
- [StanHash/FOMT-DOC](https://github.com/StanHash/FOMT-DOC) — tài liệu reverse-engineering
- [notyourav/agbcc](https://github.com/notyourav/agbcc) — compiler dùng để build

## Bản quyền

Script, tài liệu và dữ liệu trích trong repo này: MIT (xem `LICENSE`).

Harvest Moon / Story of Seasons là thương hiệu của Marvelous. Repo không phân phối ROM, không phân
phối mã nguồn decompile, và không kèm asset của game gốc. Bản ROM đã patch chỉ dùng cho mục đích cá
nhân trên bản ROM bạn tự dump — đừng chia sẻ file `.gba`.
