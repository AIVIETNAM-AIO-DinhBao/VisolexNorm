# SPECIFICATIONS.md

# Vietnamese Social Media Lexical Normalization using BARTpho

## 1. Mục tiêu và phạm vi

Dự án xây dựng hệ thống **Vietnamese Social Media Lexical Normalization** dùng **BARTpho-syllable** để chuyển văn bản tiếng Việt không chuẩn trên mạng xã hội về dạng chuẩn hơn ở mức từ vựng.

```text
Input : mik ko bt hnay đi hc ko
Output: mình không biết hôm nay đi học không
```

Hệ thống tập trung vào:

- từ viết tắt: `ko`, `bt`, `mng`;
- teencode/slang: `mik`, `mún`, `khum`;
- lỗi chính tả mang tính lexical;
- từ/cụm từ thiếu dấu;
- các biến thể từ vựng thường gặp trên mạng xã hội;
- ánh xạ 1→1, 1→n và n→1 khi dữ liệu cho phép.

Dự án **không** nhằm sửa toàn bộ ngữ pháp, paraphrase, viết lại văn phong hay làm câu trang trọng hơn. Output cần bảo toàn ý nghĩa và cấu trúc câu nhiều nhất có thể.

Câu hỏi thực nghiệm chính:

> Việc bổ sung dữ liệu social-media chưa có nhãn của ViSoLex sau khi tạo weak/pseudo labels có cải thiện BARTpho so với chỉ fine-tune trên ViLexNorm gold data hay không?

---

# 2. Kiến trúc thực nghiệm

Dự án có hai thí nghiệm chính.

## Experiment 1 — Gold-only baseline

```text
ViLexNorm Train
      ↓
BARTpho-syllable
      ↓
Model A
```

Model A là supervised baseline.

## Experiment 2 — Gold + weak/pseudo-labeled ViSoLex

```text
ViSoLex Unlabeled Corpus
      ↓
Weak/Pseudo Labeling
      ↓
Filtering
      ↓
Filtered ViSoLex Weak-Labeled Data
      +
ViLexNorm Gold Train
      ↓
BARTpho-syllable
      ↓
Model B
```

Model A và Model B được đánh giá trên cùng **ViLexNorm Test Set**.

Nguồn dữ liệu của Experiment 2 phải là **ViSoLex unlabeled corpus**. Không thay thế bằng một social-media corpus tùy ý khác nếu không thay đổi specification.

---

# 3. Module 1 — Data Preparation

## 3.1. Nguồn dữ liệu

Pipeline sử dụng đúng hai nguồn dữ liệu logic:

```text
Gold labeled data : ViLexNorm
Unlabeled data    : ViSoLex unlabeled social-media corpus
```

### ViLexNorm

ViLexNorm gồm khoảng **10.467 cặp câu noisy → normalized** được annotate thủ công.

Ba split phải được giữ riêng:

```text
Train → fine-tuning
Dev   → checkpoint / hyperparameter / threshold selection
Test  → final evaluation only
```

Mẫu chuẩn:

```json
{
  "id": "vilexnorm_train_000001",
  "dataset": "ViLexNorm",
  "split": "train",
  "input_text": "hôm nay t ko đi học",
  "target_text": "hôm nay tao không đi học",
  "label_source": "human"
}
```

### ViSoLex unlabeled corpus

Additional data phải lấy từ **unlabeled Vietnamese social-media corpus được sử dụng/xây dựng trong hướng ViSoLex**, khoảng **121.087 câu sau preprocessing**.

Corpus này được tổng hợp từ 5 nguồn:

```text
ViHSD          — Hate speech
UIT-VSMEC      — Emotion recognition
ViHOS          — Hate/offensive span
ViSpamReviews  — Product reviews/spam
UIT-ViSFD      — Sentiment & aspect analysis
```

Các câu này **không có target lexical-normalization do con người annotate**.

Mẫu chuẩn:

```json
{
  "id": "visolex_000001",
  "dataset": "ViSoLex",
  "original_source": "UIT-ViSFD",
  "input_text": "mik thấy sp này cx oke"
}
```

`dataset` phải thể hiện đây là corpus dùng theo ViSoLex; `original_source` giữ nguồn con ban đầu để audit/phân tích domain.

## 3.2. Preprocessing

Preprocessing chỉ thực hiện các biến đổi không làm mất lexical noise:

- loại null/empty;
- chuẩn hóa whitespace;
- giữ nguyên Unicode tiếng Việt;
- tạo ID ổn định;
- deduplicate;
- lưu `original_source`;
- loại exact overlap với ViLexNorm Dev/Test.

Không được:

- spell-correct trước;
- tự normalize teencode bằng dictionary trước;
- paraphrase;
- lowercase toàn bộ nếu làm mất thông tin;
- dùng ViLexNorm Test để quyết định preprocessing/threshold.

## 3.3. Output bắt buộc

```text
data/processed/vilexnorm_train.jsonl
data/processed/vilexnorm_dev.jsonl
data/processed/vilexnorm_test.jsonl
data/processed/visolex_unlabeled.jsonl
```

`visolex_unlabeled.jsonl` phải giữ được thống kê số câu theo 5 `original_source`.

---

# 4. Module 2 — Train Model A

## 4.1. Mục đích

Fine-tune **BARTpho-syllable** trên ViLexNorm Gold Train để tạo baseline và checkpoint có thể dùng làm pseudo-label teacher.

```text
Input  : ViLexNorm Train
Dev    : ViLexNorm Dev
Output : Model A checkpoint
```

## 4.2. Môi trường

Training chạy trên **Kaggle Notebook có GPU**.

Local không phải môi trường bắt buộc cho fine-tuning.

Notebook phải:

1. cài dependency;
2. load processed ViLexNorm;
3. load tokenizer + BARTpho-syllable;
4. tokenize source/target;
5. fine-tune;
6. đánh giá trên Dev;
7. lưu best checkpoint;
8. export checkpoint và run config.

## 4.3. Artifact

```text
checkpoints/model_a/
outputs/model_a/dev_predictions.jsonl
outputs/model_a/dev_metrics.json
outputs/model_a/train_config.json
```

Checkpoint phải load lại được độc lập sau khi Kaggle session kết thúc.

---

# 5. Module 3 — Weak/Pseudo Labeling ViSoLex

## 5.1. Input cố định

Mọi backend labeling đều nhận:

```text
data/processed/visolex_unlabeled.jsonl
```

Backend labeling **không quyết định nguồn corpus**. Nó chỉ quyết định cách sinh `target_text` cho câu ViSoLex.

Pipeline hỗ trợ hai phương án.

---

## 5.2. Phương án A — Model A pseudo-labeling

Luồng mặc định bám sát ý tưởng ban đầu:

```text
ViSoLex input_text
      ↓
Model A.generate()
      ↓
pseudo target
      ↓
generation confidence
      ↓
filter
```

Record:

```json
{
  "id": "visolex_000001",
  "dataset": "ViSoLex",
  "original_source": "UIT-ViSFD",
  "input_text": "mik thấy sp này cx oke",
  "target_text": "mình thấy sản phẩm này cũng oke",
  "label_source": "model_a",
  "teacher_checkpoint": "model_a",
  "confidence": -0.42,
  "accepted": true
}
```

Confidence nên dùng score được normalize theo chiều dài sequence hoặc một scoring rule tương đương được ghi rõ trong report.

Threshold chỉ được chọn bằng Dev/manual audit; không dùng Test.

Batch generation có thể chạy trên Kaggle GPU.

---

## 5.3. Phương án B — LLM API labeling

Có thể dùng LLM API, ví dụ GPT-4o, để tạo weak labels cho **chính ViSoLex corpus**.

Luồng:

```text
ViSoLex input_text
      ↓
LLM API + lexical-normalization prompt
      ↓
weak target
      ↓
validation / filtering
```

LLM chỉ đóng vai trò **offline labeler**. Final model và web app vẫn dùng BARTpho checkpoint của nhóm.

Prompt phải yêu cầu:

- chỉ lexical normalization;
- giữ nguyên nghĩa;
- không paraphrase;
- không thêm thông tin;
- không tự làm văn phong trang trọng;
- giữ nguyên câu nếu đã chuẩn;
- output đúng format, không giải thích.

Record:

```json
{
  "id": "visolex_000001",
  "dataset": "ViSoLex",
  "original_source": "UIT-ViSFD",
  "input_text": "mik thấy sp này cx oke",
  "target_text": "mình thấy sản phẩm này cũng oke",
  "label_source": "llm_api",
  "llm_model": "configured_model",
  "prompt_version": "lexical_norm_v1",
  "accepted": true
}
```

API pipeline phải hỗ trợ:

- API key qua secret/environment;
- batch/chunk;
- persistent cache;
- resume;
- retry;
- error log;
- prompt version;
- giới hạn số sample để kiểm soát chi phí.

Không bắt buộc label toàn bộ 121.087 câu. Có thể chọn subset, nhưng subset phải xuất phát từ `visolex_unlabeled.jsonl` và selection rule phải được ghi lại.

---

## 5.4. Filtering

Dù label bằng Model A hay LLM API, weak-labeled data phải qua validation/filtering.

Kiểm tra tối thiểu:

- output không rỗng;
- output không chứa giải thích/metadata ngoài text;
- output/input length ratio không bất thường;
- edit ratio không cực đoan;
- không trùng Dev/Test;
- deduplicate;
- Unicode hợp lệ.

Nên audit thủ công một random sample trước khi freeze dataset.

Output cuối:

```text
data/processed/visolex_weak_labeled.jsonl
```

Mỗi record phải giữ `label_source` để biết target được sinh bằng Model A hay LLM.

Nếu dùng cả hai backend trong một experiment, phải định nghĩa rõ rule merge/conflict; không silently trộn hai nguồn nhãn.

---

# 6. Module 4 — Train Model B

Model B được fine-tune bằng:

```text
ViLexNorm Gold Train
+
Filtered ViSoLex Weak-Labeled Data
```

Training chạy trên **Kaggle GPU**.

Phải ghi lại:

- số gold samples;
- số ViSoLex weak-labeled samples;
- backend tạo label;
- số sample trước/sau filtering;
- gold:pseudo sampling ratio;
- initialization checkpoint;
- hyperparameters.

Không bắt buộc dùng toàn bộ 121k câu.

Artifact:

```text
checkpoints/model_b/
outputs/model_b/dev_predictions.jsonl
outputs/model_b/dev_metrics.json
outputs/model_b/train_config.json
```

---

# 7. Module 5 — Evaluation, Local Inference và Web

## 7.1. Final evaluation

Sau khi configuration đã freeze, đánh giá Model A và Model B trên cùng:

```text
ViLexNorm Test
```

Metric chính:

```text
ERR
Precision
Recall
F1-score
```

Nếu có official evaluation implementation của ViLexNorm, ưu tiên dùng cùng protocol.

Kết quả phải cho phép so sánh trực tiếp:

| Model | Training Data | Weak-label Backend | ERR | Precision | Recall | F1 |
|---|---|---|---:|---:|---:|---:|
| A | ViLexNorm | — | TBD | TBD | TBD | TBD |
| B | ViLexNorm + ViSoLex | Model A / LLM | TBD | TBD | TBD | TBD |

Ngoài metric phải có error analysis tối thiểu cho:

- correct normalization;
- missed normalization;
- wrong normalization;
- over-normalization;
- 1→n / n→1 cases;
- lỗi có khả năng đến từ weak-label noise.

## 7.2. Local inference

Checkpoint tốt nhất được tải từ Kaggle về local.

Local inference:

```text
text
 ↓
tokenizer
 ↓
fine-tuned BARTpho
 ↓
normalized text
```

Local script phải chạy được mà không cần:

- Kaggle;
- training dataset;
- LLM API;
- ViSoLex corpus.

## 7.3. Web application

Web app dùng Gradio hoặc Streamlit và chạy local.

Chức năng bắt buộc:

1. ô nhập text;
2. nút `Normalize`;
3. chạy checkpoint tốt nhất;
4. hiển thị normalized output;
5. xử lý input rỗng an toàn.

Ví dụ:

```text
Input:
mik ko bt hnay đi hc ko

Output:
mình không biết hôm nay đi học không
```

Highlight các thay đổi lexical là optional.

Web app **không gọi LLM API**. Nếu LLM được dùng, nó chỉ xuất hiện ở giai đoạn offline weak-label generation.

---

# 8. Luồng hoàn chỉnh

```text
                    ViLexNorm
                Train / Dev / Test
                       │
                       ▼
               Train Model A
                [Kaggle GPU]
                       │
             ┌─────────┴─────────┐
             │                   │
             │                   ▼
             │          ViSoLex Unlabeled
             │           121,087 sentences
             │                   │
             │          ┌────────┴────────┐
             │          │                 │
             │     Model A label      LLM API label
             │          │                 │
             │          └────────┬────────┘
             │                   ▼
             │              Filtering
             │                   │
             │                   ▼
             │        ViSoLex Weak-Labeled
             │                   │
             │     ViLexNorm Gold Train
             │              +    │
             │                   ▼
             │             Train Model B
             │              [Kaggle GPU]
             │                   │
             └──────────┬────────┘
                        ▼
                 ViLexNorm Test
                        │
                        ▼
              A vs B Evaluation
                        │
                        ▼
                Best Checkpoint
                        │
                        ▼
             Local Inference / Web
```

---

# 9. Điều kiện hoàn thành

Project đạt implementation scope khi:

1. ViLexNorm Train/Dev/Test được preprocess đúng và tách biệt;
2. ViSoLex unlabeled corpus được preprocess thành artifact riêng;
3. Model A fine-tune được trên Kaggle GPU;
4. có ít nhất một pipeline tạo weak labels cho ViSoLex:
   - Model A pseudo-labeling; hoặc
   - LLM API labeling;
5. weak labels được filter và audit;
6. Model B được train bằng ViLexNorm + ViSoLex weak-labeled data;
7. Model A và B được đánh giá trên cùng ViLexNorm Test;
8. có error analysis;
9. best checkpoint chạy inference local;
10. web app local normalize được input thực tế.
