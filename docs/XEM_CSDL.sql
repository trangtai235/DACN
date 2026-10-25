-- Mở bằng Query Tool của pgAdmin, kết nối database annotaflow.
-- Bôi đen từng câu SELECT rồi bấm Execute để xem từng kết quả riêng.

-- 1. Xác nhận database đang kết nối.
SELECT current_database() AS database_dang_mo,
       current_user AS tai_khoan,
       version() AS phien_ban;

-- 2. Danh sách dự án và số bình luận mỗi dự án.
SELECT p.id, p.name AS du_an, COUNT(c.id) AS so_binh_luan
FROM core_project AS p
LEFT JOIN core_comment AS c ON c.project_id = p.id
GROUP BY p.id, p.name
ORDER BY p.id;

-- 3. Bình luận và nguồn dữ liệu.
SELECT c.id, p.name AS du_an, s.name AS nguon,
       c.text AS binh_luan, c.created_at AS ngay_nhap
FROM core_comment AS c
JOIN core_project AS p ON p.id = c.project_id
JOIN core_source AS s ON s.id = c.source_id
ORDER BY c.id
LIMIT 50;

-- 4. Kết quả ML Local và LLM cùng bình luận của từng lượt.
-- Văn bản lấy từ bản chụp khi chạy, nên vẫn đúng nếu bình luận gốc đã thay đổi.
SELECT ml.run_id AS luot_chay,
       ml.item_index + 1 AS stt,
       r.items -> ml.item_index ->> 'text' AS binh_luan,
       ml.label AS nhan_ml_local,
       llm.label AS nhan_llm,
       ROUND(ml.latency_ms::numeric, 2) AS ml_mili_giay,
       ROUND(llm.latency_ms::numeric, 2) AS llm_mili_giay,
       CASE WHEN llm.id IS NULL THEN 'Chưa có kết quả LLM'
            WHEN ml.label = llm.label THEN 'Cùng nhãn'
            ELSE 'Khác nhãn' END AS so_sanh
FROM studio_autolabelresult AS ml
JOIN studio_autolabelrun AS r ON r.id = ml.run_id
LEFT JOIN studio_autolabelresult AS llm
  ON llm.run_id = ml.run_id
 AND llm.item_index = ml.item_index
 AND llm.branch = 'llm'
WHERE ml.branch = 'local'
ORDER BY ml.run_id DESC, ml.item_index
LIMIT 50;

-- 5. Chỉ xem những bình luận có đủ hai kết quả và khác nhãn.
SELECT ml.run_id AS luot_chay,
       r.items -> ml.item_index ->> 'text' AS binh_luan,
       ml.label AS nhan_ml_local, llm.label AS nhan_llm
FROM studio_autolabelresult AS ml
JOIN studio_autolabelrun AS r ON r.id = ml.run_id
JOIN studio_autolabelresult AS llm
  ON llm.run_id = ml.run_id
 AND llm.item_index = ml.item_index
 AND llm.branch = 'llm'
WHERE ml.branch = 'local' AND ml.label <> llm.label
ORDER BY ml.run_id DESC, ml.item_index;
