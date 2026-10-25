# Ghi chú: đọc source decompile Harvest Moon – Friends of Mineral Town

Nguồn: `research/fomt` (StanHash/fomt) + `research/FOMT-DOC` (tài liệu reverse-engineering).
Mục đích: hiểu engine gốc để rút ra dữ liệu/cơ chế dùng cho một bản game kiểu Stardew Valley.

> Lưu ý pháp lý: source decompile là tác phẩm phái sinh từ game thương mại của Marvelous.
> Repo **không chứa ROM**; build cần `baserom.gba` do người dùng tự dump. Không phân phối bản build.

---

## 1. Quy mô repo

| Thành phần | Số lượng |
|---|---|
| Source C++ đã decompile (`src/*.cc`) | 40 file, 9.697 dòng |
| Header (`include/*.hh`) | 39 file, ~2.200 dòng (+ một số header hệ thống) |
| Assembly còn lại (`asm/*.s`) | 48 file, **434.464 dòng** |
| Dữ liệu nhúng ROM (`.incbin`) | phần lớn bảng số liệu vẫn là byte thô từ ROM — **riêng bảng cây trồng/thời tiết đã trích ra được** (mục 4.0) |

Nghĩa là: **chỉ ~2% game được dịch ngược thành C++ dễ đọc**; phần lớn vẫn là asm.
Các class đã có tên rõ ràng: `Farm`, `FieldPlot`, `Farmer`, `Rucksack`, `ShippingBin`,
`ToolChest`, `Npc`, `Bachelorette`, `Animal`, `Cow`, `Sheep`, `Chicken`, `Barn`, `Coop`,
`ScriptEngine`, `HarvestSprite`, `Furniture`.

Build: devkitARM (`arm-none-eabi`) + [notyourav/agbcc] (bản có `agbcp` cho C++),
`make compare` để kiểm tra sha1 ROM khớp `a2fc3574f0a65a4fcf7682fb274b9d7eebdef963`.

---

## 2. Kiến trúc engine (C++ "trần" trên GBA ARM7TDMI)

Game viết bằng C++ với runtime tự chế (`tools/libagbc++`: có `new`, `typeinfo`,
`exception`, `auto_ptr`…), biên dịch bằng `agbcp` với `-fno-exceptions -fno-rtti -fvtable-thunks`.

Quy ước ABI đã xác định (từ `FOMT-DOC/C++.txt`):

- **Constructor**: nhận con trỏ vùng nhớ đích là tham số đầu, trả lại chính con trỏ đó.
- **Destructor**: 2 tham số; bit 1 của tham số cờ = "object cấp phát động, phải free".
- **Method**: `this` là tham số ẩn đầu tiên; nếu trả về struct thì con trỏ vùng trả về chen lên trước `this`.
- **Vtable**: `+00` = offset để từ con trỏ lớp cha lấy được con trỏ object đầy đủ (đa kế thừa),
  `+04` = 0 (RTTI để trống), `+08…` = các virtual method.
- Lớp con kế thừa lớp đã có vtable thì **dùng lại** vtable của lớp cha, không thêm con trỏ mới.
- Code dùng nhiều `std::auto_ptr` (gây ra lượng lớn dead code).
- `init_array` rỗng và code chạy nó trong crt0 bị hỏng.

### Cây entity

```
AEntity (virtual, ~10 vfunc: GetBox/vfunc_10..vfunc_30, giữ GameObject*, location_map, x_q16/y_q16)
 ├── Entity
 │    ├── EntityActor ── Actor ── Npc ── Bachelorette (love, rival events)
 │    │                              └── Farmer (stamina, fatigue, rucksack, tools)
 │    └── NpcEntity (lịch trình, 763 dòng — class lớn nhất về AI)
 └── ... Animal ── BarnAnimal ── Cow / Sheep ; Coop ── Chicken ; Horse ; Dog ; Pet
```

Vị trí dùng fixed-point Q16 (`x_q16`, `y_q16`), map id 16-bit. `ActorLocation` =
`{map(10 bit), x(16), y(16), facing(8)}`.

`Farm` gộp toàn bộ nông trại trong một object: `name`, `horse`, `ShippingBin`,
`FarmHouse`, `Coop`, `Barn`, `Field<43,25>`.
→ **Lưới nông trại 43×25 = 1075 ô**, khớp với ghi chú "array of 1075 objects" trong GameData.

---

## 3. Vòng lặp ngày và logic đất trồng (phần giá trị nhất)

`FieldPlot` chỉ chiếm 4 byte, là bitfield:

| Bit | Ý nghĩa |
|---|---|
| 0–1 | Trạng thái đất: `0` đất thường, `1` đã cuốc (khô), `2` đã tưới, `3` trạng thái sau đổi mùa |
| 2–7 | ID cây/vật thể (6 bit — 0x00…0x3F) |
| 8–11 | Giai đoạn sinh trưởng (0 = trống, 1..7 = các bước, 8 = vật thể như cỏ/đá) |
| 12–16 | Bộ đếm ngày sinh trưởng |
| 17–19 | Chỉ số render (suy ra từ trạng thái) |

### Thuật toán `FieldPlot::DayUpdate(weather, date)`

1. **Chết theo mùa**: nếu ô có cây mà cây không thuộc mùa hiện tại → giai đoạn về 0.
   - Mùa Xuân: crop id `0x00–0x04, 0x0F, 0x13`
   - Mùa Hè: `0x05–0x09, 0x10`
   - Mùa Thu: `0x0A–0x0E, 0x11, 0x12`
   - `0x14` = cây đặc biệt tái sinh (giữ nguyên, reset bộ đếm khi thu hoạch)
   - `0x15+` = vật thể (cỏ dại, đá, cành…), không tính là cây trồng
2. **Sinh trưởng chỉ khi ô đang được tưới** (`state == 2`): bộ đếm ngày +1, rồi tra
   `gUnk_080E8D14[crop_id][counter]` để lấy giai đoạn mới. Bảng có **21 mục/cây**
   → tối đa 21 ngày được theo dõi cho mỗi cây.
3. **Cây tái sinh** (`0x14`): nếu không phải mùa Đông và chưa chín hẳn, counter vẫn tăng,
   và giai đoạn 7 được map về 1 để cây quay vòng ra quả tiếp.
4. **Thời tiết**:
   - Nắng (`weather == 0`): ô đã tưới `2 → 1` (khô lại). Tức mỗi ngày phải tưới lại.
   - Mưa/tuyết: ô khô `1 → 2` — **mưa tưới hộ toàn bộ**, không tốn công.
   - Bão/tuyết lớn (`weather == 3/4`): mỗi ngày **sinh thêm 2 vật thể ngẫu nhiên** trên nông trại
     (id `0x1F` hoặc `0x23`), đồng thời có xác suất phá cây con đang ở giai đoạn 1.
5. **Cỏ dại/đá mọc tự nhiên**: trên ô trống/đất chưa cuốc, mỗi ngày roll xác suất theo bảng
   `gUnk_080E8CC4[season][is_sunny]` (8 byte/mục) để mọc cỏ (`0x15`), đá (`0x16`) hoặc cành (`0x17`).
   Riêng chuyển sang Xuân còn roll thêm 10% mọc cỏ cho mỗi ô.
6. **Đổi mùa** (`method_0800AB08`): cây trái mùa bị reset; cây non của mùa mới bị xoá;
   cây đã lớn của mùa cũ về giai đoạn 6 (héo) rồi chết; cây `0x14` được giữ và reset counter.

Bảng xác suất và bảng ngày-sinh-trưởng vốn là `.incbin` từ ROM, nhưng **đã trích được đầy đủ**
bằng [extract_crop_data.py](extract_crop_data.py) với ROM sha1 khớp `a2fc3574…def963`.
Kết quả lưu ở [farm_data.json](farm_data.json). Xem mục 4.0.

---

## 4. Dữ liệu cân bằng đọc được trực tiếp

### 4.0 Cây trồng — số liệu thật trích từ ROM

Quan hệ id: **id cây = id trong `food.def`** (không phải `product.def`), hoa = id trong `article.def`.
`gUnk_080E93F8` có stride **12 byte**: `ptr(4) + 6 u8 + u16` tại `+0A` = id vật phẩm thu hoạch.

| id | Cây | Mùa | Ngày chín | Tái sinh | Giá bán |
|---|---|---|---|---|---|
| 0x00 | Turnip | Xuân | 4 | — | 60 |
| 0x01 | Potato | Xuân | 7 | — | 80 |
| 0x02 | Cucumber | Xuân | 9 | 5 ngày | 60 |
| 0x03 | Strawberry | Xuân | 8 | 2 ngày | 30 |
| 0x04 | Cabbage | Xuân | 14 | — | 250 |
| 0x05 | Tomato | Hè | 9 | 3 ngày | 60 |
| 0x06 | Corn | Hè | 14 | 3 ngày | 100 |
| 0x07 | Onion | Hè | 7 | — | 80 |
| 0x08 | Pumpkin | Hè | 14 | — | 250 |
| 0x09 | Pineapple | Hè | 20 | 5 ngày | 500 |
| 0x0A | Eggplant | Thu | 9 | 3 ngày | 80 |
| 0x0B | Carrot | Thu | 7 | — | 120 |
| 0x0C | Sweet Potato | Thu | 5 | 2 ngày | 120 |
| 0x0D | Spinach | Thu | 5 | — | 80 |
| 0x0E | Green Pepper | Thu | 7 | 2 ngày | 40 |
| 0x0F | Moon Drop Grass | Xuân | 6 | — | — |
| 0x10 | Pink Cat Grass | Hè | 6 | — | — |
| 0x11 | Blue Magic Grass | Thu | 10 | — | — |
| 0x12 | Red Magic Grass | Thu | 10 | — | — |
| 0x13 | Toy Flower | Xuân | 12 | — | — |
| 0x14 | Grass (cỏ cho gia súc) | mọi mùa trừ Đông | 11 | cắt xong quay lại stage 1 | — |

Ghi chú: 0x14 là ô cỏ — `DayUpdate` đặc cách nó (`stage 7 → 1`, chỉ khi `season != 3`),
đúng với việc cỏ tái mọc và chết mùa Đông. Đây là "cây" duy nhất tái sinh vô hạn.

Thời tiết (`gUnk_080E8CC4`, 8 byte/mục):

| Mùa | Thời tiết | Cỏ dại | Đá | Cành | Đất cuốc → thường | Cây non chết |
|---|---|---|---|---|---|---|
| Xuân | nắng | 2% | 0 | 0 | 2% | 0 |
| Xuân | mưa | 3% | 0 | 0 | 2% | 0 |
| Hè | nắng | 3% | 0 | 0 | 1% | 0 |
| Hè | mưa | 5% | 0 | 0 | 2% | 0 |
| Thu | nắng | 2% | 0 | 0 | 2% | 0 |
| Thu | mưa | 5% | 0 | 0 | 2% | 0 |
| Đông | mọi | 0 | 0 | 0 | 0 | 0 |

- Bão (`0xE8D04`): `[25, 4, 3, 2, 10, 3, 2, 10]` → cỏ 10%, đá 3%, cành 2%, **cây non chết 10%**.
- Tuyết (`0xE8D0C`): `[25, 0, 0, 0, 0, 3, 2, 0]` → không sinh cỏ, chỉ đá 3% / cành 2%.
- Ngoài ra bão/tuyết còn thả thêm 2 vật thể ngẫu nhiên (id `0x1F`/`0x23`) mỗi ngày.

### 4.1 Nông sản và giá bán (bảng `product.def`, 103 mục)

| ID | Tên | Giá | | ID | Tên | Giá |
|---|---|---|---|---|---|---|
| 00 | Turnip | 60 | | 0A | Eggplant | 80 |
| 01 | Potato | 80 | | 0B | Carrot | 120 |
| 02 | Cucumber | 60 | | 0C | Sweet Potato | 120 |
| 03 | Cabbage | 250 | | 0D | Green Pepper | 40 |
| 04 | Strawberry | 30 | | 0E | Spinach | 80 |
| 05 | Tomato | 60 | | 08 | Pineapple | **500** |
| 06 | Corn | 100 | | 09 | Pumpkin | 250 |
| 07 | Onion | 80 | | | | |

Sản phẩm động vật (thang 6 bậc S→X):

| Sản phẩm | S | M | L | G | P | X |
|---|---|---|---|---|---|---|
| Trứng | 50 | 60 | 80 | 100 | 180 | 350 |
| Mayonnaise | 100 | 150 | 200 | 300 | 450 | 800 |
| Sữa | 100 | 150 | 200 | 300 | 500 | 800 |
| Phô mai | 300 | 400 | 500 | 600 | 750 | — |

→ Tỉ lệ giá trị giữa bậc thấp nhất và cao nhất ~8×, tạo động lực rõ cho việc chăm sóc động vật.
Cùng công thức bậc S→X còn áp cho Len/Sợi (Wool/Yarn).

### 4.2 Thể lực và mệt mỏi

| Thông số | Giá trị |
|---|---|
| Stamina khởi đầu | **150** |
| Stamina tối đa | `150 + 10 × số Power Berry` (mỗi berry +10) |
| Fatigue hiển thị | `fatigue / 2` (nửa giá trị thật) |
| Ngưỡng gục | `fatigue >= 200` |
| Số ô túi đồ | **8 item + 8 tool**, 3 cấp nâng cấp (`LEVEL_0..2`) |
| Tiền khởi đầu | **500 G** (theo GameData) |

Thức ăn có 2 chỉ số: `stamina` (hồi) và `fatigue` (âm = giảm mệt). Ví dụ: Turnip 3/-1,
Strawberry 5/-2, Pineapple 5/-2, trứng X 6/-4, sữa là `is_drink`.

### 4.3 Dụng cụ

Mỗi dụng cụ có **6 bậc** (`ToolLevel LEVEL_0..5`) tương ứng Iron → Copper → Silver → Gold →
Mystrile → (Cursed/Blessed) → Mythic. Bảng `tool.def` có 83 mục, gồm 8 loại:
Sickle, Hoe, Axe, Hammer, Watering Can, Fishing Rod, Brush(?), Cow/Sheep tools.

### 4.4 Quan hệ

| Đối tượng | Giá trị |
|---|---|
| `Npc::friendship` | 8 bit, khởi đầu **50**, kẹp `0..255`; có cờ `spoken_today`, `gifted_today`, `met` |
| `Bachelorette::love` | 16 bit, kẹp `0..65535`; đếm `player_events` / `rival_events` (3 bit) + số ngày từ event gần nhất |
| `Animal::affection` | kẹp `0..250` |

### 4.5 Thời gian

Đồng hồ là bitfield: năm 8 bit, mùa 2 bit, ngày 5 bit, giờ 5 bit, phút 6 bit.
**1 phút game = 25 frame** (~0,42 s ở 60 fps). Lịch NPC lưu "số phút tính từ 6:00 sáng".

---

## 5. Event script engine

- VM dạng stack: `ScriptStack` tối đa **100** phần tử, `vmmem` **100** word.
- Mỗi script có: `code`, `pc`, `string_offset_table`, `string_pool`, `jump_table`.
- Opcode theo ghi chú của `mary`: `push/push8/16/32/pushm/pop/popm/dup`, `add/sub/mul/div/mod`,
  `equ/addequ/subequ/mulequ/divequ`, `and/or/not/neg/inc/dec`, `cmp/blt/ble/beq/bne`, `nop`.
- **1328 script** trong FoMT, bảng con trỏ ở offset `0x0F89D4`.
- `mary` decompile được 97,59% script và recompile khớp byte-exact.

Đây là chỗ chứa hội thoại, cutscene, event tình cảm, lễ hội — tức phần "nội dung" chứ không phải
phần "hệ thống".

---

## 6. Đối chiếu với Stardew Valley: FoMT có gì / thiếu gì

| Cơ chế Stardew | FoMT gốc | Ghi chú |
|---|---|---|
| Ngày 6:00–2:00, ngủ để lưu | ✅ | có, 1 phút = 25 frame |
| Thanh năng lượng + mệt mỏi + ngất | ✅ | 150 stamina, fatigue 200 → gục |
| Cuốc → tưới → gieo → thu hoạch | ✅ | đúng vòng lặp 4 bước |
| Cây theo mùa, chết khi đổi mùa | ✅ | bảng mùa rõ ràng trong code |
| Mưa tưới hộ | ✅ | |
| Bão phá cây / sinh đá cành | ✅ | 2 vật thể/ngày khi bão |
| Túi đồ + nâng cấp túi | ✅ | 8+8 ô, 3 cấp |
| Nâng cấp dụng cụ nhiều bậc | ✅ | 6 bậc |
| Shipping bin bán hàng loạt | ✅ | có thống kê từng món đã bán |
| Quan hệ NPC + quà + event | ✅ | friendship 0–255, love 0–65535 |
| Động vật có affection, sản phẩm phẩm cấp | ✅ | 0–250, thang S→X |
| **Sprinkler / tưới tự động** | ❌ | phải tưới tay từng ô mỗi ngày |
| **Hầm mỏ nhiều tầng + combat** | ❌ | FoMT chỉ có mỏ đào đá, không có quái/theo tầng kiểu Stardew |
| **Skill nghề (Farming/Mining/Foraging/Fishing/Combat) + level 1–10** | ❌ | FoMT chỉ có cấp dụng cụ, không có XP nghề |
| **Năng lượng theo từng hành động có số cụ thể** | ⚠️ | có hàm trừ stamina nhưng bảng chi phí nằm trong asm |
| **Greenhouse** | ❌ (FoMT) | |
| **Crafting / chế tạo đồ** | ❌ | FoMT dùng máy chế biến mua sẵn |
| **Nhiều loại cây quanh năm + trellis** | ⚠️ | 13 cây trồng chính, không có giàn |
| **Inventory dạng lưới nhiều trang** | ❌ | 8+8 ô cố định |

Kết luận: FoMT mạnh ở **vòng lặp nông trại cốt lõi và quan hệ NPC**, yếu ở **chiều sâu hệ thống**
(sprinkler, skill, mine, crafting) — đúng những thứ làm nên "chất Stardew".

---

## 7. Nếu muốn port/reimplement

1. Lấy **cấu trúc** từ `field.cc` (đã rõ 100%) và **giá trị** từ `product.def` / `food.def` / `tool.def`.
2. Con số còn thiếu (số ngày sinh trưởng mỗi cây, xác suất thời tiết) chỉ lấy được nếu có ROM;
   nếu không, dùng bảng đã biết của FoMT từ guide cộng đồng (turnip 4 ngày, potato 7, cabbage 14,
   pineapple 20 — chu kỳ 4/7/14/20 ngày).
   → **Đã giải quyết**: dùng ROM sha1 `a2fc3574…def963` + [extract_crop_data.py](extract_crop_data.py),
   kết quả ở [farm_data.json](farm_data.json).
3. Toàn bộ event/hội thoại có thể decompile bằng `mary` nếu có ROM — không cần thiết cho một bản clone
   vì nội dung phải viết mới để tránh bản quyền.

[notyourav/agbcc]: https://github.com/notyourav/agbcc
