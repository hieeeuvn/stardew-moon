#!/usr/bin/env python3
"""Patch dữ liệu FoMT thành "Stardew mode".

Chỉ sửa DỮ LIỆU, không sửa kích thước code — vì fomt.lds xếp các object tuần tự,
code dài ra sẽ làm lệch mọi địa chỉ tuyệt đối mà asm đang tham chiếu.

Ba thay đổi:
  1. Giá bán nông sản  -> giá kiểu Stardew Valley (data/item/product.def)
  2. Số ngày sinh trưởng -> theo Stardew (bảng gUnk_080E8D14 trong ROM)
  3. Thể lực khởi đầu 150 -> 250 (farmer.cc, vẫn nằm trong imm8 của Thumb)

Dùng:  python3 patch_stardew.py research/fomt
"""

import os
import re
import struct
import sys

# id cây (food.def) -> (tên, ngày chín kiểu Stardew, giá bán kiểu Stardew)
STARDEW = {
    0x00: ("Turnip",       4,  35),   # parsnip
    0x01: ("Potato",       6,  80),
    0x04: ("Cabbage",     12, 175),   # cauliflower
    0x07: ("Onion",        7,  80),
    0x08: ("Pumpkin",     13, 320),
    0x0B: ("Carrot",       7, 120),
    0x0D: ("Spinach",      6, 110),   # kale
}

# 8 cây tái sinh giữ nguyên số ngày của FoMT: code harvest đặt cứng (stage, counter)
# theo bảng gốc, rút ngắn ngày sẽ làm counter vượt quá bảng và cây biến mất sau hái.

GROWTH_OFF, GROWTH_LEN = 0xE8D14, 0x6E4
DAYS = 21
CROP_ROWS = 0x0F  # chỉ sửa 15 cây nông sản, giữ nguyên 5 hoa + ô cỏ

PRICE_PATCH = {
    "TURNIP": 35, "POTATO": 80, "CUCUMBER": 60, "CABBAGE": 175, "STRAWBERRY": 120,
    "TOMATO": 60, "CORN": 50, "ONION": 80, "PUMPKIN": 320, "PINEAPPLE": 250,
    "EGGPLANT": 60, "CARROT": 120, "SWEET_POTATO": 160, "SPINACH": 110, "GREEN_PEPPER": 40,
}


def ramp(days):
    """Dãy giai đoạn: index `days` là 5 (chín) — đúng quy ước của bảng gốc.

    Các bậc trước bị chặn ở 4 để giai đoạn 5 xuất hiện đúng một lần, tại `days`.
    """
    out = []
    for i in range(days + 1):
        stage = round(1 + i * 4 / days)
        out.append(max(1, min(4, stage)))
    out[-1] = 5
    return out + [0] * (DAYS - len(out))


def patch_prices(root):
    path = os.path.join(root, "data", "item", "product.def")
    src = open(path, encoding="utf-8", errors="replace").read()
    changed = 0
    for tag, price in PRICE_PATCH.items():
        pattern = re.compile(r"(o\(\s*" + tag + r",\s*[A-Z]+,\s*)(\d+)(\s*\))")
        src, n = pattern.subn(lambda m: f"{m.group(1)}{price}{m.group(3)}", src)
        changed += n
    open(path, "w", encoding="utf-8").write(src)
    return changed


def patch_growth(root):
    """Đọc bảng gốc từ baserom.gba, sinh lại phần 15 cây, ghi thành .byte."""
    rom_path = os.path.join(root, "baserom.gba")
    rom = open(rom_path, "rb").read()
    table = bytearray(rom[GROWTH_OFF:GROWTH_OFF + GROWTH_LEN])

    for cid, (_, days, _price) in STARDEW.items():
        new = ramp(days)
        base = cid * DAYS * 4
        for i, stage in enumerate(new):
            struct.pack_into("<I", table, base + i * 4, stage)

    lines = ["\t.global gUnk_080E8D14", "gUnk_080E8D14:"]
    for i in range(0, len(table), 16):
        chunk = table[i:i + 16]
        lines.append("\t.byte " + ", ".join(f"0x{b:02X}" for b in chunk))
    blob = "\n".join(lines) + "\n"

    asm_path = os.path.join(root, "asm", "data", "data_080E8610.s")
    src = open(asm_path, encoding="utf-8", errors="replace").read()
    original = '\t.global gUnk_080E8D14\ngUnk_080E8D14:\n\t.incbin "baserom.gba", 0xE8D14, 0x6E4\n'
    if original not in src:
        sys.exit("Không tìm thấy incbin gUnk_080E8D14 — repo đã bị sửa trước đó?")
    src = src.replace(original, blob)
    open(asm_path, "w", encoding="utf-8").write(src)
    return len(table)


def patch_energy(root):
    """150 -> 250 cho cả thể lực khởi đầu và công thức thể lực tối đa."""
    path = os.path.join(root, "src", "farmer.cc")
    src = open(path, encoding="utf-8", errors="replace").read()
    before = src
    src = src.replace("stamina(150),", "stamina(250),")
    src = re.sub(r"(self\.num_power_berries \* 10 \+ )150", r"\g<1>250", src)
    open(path, "w", encoding="utf-8").write(src)
    return src != before


def main():
    root = sys.argv[1] if len(sys.argv) > 1 else "research/fomt"
    print(f"patch vào {root}")

    n = patch_prices(root)
    print(f"  giá bán      : {n} mục đã đổi")

    size = patch_growth(root)
    print(f"  bảng sinh trưởng: {size} byte ({len(STARDEW)} cây đổi số ngày)")

    ok = patch_energy(root)
    print(f"  thể lực      : {'150 -> 250' if ok else 'KHÔNG đổi được (kiểm tra lại)'}")


if __name__ == "__main__":
    main()
