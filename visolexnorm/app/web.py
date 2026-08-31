"""Local Gradio interface for ViSoLexNorm lexical normalization."""

from __future__ import annotations

import argparse
import logging

from visolexnorm.app import inference


LOGGER = logging.getLogger(__name__)
LOCAL_HOST = "127.0.0.1"
READY_STATUS = "Sẵn sàng. Lần đầu xử lý có thể chậm do cần nạp mô hình."

CUSTOM_CSS = """
:root { --app-ink: #172554; --app-muted: #64748b; --app-primary: #4f46e5; }
.gradio-container { max-width: 1120px !important; margin: 0 auto !important; background: #f8fafc; }
.hero { background: linear-gradient(135deg, #312e81, #2563eb); border-radius: 24px; color: white;
        margin: 16px 0 24px; padding: 30px 34px; box-shadow: 0 16px 32px rgba(49, 46, 129, .20); }
.hero h1 { font-size: 2rem; font-weight: 750; letter-spacing: -.03em; margin: 0 0 6px; }
.hero p { font-size: 1rem; line-height: 1.55; margin: 0; opacity: .92; }
.badges { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 17px; }
.badge { background: rgba(255,255,255,.16); border: 1px solid rgba(255,255,255,.25); border-radius: 999px;
         font-size: .82rem; padding: 5px 10px; }
.panel { background: white; border: 1px solid #e2e8f0; border-radius: 20px; padding: 8px 16px 16px;
         box-shadow: 0 8px 22px rgba(15, 23, 42, .05); }
.panel h2 { color: var(--app-ink); font-size: 1rem; font-weight: 700; margin: 10px 0 2px; }
.panel .hint { color: var(--app-muted); font-size: .85rem; margin: 0 0 12px; }
#normalize-button { background: linear-gradient(135deg, #4f46e5, #2563eb); border: none; color: white; }
#status { min-height: 28px; color: #475569; font-size: .9rem; }
.privacy-note { color: #64748b; font-size: .84rem; margin: 12px 4px 0; text-align: center; }
@media (max-width: 640px) { .hero { border-radius: 18px; padding: 24px 20px; } .hero h1 { font-size: 1.55rem; } }
"""

EXAMPLES = [
    ["mik ko bt hnay đi hc ko"],
    ["t cx ko bik nua"],
    ["hnay tr troi dep wa"],
]


def normalize_text(text: str) -> tuple[str, str]:
    """UI callback that exposes safe Vietnamese messages rather than exceptions."""
    try:
        result = inference.normalize(text)
    except inference.InputValidationError as error:
        return "", str(error)
    except (FileNotFoundError, RuntimeError, ValueError) as error:
        LOGGER.exception("Local normalization failed: %s", error)
        return "", "Không thể chuẩn hóa lúc này. Hãy kiểm tra mô hình và thử lại."
    return result, "✓ Đã chuẩn hóa thành công trên thiết bị này."


def clear_text() -> tuple[str, str, str]:
    """Clear both text areas and restore the initial local-app status."""
    return "", "", READY_STATUS


def create_demo() -> object:
    """Create the local-only responsive Gradio application without starting it."""
    try:
        import gradio as gr
    except ImportError as error:
        raise RuntimeError("Chưa cài Gradio. Hãy cài requirements-inference.txt rồi thử lại.") from error

    with gr.Blocks(title="ViSoLexNorm") as demo:
        gr.HTML(
            "<section class='hero'><h1>ViSoLexNorm</h1>"
            "<p>Chuẩn hóa từ vựng tiếng Việt mạng xã hội bằng BARTpho.</p>"
            "<div class='badges'><span class='badge'>● Chạy local</span>"
            "<span class='badge'>Model C</span><span class='badge'>Không gọi LLM API</span></div></section>"
        )
        with gr.Row(equal_height=True):
            with gr.Column(elem_classes="panel"):
                gr.HTML("<h2>Văn bản gốc</h2><p class='hint'>Tối đa 128 token. Không gửi dữ liệu ra ngoài thiết bị.</p>")
                source = gr.Textbox(
                    label="Nhập câu cần chuẩn hóa",
                    placeholder="Ví dụ: mik ko bt hnay đi hc ko",
                    lines=8,
                )
                with gr.Row():
                    normalize_button = gr.Button("Normalize", variant="primary", elem_id="normalize-button")
                    clear_button = gr.Button("Xóa", variant="secondary")
            with gr.Column(elem_classes="panel"):
                gr.HTML("<h2>Kết quả chuẩn hóa</h2><p class='hint'>Kết quả được tạo bởi checkpoint đã xác minh.</p>")
                result = gr.Textbox(label="Kết quả", lines=8, interactive=False)
                status = gr.Markdown(READY_STATUS, elem_id="status")
        normalize_button.click(normalize_text, inputs=source, outputs=[result, status], concurrency_limit=1)
        clear_button.click(clear_text, outputs=[source, result, status], queue=False)
        gr.Examples(examples=EXAMPLES, inputs=source, label="Thử nhanh")
        gr.Markdown(
            "<p class='privacy-note'>Mô hình chạy hoàn toàn trên thiết bị này. "
            "Ứng dụng không dùng Kaggle, dataset hay Gemini API.</p>"
        )
        with gr.Accordion("Hướng dẫn", open=False):
            gr.Markdown(
                "Nhập một câu tiếng Việt mạng xã hội rồi nhấn **Normalize**. "
                "Ứng dụng chỉ chuẩn hóa từ vựng như teencode, viết tắt và lỗi chính tả; "
                "không chủ động diễn đạt lại nội dung."
            )
    return demo.queue(default_concurrency_limit=1)


def launch_demo(demo: object, *, port: int | None = None) -> object:
    """Launch the styled app only on the local loopback interface."""
    try:
        import gradio as gr
    except ImportError as error:
        raise RuntimeError("Chưa cài Gradio. Hãy cài requirements-inference.txt rồi thử lại.") from error
    theme = gr.themes.Soft(primary_hue="indigo", secondary_hue="blue", neutral_hue="slate")
    return demo.launch(
        server_name=LOCAL_HOST,
        server_port=port,
        share=False,
        theme=theme,
        css=CUSTOM_CSS,
    )


def main() -> None:
    """Start the application on the loopback interface only."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=None, help="Cổng local tùy chọn.")
    args = parser.parse_args()
    launch_demo(create_demo(), port=args.port)


if __name__ == "__main__":
    main()