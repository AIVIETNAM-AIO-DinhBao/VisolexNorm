import React from 'react';

export const AboutPage: React.FC = () => {
  return (
    <main className="mx-auto w-full max-w-3xl flex-1 px-4 py-10 sm:px-6 sm:py-14">
      <article className="space-y-12">
        {/* Header / Intro */}
        <header className="space-y-3">
          <h1 className="font-serif text-3xl font-normal tracking-tight text-ink sm:text-4xl">
            Giới thiệu VisolexNorm
          </h1>
          <p className="text-base leading-relaxed text-muted sm:text-lg">
            Hệ thống chuẩn hóa từ vựng tiếng Việt mạng xã hội (*ViSoLexNorm*) dựa trên kiến trúc mô hình ngôn ngữ BARTpho.
          </p>
        </header>

        {/* 1. Bài toán */}
        <section aria-labelledby="problem-heading" className="space-y-4">
          <h2
            id="problem-heading"
            className="font-serif text-2xl font-normal tracking-tight text-ink border-b border-hairline pb-2"
          >
            1. Bài toán chuẩn hóa từ vựng
          </h2>
          <p className="text-sm leading-relaxed text-body sm:text-base">
            Văn bản trên mạng xã hội tiếng Việt thường chứa nhiều dạng viết tắt, teencode, từ lóng (slang), thiếu dấu thanh và lỗi chính tả từ vựng. <strong>VisolexNorm</strong> được thiết kế nhằm chuẩn hóa tự động các từ ngữ này về dạng tiếng Việt chuẩn mực, giúp cải thiện chất lượng cho các tác vụ xử lý ngôn ngữ tự nhiên phía sau như phân tích cảm xúc, dịch máy hay trích xuất thông tin.
          </p>
          <div className="rounded-lg border border-hairline bg-surface-card p-4 text-sm text-body">
            <p className="font-medium text-ink mb-1.5">Nguyên tắc chuẩn hóa:</p>
            <ul className="list-disc list-inside space-y-1 text-muted text-xs sm:text-sm">
              <li>Tập trung chuẩn hóa từ vựng, viết tắt, teencode và dấu tiếng Việt.</li>
              <li>Giữ nguyên ngữ nghĩa gốc, không paraphrase, không thay đổi sắc thái (sentiment).</li>
              <li>Không tự ý thêm thông tin ngoài ngữ cảnh hoặc tự kiểm duyệt nội dung.</li>
            </ul>
          </div>
        </section>

        {/* 2. Cách hệ thống hoạt động */}
        <section aria-labelledby="workflow-heading" className="space-y-4">
          <h2
            id="workflow-heading"
            className="font-serif text-2xl font-normal tracking-tight text-ink border-b border-hairline pb-2"
          >
            2. Quy trình xử lý
          </h2>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 text-center">
            <div className="rounded-lg border border-hairline bg-white p-4 shadow-2xs">
              <span className="text-xs font-semibold uppercase tracking-wider text-muted">Bước 1</span>
              <p className="mt-1 font-medium text-ink text-sm">Văn bản đầu vào</p>
              <p className="mt-1 text-xs text-muted">Nhận văn bản chứa teencode, viết tắt</p>
            </div>
            <div className="rounded-lg border border-hairline bg-white p-4 shadow-2xs">
              <span className="text-xs font-semibold uppercase tracking-wider text-muted">Bước 2</span>
              <p className="mt-1 font-medium text-ink text-sm">Suy luận Seq2Seq</p>
              <p className="mt-1 text-xs text-muted">Mô hình BARTpho xử lý hoàn toàn offline</p>
            </div>
            <div className="rounded-lg border border-hairline bg-white p-4 shadow-2xs">
              <span className="text-xs font-semibold uppercase tracking-wider text-muted">Bước 3</span>
              <p className="mt-1 font-medium text-ink text-sm">Văn bản chuẩn hóa</p>
              <p className="mt-1 text-xs text-muted">Trả về tiếng Việt đúng chuẩn và tự nhiên</p>
            </div>
          </div>
        </section>

        {/* 3. Mô hình & Phương pháp */}
        <section aria-labelledby="model-heading" className="space-y-4">
          <h2
            id="model-heading"
            className="font-serif text-2xl font-normal tracking-tight text-ink border-b border-hairline pb-2"
          >
            3. Mô hình & Phương pháp huấn luyện
          </h2>
          <p className="text-sm leading-relaxed text-body sm:text-base">
            Hệ thống sử dụng kiến trúc Seq2Seq trên nền tảng mô hình tiền huấn luyện <strong>BARTpho</strong> cho tiếng Việt, kết hợp kỹ thuật học bán giám sát (Weak Supervision) với quy trình kiểm duyệt nhãn nghiêm ngặt:
          </p>
          <div className="space-y-3">
            <div className="rounded-lg border border-hairline bg-white p-4">
              <p className="text-sm font-semibold text-ink">Model A (Baseline)</p>
              <p className="text-xs sm:text-sm text-muted mt-1">
                Được huấn luyện có giám sát trực tiếp trên tập dữ liệu chuẩn mực ViLexNorm Train.
              </p>
            </div>
            <div className="rounded-lg border border-hairline bg-white p-4">
              <p className="text-sm font-semibold text-ink">Weak-Label Review (Gemini LLM)</p>
              <p className="text-xs sm:text-sm text-muted mt-1">
                Model A tạo candidate từ các câu chưa gán nhãn trong tập ViSoLex. Mỗi candidate được kiểm duyệt độc lập theo 3 quyết định: <code>KEEP</code> (giữ nguyên), <code>EDIT</code> (sửa tối thiểu) hoặc <code>REJECT</code> (loại bỏ khỏi tập huấn luyện).
              </p>
            </div>
            <div className="rounded-lg border border-hairline bg-white p-4">
              <p className="text-sm font-semibold text-ink">Model C (Mô hình triển khai hiện tại)</p>
              <p className="text-xs sm:text-sm text-muted mt-1">
                Huấn luyện mở rộng kết hợp ViLexNorm Train và 64.813 weak-labels đã được kiểm duyệt, là checkpoint hoạt động mặc định của ứng dụng (với Model B là bản dự phòng rollback).
              </p>
            </div>
          </div>
        </section>

        {/* 4. Dữ liệu */}
        <section aria-labelledby="dataset-heading" className="space-y-4">
          <h2
            id="dataset-heading"
            className="font-serif text-2xl font-normal tracking-tight text-ink border-b border-hairline pb-2"
          >
            4. Dữ liệu thực nghiệm
          </h2>
          <p className="text-sm leading-relaxed text-body sm:text-base">
            Dự án kết hợp giữa tập dữ liệu chuẩn hóa có nhãn <strong>ViLexNorm</strong> và tập dữ liệu mạng xã hội <strong>ViSoLex Canonical</strong> (đã lọc trùng và tiền xử lý):
          </p>

          <div className="overflow-x-auto rounded-lg border border-hairline bg-white">
            <table className="w-full text-left text-xs sm:text-sm border-collapse">
              <thead>
                <tr className="border-b border-hairline bg-surface-soft/60 text-muted">
                  <th className="p-3 font-semibold">Tập dữ liệu / Nguồn</th>
                  <th className="p-3 font-semibold text-right">Số lượng câu</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-hairline text-body">
                <tr>
                  <td className="p-3 font-medium">ViLexNorm Train</td>
                  <td className="p-3 font-mono text-right">8.372</td>
                </tr>
                <tr>
                  <td className="p-3 font-medium">ViLexNorm Dev</td>
                  <td className="p-3 font-mono text-right">1.050</td>
                </tr>
                <tr>
                  <td className="p-3 font-medium">ViLexNorm Test (Đóng băng)</td>
                  <td className="p-3 font-mono text-right">1.045</td>
                </tr>
                <tr>
                  <td className="p-3 font-medium">ViSoLex Canonical (Tổng hợp từ ViHSD, UIT-VSMEC, ViSpamReviews, UIT-ViSFD)</td>
                  <td className="p-3 font-mono text-right">68.411</td>
                </tr>
                <tr className="bg-surface-card/40 font-semibold text-ink">
                  <td className="p-3">Weak labels được duyệt cho Model C</td>
                  <td className="p-3 font-mono text-right">64.813</td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>

        {/* 5. Đánh giá */}
        <section aria-labelledby="eval-heading" className="space-y-4">
          <h2
            id="eval-heading"
            className="font-serif text-2xl font-normal tracking-tight text-ink border-b border-hairline pb-2"
          >
            5. Kết quả đánh giá
          </h2>
          <p className="text-sm leading-relaxed text-body sm:text-base">
            Kết quả khoa học chính thức trên tập kiểm thử độc lập đóng băng <strong>ViLexNorm Test</strong> (Phase 5):
          </p>

          <div className="overflow-x-auto rounded-lg border border-hairline bg-white">
            <table className="w-full text-left text-xs sm:text-sm border-collapse">
              <thead>
                <tr className="border-b border-hairline bg-surface-soft/60 text-muted">
                  <th className="p-3 font-semibold">Mô hình</th>
                  <th className="p-3 font-semibold text-right">ERR</th>
                  <th className="p-3 font-semibold text-right">Precision</th>
                  <th className="p-3 font-semibold text-right">Recall</th>
                  <th className="p-3 font-semibold text-right">F1 Score</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-hairline font-mono text-body">
                <tr>
                  <td className="p-3 font-sans font-medium">Model A (Baseline)</td>
                  <td className="p-3 text-right">0.7030</td>
                  <td className="p-3 text-right">0.7340</td>
                  <td className="p-3 text-right">0.7030</td>
                  <td className="p-3 text-right">0.7182</td>
                </tr>
                <tr className="bg-surface-card/40 font-semibold text-ink">
                  <td className="p-3 font-sans">Model B (Weak Supervised)</td>
                  <td className="p-3 text-right">0.7238</td>
                  <td className="p-3 text-right">0.7615</td>
                  <td className="p-3 text-right">0.7238</td>
                  <td className="p-3 text-right">0.7422</td>
                </tr>
              </tbody>
            </table>
          </div>

          <p className="text-xs text-muted leading-relaxed">
            * Tại Phase 9 hậu kiểm mô tả, Model C đạt điểm F1 là 0.7650 (+0.0228 F1 so với Model B, khoảng tin cậy Bootstrap 95% [0.0121, 0.0332]) và được chọn làm checkpoint triển khai ứng dụng.
          </p>
        </section>

        {/* 6. Ví dụ chuẩn hóa */}
        <section aria-labelledby="examples-heading" className="space-y-4">
          <h2
            id="examples-heading"
            className="font-serif text-2xl font-normal tracking-tight text-ink border-b border-hairline pb-2"
          >
            6. Một số ví dụ tiêu biểu
          </h2>
          <div className="space-y-2 text-xs sm:text-sm font-mono">
            <div className="rounded-md border border-hairline bg-surface-card p-3">
              <span className="text-muted">Gốc: </span>
              <span className="text-body">hnay t di hoc</span>
              <br />
              <span className="text-muted">Chuẩn hóa: </span>
              <span className="font-semibold text-ink">hôm nay tôi đi học</span>
            </div>
            <div className="rounded-md border border-hairline bg-surface-card p-3">
              <span className="text-muted">Gốc: </span>
              <span className="text-body">mik ko bt hnay đi hc ko</span>
              <br />
              <span className="text-muted">Chuẩn hóa: </span>
              <span className="font-semibold text-ink">mình không biết hôm nay đi học không</span>
            </div>
            <div className="rounded-md border border-hairline bg-surface-card p-3">
              <span className="text-muted">Gốc: </span>
              <span className="text-body">tks b nhieu nha</span>
              <br />
              <span className="text-muted">Chuẩn hóa: </span>
              <span className="font-semibold text-ink">cảm ơn bạn nhiều nha</span>
            </div>
          </div>
        </section>

        {/* 7. Thông tin dự án */}
        <section aria-labelledby="team-heading" className="space-y-3 pt-4 border-t border-hairline text-xs text-muted">
          <p>
            Dự án nghiên cứu & phát triển hệ thống chuẩn hóa từ vựng tiếng Việt VisolexNorm.
          </p>
          <p>
            Mã nguồn & Checkpoint: Phiên bản Release v1.0.0 (Copyright &copy; 2026 AIVIETNAM-AIO-DinhBao).
          </p>
        </section>
      </article>
    </main>
  );
};
