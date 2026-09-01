# FRONTEND_IMPLEMENTATION.md — VietNorm

## 0. Mission

Build the frontend for **VietNorm**, a Vietnamese text normalization application.

Core task:

> **Informal / teen-code Vietnamese → Standard Vietnamese**

Example:

- Input: `hnay t di hoc`
- Output: `hôm nay tôi đi học`

The product should feel like a **focused translation / language utility**, not a chatbot. It must be polished, responsive, accessible, and suitable for an academic NLP project demo.

---

## 1. Tech Stack

Use:

- **React**
- **Vite**
- **TypeScript**
- **Tailwind CSS**
- **Lucide React** for icons

Prefer React local state, small reusable components, `localStorage` for history, and a small API service wrapper.

Do **not** introduce Redux, Zustand, Next.js, authentication, a database, or other unnecessary infrastructure.

---

## 2. Design System

The project follows the **Claude DESIGN.md** visual direction selected for this project.

If `DESIGN.md` exists in the repository, treat it as the visual source of truth. Follow its typography, colors, spacing, surfaces, borders, buttons, and hierarchy.

The interface should feel:

- warm
- minimal
- editorial
- quiet
- modern
- intelligent
- text-first

Avoid:

- purple-blue AI gradients
- neon
- glassmorphism
- giant hero sections
- glowing AI effects
- floating decorative blobs
- excessive shadows/cards
- chatbot bubbles
- dashboard clutter

The UI should resemble a **language transformation tool**, not an AI assistant.

---

## 3. Product Name

Use **VietNorm**.

Do not rename it unless explicitly requested later.

---

## 4. Primary User Flow

```text
Enter informal Vietnamese
        ↓
Normalize
        ↓
Read normalized Vietnamese
        ↓
Inspect differences
        ↓
Copy / reuse result
```

The workflow should be obvious within a few seconds.

---

## 5. Routes

Implement only:

- `/` — main normalization application
- `/about` — project / academic information

Do not add unnecessary routes.

---

## 6. Main Page Structure

Order:

```text
Header
↓
Intro
↓
Input / Output Workspace
↓
Normalize Button
↓
Example Inputs
↓
Difference Box
↓
Recent History
↓
Footer
```

Recommended desktop layout:

```text
┌───────────────────────────────────────────────────────────────┐
│ VietNorm                                           Giới thiệu │
├───────────────────────────────────────────────────────────────┤
│                                                               │
│              Chuẩn hóa văn bản tiếng Việt                    │
│     Chuyển teen code thành tiếng Việt tự nhiên, đúng chuẩn   │
│                                                               │
│ ┌────────────────────────┬─────────────────────────────────┐  │
│ │ Văn bản gốc            │ Văn bản chuẩn hóa               │  │
│ │                        │                                 │  │
│ │ hnay t di hoc          │ hôm nay tôi đi học              │  │
│ │                        │                                 │  │
│ │                        │                                 │  │
│ │ 14 / 500        Xóa    │                     Sao chép    │  │
│ └────────────────────────┴─────────────────────────────────┘  │
│                                                               │
│                       [ Chuẩn hóa ]                           │
│                                                               │
│ Thử với ví dụ                                                 │
│ [hnay t di hoc] [mik cx k bt] [mai mk ko di dau]             │
│                                                               │
│ So sánh thay đổi                                              │
│ ┌───────────────────────────────────────────────────────────┐ │
│ │ Gốc:       t là [hs] lớp 12                              │ │
│ │ Chuẩn hóa: tôi là [học sinh] lớp 12                      │ │
│ └───────────────────────────────────────────────────────────┘ │
│                                                               │
│ Lịch sử gần đây                                               │
│ ...                                                           │
└───────────────────────────────────────────────────────────────┘
```

---

## 7. Header

Keep it minimal.

Left:

- `VietNorm`

Right:

- `Giới thiệu`
- optional GitHub link only if repository information already exists

Do not add login, profile, settings, pricing, sidebar navigation, or dashboard menus.

---

## 8. Intro Section

Compact intro only.

Title:

`Chuẩn hóa văn bản tiếng Việt`

Subtitle:

`Chuyển teen code và văn bản không chuẩn thành tiếng Việt tự nhiên, đúng chuẩn.`

The editor must remain visually more important than the intro.

---

## 9. Input / Output Workspace

This is the visual center of the application.

### Desktop

Use two equal-width columns inside **one shared workspace**:

```text
50% original input
50% normalized output
```

Prefer one outer container with a divider. Do not render them as two unrelated floating cards.

### Mobile

Stack:

```text
Input
↓
Normalize
↓
Output
```

---

## 10. Input Panel

Header:

`Văn bản gốc`

Use an accessible `<textarea>`.

Required behavior:

- type and paste normally
- maximum **500 characters**
- live character count: `0 / 500`
- `Xóa` action
- `Ctrl + Enter` and `Cmd + Enter` trigger normalization
- empty/whitespace-only input cannot be submitted

Placeholder:

`Nhập văn bản cần chuẩn hóa...`

Do not use a rich-text editor.

---

## 11. Output Panel

Header:

`Văn bản chuẩn hóa`

Before success:

`Kết quả chuẩn hóa sẽ xuất hiện ở đây.`

After success:

- render normalized text
- preserve Vietnamese diacritics
- preserve paragraph breaks when possible
- show `Sao chép`

Copy feedback:

```text
Sao chép
→
Đã sao chép ✓
```

Return to normal after a short delay.

---

## 12. Normalize Button

Primary CTA:

`Chuẩn hóa`

Optional Lucide icon: `Sparkles` or `WandSparkles`.

States:

- Ready: `Chuẩn hóa`
- Loading: `Đang chuẩn hóa...` + small spinner
- Disabled: empty input or active request

Prevent duplicate requests while loading.

---

## 13. Keyboard Shortcut

`Ctrl + Enter` / `Cmd + Enter` triggers normalization.

Do not hijack normal Enter behavior inside the textarea.

---

## 14. Example Inputs

Label:

`Thử với ví dụ`

Suggested examples:

- `hnay t di hoc`
- `mik cx k bt`
- `mai mk ko di dau`
- `tks b nhieu nha`

Clicking a chip fills the input only; it does not auto-submit.

Keep examples in a single constants/config file so they are easy to replace.

---

## 15. Difference Box

This is a **separate box below the main workspace**.

Do **not** render differences as a list like:

```text
hs → học sinh
t → tôi
```

Instead render two text rows:

```text
Gốc:
t là hs lớp 12

Chuẩn hóa:
tôi là học sinh lớp 12
```

Changed spans must be highlighted.

Example:

```text
Gốc:
[t] là [hs] lop 12

Chuẩn hóa:
[tôi] là [học sinh] lớp 12
```

Corresponding changed regions must use matching highlight colors:

- `t` ↔ `tôi`
- `hs` ↔ `học sinh`
- `lop` ↔ `lớp`

The diff must support:

- replacement
- insertion
- deletion
- one token → multiple tokens
- multiple tokens → one token

Prioritize readability over mathematically perfect alignment.

This is **frontend textual comparison only**. Never call it model reasoning, attention, or explanation.

Hide the Difference Box until a successful output exists.

---

## 16. Edit Result Again

After success, provide a secondary action:

`Chỉnh sửa lại`

Behavior:

- copy normalized output back into the input textarea
- focus input
- allow user to edit and normalize again

This action is secondary to `Sao chép`.

---

## 17. Loading State

While normalizing:

- keep the workspace visible
- preserve user input
- disable Normalize
- show `Đang chuẩn hóa...`
- show subtle loading feedback inside output

Do not use full-screen loaders or flashy AI animations.

---

## 18. Error State

Show a user-friendly message near the workspace:

`Không thể chuẩn hóa văn bản. Vui lòng thử lại.`

Optional action:

`Thử lại`

Do not expose raw backend stack traces, CUDA errors, Python exceptions, or HTTP internals.

---

## 19. Input Validation

Limit: **500 characters**.

Rules:

- trim only for validation checks
- do not silently destroy intentional whitespace/newlines
- reject empty/whitespace-only input
- block requests above the limit
- show live character count

Error message if needed:

`Văn bản vượt quá giới hạn 500 ký tự.`

---

## 20. Recent History

Use **`localStorage` only**.

Store at most **10 most recent successful normalizations**.

Type:

```ts
type HistoryItem = {
  id: string;
  input: string;
  output: string;
  createdAt: string;
};
```

Behavior:

- newest first
- avoid exact consecutive duplicate entries
- trim to 10 after insert

Actions:

- `Khôi phục`
- `Sao chép`
- `Xóa`

`Khôi phục` loads the original input into the textarea.

Optional: also restore output if it does not complicate state.

Show `Xóa lịch sử` only when history is non-empty.

Do not create a ChatGPT-like history sidebar.

---

## 21. Footer

Minimal footer only.

Example:

`VietNorm — Vietnamese Text Normalization`

---

## 22. About Page

Route: `/about`

Sections:

### Problem
Explain Vietnamese teen-code / informal text normalization.

Example:

```text
hnay t di hoc
→
hôm nay tôi đi học
```

### Model / Method
Provide a clean section for real model information.

**Do not invent architecture details.**

### Dataset
Provide a section for real dataset information.

**Do not fabricate dataset size/source.**

### Evaluation
Support real metrics if provided later, such as:

- BLEU
- ROUGE
- CER
- WER
- Exact Match

Render only metrics that actually exist.

### Examples
Show real normalization examples.

### Team
Simple team information section.

---

## 23. API Layer

Keep backend integration isolated from UI components.

Recommended file:

```text
src/services/normalizeApi.ts
```

Default contract:

```http
POST /normalize
Content-Type: application/json
```

Request:

```json
{
  "text": "hnay t di hoc"
}
```

Expected response:

```json
{
  "normalized_text": "hôm nay tôi đi học"
}
```

API base URL must be configurable via:

```text
VITE_API_BASE_URL
```

Suggested interface:

```ts
export async function normalizeText(text: string): Promise<string> {
  // call backend
  // validate response
  // return normalized_text
}
```

Do not scatter `fetch()` calls across components.

---

## 24. Development Mock Mode

If backend is unavailable during frontend development:

- preserve the real API interface
- provide an easily removable mock implementation
- clearly separate mock data from production API code

Do not hard-code fake inference in a way that could be mistaken for the real model.

---

## 25. Suggested React State

```ts
const [inputText, setInputText] = useState("");
const [outputText, setOutputText] = useState("");
const [isLoading, setIsLoading] = useState(false);
const [error, setError] = useState<string | null>(null);
const [history, setHistory] = useState<HistoryItem[]>([]);
```

Optional:

```ts
const [copyState, setCopyState] = useState<"idle" | "copied">("idle");
```

No global state library is required.

---

## 26. Suggested Project Structure

```text
src/
├── app/
│   └── App.tsx
├── pages/
│   ├── HomePage.tsx
│   └── AboutPage.tsx
├── components/
│   ├── layout/
│   │   ├── Header.tsx
│   │   └── Footer.tsx
│   ├── normalization/
│   │   ├── NormalizationWorkspace.tsx
│   │   ├── InputPanel.tsx
│   │   ├── OutputPanel.tsx
│   │   ├── NormalizeButton.tsx
│   │   ├── ExampleInputs.tsx
│   │   └── DifferenceBox.tsx
│   ├── history/
│   │   ├── HistoryList.tsx
│   │   └── HistoryItem.tsx
│   └── common/
│       ├── ErrorMessage.tsx
│       └── CopyButton.tsx
├── services/
│   └── normalizeApi.ts
├── hooks/
│   └── useNormalizationHistory.ts
├── utils/
│   ├── textDiff.ts
│   └── storage.ts
├── constants/
│   └── examples.ts
└── types/
    └── index.ts
```

This is a guideline, not a requirement to over-abstract.

---

## 27. Difference Algorithm Guidance

Keep diff logic in:

```text
src/utils/textDiff.ts
```

Suggested approach:

1. tokenize Vietnamese text while preserving punctuation/whitespace where practical
2. compute sequence alignment between source and normalized tokens
3. group nearby replacements where appropriate
4. assign stable highlight group IDs to corresponding changed regions
5. render original and normalized rows using those IDs

Suggested internal shape:

```ts
type DiffSegment = {
  text: string;
  type: "equal" | "changed" | "inserted" | "deleted";
  groupId?: number;
};
```

Important example:

```text
Original:   hs
Normalized: học sinh
```

These must be treated as corresponding changed regions and share the same highlight group.

Do not assume one input token always maps to exactly one output token.

---

## 28. Responsive Behavior

### Desktop `>= 900px`

- input/output side by side
- centered workspace
- comfortable whitespace

### Tablet

Use side-by-side only while readable; otherwise stack.

### Mobile `< 640px`

```text
Input
↓
Normalize
↓
Output
↓
Examples
↓
Difference Box
↓
History
```

Requirements:

- no horizontal page scroll
- touch targets ~44px when appropriate
- example chips wrap
- text areas remain comfortable to edit

---

## 29. Accessibility

Required:

- semantic HTML
- visible keyboard focus
- sufficient contrast
- real `<textarea>`
- buttons for actions
- `aria-label` on icon-only controls
- status must not rely on color alone
- keyboard-accessible history actions
- understandable copy feedback
- respect `prefers-reduced-motion`

---

## 30. Motion

Keep motion restrained:

- 150–200ms
- opacity
- small background/border changes
- tiny translate transitions only where helpful

Appropriate uses:

- hover/focus
- copy confirmation
- result appearance
- history insertion

Do not animate text excessively.

---

## 31. Icons

Use **Lucide React** consistently.

Possible icons:

- `Copy`
- `Check`
- `X`
- `Trash2`
- `RotateCcw`
- `Sparkles`
- `LoaderCircle`
- `AlertCircle`
- `Github`

Icons should remain secondary to text labels.

---

## 32. UI Language

Primary UI language: **Vietnamese**.

Use labels such as:

- `Văn bản gốc`
- `Văn bản chuẩn hóa`
- `Chuẩn hóa`
- `Sao chép`
- `Đã sao chép`
- `Xóa`
- `Thử với ví dụ`
- `So sánh thay đổi`
- `Lịch sử gần đây`
- `Khôi phục`
- `Chỉnh sửa lại`
- `Giới thiệu`

Code identifiers may remain English.

---

## 33. Required UI States

Explicitly support:

```text
idle
 typing
ready
loading
success
error
```

### Idle
- empty input
- normalize disabled
- output placeholder visible

### Typing
- update character count
- clear stale validation error

### Ready
- valid input
- normalize enabled

### Loading
- normalize disabled
- loading feedback visible

### Success
- output visible
- copy enabled
- Difference Box visible
- successful result saved to history

### Error
- error visible
- input preserved
- retry possible

---

## 34. Functional Requirements Checklist

Implementation is complete only when all work:

- [ ] Enter Vietnamese text
- [ ] Paste into input
- [ ] Maximum 500 characters
- [ ] Live character count
- [ ] Empty input cannot submit
- [ ] Clear input
- [ ] Normalize calls API
- [ ] Ctrl/Cmd + Enter normalizes
- [ ] Loading prevents duplicate requests
- [ ] User-friendly API errors
- [ ] Output renders normalized text
- [ ] Copy output
- [ ] Copy confirmation
- [ ] Example chips populate input
- [ ] Separate Difference Box after success
- [ ] Difference Box has original and normalized rows
- [ ] Changed source spans highlighted
- [ ] Corresponding output spans use matching highlights
- [ ] One-to-many mapping such as `hs → học sinh` works
- [ ] Edit result again works
- [ ] Successful results stored in localStorage
- [ ] Maximum 10 history items
- [ ] History restore
- [ ] History copy
- [ ] History delete
- [ ] Desktop responsive layout
- [ ] Mobile responsive layout
- [ ] `/about` exists
- [ ] No model status indicator
- [ ] No batch normalization
- [ ] No chatbot UI

---

## 35. Explicitly Out of Scope

Do **not** implement:

- chatbot interface
- conversation history
- model status indicator
- fake confidence score
- batch normalization
- CSV upload
- file upload normalization
- authentication
- user accounts
- database
- payment
- pricing page
- admin dashboard
- analytics dashboard
- complex settings
- sidebar navigation
- fabricated model explanations
- fabricated evaluation metrics

Do not expand scope without explicit approval.

---

## 36. Quality Expectations

The frontend must be:

- visually coherent
- responsive
- accessible
- easy to demo
- easy to connect to backend
- easy to understand and maintain
- free of unnecessary abstractions

Prefer a polished small product over a feature-heavy demo.

---

## 37. Agent Working Rules

1. Read this file completely before coding.
2. Read `DESIGN.md` if it exists.
3. Preserve the Claude-derived visual system.
4. Do not change agreed product scope.
5. Do not add features just because they might be useful.
6. Keep normalization as the visual center.
7. Keep API logic isolated.
8. Keep diff logic isolated.
9. Keep history local-only.
10. Use Vietnamese UI text.
11. Do not fabricate backend/model capabilities.
12. Make reasonable implementation decisions without asking about trivial details.
13. Ask only when a missing decision blocks correct implementation.
14. Ensure TypeScript checks pass.
15. Ensure there are no obvious console errors.
16. Test desktop and mobile behavior before considering the task complete.

---

## 38. Definition of Done

A user can:

```text
1. Open VietNorm
2. Enter up to 500 characters of informal Vietnamese
3. Normalize it
4. See the normalized result
5. Copy the result
6. Compare source and normalized text in a separate highlighted Difference Box
7. Try built-in examples
8. Re-edit the normalized result
9. Access the last 10 successful normalizations
10. Use the app comfortably on desktop and mobile
```

The product should communicate one idea extremely clearly:

> **VietNorm transforms informal Vietnamese into standard Vietnamese.**
