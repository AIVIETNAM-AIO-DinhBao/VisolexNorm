# PLAN.md

# Kế hoạch triển khai 14 ngày

Kế hoạch này bám theo kiến trúc dữ liệu cố định:

```text
Gold      = ViLexNorm
Unlabeled = ViSoLex corpus canonical (68.411 câu sau preprocessing/deduplicate)
Model     = BARTpho-syllable
Training  = Kaggle GPU
Inference/Web = Local
```

ViSoLex weak labels được tạo theo pipeline chính: **Model A sinh candidate → LLM review theo KEEP / EDIT / REJECT → validation/filtering**. LLM không thay thế nguồn unlabeled data và không xuất hiện trong final web inference.

Mục tiêu là có baseline end-to-end sớm, sau đó dành phần lớn thời gian cho chất lượng weak labels, Model B và evaluation.

---

# Phase 1 — Chuẩn hóa dữ liệu
**Ngày 1–2**

## Kết quả phải đạt

Có 4 artifact ổn định:

```text
vilexnorm_train.jsonl
vilexnorm_dev.jsonl
vilexnorm_test.jsonl
visolex_unlabeled.jsonl
```

`visolex_unlabeled.jsonl` chứa 68.411 câu canonical và giữ `original_source`. Bốn nguồn còn
record sau preprocessing/deduplicate; ViHOS được ghi nhận quota 0:

```text
ViHSD
UIT-VSMEC
ViHOS
ViSpamReviews
UIT-ViSFD
```

## Các bước

### 1.1. Chuẩn bị ViLexNorm
- load đúng Train/Dev/Test;
- map về `input_text`, `target_text`;
- gắn ID và `label_source=human`;
- validate null/empty/duplicate;
- không thay đổi lexical noise.

### 1.2. Chuẩn bị ViSoLex
- lấy corpus unlabeled theo ViSoLex;
- thống nhất text field;
- gắn `dataset=ViSoLex`;
- giữ `original_source`;
- normalize whitespace;
- loại empty;
- deduplicate.

### 1.3. Chống leakage
- loại exact overlap của ViSoLex với ViLexNorm Dev/Test;
- ghi số sample bị loại;
- không dùng Test để tune rule.

### 1.4. Audit
- random sample từng nguồn;
- kiểm tra encoding;
- kiểm tra social-media noise còn nguyên;
- xuất thống kê số câu theo source.

## Exit criteria
- 4 JSONL load được;
- split ViLexNorm không trộn;
- ViSoLex có provenance rõ;
- preprocessing rerun cho cùng kết quả.

---

# Phase 2 — Baseline Model A
**Ngày 2–4**

## Kết quả phải đạt

Có checkpoint BARTpho-syllable fine-tuned bằng **ViLexNorm Train**, chọn bằng Dev và tải được về local.

## Các bước

### 2.1. Kaggle notebook skeleton
Notebook tự:
1. install dependency;
2. mount/load dataset;
3. load config;
4. load BARTpho-syllable;
5. tokenize;
6. train;
7. evaluate Dev;
8. save checkpoint.

### 2.2. Overfit smoke test
- lấy 50–200 samples;
- train ngắn;
- xác nhận loss giảm;
- generate output;
- test save/load checkpoint.

### 2.3. Full baseline run
- train ViLexNorm Train;
- validate trên Dev;
- chỉ thử thêm config nếu baseline có dấu hiệu bất thường.

### 2.4. Export
Lưu:
```text
model_a checkpoint
train config
dev predictions
dev metrics
```

### 2.5. Local checkpoint smoke test
- tải checkpoint;
- chạy vài câu local;
- xác nhận tokenizer/model path portable.

## Exit criteria
- Model A generate được output hợp lệ;
- checkpoint load lại được;
- có Dev results;
- có thể dùng checkpoint để batch-generate candidate normalization cho ViSoLex.

---

# Phase 3 — Model A candidates + LLM review cho ViSoLex
**Ngày 4–7**

## Kết quả phải đạt

Có hai artifact chính:

```text
visolex_model_a_candidates.jsonl
visolex_weak_labeled.jsonl
```

`visolex_weak_labeled.jsonl` phải được tạo từ ViSoLex theo pipeline:

```text
ViSoLex
  ↓
Model A candidate + confidence
  ↓
LLM Reviewer
  ↓
KEEP / EDIT / REJECT
  ↓
validation + filtering
  ↓
final weak labels
```

Mọi sample được đưa vào training Model B phải trace được về source ViSoLex, candidate của Model A và quyết định của LLM reviewer.

---

## 3.1. Chốt subset/pool ViSoLex cần xử lý

### Bước nhỏ

1. xác định budget số câu dự kiến dùng cho Experiment 2;
2. sinh candidate cho toàn bộ 68.411 câu canonical và chọn manifest review 20.000 bằng rule cố định;
3. ưu tiên stratify theo 5 `original_source` để không vô tình chỉ lấy một domain;
4. lưu danh sách ID được chọn;
5. không dùng ViLexNorm Test để chọn sample.

Có thể tạo candidate cho toàn bộ pool lớn trước rồi mới chọn sample đưa sang LLM review nếu GPU rẻ hơn API cost.

### Kết quả

Có manifest cố định, ví dụ:

```text
data/intermediate/visolex_review_manifest.jsonl
```

---

## 3.2. Sinh candidate bằng Model A

### Bước nhỏ

1. load Model A checkpoint;
2. batch tokenize ViSoLex trên Kaggle GPU;
3. chạy `generate()`;
4. lấy `candidate_text`;
5. tính/lưu `model_a_confidence`;
6. cache theo chunk;
7. hỗ trợ resume nếu session ngắt;
8. validate ID và số dòng;
9. export candidate artifact.

Record tối thiểu:

```text
id
original_source
input_text
candidate_text
model_a_confidence
candidate_checkpoint
```

### Kết quả

```text
data/intermediate/visolex_model_a_candidates.jsonl
```

Model A output lúc này **chưa phải target để train Model B**.

---

## 3.3. Thiết kế LLM Reviewer

### Bước nhỏ

1. định nghĩa schema `KEEP / EDIT / REJECT`;
2. viết prompt yêu cầu chỉ lexical normalization;
3. yêu cầu LLM xác định normalization của source **độc lập trước khi so với candidate** để giảm anchoring;
4. cấm paraphrase, grammar rewrite, thêm thông tin và làm văn phong trang trọng;
5. quy định `EDIT` chỉ được sửa tối thiểu;
6. `REJECT` khi câu mơ hồ hoặc không đủ chắc chắn;
7. dùng structured JSON output nếu API hỗ trợ;
8. version hóa prompt, ví dụ `lexical_norm_review_v1`.

Reviewer input:

```text
SOURCE
CANDIDATE
```

Reviewer output logic:

```text
KEEP   → candidate đúng
EDIT   → trả corrected_text
REJECT → không dùng sample
```

---

## 3.4. Pilot LLM review trước batch lớn

### Bước nhỏ

1. chọn khoảng 100–300 candidate có diversity tốt;
2. bao gồm confidence cao/trung bình/thấp;
3. bao gồm đủ 5 `original_source` nếu có thể;
4. gọi LLM reviewer;
5. audit thủ công;
6. kiểm tra các failure mode:
   - paraphrase;
   - over-normalization;
   - đổi nghĩa;
   - mất slang/sắc thái;
   - bỏ emoji/hashtag không cần thiết;
   - `KEEP` nhầm candidate sai;
7. sửa prompt/schema nếu cần;
8. chỉ freeze prompt sau pilot.

**Cổng duyệt hiện hành:** audit toàn bộ 240 mẫu và chỉ freeze khi tỷ lệ lỗi major không vượt
3,0%. Pilot v6 đạt 7/240 = 2,9167% theo quyết định chủ dự án ngày 2026-08-21. Hash freeze
bao gồm cả nội dung prompt và lexical policy versioned, để full review dùng đúng policy đã audit.

### Kết quả

Có prompt version đã freeze và một bảng audit pilot ngắn.

---

## 3.5. Batch LLM review

### Bước nhỏ

1. load candidate artifact/manifest;
2. gọi API theo chunk;
3. persistent cache từng result;
4. implement retry + backoff;
5. resume được sau interruption;
6. log API/parse errors;
7. validate structured response;
8. lưu `llm_model` + `prompt_version`;
9. không commit API key;
10. theo dõi số request/sample để kiểm soát cost.

Record review nên giữ:

```text
id
input_text
candidate_text
model_a_confidence
llm_decision
llm_corrected_text
llm_model
prompt_version
```

---

## 3.6. Xây final target và filtering

Rule:

```text
KEEP   → target_text = candidate_text
EDIT   → target_text = llm_corrected_text
REJECT → drop
```

Sau đó filter:

1. empty/invalid output;
2. parse artifacts;
3. length ratio bất thường;
4. edit ratio cực đoan;
5. Unicode lỗi;
6. overlap với ViLexNorm Dev/Test;
7. duplicate;
8. các record không nhất quán với decision.

Final record phải có:

```text
id
dataset=ViSoLex
original_source
input_text
candidate_text
model_a_confidence
llm_decision
llm_corrected_text
target_text
label_source=model_a+llm_review
accepted
```

---

## 3.7. Audit và statistics

### Bước nhỏ

1. random audit final accepted samples;
2. stratify theo `KEEP / EDIT / REJECT`;
3. stratify theo `original_source`;
4. kiểm tra sample confidence cao/trung bình/thấp;
5. tính:
   - Model A candidate count;
   - LLM reviewed count;
   - KEEP rate;
   - EDIT rate;
   - REJECT rate;
   - validation-drop rate;
   - final accepted count;
6. lưu một số case study Model A sai nhưng LLM sửa đúng để dùng trong report.

### Kết quả cuối Phase

```text
data/processed/visolex_weak_labeled.jsonl
outputs/weak_label_stats.json
```

## Exit criteria

- Model A candidates đã được lưu và reproduce được;
- prompt reviewer đã pilot và freeze;
- mọi training weak label đã qua LLM review;
- manifest 20.000 được reconcile thành 19.997 review hợp lệ và 3 approved provider exclusions;
- `KEEP/EDIT/REJECT` trace được;
- weak-label artifact đã validate + audit;
- có statistics before/after review/filtering;
- không dùng ViLexNorm Test để quyết định prompt, subset hay filtering.

**Kết quả đóng Phase 3 (2026-08-22):** 18.970 weak labels accepted, 0 schema error,
0 duplicate, 0 Dev/Test overlap. Bằng chứng và checksum nằm tại
`specs/003-weak-labeling-llm-review/phase3-exit-report.md`; binary/data artifacts lưu ngoài Git.

---

# Phase 4 — Train Model B
**Ngày 7–9**

## Kết quả phải đạt

Có checkpoint Model B được train từ:

```text
ViLexNorm Gold Train
+
Filtered ViSoLex Weak-Labeled Data
```

## Các bước

### 4.1. Build training mixture
- merge ViLexNorm gold + **LLM-reviewed ViSoLex weak labels**;
- giữ `label_source`, `llm_decision` và provenance cần thiết;
- quyết định gold:pseudo ratio;
- không để pseudo-data áp đảo gold một cách vô thức.

### 4.2. Smoke test
- train trên subset;
- xác nhận loss và batching đúng;
- kiểm tra data collator không phân biệt sai gold/pseudo.

### 4.3. Full Kaggle training
- chạy Model B;
- validate trên ViLexNorm Dev;
- save best checkpoint.

### 4.4. Nếu Model B kém rõ rệt trên Dev
Thử theo thứ tự:
1. kiểm tra lại `KEEP/EDIT/REJECT` samples và weak-label noise;
2. giảm weak-labeled sample;
3. tăng tỷ lệ gold;
4. siết filtering hoặc loại nhóm review/problematic source có chất lượng thấp;
5. nếu cần, chỉnh prompt reviewer bằng **Dev/manual audit**, sau đó tạo một version mới rõ ràng.

Không tune prompt/filter bằng Test và không mở rộng sang kiến trúc mới.

## Exit criteria
- Model B checkpoint load được;
- có Dev predictions/metrics;
- biết chính xác số gold/pseudo đã dùng.

---

# Phase 5 — Freeze experiment và Final Evaluation
**Ngày 9–11**

## Kết quả phải đạt

Có bảng kết quả cuối Model A vs Model B trên **cùng ViLexNorm Test**.

## Các bước

### 5.1. Freeze
Chốt:
- Model A checkpoint;
- Model B checkpoint;
- weak-label dataset;
- generation config;
- evaluation script.

Sau điểm này không tune dựa trên Test.

### 5.2. Test inference
Generate predictions cho toàn bộ ViLexNorm Test.

### 5.3. Metrics
Tính:
```text
ERR
Precision
Recall
F1
```

Ưu tiên cùng evaluation protocol của ViLexNorm nếu khả dụng.

### 5.4. Error analysis dataset
Tạo file chứa:
```text
input
gold
model_a_prediction
model_b_prediction
error category
```

### 5.5. Phân tích
Tập trung:
- correct normalization;
- missed normalization;
- over-normalization;
- wrong normalization;
- 1→n / n→1;
- trường hợp Model B cải thiện;
- trường hợp Model B bị weak-label noise làm xấu đi;
- case Model A candidate được LLM `EDIT` hoặc `REJECT`, đặc biệt các case cho thấy review có giá trị.

## Exit criteria
- bảng A/B hoàn chỉnh;
- có raw predictions;
- có error examples;
- có thể kết luận research question dù B tốt hơn hay không.

---

# Phase 6 — Local inference và Web App
**Ngày 11–12**

**Trạng thái hiện hành**: Đang thực hiện. Phase 10 đã cung cấp app selection, inventory
verification, lazy loader, CLI và rollback tests; còn real CPU smoke, Gradio và offline acceptance.

## Kết quả phải đạt

Best checkpoint chạy hoàn toàn local và có web app demo.

## Các bước

### 6.1. Chọn application checkpoint
Historical Phase 5 chọn Model B giữa A/B. Sau benchmark hậu kiểm Phase 9, Phase 10 tạo
`outputs/app/model_selection.json`: Model C là current app checkpoint và Model B là rollback.
Phase 6 dùng artifact này và verify inventory trước khi load.

### 6.2. Local inference module
Implement:
```text
load tokenizer
load checkpoint
normalize(text)
return prediction
```

Không phụ thuộc:
- Kaggle;
- ViSoLex;
- API LLM;
- training code.

### 6.3. Web UI
Gradio hoặc Streamlit:
- textbox input;
- Normalize button;
- output textbox;
- input validation.

### 6.4. Smoke test
Test:
- câu rỗng;
- câu chuẩn;
- teencode;
- viết tắt;
- câu dài vừa phải;
- nhiều lần inference liên tục.

## Exit criteria
- app khởi động bằng một command;
- local inference ổn định;
- app sử dụng checkpoint của project, không gọi LLM API.

---

# Phase 8 — Mở rộng LLM review và huấn luyện Model C
**Chạy song song Phase 6, sau Phase 5**

## Phạm vi

68.411 candidate của Model A đã có sẵn. Phase 3 đã review 20.000 ID và tạo 18.970 weak label
hợp lệ. Phase 8 chỉ review **48.411 ID còn lại**, hợp nhất KEEP/EDIT mới với artifact cũ rồi
huấn luyện Model C từ Model A. Không review lại ID cũ và không ghi đè Model B.

## Ràng buộc hậu kiểm

ViLexNorm Test đã được mở ở Phase 5. Vì vậy Model C chỉ được chọn bằng Dev trong Phase 8; không
load Test cũ hoặc dùng kết quả Test để đổi prompt/filter/siêu tham số. Phase 9 sau đó thực hiện
benchmark hậu kiểm có caveat và Phase 10 chọn Model C cho app với Model B rollback. Một holdout
độc lập vẫn cần thiết cho kết luận khoa học cuối cùng mạnh hơn.

## Các bước

1. Verify candidate/manifest Phase 3 và tạo hiệu tập 48.411 ID theo thứ tự candidate gốc.
2. Reuse prompt/policy/model identity đã freeze, review local theo batch 15 với cache/resume,
   round-robin key, cooldown và retry như Phase 3.
3. Reconcile toàn bộ ID còn lại; chỉ KEEP/EDIT hợp lệ được union với 18.970 weak label cũ.
4. Train Model C trên Kaggle từ checkpoint Model A. Mỗi epoch dùng 8.372 gold + 8.372 pseudo,
   ưu tiên pseudo chưa dùng đến khi toàn bộ pool mở rộng được cover.
5. Export checkpoint, provenance và Dev-only metrics/report trong namespace `model_c`.

## Exit criteria

- 68.411 candidate có trạng thái review cuối hoặc provider exclusion được phê duyệt.
- Pool mở rộng không trùng, không chứa REJECT và không overlap Dev/Test.
- Model C có full pseudo coverage, checkpoint load lại được và có Dev artifact.
- Phase 8 không tự thay đổi checkpoint app hoặc artifact Test đã freeze ở Phase 5; app chỉ đổi
  sau quyết định riêng ở Phase 10.

---

# Phase 7 — Reproducibility và đóng gói
**Ngày 12–14**

**Trạng thái hiện hành**: Hoàn thành. Release `v1.0.0` có manifest/checksum, Kaggle Dataset v1
cho Model C/B, clean-room offline acceptance, notebook cleanup và strict verification.

## Kết quả phải đạt

Một người khác có thể hiểu và chạy lại pipeline theo thứ tự.

## Các bước

### 7.1. Clean notebooks
Mỗi notebook phải:
- chạy từ đầu đến cuối;
- không phụ thuộc biến ẩn;
- không chứa secret;
- ghi rõ input/output artifact.

### 7.2. Freeze configs
Lưu config cuối:
```text
Model A
weak-label generation
Model B
Model C và review mở rộng (nếu Phase 8 hoàn thành)
evaluation
Phase 9 post-hoc benchmark
Phase 10 app selection và rollback
```

### 7.3. README execution flow
Mô tả đúng thứ tự:
```text
prepare data
→ train A on Kaggle
→ generate Model A candidates for ViSoLex
→ LLM review KEEP/EDIT/REJECT
→ build reviewed weak labels
→ train B on Kaggle
→ evaluate
→ review ViSoLex còn lại
→ train Model C trên Kaggle (Phase 8 Dev-only)
→ benchmark hậu kiểm A/B/C (Phase 9)
→ chọn Model C cho app, Model B rollback (Phase 10)
→ hoàn tất local app/Gradio (Phase 6)
→ đóng gói và release (Phase 7)
```

### 7.4. Submission artifacts
Kiểm tra:
- source code;
- notebooks;
- processed/training data theo yêu cầu;
- model weights;
- metrics;
- predictions;
- report assets;
- web app.

### 7.5. Final demo rehearsal
Demo tối thiểu:
1. giải thích noisy input;
2. nhập một câu;
3. normalize;
4. cho thấy output;
5. trình bày Model A vs B;
6. giải thích pipeline Model A candidate → LLM review → ViSoLex weak labels.

## Exit criteria
- clean run path rõ ràng;
- không thiếu checkpoint/config;
- demo không phụ thuộc mạng, trừ khi chủ động demo phần labeling API;
- final web inference chạy local.

---

# Roadmap hiện hành sau Phase 5

| Ngày | Mục tiêu chính |
|---|---|
| Đã hoàn thành | Phase 5 giữ frozen A/B Test evaluation; historical winner là Model B |
| Đã hoàn thành | Phase 8 review 48.411 candidate còn lại, build pool mở rộng và train Model C Dev-only |
| Đã hoàn thành | Common Dev selection chọn Model C cho app, Model B fallback; Test báo cáo A/B/C |
| Đã hoàn thành | Phase 6 real CPU smoke, Gradio và offline acceptance |
| Đã hoàn thành | Phase 7 reproducibility, packaging và release verification `v1.0.0` |

---

# Mốc kiểm soát quan trọng

## Cuối ngày 2
**Data milestone:** ViLexNorm và ViSoLex processed xong.

## Cuối ngày 4
**Baseline milestone:** Model A usable.

## Cuối ngày 7
**Augmentation milestone:** Model A candidates đã qua LLM review, ViSoLex weak labels và KEEP/EDIT/REJECT statistics đã freeze.

## Cuối ngày 9
**Training milestone:** Model B usable.

## Cuối ngày 11
**Research milestone:** Có kết quả A vs B và error analysis.

## Sau Phase 6
**Application milestone:** Model C chạy local/web với Model B rollback, không gọi LLM API.

## Sau Phase 8
**Expanded-data milestone:** 68.411 candidate được reconcile; Model C có Dev-only report và
không làm thay đổi kết quả Test Phase 5.

## Đóng gói
Phase 8–10 đã hoàn thành. Chỉ bắt đầu Phase 7 sau khi Phase 6 có real offline smoke và Gradio
acceptance; checkpoint demo mặc định là Model C và rollback là Model B.
