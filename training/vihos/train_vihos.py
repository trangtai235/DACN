"""train_vihos.py — Huấn luyện mô hình phát hiện span độc hại tiếng Việt trên bộ ViHOS.

--------------------------------------------------------------------------------
CÁCH DÙNG NHANH (chạy trên Google Colab hoặc máy có GPU):

  # 0) Kiểm tra dữ liệu đã đúng chưa (không cần GPU, không cần torch)
  python train_vihos.py --check-data

  # 1) Chạy thử 2 phút để chắc pipeline đúng (không cần chờ lâu)
  python train_vihos.py --smoke

  # 2) Chạy thật — KHUYẾN NGHỊ CHO HÔM NAY: XLM-R base + bản Syllable
  python train_vihos.py --variant syllable --model xlm-roberta-base \
      --epochs 5 --batch-size 16 --lr 3e-5 --test --out models/xlmr-base

  # 3) So sánh với PhoBERT (bản Word, đúng như bài báo ViHOS dùng)
  python train_vihos.py --variant word --model vinai/phobert-base \
      --epochs 5 --batch-size 32 --lr 2e-5 --out models/phobert-base

  # 4) Mạnh nhất (cần Colab Pro / Kaggle 2xT4)
  python train_vihos.py --variant syllable --model xlm-roberta-large \
      --epochs 4 --batch-size 8 --lr 1e-5 --grad-accum 2 --test --out models/xlmr-large

--------------------------------------------------------------------------------
HAI BẢN DỮ LIỆU — CHỌN ĐÚNG KẺO SAI:

  syllable : mỗi âm tiết là 1 token, gần như trùng cách tách theo khoảng trắng của
             văn bản thô  =>  dùng cho XLM-R, và CHẤM ĐƯỢC trên test.csv chính thức.
  word     : đã tách từ bằng VnCoreNLP, từ ghép nối bằng '_' (vd 'Bấp_bênh')
             =>  dùng cho PhoBERT. Muốn chấm trên test.csv phải tách từ lại
             (thêm --word-segment để dùng underthesea).

Kết quả in ra gồm 3 loại F1:
  partial : span dự đoán CHỒNG LẤN span vàng là tính đúng (chuẩn thường dùng)
  strict  : phải trùng khít cả điểm đầu và điểm cuối
  char    : F1 ở mức ký tự (ổn định nhất khi ranh giới span lệch)
"""

import argparse
import json
import os
import random
import sys
import time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import vihos_data as V  # noqa: E402

def resolve_data_root():
    """Tìm thư mục dữ liệu ViHOS — chịu được cả máy local lẫn Google Colab."""
    here = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        os.environ.get("VIHOS_ROOT"),
        os.path.join(here, "datasets", "ViHOS"),
        os.path.abspath(os.path.join(here, "..", "datasets", "ViHOS")),
        os.path.join(os.getcwd(), "datasets", "ViHOS"),
        "/content/datasets/ViHOS",
    ]
    for c in candidates:
        if c and os.path.isdir(c):
            try:
                V._find(c, "test.csv")
                return os.path.abspath(c)
            except FileNotFoundError:
                continue
    return os.path.abspath(os.path.join(here, "..", "datasets", "ViHOS"))


DATA_ROOT = resolve_data_root()


def _need(pkgs):
    """Nhập thư viện nặng muộn, kèm thông báo cài đặt rõ ràng."""
    missing = []
    mods = {}
    for p in pkgs:
        try:
            mods[p] = __import__(p)
        except ImportError:
            missing.append(p)
    if missing:
        sys.exit(
            "THIẾU THƯ VIỆN: " + ", ".join(missing) + "\n"
            "Cài bằng:  pip install torch transformers\n"
            "(Trên Colab thường đã có sẵn. Kiểm tra bằng --check-data.)"
        )
    return mods


# --------------------------------------------------------------------- mã hoá
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

    # --- đường dự phòng cho tokenizer chậm ---
    unk = tokenizer.unk_token_id
    parts, wids = [], []
    for i, w in enumerate(words):
        sub = tokenizer.encode(w, add_special_tokens=False) or [unk]
        parts.extend(sub)
        wids.extend([i] * len(sub))
    # Đếm số token đặc biệt ở đầu/cuối bằng một mã không thể trùng với token thật
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


class VihosDataset:
    """Mã hoá câu thành input_ids + nhãn gán cho subword ĐẦU của mỗi token.

    Dùng đối tượng thuần Python (không kế thừa torch.utils.data.Dataset) để có thể
    kiểm tra dữ liệu mà không cần cài torch.
    """

    def __init__(self, sents, tokenizer, max_len=128, limit=None, nhan=None):
        if limit:
            sents = sents[:limit]
        self.items = []
        self.used_fallback = False
        n = len(sents)
        for i, s in enumerate(sents):
            if nhan and n >= 500 and i and i % 2000 == 0:
                print(f"    ... đã xử lý {i:,}/{n:,} câu "
                      f"({i * 100 // n}%)", flush=True)
            words, tags = s["words"], s["tags"]
            ids, word_ids, fb = encode_words(tokenizer, words, max_len)
            self.used_fallback = self.used_fallback or fb
            labels, first_idx, prev = [], [], None
            for pos, wid in enumerate(word_ids):
                if wid is None:                      # token đặc biệt <s> </s>
                    labels.append(-100)
                elif wid != prev:                    # subword ĐẦU của một từ
                    labels.append(V.TAG2ID[tags[wid]])
                    first_idx.append(pos)
                    prev = wid
                else:                                # subword phụ -> bỏ qua
                    labels.append(-100)
            if len(labels) != len(ids):
                raise RuntimeError(
                    f"Số nhãn ({len(labels)}) không khớp số token ({len(ids)}).")
            self.items.append({
                "input_ids": ids,
                "attention_mask": [1] * len(ids),
                "labels": labels,
                "first_idx": first_idx,
                "n_words": len(first_idx),
                "gold_words": words,
                "gold_tags": tags[:len(first_idx)],
            })

    def __len__(self):
        return len(self.items)

    def __getitem__(self, i):
        return self.items[i]


def collate(batch):
    """Đệm cho bằng nhau trong lô.

    Trả về (dict các LIST đã đệm, danh sách metadata gốc) để vòng lặp huấn luyện
    và hàm dự đoán đều dùng được câu gốc + nhãn vàng.
    """
    max_len = max(len(b["input_ids"]) for b in batch)
    max_words = max(b["n_words"] for b in batch)
    out = {"input_ids": [], "attention_mask": [], "labels": [],
           "first_idx": [], "word_mask": []}
    for b in batch:
        pad = max_len - len(b["input_ids"])
        out["input_ids"].append(b["input_ids"] + [0] * pad)
        out["attention_mask"].append(b["attention_mask"] + [0] * pad)
        out["labels"].append(b["labels"] + [-100] * pad)
        wpad = max_words - b["n_words"]
        out["first_idx"].append(b["first_idx"] + [0] * wpad)
        out["word_mask"].append([True] * b["n_words"] + [False] * wpad)
    return out, batch


def to_device(batch, torch, device):
    return {k: torch.tensor(v, device=device) for k, v in batch.items()}


# ------------------------------------------------------------------- dự đoán
def predict(model, loader, torch, device, use_fp16):
    """Trả về (list nhãn theo token, list metadata)."""
    model.eval()
    all_tags, all_meta = [], []
    with torch.no_grad():
        for raw, meta in loader:
            batch = to_device(raw, torch, device)
            with torch.autocast("cuda", enabled=use_fp16 and device.type == "cuda"):
                logits = model(input_ids=batch["input_ids"],
                               attention_mask=batch["attention_mask"]).logits
            logits = logits.float().cpu().numpy()
            for i in range(logits.shape[0]):
                n = int(batch["word_mask"][i].sum())
                idx = batch["first_idx"][i][:n].cpu().numpy()
                preds = logits[i][idx].argmax(-1)
                all_tags.append([V.ID2TAG[int(p)] for p in preds])
            all_meta.extend(meta)
    return all_tags, all_meta


def eval_on_dev(model, loader, torch, device, use_fp16):
    """Chấm trên dev: BIO -> span ký tự -> F1."""
    pred_tags, meta = predict(model, loader, torch, device, use_fp16)
    gold_spans, pred_spans = [], []
    for tags, m in zip(pred_tags, meta):
        _text, offsets = V.reconstruct(m["gold_words"])
        gold_spans.append(V.token_spans_to_char_spans(
            V.bio_to_token_spans(m["gold_tags"]), offsets))
        pred_spans.append(V.token_spans_to_char_spans(
            V.bio_to_token_spans(tags), offsets))
    return {
        "partial": {k: round(v, 4) for k, v in
                    V.corpus_span_f1(gold_spans, pred_spans, partial=True).items()},
        "strict": {k: round(v, 4) for k, v in
                   V.corpus_span_f1(gold_spans, pred_spans, partial=False).items()},
        "char": {k: round(v, 4) for k, v in V.char_prf(gold_spans, pred_spans).items()},
    }


def eval_on_test(model, tokenizer, torch, device, use_fp16, seg=None):
    """Chấm trên test.csv chính thức (span theo ký tự).

    Dùng CHÍNH hàm mã hoá của lúc huấn luyện (encode_words) nên chạy được với
    cả tokenizer nhanh (XLM-R) lẫn chậm (PhoBERT).
    """
    ds = V.load_test(V._find(DATA_ROOT, "test.csv"))
    gold_spans = [s["spans"] for s in ds]
    rows_text = [s["content"] for s in ds]
    pred_spans = []
    used_fallback = False
    model.eval()
    with torch.no_grad():
        for i in range(0, len(rows_text), 16):
            chunk = rows_text[i:i + 16]
            ids_all, wids_all, offs_all = [], [], []
            for text in chunk:
                words = [w for w, _a, _b in V.tokenize_with_offsets(text)]
                ids, wids, fb = encode_words(tokenizer, words, 160)
                used_fallback = used_fallback or fb
                ids_all.append(ids)
                wids_all.append(wids)
                offs_all.append([(a, b) for _w, a, b
                                 in V.tokenize_with_offsets(text)])
            width = max(len(r) for r in ids_all)
            pad = tokenizer.pad_token_id if tokenizer.pad_token_id is not None else 0
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
                preds = logits[j][first].argmax(-1) if first else []
                offs = offs_all[j][:len(preds)]
                tags = [V.ID2TAG[int(p)] for p in preds]
                pred_spans.append(V.token_spans_to_char_spans(
                    V.bio_to_token_spans(tags), offs))
    if used_fallback:
        print("  (đã dùng cách ghép từng từ cho tokenizer chậm)")
    return {
        "partial": {k: round(v, 4) for k, v in
                    V.corpus_span_f1(gold_spans, pred_spans, partial=True).items()},
        "strict": {k: round(v, 4) for k, v in
                   V.corpus_span_f1(gold_spans, pred_spans, partial=False).items()},
        "char": {k: round(v, 4) for k, v in V.char_prf(gold_spans, pred_spans).items()},
    }


# -------------------------------------------------------- kiểm tra dữ liệu
def check_data():
    data = V.load_all(DATA_ROOT)
    print(f"Thư mục dữ liệu: {DATA_ROOT}\n")
    for name in ["train_word", "dev_word", "train_syllable", "dev_syllable"]:
        sents = data[name]
        n_spans = sum(len(V.bio_to_token_spans(s["tags"])) for s in sents)
        n_toxic = sum(any(t != "O" for t in s["tags"]) for s in sents)
        print(f"{name:16} {len(sents):>6,} câu | {n_spans:>6,} span | "
              f"{100*n_toxic/len(sents):>4.1f}% câu có độc hại")
    t = data["test"]
    print(f"{'test':16} {len(t):>6,} câu | "
          f"{sum(len(s['spans']) for s in t):>6,} span | "
          f"{100*sum(1 for s in t if s['spans'])/len(t):>4.1f}% câu có độc hại")
    print("\nDữ liệu OK — sẵn sàng huấn luyện.")
    try:
        import torch
        import transformers
        print(f"torch {torch.__version__} | transformers {transformers.__version__} | "
              f"cuda: {torch.cuda.is_available()}")
        if torch.cuda.is_available():
            print("GPU:", torch.cuda.get_device_name(0))
    except ImportError:
        print("Chưa có torch/transformers — cài: pip install torch transformers")


# --------------------------------------------------------------------- train
def _make_seg(args):
    """test.csv chỉ chấm được với bản syllable. Trả về (seg, có_chấm_được_không)."""
    if args.variant != "word":
        print("\nĐang chấm trên test.csv chính thức...", flush=True)
        return None, True
    print("\n!!! BỎ QUA CHẤM TEST — bản --variant word KHÔNG chấm được test.csv.\n"
          "    Lý do: test.csv là văn bản thô, bản word phải tách từ trước, mà\n"
          "    tách từ làm mất vị trí ký tự của span -> điểm sẽ SAI, không phải thấp.\n"
          "    Muốn có điểm test: huấn luyện bản syllable\n"
          "      --variant syllable --test\n"
          "    (Bản word vẫn so sánh được với nhau qua điểm dev.)", flush=True)
    return None, False


def eval_only(args):
    """Chấm lại trên test.csv bằng mô hình ĐÃ LƯU — không huấn luyện lại."""
    if not os.path.isdir(args.out):
        raise SystemExit(
            f"Không thấy thư mục mô hình: {args.out}\n"
            f"Hãy trỏ --out vào thư mục mô hình đã lưu (có file config.json).")

    mp = os.path.join(args.out, "metrics.json")
    old = {}
    if os.path.exists(mp):
        with open(mp, encoding="utf-8") as f:
            old = json.load(f)
        if old.get("variant") in ("syllable", "word") and args.variant != old["variant"]:
            print(f"(tự nhận --variant {old['variant']} theo metrics.json)", flush=True)
            args.variant = old["variant"]

    torch = _need(["torch"])["torch"]
    _need(["transformers"])
    from transformers import AutoModelForTokenClassification, AutoTokenizer

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Thiết bị: {device}  |  mô hình: {args.out}", flush=True)
    tokenizer = AutoTokenizer.from_pretrained(args.out)
    model = AutoModelForTokenClassification.from_pretrained(args.out)
    model.to(device).eval()

    seg, chay_duoc = _make_seg(args)
    if not chay_duoc:
        return None
    print("(KHÔNG huấn luyện lại — chỉ chấm điểm, khoảng 1-2 phút)", flush=True)

    res = eval_on_test(model, tokenizer, torch, device,
                       device.type == "cuda", seg)
    old["test"] = res
    old["test_word_segment"] = "underthesea" if seg is not None else None
    with open(mp, "w", encoding="utf-8") as f:
        json.dump(old, f, ensure_ascii=False, indent=2)

    print("\n=== KẾT QUẢ TEST ===")
    for k in ("partial", "strict", "char"):
        if k in res:
            print(f"  {k:8} P={res[k]['precision']:.4f}  R={res[k]['recall']:.4f}  "
                  f"F1={res[k]['f1']:.4f}")
    print(f"\nĐã ghi vào {mp}")
    return res


def train(args):
    torch = _need(["torch"])["torch"]
    _need(["transformers"])
    from transformers import AutoModelForTokenClassification, AutoTokenizer
    from torch.utils.data import DataLoader

    random.seed(args.seed)
    np.random.seed(args.seed)
    torch.manual_seed(args.seed)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    use_fp16 = device.type == "cuda"
    print(f"Thiết bị: {device}  |  fp16: {use_fp16}", flush=True)
    print(f"GPU: {torch.cuda.get_device_name(0)}" if device.type == "cuda"
          else "CẢNH BÁO: không có GPU — huấn luyện sẽ rất chậm.", flush=True)

    data = V.load_all(DATA_ROOT)
    tr, dv = data[f"train_{args.variant}"], data[f"dev_{args.variant}"]
    limit = 300 if args.smoke else (args.limit or None)
    print(f"Dữ liệu: {len(tr):,} câu train, {len(dv):,} câu dev (bản {args.variant})",
          flush=True)

    tokenizer = AutoTokenizer.from_pretrained(args.model, use_fast=True)
    model = AutoModelForTokenClassification.from_pretrained(
        args.model, num_labels=3, id2label=V.ID2TAG, label2id=V.TAG2ID)

    print("Đang tách từ dữ liệu (tokenizer chậm như PhoBERT có thể mất vài phút)...",
          flush=True)
    train_ds = VihosDataset(tr, tokenizer, args.max_len, limit, nhan=True)
    dev_ds = VihosDataset(dv, tokenizer, args.max_len, 200 if args.smoke else None)
    train_loader = DataLoader(train_ds, batch_size=args.batch_size, shuffle=True,
                              collate_fn=collate, num_workers=0)
    dev_loader = DataLoader(dev_ds, batch_size=args.batch_size * 2, shuffle=False,
                            collate_fn=collate, num_workers=0)
    print(f"Train {len(train_ds):,} câu / {len(train_loader)} lô | "
          f"Dev {len(dev_ds):,} câu")
    if train_ds.used_fallback:
        print("Chú ý: tokenizer này không hỗ trợ word_ids() (tokenizer chậm) — "
              "đã dùng cách ghép từng từ để căn chỉnh nhãn.")

    no_decay = ["bias", "LayerNorm.weight"]
    params = [
        {"params": [p for n, p in model.named_parameters()
                    if not any(nd in n for nd in no_decay)], "weight_decay": 0.01},
        {"params": [p for n, p in model.named_parameters()
                    if any(nd in n for nd in no_decay)], "weight_decay": 0.0},
    ]
    optim = torch.optim.AdamW(params, lr=args.lr)
    epochs = 1 if args.smoke else args.epochs
    total = max(1, len(train_loader) * epochs // max(1, args.grad_accum))
    sched = torch.optim.lr_scheduler.OneCycleLR(
        optim, max_lr=args.lr, total_steps=total, pct_start=0.1)
    scaler = torch.amp.GradScaler("cuda", enabled=use_fp16)

    model.to(device)
    best_f1, best_state, history = -1.0, None, []
    for epoch in range(1, epochs + 1):
        model.train()
        t0, running = time.time(), 0.0
        optim.zero_grad(set_to_none=True)
        for step, (raw, _meta) in enumerate(train_loader, 1):
            batch = to_device(raw, torch, device)
            with torch.autocast("cuda", enabled=use_fp16):
                loss = model(**batch).loss / args.grad_accum
            scaler.scale(loss).backward()
            running += loss.item() * args.grad_accum
            if step % args.grad_accum == 0:
                scaler.unscale_(optim)
                torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                scale_before = scaler.get_scale()
                scaler.step(optim)
                scaler.update()
                optim.zero_grad(set_to_none=True)
                # Chỉ bước scheduler nếu optimizer THỰC SỰ cập nhật trọng số.
                # GradScaler bỏ qua bước khi gradient có inf/nan; gọi scheduler
                # lúc đó sẽ gây cảnh báo "lr_scheduler.step() before optimizer.step()".
                if scaler.get_scale() >= scale_before:
                    sched.step()
            if step % 25 == 0:
                print(f"  epoch {epoch} | bước {step}/{len(train_loader)} | "
                      f"loss {running/step:.4f} | {time.time()-t0:.0f}s", flush=True)

        m = eval_on_dev(model, dev_loader, torch, device, use_fp16)
        f1 = m["partial"]["f1"]
        history.append({"epoch": epoch,
                        "train_loss": round(running / len(train_loader), 4), "dev": m})
        print(f"== epoch {epoch}: loss {running/len(train_loader):.4f} | "
              f"dev span F1 partial = {f1:.4f} | strict = {m['strict']['f1']:.4f} | "
              f"char F1 = {m['char']['f1']:.4f}")
        if f1 > best_f1:
            best_f1 = f1
            best_state = {k: v.detach().cpu().clone()
                          for k, v in model.state_dict().items()}
            print("   -> lưu checkpoint tốt nhất")

    if best_state:
        model.load_state_dict(best_state)
    result = {"variant": args.variant, "model": args.model, "epochs": epochs,
              "lr": args.lr, "batch_size": args.batch_size, "seed": args.seed,
              "n_train": len(train_ds), "best_dev_span_f1_partial": round(best_f1, 4),
              "dev_best": history[-1]["dev"] if history else {}, "history": history}

    if args.test and not args.smoke:
        seg, chay_duoc = _make_seg(args)
        if chay_duoc:
            result["test"] = eval_on_test(model, tokenizer, torch, device, use_fp16, seg)
            result["test_word_segment"] = "underthesea" if seg is not None else None
            print("== TEST chính thức:", json.dumps(result["test"], ensure_ascii=False))

    os.makedirs(args.out, exist_ok=True)
    model.save_pretrained(args.out)
    tokenizer.save_pretrained(args.out)
    with open(os.path.join(args.out, "metrics.json"), "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"\nĐã lưu mô hình + metrics vào {args.out}")
    if args.smoke:
        print("\nSMOKE TEST XONG — pipeline chạy đúng. Giờ chạy lệnh thật (bỏ --smoke).")
    return result


def build_parser():
    p = argparse.ArgumentParser(description="Huấn luyện trên bộ ViHOS")
    p.add_argument("--variant", choices=["syllable", "word"], default="syllable")
    p.add_argument("--model", default="xlm-roberta-base")
    p.add_argument("--epochs", type=int, default=5)
    p.add_argument("--batch-size", type=int, default=16)
    p.add_argument("--grad-accum", type=int, default=1)
    p.add_argument("--lr", type=float, default=3e-5)
    p.add_argument("--max-len", type=int, default=128)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--out", default="models/vihos-run")
    p.add_argument("--limit", type=int, default=0, help="giới hạn số câu train (0 = tất cả)")
    p.add_argument("--smoke", action="store_true", help="chạy thử nhanh 300 câu")
    p.add_argument("--test", action="store_true", help="chấm trên test.csv chính thức")
    p.add_argument("--word-segment", action="store_true",
                   help="(đã bỏ — chỉ bản syllable chấm được test.csv)")
    p.add_argument("--check-data", action="store_true", help="chỉ kiểm tra dữ liệu")
    p.add_argument("--eval-only", action="store_true",
                   help="chỉ chấm lại trên test bằng mô hình trong --out (không huấn luyện)")
    p.add_argument("--data-root", default=None, help="thư mục chứa dữ liệu ViHOS")
    return p


if __name__ == "__main__":
    a = build_parser().parse_args()
    if a.data_root:
        DATA_ROOT = os.path.abspath(a.data_root)
    if a.check_data:
        check_data()
    elif a.eval_only:
        eval_only(a)
    else:
        train(a)
