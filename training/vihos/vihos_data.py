"""vihos_data.py — Xử lý dữ liệu ViHOS, KHÔNG cần thư viện ngoài (chỉ stdlib).

ViHOS (Hoang et al., EACL 2023) — 26.467 span độc hại trên 11.056 bình luận tiếng Việt.
  data/Sequence_labeling_based_version/Word/       -> dùng cho PhoBERT (đã tách từ bằng VnCoreNLP)
  data/Sequence_labeling_based_version/Syllable/   -> dùng cho XLM-R (tách âm tiết)
  data/Test_data/test.csv                          -> TẬP TEST CHÍNH THỨC (span theo ký tự)

Nhãn: O = không độc hại, B-T = bắt đầu span, I-T = trong span.
"""

import csv
import os
import re
from collections import defaultdict

TAG2ID = {"O": 0, "B-T": 1, "I-T": 2}
ID2TAG = {v: k for k, v in TAG2ID.items()}


# ----------------------------------------------------------------- dữ liệu BIO
def load_bio(path):
    """Đọc file BIO -> danh sách câu: [{'sid': int, 'words': [...], 'tags': [...]}]."""
    buckets = defaultdict(lambda: {"words": [], "tags": []})
    with open(path, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            word = (row.get("Word") or row.get("word") or "").strip()
            if not word:
                continue
            sid = int(row["sentence_id"])
            buckets[sid]["words"].append(word)
            buckets[sid]["tags"].append(row["Tag"].strip())
    return [{"sid": k, "words": v["words"], "tags": v["tags"]}
            for k, v in sorted(buckets.items())]


def load_test(path):
    """Đọc test.csv chính thức: [{'content': str, 'spans': [(start, end), ...]}] (end độc quyền)."""
    import ast

    out = []
    with open(path, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            raw = (row.get("index_spans") or "[]").strip()
            try:
                chars = ast.literal_eval(raw)
            except (ValueError, SyntaxError):
                chars = []
            out.append({"content": row["content"], "spans": chars_to_spans(chars)})
    return out


def chars_to_spans(chars):
    """[26, 27, 40, 41, 42] -> [(26, 28), (40, 43)]  (end độc quyền)."""
    if not chars:
        return []
    chars = sorted(set(int(c) for c in chars))
    spans, start, prev = [], chars[0], chars[0]
    for c in chars[1:]:
        if c == prev + 1:
            prev = c
            continue
        spans.append((start, prev + 1))
        start = prev = c
    spans.append((start, prev + 1))
    return spans


# ------------------------------------------------------------------ chuyển đổi
def bio_to_token_spans(tags):
    """['O','B-T','I-T','O'] -> [(1, 3)]  (chỉ số token, end độc quyền)."""
    spans, start = [], None
    for i, t in enumerate(tags):
        if t == "B-T":
            if start is not None:
                spans.append((start, i))
            start = i
        elif t == "I-T":
            if start is None:
                start = i
        else:
            if start is not None:
                spans.append((start, i))
                start = None
    if start is not None:
        spans.append((start, len(tags)))
    return spans


def reconstruct(words, joiner=" "):
    """Ghép token thành câu + trả về vị trí ký tự của từng token."""
    text, offsets, cursor = [], [], 0
    for w in words:
        token = w.replace("_", " ")
        text.append(token)
        offsets.append((cursor, cursor + len(token)))
        cursor += len(token) + len(joiner)
    return joiner.join(text), offsets


def token_spans_to_char_spans(spans, offsets):
    """[(1,3)] + offsets -> [(char_start, char_end)] (end độc quyền)."""
    out = []
    for s, e in spans:
        if s >= len(offsets):
            continue
        e = min(e, len(offsets))
        out.append((offsets[s][0], offsets[e - 1][1]))
    return out


TOKEN_RE = re.compile(r"\w+|[^\w\s]", re.UNICODE)


def tokenize_with_offsets(text):
    """Tách văn bản thô thành token + vị trí ký tự. Mô phỏng VnCoreNLP: tách dấu câu riêng."""
    return [(m.group(0), m.start(), m.end()) for m in TOKEN_RE.finditer(text)]


# ---------------------------------------------------------------------- đánh giá
def _match(gold, pred, partial=True):
    """Ghép span gold/pred trong 1 câu. Trả về (tp, fp, fn)."""
    gold, pred = list(gold), list(pred)
    used = [False] * len(gold)
    tp = 0
    for ps, pe in pred:
        hit = -1
        for i, (gs, ge) in enumerate(gold):
            if used[i]:
                continue
            ok = (ps < ge and gs < pe) if partial else (ps == gs and pe == ge)
            if ok:
                hit = i
                break
        if hit >= 0:
            used[hit] = True
            tp += 1
    return tp, len(pred) - tp, used.count(False)


def corpus_span_f1(gold_sents, pred_sents, partial=True):
    """Micro P/R/F1 trên toàn bộ tập. gold_sents/pred_sents: list[list[(s,e)]]."""
    tp = fp = fn = 0
    for g, p in zip(gold_sents, pred_sents):
        a, b, c = _match(g, p, partial=partial)
        tp += a
        fp += b
        fn += c
    prec = tp / (tp + fp) if tp + fp else 0.0
    rec = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
    return {"precision": prec, "recall": rec, "f1": f1, "tp": tp, "fp": fp, "fn": fn}


def char_prf(gold_sents, pred_sents):
    """P/R/F1 ở mức KÝ TỰ — chỉ số phụ, ổn định hơn khi ranh giới span lệch."""
    tp = fp = fn = 0
    for g, p in zip(gold_sents, pred_sents):
        gset = {c for s, e in g for c in range(s, e)}
        pset = {c for s, e in p for c in range(s, e)}
        tp += len(gset & pset)
        fp += len(pset - gset)
        fn += len(gset - pset)
    prec = tp / (tp + fp) if tp + fp else 0.0
    rec = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
    return {"precision": prec, "recall": rec, "f1": f1}


def sentence_scramble_check(sents):
    """Kiểm tra mỗi câu có ít nhất 1 nhãn và độ dài hợp lý."""
    bad = []
    for s in sents:
        if len(s["words"]) != len(s["tags"]):
            bad.append((s["sid"], "độ dài words != tags"))
        elif not any(t != "O" for t in s["tags"]) and s["sid"] % 7 == 0:
            bad.append((s["sid"], "không có nhãn độc hại (có thể bình thường)"))
    return bad


def _find(root, filename):
    """Tìm file trong cây thư mục (chịu được nhiều cách sắp xếp)."""
    direct = os.path.join(root, filename)
    if os.path.exists(direct):
        return direct
    for dirpath, _dirs, files in os.walk(root):
        if filename in files:
            return os.path.join(dirpath, filename)
    raise FileNotFoundError(f"Không tìm thấy {filename} trong {root}")


def load_all(root):
    """Đọc cả 5 file trong 1 lần, không phụ thuộc cách sắp xếp thư mục."""
    return {
        "train_word": load_bio(_find(root, "train_BIO_Word.csv")),
        "dev_word": load_bio(_find(root, "dev_BIO_Word.csv")),
        "train_syllable": load_bio(_find(root, "train_BIO_syllable.csv")),
        "dev_syllable": load_bio(_find(root, "dev_BIO_syllable.csv")),
        "test": load_test(_find(root, "test.csv")),
    }
