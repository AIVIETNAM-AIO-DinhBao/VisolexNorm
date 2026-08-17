# PLAN.md

# Kế hoạch triển khai 14 ngày

Kế hoạch này bám theo kiến trúc dữ liệu cố định:

```text
Gold      = ViLexNorm
Unlabeled = ViSoLex corpus (~121,087 câu)
Model     = BARTpho-syllable
Training  = Kaggle GPU
Inference/Web = Local
```

LLM API, nếu dùng, chỉ là một **labeling backend cho ViSoLex**, không thay thế nguồn unlabeled data.

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

`visolex_unlabeled.jsonl` phải chứa corpus ViSoLex khoảng 121k câu và giữ `original_source` thuộc 5 nguồn:

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
- có thể dùng checkpoint cho batch pseudo-labeling.

---

# Phase 3 — Xây weak-label pipeline cho ViSoLex
**Ngày 4–7**

## Kết quả phải đạt

Có một file:

```text
visolex_weak_labeled.jsonl
```

được tạo từ **visolex_unlabeled.jsonl**, có provenance đầy đủ và đã qua filtering.

Có hai phương án triển khai; team có thể chọn một làm chính và phương án còn lại làm fallback/experiment phụ.

---

## 3A. Model A pseudo-labeling

### Bước nhỏ

1. load `visolex_unlabeled.jsonl`;
2. batch tokenize;
3. chạy `Model A.generate()` trên Kaggle GPU;
4. lấy prediction;
5. tính generation confidence;
6. cache raw prediction;
7. filter confidence thấp;
8. filter output bất thường;
9. audit random sample;
10. freeze accepted set.

Record phải chứa:
```text
id
dataset=ViSoLex
original_source
input_text
target_text
label_source=model_a
confidence
accepted
```

### Kết quả
Có thể thống kê:
- số câu generate;
- số câu accepted;
- acceptance rate;
- phân bố theo 5 source;
- examples tốt/xấu.

---

## 3B. LLM API labeling

LLM vẫn nhận **câu từ ViSoLex**.

### Bước nhỏ

1. version hóa prompt lexical normalization;
2. test prompt trên 50–100 câu ViSoLex;
3. audit paraphrase/over-normalization;
4. sửa prompt nếu cần;
5. implement cache + resume;
6. implement retry/error log;
7. label theo chunk;
8. validate output format;
9. filter output bất thường;
10. freeze accepted set.

Record phải chứa:
```text
id
dataset=ViSoLex
original_source
input_text
target_text
label_source=llm_api
llm_model
prompt_version
accepted
```

Không cần label toàn bộ 121k ngay. Có thể chọn subset hợp lý theo:
- random stratified by source;
- top-K;
- budget cố định.

Selection rule phải được lưu.

---

## 3.3. Quyết định cuối Phase

Chọn weak-labeled dataset dùng cho Model B dựa trên:
- manual audit;
- Dev-side experiment nếu cần;
- độ ổn định output;
- số lượng sample;
- chi phí/tốc độ.

Không dùng ViLexNorm Test để chọn backend.

## Exit criteria
- weak-label artifact được freeze;
- mỗi sample trace được về ViSoLex source;
- biết rõ label sinh bởi Model A hay LLM;
- có thống kê before/after filtering.

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
- merge gold + weak data;
- giữ `label_source`;
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
1. giảm pseudo sample;
2. tăng tỷ lệ gold;
3. tăng filtering;
4. đổi weak-label backend nếu backend kia đã sẵn sàng.

Không mở rộng sang kiến trúc mới.

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
- trường hợp Model B bị weak-label noise làm xấu đi.

## Exit criteria
- bảng A/B hoàn chỉnh;
- có raw predictions;
- có error examples;
- có thể kết luận research question dù B tốt hơn hay không.

---

# Phase 6 — Local inference và Web App
**Ngày 11–12**

## Kết quả phải đạt

Best checkpoint chạy hoàn toàn local và có web app demo.

## Các bước

### 6.1. Chọn best checkpoint
Chọn A hoặc B theo kết quả final experiment/reporting rule.

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

# Phase 7 — Reproducibility và đóng gói
**Ngày 12–14**

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
evaluation
```

### 7.3. README execution flow
Mô tả đúng thứ tự:
```text
prepare data
→ train A on Kaggle
→ label ViSoLex
→ train B on Kaggle
→ evaluate
→ download best checkpoint
→ run local app
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
6. giải thích ViSoLex weak-label pipeline.

## Exit criteria
- clean run path rõ ràng;
- không thiếu checkpoint/config;
- demo không phụ thuộc mạng, trừ khi chủ động demo phần labeling API;
- final web inference chạy local.

---

# Lịch 14 ngày gợi ý

| Ngày | Mục tiêu chính |
|---|---|
| 1 | ViLexNorm preprocessing + bắt đầu ViSoLex preprocessing |
| 2 | Freeze processed data + dựng Kaggle Model A |
| 3 | Train/debug Model A |
| 4 | Export Model A + bắt đầu label ViSoLex |
| 5 | Weak-label generation |
| 6 | Filtering + audit weak labels |
| 7 | Freeze weak-label dataset + build Model B mixture |
| 8 | Train Model B |
| 9 | Debug/rerun Model B nếu cần |
| 10 | Freeze models + final Test evaluation |
| 11 | Error analysis + chọn best checkpoint |
| 12 | Local inference + web app |
| 13 | Reproducibility + report artifacts |
| 14 | Packaging + demo rehearsal + buffer |

---

# Mốc kiểm soát quan trọng

## Cuối ngày 2
**Data milestone:** ViLexNorm và ViSoLex processed xong.

## Cuối ngày 4
**Baseline milestone:** Model A usable.

## Cuối ngày 7
**Augmentation milestone:** ViSoLex weak labels đã freeze.

## Cuối ngày 9
**Training milestone:** Model B usable.

## Cuối ngày 11
**Research milestone:** Có kết quả A vs B và error analysis.

## Cuối ngày 12
**Application milestone:** Best checkpoint chạy local/web.

## Ngày 13–14
Chỉ còn reproducibility, packaging, report và buffer; không nên bắt đầu experiment lớn mới.
