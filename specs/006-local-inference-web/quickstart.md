# Nghiệm thu nhanh Phase 6

```powershell
Set-Location 'D:\University\Năm 3 ĐH\Kì 3 (18th6)\Statiscal Learning\VisolexNorm'
.venv\Scripts\python.exe -m pip install -r requirements-inference.txt
.venv\Scripts\python.exe -m visolexnorm.app.inference --smoke
.venv\Scripts\python.exe -m visolexnorm.app.inference --text "mik ko bt hnay đi hc ko"
.venv\Scripts\python.exe -m visolexnorm.app.web
```

Mở URL `http://127.0.0.1:7860` do Gradio in ra trên terminal. App chỉ bind loopback và không
tạo public share link. Dùng `--port 7861` nếu cổng mặc định đang bận.

Nghiệm thu lần lượt input rỗng, câu chuẩn, teencode, viết tắt, Unicode và nhiều lần liên tiếp.
Lần chuẩn hóa đầu tiên có thể chậm vì app nạp checkpoint BARTpho local; các lượt sau phải tái sử
dụng runtime đã xác minh. Nút `Xóa` phải xóa cả input, output và đưa trạng thái về “Sẵn sàng”.

Tắt mạng sau khi checkpoint và dependency đã có local, sau đó xác nhận CLI và web vẫn chuẩn hóa
được. App không cần Kaggle, dataset, Gemini API hoặc truy cập Hugging Face Hub.