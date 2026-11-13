# Báo cáo cá nhân — Day 6

- Họ và tên: Nguyễn Quang Duy
- MSSV: 2A202603462
- Lớp: L3A
- Thời điểm chạy: 2026-11-13, ingest lúc 17:54, eval lúc 17:57


## Dữ liệu và pipeline

### Chủ đề, nguồn/quyền, số trang và quy tắc tính trang

- **Chủ đề:** thu thập, chuẩn bị dữ liệu và đạo đức trong vòng đời khoa học dữ liệu.
- **Nguồn:** sách *Principles of Data Science* (OpenStax, ©2025 Rice University), file `data/Book2.pdf`, tải từ <https://openstax.org/details/books/principles-data-science> ngày 2026-11-13. Bản PDF tạo ngày 2026-04-20, 569 trang vật lý.
- **Quyền:** CC BY-NC-SA 4.0 (ghi ở trang 4 của PDF). Dùng cho mục đích học tập, phi thương mại. Access for free at openstax.org.
- **Phạm vi dùng:**

| Section (trường lọc) | Nội dung | Trang PDF | Số trang |
|---|---|---|---|
| `chapter_2_collecting_preparing_data` | Chapter 2, mục 2.1–2.5 | 67–103 | 37 |
| `chapter_8_ethics` | Chapter 8, mục 8.1–8.3 | 387–412 | 26 |

- **Tổng: 63 trang nội dung** (yêu cầu ≥ 30). Danh sách trang và số ký tự từng trang: `results/content_pages.csv`. Manifest: `data/manifest.json`.
- **Quy tắc tính trang:** chỉ tính trang vật lý của PDF nằm trong hai khoảng trên và có ≥ 200 ký tự sau chuẩn hóa. Không tính bìa, mục lục, lời nói đầu, Key Terms, bài tập cuối chương, References và các chương khác.
- **Lưu ý về số trang:** `page` là số trang vật lý của PDF, không phải số in trên trang sách. Trong phạm vi đã dùng, số in trên sách = số trang PDF − 10 (ví dụ trang PDF 92 in số 82, trang PDF 410 in số 400).

### Chuẩn hóa, lỗi và giới hạn

- Đọc PDF bằng `pypdf` 6.21.4, mỗi trang vật lý thành một `DocumentPage`; chỉ trích các trang ghi trong manifest.
- Chuẩn hóa (`starter/src/ingestion.py`): Unicode NFC, đổi khoảng trắng không ngắt thành khoảng trắng thường, nối từ bị ngắt dòng bằng gạch nối, gộp khoảng trắng, xuống dòng đơn thành dấu cách.
- Lỗi đọc: 0 trang rỗng, 0 trang lỗi, 0 trang bị bỏ qua (`results/ingest_errors.json`). Không cần OCR.
- Giới hạn đã biết:
  - `pypdf` không trả về dòng trống giữa các đoạn nên toàn bộ trang thành một khối; ranh giới đoạn bị mất.
  - Dòng đầu/cuối trang của sách vẫn nằm trong text (ví dụ "82 2 • Collecting and Preparing Data Access for free at openstax.org").
  - Bảng bị dàn phẳng thành một dòng, mất ranh giới cột.
  - Hình ảnh không được trích; chỉ còn chú thích.

### Embedding model, vector store, metric, lệnh chạy và chi phí

| Hạng mục | Giá trị |
|---|---|
| Embedding model | `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`, chạy local trên CPU |
| Thư viện | `sentence-transformers` 6.3.0, `torch` 2.15.0 |
| Số chiều | 384 |
| Xử lý query/document | Cùng một hàm `encode`, không thêm tiền tố, chuẩn hóa vector về độ dài 1 |
| Vector store | Chroma 1.5.9, `PersistentClient` lưu tại thư mục `chroma_db/` |
| Collection | `day06_fixed` (cấu hình A), `day06_paragraph` (cấu hình B và C) |
| Metric và kiểu tìm kiếm | Cosine, chỉ mục HNSW (approximate search), tham số mặc định; `score = 1 − distance` |
| Python | 3.14 (môi trường ảo `.venv`) |
| Chi phí | 0 USD (không dùng API trả phí) |

Lệnh chạy, từ thư mục `starter/` sau khi kích hoạt môi trường ảo và `pip install -r requirements.txt`:

```powershell
python -m src.run check    # kiểm tra corpus và evidence của benchmark
python -m src.run ingest   # chunk, embed, lưu Chroma cho A và B
python -m src.run eval     # top-3, trace, Hit@1/Hit@3, bảng chấm tay
```

**Nạp lại không nhân đôi:** `chunk_id` có dạng `{document_id}-p{trang}-{fix|par}-{thứ tự}` nên ổn định giữa các lần chạy; ghi bằng `upsert` và xóa các ID không còn tồn tại. Lệnh `ingest` đã chạy hai lần liên tiếp; lần hai số bản ghi vẫn là 464 (A) và 489 (B), số chunk cũ bị xóa là 0 (`results/ingest_stats.json`). Khi tài liệu thay đổi, chunk có ID không còn xuất hiện sẽ bị xóa khỏi collection.

### Metadata bắt buộc, trường lọc bổ sung, nguồn giá trị và lý do chọn

| Trường | Kiểu | Nguồn giá trị |
|---|---|---|
| `document_id` | chuỗi | `source_id` trong manifest (`openstax-data-science`) |
| `source` | chuỗi | tên file PDF (`Book2.pdf`) |
| `page` | số nguyên | số trang vật lý của PDF |
| `section` (trường lọc) | chuỗi | khoảng trang của từng chương trong manifest, lấy theo mục lục của PDF |
| `title` | chuỗi | tên sách trong manifest |

Chọn `section` làm trường lọc vì hai chương cùng nói về dữ liệu và có các khái niệm trùng nhau (data collection, outliers, data validation), nên câu hỏi dễ lấy nhầm chương nếu không giới hạn phạm vi.

## Cấu hình và benchmark

### A / B / C

| Cấu hình | Chunking | Tham số | Filter |
|---|---|---|---|
| A | Cửa sổ ký tự cố định, theo từng trang | 500 ký tự, overlap 50 | Không |
| B | Gom theo đoạn/câu, không cắt giữa câu, theo từng trang | tối đa 500 ký tự, không overlap | Không |
| C | Giống hệt B (dùng chung collection) | như B | `section`, chỉ áp dụng cho câu hỏi có trường `filter` |

- **A–B** chỉ khác cách chunk. **B–C** chỉ khác việc áp dụng filter: đây là khác biệt duy nhất, vì C truy vấn đúng collection của B.
- Vì `pypdf` không giữ dòng trống, B trên thực tế tách theo câu (dấu `. ! ? … : ;`) rồi gom lại tới 500 ký tự.

### Bộ câu hỏi

- 20 câu, tiếng Anh (cùng ngôn ngữ với corpus): `benchmark/questions.json`.
- Tách **15 dev / 5 test** trước khi chạy truy xuất với model thật. Chương 2: 12 câu; chương 8: 8 câu.
- Loại câu: 8 trực tiếp, 5 diễn đạt lại, 3 điều kiện/ngoại lệ, 4 có metadata filter (q01, q09, q13 thuộc dev; q20 thuộc test).
- Filter là input giả định có trước khi truy xuất: người dùng đang hỏi trong phạm vi một chương. Giá trị filter không chứa đáp án hay trang gold.
- **Kiểm chứng evidence:** lệnh `python -m src.run check` so từng `evidence_quote` với text đã chuẩn hóa của đúng `gold_page`; cả 20 câu khớp. `<điền: học viên đã đối chiếu tay những câu nào với PDF>`
- **Nguy cơ rò rỉ:** dev và test lấy từ cùng hai chương, nên test không độc lập về chủ đề với dev.

### Tiêu chí chọn chiến lược đã chốt trước khi xem test

Ưu tiên Evidence Hit@3 trên dev; nếu bằng nhau thì xét grounding; sau đó tới số chunk và thời gian ingest.

## Kết quả

| Strategy | Split | Hit@1 (n/N) | Evidence Hit@3 (n/N) | Chunk count | Thời gian | Chi phí |
|---|---|---|---|---|---|---|
| A | dev | 5/15 | 10/15 | 464 | 25.09 s | 0 |
| A | test | 2/5 | 3/5 | 464 | 25.09 s | 0 |
| B | dev | 5/15 | 9/15 | 489 | 27.76 s | 0 |
| B | test | 3/5 | 4/5 | 489 | 27.76 s | 0 |
| C | dev | 5/15 | 9/15 | 489 (chung với B) | không ingest riêng | 0 |
| C | test | 3/5 | 4/5 | 489 (chung với B) | không ingest riêng | 0 |

Thời gian là thời gian ingest (chunk, embed, ghi Chroma) đo một lần trên CPU. Phân bố độ dài chunk: A từ 57 đến 500 ký tự, trung vị 500, tổng 217 568 ký tự; B từ 40 đến 500, trung vị 425, tổng 197 203 ký tự.

| Strategy | Coherence trung bình /2 (n) | Metadata đủ và đúng (n/N) | Filter tuân thủ (n/N hoặc N/A) | Grounding 0/1/2 (số câu) và trung bình /2 |
|---|---|---|---|---|
| A | 1.2 (n = 10) | 15/15 | N/A | 0 / 2 / 3, trung bình 1.6 |
| B | 1.4 (n = 10) | 15/15 | N/A | 0 / 1 / 4, trung bình 1.8 |
| C | 1.4 (n = 10, cùng chunk với B) | 15/15 | test 1/1 (dev 3/3) | 0 / 1 / 4, trung bình 1.8 |

### Đường dẫn trace, nhãn thủ công và cách chọn mẫu

- Trace top-3 đầy đủ: `results/trace_A.json`, `results/trace_B.json`, `results/trace_C.json`. Tổng hợp: `results/summary.json`. Thống kê ingest: `results/ingest_stats.json`.
- **Coherence** (`results/audit_coherence.csv`): 10 vị trí là 10 trang nội dung đầu tiên theo thứ tự (trang PDF 67–76), xác định trước khi xem điểm; với mỗi trang chấm chunk đầu tiên của A và của B. C dùng chung chunk với B.
- **Metadata** (`results/audit_metadata.csv`): 5 câu test × top-3 × 3 cấu hình = 45 bản ghi. Mỗi bản ghi được kiểm tra: toàn bộ text của chunk có nằm ở đúng trang PDF ghi trong `page` không (trích lại trang đó từ PDF rồi so khớp), trang có thuộc đúng chương theo mục lục không, và `source` có đúng file không.
- **Grounding** (`results/audit_grounding.csv`): 5 câu test × 3 cấu hình, chấm trên cả top-3 theo thang 0–2 của GUIDE.

## Phân tích và kết luận

### So sánh A–B (thay cách chunk)

- **Retrieval:** A hơn B một câu trên dev (10/15 so với 9/15), B hơn A một câu trên test (4/5 so với 3/5). Chênh lệch một câu, theo hai hướng ngược nhau, không đủ để kết luận cách nào tốt hơn.
- A trúng mà B trượt: q06, q10. B trúng mà A trượt: q01, q20.
- **Coherence:** B cao hơn (1.4 so với 1.2). Cả 10 chunk mẫu của A đều kết thúc giữa từ (trong đó 2 chunk vẫn giữ trọn ý chính); chunk của B kết thúc đúng cuối câu trừ khi gặp bảng.
- **Grounding:** B cao hơn (1.8 so với 1.6), khác nhau ở q20.
- **Tài nguyên:** B nhiều hơn 25 chunk (489 so với 464) và ingest lâu hơn khoảng 2.7 giây; A lưu nhiều ký tự hơn do overlap.

### So sánh B–C (thêm filter)

- Số Hit giống hệt nhau trên cả dev và test. Ba câu có filter q01, q13, q20 thì B đã trúng sẵn; q09 thì filter không cứu được.
- Filter hoạt động đúng: 4/4 câu có filter trả về top-3 nằm trọn trong chương được yêu cầu.
- Tác dụng nhìn thấy được là ở thành phần top-3 chứ không ở số Hit: với q20, B còn hai chunk của chương 2 ở hạng 2–3, còn C trả về cả ba chunk thuộc chương 8.

### Hai ví dụ sai

1. **q05 (dev, gold: `openstax-data-science` trang 76), lỗi do ranh giới chunk, trượt ở cả A, B, C.** Evidence gồm hai câu liền nhau: tên kỹ thuật ("…is called stratified sampling.") và phần mô tả ("This involves dividing the population into subgroups or strata…"). A cắt ngang câu đầu; B tách đúng tại ranh giới câu, nên chunk hạng 1 của B (`…-p0076-par-002`, score 0.857) có phần mô tả nhưng thiếu tên kỹ thuật. Không chunk nào chứa trọn evidence.
2. **q09 (dev, có filter, gold trang 87), lỗi xếp hạng, trượt ở cả A, B, C.** Chunk gold tồn tại (`…-p0087-par-001`) nhưng không vào top-3. B trả về hai chunk của chương 8 ở hạng 1–2 (trang 403 và 400). C có filter nên top-3 đều thuộc chương 2 (trang 87, 87, 91), nhưng là các đoạn nói về xử lý outlier chứ không phải đoạn nêu cách nhận diện. Filter thu hẹp đúng phạm vi nhưng không sửa được xếp hạng trong phạm vi đó.

Ví dụ trên test: **q16** (gold trang 74) trượt ở cả ba cấu hình. Chunk hạng 3 có ý "hard-to-reach populations" nhưng tên "snowball sampling" nằm ở chunk liền trước, nên grounding chỉ đạt mức 1.

### Chiến lược chọn, đánh đổi, điều kiện áp dụng

- Theo tiêu chí đã chốt trước (Evidence Hit@3 trên dev), **chọn A** (10/15 so với 9/15).
- Kết quả test không dùng để đổi lựa chọn. Trên test, B và C nhỉnh hơn A (4/5 so với 3/5) và có coherence, grounding cao hơn, nên lựa chọn A không vững: nó dựa trên chênh lệch đúng một câu.
- Đánh đổi: A đơn giản, ít chunk hơn, nhưng chunk hay bị cắt giữa câu; B và C cho chunk dễ đọc hơn nhưng tách tiêu đề hoặc tên khái niệm khỏi câu mô tả.
- Filter của C chỉ dùng được khi người dùng hoặc ứng dụng cung cấp sẵn phạm vi chương trước khi truy xuất.
- Các nhận xét này chỉ đúng với corpus 63 trang và 20 câu hỏi này, không suy rộng.

### Hạn chế

- **Mẫu nhỏ:** test chỉ có 5 câu, mỗi câu tương ứng 20 điểm phần trăm; dev 15 câu. Chưa tính khoảng tin cậy.
- **Bộ câu hỏi:** do AI soạn và học viên rà soát; evidence của q05 và q10 trải trên hai câu nên bất lợi cho cách chunk theo câu; dev và test cùng nguồn.
- **Định nghĩa hit chặt:** chunk phải đúng trang và chứa trọn evidence, nên một chunk liền kề có nội dung gần đúng vẫn tính là trượt (q02, q06, q16).
- **Chunking của B:** coi dấu `:` và `;` là ranh giới câu nên sinh ra mẩu ngắn (ví dụ chú thích hình bị cắt tại "(credit:"); bảng không có dấu câu nên bị cắt cứng.
- **Chunk theo từng trang:** câu vắt qua hai trang bị tách (nhiều chunk mở đầu bằng mẩu câu của trang trước).
- **Model:** `paraphrase-multilingual-MiniLM-L12-v2` có giới hạn độ dài đầu vào (mặc định 128 token theo tài liệu model; chưa kiểm tra lại bằng `model.max_seq_length`), nên chunk gần 500 ký tự có thể bị cắt bớt khi embed.
- **Nhãn thủ công:** một nguồn chấm, không chấm độc lập với điểm số, có nguy cơ thiên lệch như nêu ở trên.
- **Thời gian:** đo một lần trên một máy, không lặp lại; lần đầu còn gồm thời gian nạp model.
- **Tìm kiếm xấp xỉ:** HNSW có thể bỏ sót láng giềng gần nhất; chưa so với exact search.

### Nếu làm lại hoặc mở rộng

- Chunk xuyên trang thay vì theo từng trang, và giữ tiêu đề mục đi kèm đoạn nội dung ngay sau nó.
- Bỏ `:` và `;` khỏi danh sách dấu tách câu; xử lý bảng riêng; lọc dòng đầu/cuối trang trước khi chunk.
- Thêm metadata mục con (2.1, 2.2, …) lấy từ mục lục PDF để lọc mịn hơn.
- Thử hybrid retrieval (dense + BM25) cho các câu hỏi chứa thuật ngữ cụ thể như q16.
- Mở rộng bộ test và tạo tập test mới từ chương khác để giảm rò rỉ; nhờ người thứ hai chấm độc lập.
