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

## Experiment 2 — Gold + LLM-reviewed pseudo-labeled ViSoLex

```text
ViSoLex Unlabeled Corpus
      ↓
Model A candidate generation
      ↓
Candidate normalization + confidence
      ↓
LLM Reviewer
      ↓
KEEP / EDIT / REJECT
      ↓
Validation + Filtering
      ↓
LLM-reviewed ViSoLex Weak-Labeled Data
      +
ViLexNorm Gold Train
      ↓
BARTpho-syllable
      ↓
Model B
```

Model A và Model B được đánh giá trên cùng **ViLexNorm Test Set**.

Nguồn dữ liệu của Experiment 2 phải là **ViSoLex unlabeled corpus**. Model A không được xem là ground-truth teacher: nó chỉ sinh **candidate normalization**. LLM đóng vai trò reviewer độc lập để xác nhận, sửa tối thiểu hoặc loại candidate trước khi dữ liệu được dùng để train Model B.

LLM chỉ xuất hiện trong giai đoạn offline data preparation. Final checkpoint và web application vẫn chỉ sử dụng BARTpho do nhóm fine-tune.

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

Fine-tune **BARTpho-syllable** trên ViLexNorm Gold Train để tạo supervised baseline. Trong Module 3, checkpoint này đồng thời đóng vai trò **candidate generator** cho ViSoLex; prediction của Model A chưa được xem là nhãn cuối.

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

# 5. Module 3 — Model A Candidate Generation + LLM Review

## 5.1. Mục tiêu và input cố định

Module này biến ViSoLex unlabeled corpus thành weak-labeled data đủ tin cậy để bổ sung vào training.

Input duy nhất:

```text
data/processed/visolex_unlabeled.jsonl
```

Pipeline chính:

```text
ViSoLex input_text
      ↓
Model A.generate()
      ↓
candidate_text + model_a_confidence
      ↓
LLM review
      ↓
KEEP / EDIT / REJECT
      ↓
validation + filtering
      ↓
visolex_weak_labeled.jsonl
```

**Nguyên tắc:** Model A đề xuất, LLM kiểm tra. Không đưa trực tiếp prediction của Model A vào Model B mà không qua review trong pipeline chính.

Không bắt buộc xử lý toàn bộ 121.087 câu. Có thể chọn một subset ViSoLex phù hợp với budget/thời gian, nhưng selection rule phải deterministic hoặc được lưu lại và phải giữ provenance theo `original_source`.

---

## 5.2. Bước 1 — Model A sinh candidate

Model A chạy batch inference trên ViSoLex bằng Kaggle GPU.

Mỗi sample cần tạo:

- `candidate_text`: normalization do Model A đề xuất;
- `model_a_confidence`: generation score được normalize theo chiều dài hoặc scoring rule tương đương;
- generation metadata cần thiết để reproduce.

Artifact trung gian:

```text
data/intermediate/visolex_model_a_candidates.jsonl
```

Ví dụ:

```json
{
  "id": "visolex_000001",
  "dataset": "ViSoLex",
  "original_source": "UIT-ViSFD",
  "input_text": "mik ko bt hnay",
  "candidate_text": "mình không biết hnay",
  "model_a_confidence": -0.31,
  "candidate_checkpoint": "model_a"
}
```

Candidate generation phải hỗ trợ:

- batch inference;
- checkpoint/config cố định;
- cache kết quả;
- resume nếu Kaggle session bị ngắt;
- không thay đổi thứ tự/ID của sample.

`model_a_confidence` dùng để audit, phân tầng sample và có thể ưu tiên thứ tự review. Nó **không đủ để biến candidate thành final target**.

---

## 5.3. Bước 2 — LLM Reviewer

LLM nhận ít nhất hai trường:

```text
SOURCE    = input_text gốc của ViSoLex
CANDIDATE = candidate_text của Model A
```

Reviewer phải đánh giá lexical normalization, không đánh giá văn phong.

### 5.3.1. Reviewer contract

LLM phải chọn đúng một trong ba quyết định:

#### `KEEP`

Candidate đã là lexical normalization phù hợp. Final target giữ nguyên `candidate_text`.

#### `EDIT`

Candidate gần đúng nhưng còn lỗi. LLM trả về một `corrected_text` với **mức chỉnh sửa tối thiểu cần thiết**.

#### `REJECT`

Sample quá mơ hồ, candidate không đáng tin, hoặc không thể tạo target lexical normalization đủ chắc chắn. Sample không được đưa vào Model B.

### 5.3.2. Giảm anchoring vào Model A

Prompt phải yêu cầu reviewer:

1. trước tiên xác định độc lập normalization phù hợp của `SOURCE`;
2. sau đó mới so sánh với `CANDIDATE`;
3. chỉ `KEEP` nếu candidate tương đương với normalization mà reviewer xác định;
4. nếu khác, dùng `EDIT` và sửa tối thiểu;
5. nếu nghĩa không rõ hoặc có nhiều cách hiểu đáng kể, dùng `REJECT`.

Prompt phải nhấn mạnh:

- chỉ lexical normalization;
- giữ nguyên nghĩa và sắc thái;
- không paraphrase;
- không sửa toàn bộ ngữ pháp;
- không làm văn phong trang trọng hơn;
- không thêm/xóa thông tin;
- không tự censor profanity/slang nếu không cần để normalize;
- giữ emoji/hashtag/punctuation trừ khi có lý do lexical rõ ràng;
- nếu source đã chuẩn thì giữ nguyên;
- output đúng schema, không kèm giải thích tự do.

### 5.3.3. Structured output

Reviewer nên trả structured output, ví dụ:

```json
{
  "decision": "EDIT",
  "corrected_text": "mình không biết hôm nay"
}
```

Với `KEEP`, `corrected_text` có thể bằng candidate hoặc `null` theo implementation đã chốt. Với `REJECT`, sample phải có reason code ngắn nếu API/schema cho phép để phục vụ audit, nhưng reason không được dùng làm target.

### 5.3.4. API requirements

LLM review pipeline phải hỗ trợ:

- API key qua secret/environment variable;
- model name configurable;
- `prompt_version` cố định;
- chunk/batch processing khi API cho phép;
- persistent cache;
- resume;
- retry với backoff;
- error log;
- validation JSON/schema;
- lưu raw response tối thiểu cần thiết để audit nhưng không commit secret.

Trước batch lớn phải pilot trên một sample nhỏ và audit các lỗi như paraphrase, over-normalization, mất slang/sắc thái hoặc thay đổi nghĩa.

---

## 5.4. Bước 3 — Xây final weak label

Rule tạo target cuối:

```text
KEEP   → target_text = candidate_text
EDIT   → target_text = corrected_text
REJECT → drop sample
```

Record cuối nên giữ toàn bộ provenance:

```json
{
  "id": "visolex_000001",
  "dataset": "ViSoLex",
  "original_source": "UIT-ViSFD",
  "input_text": "mik ko bt hnay",
  "candidate_text": "mình không biết hnay",
  "model_a_confidence": -0.31,
  "llm_decision": "EDIT",
  "llm_corrected_text": "mình không biết hôm nay",
  "target_text": "mình không biết hôm nay",
  "label_source": "model_a+llm_review",
  "llm_model": "configured_model",
  "prompt_version": "lexical_norm_review_v1",
  "accepted": true
}
```

Output chính:

```text
data/processed/visolex_weak_labeled.jsonl
```

---

## 5.5. Validation và Filtering

Sau review vẫn phải chạy automatic validation:

- output không rỗng;
- `KEEP` phải có candidate hợp lệ;
- `EDIT` phải có `corrected_text` hợp lệ;
- `REJECT` không được lọt vào training set;
- output/input length ratio không bất thường;
- edit ratio không cực đoan;
- Unicode hợp lệ;
- không chứa explanation/JSON artifact trong `target_text`;
- không overlap ViLexNorm Dev/Test;
- deduplicate theo rule đã định nghĩa.

Sau filtering phải audit thủ công một random sample, ưu tiên stratify theo:

- `KEEP` / `EDIT` / `REJECT`;
- 5 `original_source` của ViSoLex;
- vùng confidence cao/trung bình/thấp của Model A.

Module phải xuất statistics tối thiểu:

```text
number of Model A candidates
number sent to LLM review
KEEP count / rate
EDIT count / rate
REJECT count / rate
validation-drop count / rate
final accepted count
counts by original_source
```

Các tỷ lệ `KEEP/EDIT/REJECT` là một phần của analysis: nếu `EDIT` hoặc `REJECT` cao, đó là bằng chứng trực tiếp rằng Model A pseudo-labeling thuần túy chứa noise đáng kể.

---

## 5.6. Cost-control strategy

Nếu không muốn review toàn bộ 121k câu, pipeline được phép chọn subset trước khi gọi LLM.

Khuyến nghị:

1. tạo candidate cho toàn bộ hoặc một pool lớn bằng Model A;
2. chọn subset ViSoLex theo rule được lưu lại, có thể stratify theo `original_source` và confidence;
3. **mọi sample được chọn để đưa vào weak-labeled training set đều phải qua LLM review**;
4. không auto-accept chỉ vì confidence cao trong experiment chính.

Confidence cao có thể dùng để ưu tiên sampling hoặc làm ablation sau này, nhưng không thay thế LLM review trong pipeline chính đã chốt.

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
- số candidate Model A và LLM review configuration;
- KEEP/EDIT/REJECT statistics và số sample trước/sau filtering;
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

| Model | Training Data | Weak-label Method | ERR | Precision | Recall | F1 |
|---|---|---|---:|---:|---:|---:|
| A | ViLexNorm | — | TBD | TBD | TBD | TBD |
| B | ViLexNorm + ViSoLex | Model A candidates + LLM review | TBD | TBD | TBD | TBD |

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
             │           ~121,087 sentences
             │                   │
             │                   ▼
             │           Model A candidates
             │          + generation confidence
             │                   │
             │                   ▼
             │              LLM Reviewer
             │                   │
             │        ┌──────────┼──────────┐
             │        ▼          ▼          ▼
             │      KEEP        EDIT      REJECT
             │        │          │
             │        └────┬─────┘
             │             ▼
             │       Validation / Filter
             │             │
             │             ▼
             │   LLM-reviewed ViSoLex Weak Labels
             │             │
             │     ViLexNorm Gold Train
             │          +  │
             │             ▼
             │        Train Model B
             │         [Kaggle GPU]
             │             │
             └───────┬─────┘
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
          Local Inference / Web App
```

---

# 9. Điều kiện hoàn thành

Project đạt implementation scope khi:

1. ViLexNorm Train/Dev/Test được preprocess đúng và tách biệt;
2. ViSoLex unlabeled corpus được preprocess thành artifact riêng;
3. Model A fine-tune được trên Kaggle GPU;
4. Model A sinh được candidate + confidence cho ViSoLex subset/pool đã chọn;
5. LLM reviewer xử lý candidate theo `KEEP / EDIT / REJECT`, sau đó weak labels được validate, filter và audit;
6. Model B được train bằng ViLexNorm + **LLM-reviewed ViSoLex weak-labeled data**;
7. Model A và B được đánh giá trên cùng ViLexNorm Test;
8. có error analysis;
9. best checkpoint chạy inference local;
10. web app local normalize được input thực tế.
