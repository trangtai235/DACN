#!/usr/bin/env python3
"""eval_model.py — Chấm điểm và XEM TẬN MẮT mô hình đã train.

Dùng cho mô hình đã lưu (ví dụ trên Google Drive). Không cần huấn luyện lại.

--------------------------------------------------------------------
CÁCH DÙNG
--------------------------------------------------------------------
1) Chấm trên test.csv chính thức:
       python eval_model.py --model models/xlmr-base --data-root datasets/ViHOS

2) Chấm + in 25 ví dụ dự đoán để xem mô hình đúng/sai ở đâu:
       python eval_model.py --model models/xlmr-base --data-root datasets/ViHOS --show 25

3) Thử một câu bất kỳ:
       python eval_model.py --model models/xlmr-base --text "dm may ngu the"

4) Xuất kết quả chi tiết ra JSON:
       python eval_model.py --model models/xlmr-base --data-root . --out ket_qua.json

--------------------------------------------------------------------
CÁCH CHẤM — 3 chế độ (giống lúc huấn luyện)
--------------------------------------------------------------------
  partial : span chỉ cần CHỒNG LẤN là tính đúng   (chỉ số chính)
  strict  : span phải đúng CẢ HAI đầu
  char    : đo ở mức KÝ TỰ

--------------------------------------------------------------------
LƯU Ý QUAN TRỌNG
--------------------------------------------------------------------
  Chỉ chấm được trên test.csv nếu mô hình train bằng bản --variant syllable.
  Bản --variant word cần tách từ trước -> làm lệch vị trí ký tự -> điểm sai.
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import vihos_data as V          # noqa: E402


# ======================================================================
# MÃ HOÁ — phải GIỐNG HỆT lúc huấn luyện
# ======================================================================


def encode_words(tokenizer, words, max_len):
    """Mã hoá danh sách từ -> (input_ids, word_ids, dùng_fallback).

    Tokenizer NHANH (XLM-R)  : dùng API chuẩn is_split_into_words + word_ids().
    Tokenizer CHẬM (PhoBERT) : word_ids() không tồn tại -> tự ghép từng từ một.
    """
    try:
        enc = tokenizer(words, is_split_into_words=True, add_special_tokens=True)
        wids = enc.word_ids()
        if wids is not None:
            return enc["input_ids"][:max_len], list(wids)[:max_len], False
    except (ValueError, TypeError, AttributeError):
        pass

    unk = tokenizer.unk_token_id
    parts, wids = [], []
    for i, w in enumerate(words):
        sub = tokenizer.encode(w, add_special_tokens=False) or [unk]
        parts.extend(sub)
        wids.extend([i] * len(sub))
    sentinel = -999999
    probe = tokenizer.build_inputs_with_special_tokens([sentinel])
    lead = probe.index(sentinel)
    trail = len(probe) - lead - 1
    ids = tokenizer.build_inputs_with_special_tokens(parts)
    full_wids = [None] * lead + wids + [None] * trail
    if len(ids) != len(full_wids):
        raise RuntimeError(
            f"Không căn chỉnh được token với từ ({len(ids)} vs {len(full_wids)}).")
    return ids[:max_len], full_wids[:max_len], True


# ======================================================================
# DỰ ĐOÁN
# ======================================================================


def du_doan_lo(model, tok, texts, torch, device, use_fp16, max_len=160, batch=16):
    """Dự đoán cho nhiều câu -> list[list[(start,end)]] (span theo ký tự)."""
    ra = []
    dung_fallback = False
    model.eval()
    with torch.no_grad():
        for i in range(0, len(texts), batch):
            chunk = texts[i:i + batch]
            ids_all, wids_all, offs_all = [], [], []
            for text in chunk:
                tu = V.tokenize_with_offsets(text)
                words = [w for w, _a, _b in tu]
                offs = [(a, b) for _w, a, b in tu]
                ids, wids, fb = encode_words(tok, words, max_len)
                dung_fallback = dung_fallback or fb
                ids_all.append(ids)
                wids_all.append(wids)
                offs_all.append(offs)
            width = max(len(r) for r in ids_all)
            pad = tok.pad_token_id if tok.pad_token_id is not None else 0
            enc = {
                "input_ids": torch.tensor(
                    [r + [pad] * (width - len(r)) for r in ids_all], device=device),
                "attention_mask": torch.tensor(
                    [[1] * len(r) + [0] * (width - len(r)) for r in ids_all],
                    device=device),
            }
            with torch.autocast("cuda", enabled=use_fp16 and device.type == "cuda"):
                logits = model(**enc).logits
            logits = logits.float().cpu().numpy()
            for j, wids in enumerate(wids_all):
                first, prev = [], None
                for pos, wid in enumerate(wids):
                    if wid is not None and wid != prev:
                        first.append(pos)
                        prev = wid
                if first:
                    preds = logits[j][first].argmax(-1)
                else:
                    preds = []
                offs = offs_all[j][:len(preds)]
                tags = [V.ID2TAG[int(p)] for p in preds]
                ra.append(V.token_spans_to_char_spans(
                    V.bio_to_token_spans(tags), offs))
    return ra, dung_fallback


def du_doan_mot_cau(model, tok, text, torch, device, use_fp16):
    """Dự đoán 1 câu, trả về (từ, offset, nhãn, xác suất, span)."""
    tu = V.tokenize_with_offsets(text)
    words = [w for w, _a, _b in tu]
    offs = [(a, b) for _w, a, b in tu]
    ids, wids, _fb = encode_words(tok, words, 160)
    pad = tok.pad_token_id if tok.pad_token_id is not None else 0

    first, prev = [], None
    for pos, wid in enumerate(wids):
        if wid is not None and wid != prev:
            first.append(pos)
            prev = wid
    if not first:
        return words, offs, [], [], []

    enc = {
        "input_ids": torch.tensor([ids], device=device),
        "attention_mask": torch.tensor([[1] * len(ids)], device=device),
    }
    model.eval()
    with torch.no_grad():
        with torch.autocast("cuda", enabled=use_fp16 and device.type == "cuda"):
            logits = model(**enc).logits
    logits = logits.float().cpu().numpy()[0]
    import numpy as np
    sub = logits[first]
    e = np.exp(sub - sub.max(-1, keepdims=True))
    probs = e / e.sum(-1, keepdims=True)
    tags = [V.ID2TAG[int(p)] for p in sub.argmax(-1)]
    conf = probs.max(-1)
    offs = offs[:len(tags)]
    spans = V.token_spans_to_char_spans(V.bio_to_token_spans(tags), offs)
    return words, offs, tags, conf, spans


# ======================================================================
# TRÌNH BÀY
# ======================================================================


def cat(text, span):
    """Cắt đoạn văn bản theo (start, end)."""
    return text[span[0]:span[1]]


def mo_ta_span(text, sp):
    return f"[{sp[0]:>3}-{sp[1]:>3}] «{cat(text, sp)}»"


def cham_va_in(model, tok, ds, torch, device, use_fp16, show=0, out=None):
    gold = [s["spans"] for s in ds]
    texts = [s["content"] for s in ds]
    pred, fallback = du_doan_lo(model, tok, texts, torch, device, use_fp16)
    if fallback:
        print("  (đã dùng cách ghép từng từ cho tokenizer chậm)")

    pa = V.corpus_span_f1(gold, pred, partial=True)
    st = V.corpus_span_f1(gold, pred, partial=False)
    ch = V.char_prf(gold, pred)

    print()
    print("=" * 70)
    print(f"KẾT QUẢ TRÊN TEST.CSV — {len(ds)} câu, {sum(len(g) for g in gold)} span thật")
    print("=" * 70)
    print(f"{'chế độ':<10}{'precision':>12}{'recall':>12}{'F1':>12}")
    print("-" * 70)
    for ten, r in (("partial", pa), ("strict", st), ("ký tự", ch)):
        print(f"{ten:<10}{r['precision']:>12.4f}{r['recall']:>12.4f}{r['f1']:>12.4f}")
    print("-" * 70)
    print(f"  tp = {pa['tp']}   fp = {pa['fp']}   fn = {pa['fn']}   (ở mức span)")
    print()

    # --- đếm theo mức bình luận
    n_dung = n_sai = 0
    for g, p in zip(gold, pred):
        if bool(g) == bool(p):
            n_dung += 1
        else:
            n_sai += 1
    print(f"Ở MỨC BÌNH LUẬN (chỉ hỏi: câu này CÓ độc hại hay không):")
    print(f"  Đúng: {n_dung}/{len(ds)} = {n_dung/len(ds)*100:.1f}%")
    print(f"  Sai : {n_sai}/{len(ds)}")
    print()

    if show:
        print("=" * 70)
        print(f"{show} VÍ DỤ ĐẦU TIÊN — so sánh ĐÁP ÁN với DỰ ĐOÁN")
        print("=" * 70)
        for i in range(min(show, len(ds))):
            g, p = gold[i], pred[i]
            if not g and not p:
                kq = "✓ đúng (không có gì độc hại)"
            elif g and p and V._match(g, p, partial=True)[0] == len(g):
                kq = "✓ đúng"
            elif not p:
                kq = "✗ BỎ SÓT"
            elif not g:
                kq = "✗ BÁO NHẦM"
            else:
                kq = "~ đúng một phần"
            print()
            print(f"[{i+1}] {kq}")
            print(f"    câu   : {texts[i][:110]}")
            print(f"    đáp án: {', '.join(mo_ta_span(texts[i], s) for s in g) or '(không có)'}")
            print(f"    dự đoán: {', '.join(mo_ta_span(texts[i], s) for s in p) or '(không có)'}")

    if out:
        kq = {
            "so_cau": len(ds),
            "partial": pa, "strict": st, "char": ch,
            "muc_binh_luan": {"dung": n_dung, "sai": n_sai,
                              "do_chinh_xac": round(n_dung / len(ds), 4)},
            "du_doan": [{"content": t, "gold": g, "pred": p}
                        for t, g, p in zip(texts, gold, pred)],
        }
        with open(out, "w", encoding="utf-8") as f:
            json.dump(kq, f, ensure_ascii=False, indent=2)
        print()
        print(f"Đã xuất chi tiết -> {out}")

    return pa, st, ch


def in_mot_cau(model, tok, text, torch, device, use_fp16):
    words, offs, tags, conf, spans = du_doan_mot_cau(
        model, tok, text, torch, device, use_fp16)
    print()
    print("=" * 70)
    print(f"CÂU: {text}")
    print("=" * 70)
    if not words:
        print("  (không có từ nào)")
        return
    for w, t, c in zip(words, tags, conf):
        dau = "🔴" if t != "O" else "  "
        print(f"  {dau} {w:<22} {t:<6} {c*100:5.1f}%")
    print()
    if spans:
        print(f"  ➜ TÌM THẤY {len(spans)} ĐOẠN ĐỘC HẠI:")
        for s in spans:
            print(f"       «{cat(text, s)}»")
    else:
        print("  ➜ KHÔNG có đoạn độc hại nào")


# ======================================================================
# MAIN
# ======================================================================


def main():
    ap = argparse.ArgumentParser(
        description="Chấm điểm và xem dự đoán của mô hình đã train.",
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model", required=True,
                    help="thư mục mô hình đã lưu (có config.json + model.safetensors)")
    ap.add_argument("--data-root", default=".",
                    help="thư mục chứa test.csv (tìm đệ quy)")
    ap.add_argument("--show", type=int, default=0,
                    help="in bao nhiêu ví dụ đầu tiên")
    ap.add_argument("--text", action="append", default=None,
                    help="thử một câu bất kỳ (dùng được nhiều lần)")
    ap.add_argument("--out", default=None, help="xuất kết quả chi tiết ra JSON")
    ap.add_argument("--max-len", type=int, default=160)
    args = ap.parse_args()

    if not os.path.isdir(args.model):
        sys.exit(f"Không thấy thư mục mô hình: {args.model}")
    if not os.path.isfile(os.path.join(args.model, "config.json")):
        sys.exit(f"Thư mục {args.model} thiếu config.json — không phải mô hình đã lưu.")

    import torch
    from transformers import AutoModelForTokenClassification, AutoTokenizer

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    use_fp16 = device.type == "cuda"
    print(f"Thiết bị: {device}" + (
        f"  |  GPU: {torch.cuda.get_device_name(0)}" if use_fp16 else ""))

    tok = AutoTokenizer.from_pretrained(args.model)
    model = AutoModelForTokenClassification.from_pretrained(args.model).to(device)

    # kiểm tra nhãn có khớp không
    id2 = {int(k): v for k, v in (model.config.id2label or {}).items()}
    print(f"Nhãn của mô hình: {id2}")
    lech = [k for k, v in id2.items() if V.ID2TAG.get(k) != v]
    if lech:
        sys.exit(f"LỖI: nhãn mô hình khác mã nguồn ở vị trí {lech}. "
                 f"Không chấm được vì sẽ ra kết quả sai.")

    if args.text:
        for t in args.text:
            in_mot_cau(model, tok, t, torch, device, use_fp16)
        return 0

    test_path = V._find(args.data_root, "test.csv")
    print(f"Dữ liệu test: {test_path}")
    ds = V.load_test(test_path)
    cham_va_in(model, tok, ds, torch, device, use_fp16,
               show=args.show, out=args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
