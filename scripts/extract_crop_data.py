#!/usr/bin/env python3
"""Trích toàn bộ dữ liệu cây trồng + thời tiết của FoMT (US) từ ROM.

Đọc trực tiếp các bảng mà repo decompile để dạng `.incbin`:

    0xE8CC4  0x40  gUnk_080E8CC4   xác suất mọc cỏ/đá/cành theo mùa + thời tiết
    0xE8D04  0x08  gUnk_080E8D04   bảng dùng khi bão/tuyết lớn
    0xE8D0C  0x08  gUnk_080E8D0C   bảng dùng khi tuyết
    0xE8D14  0x6E4 gUnk_080E8D14   [crop][ngay] -> giai đoạn sinh trưởng (21 cây x 21 mục x u32)
    0xE93F8  0x1D4 gUnk_080E93F8   [crop] -> struct 12 byte, +0A = id vật phẩm thu hoạch

Tên và giá được đọc từ chính repo decompile (data/item/*.def) để không phải gõ tay.

    python3 extract_crop_data.py ../rom/baserom.gba --json farm_data.json
"""

import argparse
import hashlib
import json
import os
import re
import struct
import sys

EXPECTED_SHA1 = "a2fc3574f0a65a4fcf7682fb274b9d7eebdef963"

WEATHER_OFF, WEATHER_LEN = 0xE8CC4, 0x40
STORM_OFF, STORM_LEN = 0xE8D04, 0x08
SNOW_OFF, SNOW_LEN = 0xE8D0C, 0x08
GROWTH_OFF, GROWTH_LEN = 0xE8D14, 0x6E4
CROPDEF_OFF, CROPDEF_LEN, CROPDEF_STRIDE = 0xE93F8, 0x1D4, 12

DAYS = 21
# từ FieldPlot::method_0800A4A4: sau thu hoạch, cây tái sinh được đặt (stage, counter)
REGROW = {0x02: (2, 4), 0x03: (3, 6), 0x05: (4, 6), 0x06: (4, 11),
          0x09: (4, 15), 0x0A: (3, 6), 0x0C: (2, 3), 0x0E: (4, 5)}
SEASON_OF = {0x00: "Spring", 0x05: "Summer", 0x0A: "Fall"}
FLOWER_OF = {0x0F: "Spring", 0x10: "Summer", 0x11: "Fall", 0x12: "Fall", 0x13: "Spring"}

DEF_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fomt", "data", "item")


def parse_def(name, pattern):
    path = os.path.join(DEF_DIR, name)
    rows = {}
    for line in open(path, encoding="utf-8", errors="replace"):
        m = re.match(pattern, line)
        if m:
            rows[m.group(1)] = [g.strip().strip('"') for g in m.groups()[1:] if g]
    return rows


def load_defs():
    # food: o( tag, is_drink, stamina, fatigue, icon, name, desc ) -> name là group thứ 3
    raw_food = parse_def("food.def",
                         r'/\* ([0-9A-F]{2}) \*/\s*o\(\s*([A-Z_0-9]+),\s*(\w+),\s*[-\d]+,\s*[-\d]+,\s*\d+,\s*("[^"]*")')
    food = {k: (v[0], v[2]) for k, v in raw_food.items()}
    # article: o( tag, icon, name ) -> name là group thứ 2
    raw_article = parse_def("article.def",
                            r'/\* ([0-9A-F]{2}) \*/\s*o\(\s*([A-Z_0-9]+),\s*\d+,\s*("[^"]*")')
    article = {k: (v[0], v[1]) for k, v in raw_article.items()}
    product = {}
    for line in open(os.path.join(DEF_DIR, "product.def"), encoding="utf-8", errors="replace"):
        m = re.match(r'/\* ([0-9A-F]{2}) \*/\s*o\(\s*([A-Z_0-9]+),\s*(\w+),\s*(\d+)\s*\)', line)
        if m:
            product[m.group(2)] = int(m.group(4))
    return food, article, product


def read(rom, off, length):
    if len(rom) < off + length:
        sys.exit(f"ROM quá ngắn: cần 0x{off + length:X}, file có 0x{len(rom):X}")
    return rom[off:off + length]


def dump_weather(rom):
    data = read(rom, WEATHER_OFF, WEATHER_LEN)
    out = []
    for s, season in enumerate(["Spring", "Summer", "Fall", "Winter"]):
        for sunny in (True, False):
            v = list(data[(s * 2 + (0 if sunny else 1)) * 8:][:8])
            out.append({
                "season": season,
                "weather": "sunny" if sunny else "rain_or_snow",
                "raw": v,
                "tilled_revert_pct": v[1],
                "tilled_stone_pct": v[2],
                "tilled_branch_pct": v[3],
                "empty_weed_pct": v[4],
                "empty_stone_pct": v[5],
                "empty_branch_pct": v[6],
                "seedling_death_pct": v[7],
                "unk_00": v[0],
            })
    return out


def dump_growth(rom):
    data = read(rom, GROWTH_OFF, GROWTH_LEN)
    rows = []
    for c in range(GROWTH_LEN // (DAYS * 4)):
        rows.append(list(struct.unpack_from(f"<{DAYS}I", data, c * DAYS * 4)))
    return rows


def dump_cropdefs(rom):
    data = read(rom, CROPDEF_OFF, CROPDEF_LEN)
    out = []
    for i in range(CROPDEF_LEN // CROPDEF_STRIDE):
        b = data[i * CROPDEF_STRIDE:(i + 1) * CROPDEF_STRIDE]
        out.append({"ptr": struct.unpack_from("<I", b, 0)[0], "fields": list(b[4:10]),
                    "item_id": struct.unpack_from("<H", b, 0x0A)[0]})
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("rom")
    ap.add_argument("--json")
    args = ap.parse_args()

    rom = open(args.rom, "rb").read()
    sha1 = hashlib.sha1(rom).hexdigest()
    print(f"ROM      : {os.path.basename(args.rom)}  ({len(rom)} bytes)")
    print(f"sha1     : {sha1}")
    print(f"khớp bản US decompile: {'YES' if sha1 == EXPECTED_SHA1 else 'NO'}\n")

    food, article, product = load_defs()
    growth = dump_growth(rom)
    cropdefs = dump_cropdefs(rom)

    crops = []
    for cid, row in enumerate(growth[:0x15]):
        mature = next((d for d, st in enumerate(row) if st == 5), None)
        rg = REGROW.get(cid)
        rg_days = None
        if rg:
            c = rg[1]
            rg_days = next((d for d in range(c + 1, DAYS) if row[d] == 5), None)
            rg_days = rg_days - c if rg_days else None
        if cid < 0x0F:
            tag, name = food.get(f"{cid:02X}", [None, f"0x{cid:02X}"])[0:2]
            kind, season = "crop", next((s for b, s in SEASON_OF.items() if cid >= b), None)
            season = ["Spring", "Summer", "Fall"][cid // 5] if cid < 0x0F else season
            price = product.get(tag or "", None)
        elif cid <= 0x13:
            tag, name = article.get(f"{cid - 0x0F:02X}", [None, f"0x{cid:02X}"])[0:2]
            kind, season, price = "flower", FLOWER_OF.get(cid), None
        else:
            tag, name, kind, season, price = None, "Grass", "grass", None, None
        crops.append({
            "id": f"0x{cid:02X}", "tag": tag, "name": name, "kind": kind,
            "season": season, "days_to_mature": mature, "regrow_days": rg_days,
            "sell_price": price, "stages": row, "harvest_item_id": cropdefs[cid]["item_id"],
        })

    print("== Cây trồng ==")
    print(f"{'id':<5}{'tên':<16}{'mùa':<8}{'ngày':>5}{'tái sinh':>9}{'giá':>6}  tiến trình giai đoạn")
    for c in crops:
        rg = f"{c['regrow_days']}d" if c["regrow_days"] else "—"
        print(f"{c['id']:<5}{c['name']:<16}{c['season'] or '—':<8}{c['days_to_mature']:>5}"
              f"{rg:>9}{str(c['sell_price'] or '—'):>6}  {''.join(str(s) if s else '.' for s in c['stages'])}")

    weather = dump_weather(rom)
    print("\n== Thời tiết / cỏ dại (%, mỗi mùa) ==")
    print(f"{'mùa':<8}{'thời tiết':<14}{'cỏ':>5}{'đá':>5}{'cành':>5}   {'đất cuốc->thường':>17}{'cây non chết':>14}")
    for w in weather:
        print(f"{w['season']:<8}{w['weather']:<14}{w['empty_weed_pct']:>5}{w['empty_stone_pct']:>5}"
              f"{w['empty_branch_pct']:>5}{w['tilled_revert_pct']:>17}{w['seedling_death_pct']:>14}")

    storm = list(read(rom, STORM_OFF, STORM_LEN))
    snow = list(read(rom, SNOW_OFF, SNOW_LEN))
    print(f"\nbão   (0xE8D04): {storm}  -> cây non chết {storm[7]}%")
    print(f"tuyết (0xE8D0C): {snow}")

    if args.json:
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump({"sha1": sha1, "crops": crops, "weather": weather,
                       "storm": storm, "snow": snow}, f, ensure_ascii=False, indent=2)
        print(f"\nđã ghi {args.json}")


if __name__ == "__main__":
    main()
