# Patch FoMT theo hướng Stardew Valley

ROM gốc: `Harvest Moon - Friends of Mineral Town (U) [!].gba`, sha1 `a2fc3574…def963` (bản US mà
repo StanHash/fomt nhắm tới). ROM do người dùng cung cấp, chỉ dùng cục bộ, **không** commit, **không**
phân phối. `rom/`, `*.gba`, `.toolchain/`, `.build/` đã nằm trong `.gitignore`.

---

## 1. Dựng toolchain (không cần root)

Container bật `no new privileges` nên `sudo`/`apt` không dùng được. Cách đã làm:

```bash
# 1. Arm GNU Toolchain (assembler/linker/objcopy) — giải nén vào workspace
curl -L -o .toolchain/arm.tar.xz \
  https://developer.arm.com/-/media/Files/downloads/gnu/13.2.rel1/binrel/arm-gnu-toolchain-13.2.rel1-x86_64-arm-none-eabi.tar.xz
tar xf .toolchain/arm.tar.xz -C .toolchain

# 2. agbcc (compiler C/C++ của repo) — build từ source bằng gcc host
git clone --depth 1 -b cp https://github.com/notyourav/agbcc .build/agbcc
cd .build/agbcc
make -C gcc old && mv gcc/old_agbcc .        # C compiler (kiểu cũ)
make -C gcc clean && make -C gcc && mv gcc/agbcc .
cd g++ && ./configure --target=thumb-elf --disable-werror --with-cpu=arm7tdmi \
  --with-no-thumb-interwork --disable-multilib --enable-languages=c++ \
  --host=i686-pc-linux --build=i686-pc-linux && make cc1plus && cd ..
mv g++/cc1plus agbcp
export PATH="$PWD/../../.toolchain/arm-gnu-toolchain-13.2.Rel1-x86_64-arm-none-eabi/bin:$PATH"
make -C libgcc && make -C libc               # runtime, cần arm-none-eabi-as trong PATH
```

Cài vào repo: `tools/agbcc/bin/{agbcc,old_agbcc,agbcp}`, `tools/agbcc/{include,lib,include/…}`,
`libgcc.a` + `libc.a` vào `tools/agbcc/lib/`.

Lưu ý: hai frontend ARM (`agbcp_arm`, `agbcc_arm`) **không cần** cho build này nên bỏ qua —
`install.sh` của agbcc có nhắc tới chúng nhưng Makefile của fomt không dùng.

## 2. Build kiểm chứng

```bash
cp rom/*.gba research/fomt/baserom.gba
cd research/fomt
export PATH="$PWD/../../.toolchain/arm-gnu-toolchain-13.2.Rel1-x86_64-arm-none-eabi/bin:$PATH"
make -j2 compare
# → sha1sum -c fomt.sha1
# → fomt.gba: OK
```

**Trước khi patch, build khớp tuyệt đối với ROM gốc** — tức mọi thay đổi sau đó đều đo được.

---

## 3. Ràng buộc quan trọng: không được để code dài ra

`fomt.lds` xếp các object `.text` **tuần tự**, không neo địa chỉ từng object. Assembly chiếm ~98%
game và gọi hàm bằng địa chỉ tuyệt đối (`bl 0x0800xxxx`). Nếu một object dài thêm vài byte, mọi
object sau nó dịch lên và toàn bộ ROM hỏng.

Vì vậy patch hiện tại **chỉ sửa dữ liệu và giá trị immediate cùng kích thước lệnh**:

- bảng giá (`product.def` → `gProductInfo`)
- bảng sinh trưởng (`gUnk_080E8D14`, đổi `.incbin` thành `.byte` nhưng **giữ đúng 0x6E4 byte**)
- thể lực `150 → 250` (vẫn vừa `movs Rd, #imm8` của Thumb nên lệnh không đổi kích thước)

## 4. Nội dung patch (`patch_stardew.py`)

| Hạng mục | Trước (FoMT) | Sau (Stardew) |
|---|---|---|
| Giá bán 15 nông sản | 60/80/60/250/30/60/100/80/250/500/80/120/120/40/80 | 35/80/60/175/120/60/50/80/320/250/60/120/160/110/40 |
| Ngày chín — Turnip | 4 | 4 |
| Ngày chín — Potato | 7 | 6 |
| Ngày chín — Cabbage | 14 | 12 |
| Ngày chín — Onion | 7 | 7 |
| Ngày chín — Pumpkin | 14 | 13 |
| Ngày chín — Carrot | 7 | 7 |
| Ngày chín — Spinach | 5 | 6 |
| Thể lực khởi đầu | 150 | 250 |

8 cây tái sinh (cucumber, strawberry, tomato, corn, pineapple, eggplant, sweet potato, green pepper)
**giữ nguyên số ngày**: hàm harvest đặt cứng cặp `(stage, counter)` theo bảng gốc; rút ngắn ngày sẽ
làm counter vượt quá bảng và cây biến mất ngay sau khi hái.

## 5. Kiểm chứng

Build sau patch: cùng kích thước 8.388.608 byte, **64 byte khác** trong đúng 3 vùng:

| Vùng | Ý nghĩa |
|---|---|
| `0x00E438`, `0x00E52A` | 2 byte immediate của thể lực trong code |
| `0x0E8D18–0x0E9170` | bảng sinh trưởng `gUnk_080E8D14` |
| `0x0F0348–0x0F0380` | bảng giá `gProductInfo` |

Chạy lại `extract_crop_data.py` trên ROM đã patch cho ra đúng bảng mới (4/6/12/7/13/7/6 ngày,
giá 35…320) → chứng minh patch có hiệu lực thật trong ROM.

## 6. Những thứ **không** làm được bằng cách này

Sprinkler, kỹ năng nghề có XP, hầm mỏ nhiều tầng có quái, crafting, greenhouse, lưới túi đồ nhiều
trang — tất cả nằm trong phần asm chưa dịch ngược hoặc cần **thêm code** (thêm object, thêm
sprite, thêm mục shop), mà thêm code là thứ làm vỡ layout ở mục 3.

Muốn đi xa hơn phải một trong hai:

1. **Dịch ngược thêm asm** của các hàm liên quan (dùng FOMT Studio / mary + IDA) rồi mới sửa —
   mỗi hàm là một dự án nhỏ, và vẫn bị chặn bởi giới hạn phần cứng GBA.
2. **Viết engine mới** (PC/browser) lấy dữ liệu FoMT làm nền — đây là con đường duy nhất để có
   đầy đủ hệ thống Stardew.

## 7. Rebuild / hoàn nguyên

```bash
cd research/fomt
git checkout -- .                      # bỏ mọi patch
cp ../../rom/*.gba baserom.gba
make -j2 compare                       # → fomt.gba: OK (bản gốc)
```

ROM đã patch nằm ở `research/fomt/fomt.gba` (sha1 `83d5dde…` khi patch hiện tại).
