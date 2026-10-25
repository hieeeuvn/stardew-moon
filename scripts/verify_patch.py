#!/usr/bin/env python3
"""So sánh ROM gốc với ROM đã patch để chắc chắn patch không làm hỏng layout.

Một patch an toàn phải:
  - giữ nguyên kích thước file
  - chỉ đổi byte trong vài vùng nhỏ (bảng dữ liệu / immediate), không dịch địa chỉ

Dùng:  python3 verify_patch.py baserom.gba fomt.gba
"""

import sys

KNOWN_ZONES = [
    (0x00E000, 0x00FFFF, "code: immediate (thể lực)"),
    (0x0E8CC4, 0x0E93F8, "bảng thời tiết + bảng sinh trưởng"),
    (0x0F0300, 0x0F0400, "bảng giá sản phẩm"),
]


def ranges(offsets):
    out = []
    if not offsets:
        return out
    start = prev = offsets[0]
    for i in offsets[1:]:
        if i == prev + 1:
            prev = i
        else:
            out.append((start, prev))
            start = prev = i
    out.append((start, prev))
    return out


def zone_of(off):
    for lo, hi, label in KNOWN_ZONES:
        if lo <= off <= hi:
            return label
    return "NGOÀI VÙNG ĐÃ BIẾT"


def main():
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    a = open(sys.argv[1], "rb").read()
    b = open(sys.argv[2], "rb").read()

    print(f"gốc   : {sys.argv[1]}  {len(a)} byte")
    print(f"patch : {sys.argv[2]}  {len(b)} byte")

    if len(a) != len(b):
        print("\nLỖI: kích thước khác nhau — code đã dài ra, layout ROM sẽ hỏng.")
        sys.exit(1)

    diffs = [i for i in range(len(a)) if a[i] != b[i]]
    if not diffs:
        print("\nHai file giống hệt — chưa patch gì.")
        return

    print(f"\n{len(diffs)} byte khác, {len(ranges(diffs))} vùng:")

    outside = 0
    seen = {}
    for s, e in ranges(diffs):
        zone = zone_of(s)
        if zone.startswith("NGOÀI"):
            outside += 1
            print(f"  0x{s:06X}-0x{e:06X}  ({e - s + 1} byte)  <-- {zone}")
        else:
            seen[zone] = seen.get(zone, 0) + (e - s + 1)

    for zone, n in seen.items():
        print(f"  {zone}: {n} byte")

    print()
    if outside:
        print(f"CẢNH BÁO: {outside} vùng đổi nằm ngoài khu vực mong đợi — kiểm tra lại patch.")
        sys.exit(2)
    print("OK: mọi thay đổi nằm trong vùng dữ liệu đã biết, địa chỉ không bị dịch.")


if __name__ == "__main__":
    main()
