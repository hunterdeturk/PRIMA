#!/usr/bin/env python3
# pdf_to_peco.py  — Extract PECO from PDFs → Excel/CSV
# Requires: openai>=1.0, pandas, openpyxl, tqdm, PyMuPDF (fitz) or pdfminer.six

import os, re, json, time, argparse, glob
import pandas as pd

from tqdm import tqdm

# ADD for forced OCR
import tempfile, subprocess, shutil

# --- OCR prepass (inline, no extra files) --------------------
def ensure_searchable_pdf_inline(in_path: str, lang: str = "eng") -> str:
    """
    Always run OCRmyPDF with --force-ocr, returning the OCR'd temp path.
    If ocrmypdf isn't available or OCR fails, fall back to the original path.
    """
    if shutil.which("ocrmypdf") is None:
        return in_path

    tmpdir = tempfile.mkdtemp(prefix="ocr_")
    out_path = os.path.join(tmpdir, "searchable_force.pdf")

    cmd = [
        "ocrmypdf", "--force-ocr", "--rotate-pages", "--deskew",
        "--optimize", "1", "--language", lang, in_path, out_path
    ]
    try:
        subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return out_path
    except subprocess.CalledProcessError:
        return in_path
# -------------------------------------------------------------

# --- PDF readers (prefer PyMuPDF; fallback to pdfminer) ---
def read_pdf_text(path: str) -> str:
    """Return raw text from a PDF using PyMuPDF; fallback to pdfminer.six."""
    try:
        import fitz  # PyMuPDF
        doc = fitz.open(path)
        text = []
        for page in doc:
            text.append(page.get_text("text"))
        doc.close()
        return "\n".join(text)
    except Exception:
        # Fallback: pdfminer.six
        try:
            from pdfminer.high_level import extract_text
            return extract_text(path) or ""
        except Exception as e:
            print(f"   ⚠️  PDF parse failed for {os.path.basename(path)}: {e}")
            return ""

# --- Abstract-first extraction (simple heuristics) ---
_ABS_HDR = re.compile(r'\babstract\b[:\s]*', re.I)
_METHODS_HDR = re.compile(r'\bmethods?\b', re.I)

def extract_abstract_then_full(text: str, max_chars_abstract=0, max_chars_full=120000):
    """
    Always return an empty abstract and a long full-text slice.
    This ensures the model processes the entire PDF content
    rather than just the abstract section.
    """
    if not text:
        return "", ""

    # Normalize whitespace for consistency
    t = re.sub(r'\s+', ' ', text)

    # Skip abstract entirely
    abstract = ""

    # Use as much full text as possible (up to model input limits)
    full = t[:max_chars_full]

    return abstract, full

# --- OpenAI client (reads OPENAI_API_KEY from env) ---
from openai import OpenAI
client = OpenAI()  # do not pass temperature; some models enforce default

MODEL = os.environ.get("OPENAI_MODEL", "gpt-5")  # switch to a model you have access to if needed
MAX_RETRIES = 3
BACKOFF = 3

SYSTEM_PROMPT = (
    "You extract structured evidence for meta-analysis.\n"
    "Return ONLY valid JSON using keys:\n"
    " 'title','year','journal','doi','population','exposure_or_intervention','comparator','outcomes',"
    " 'follow_up','sample_size_total','study_design','effect_measures','notes',\n"
    " 'a_elc_pos_cad_pos','b_elc_pos_cad_neg','c_elc_neg_cad_pos','d_elc_neg_cad_neg','p_value'.\n"
    "If a field is unknown, use null. Prefer tables.\n"
    "Treat ELC = DELC (diagonal ear lobe crease).\n"
    "For the 2×2 use counts (integers) with layout:\n"
    "  a = +ELC & +CAD, b = +ELC & −CAD, c = −ELC & +CAD, d = −ELC & −CAD.\n"
)

USER_TEMPLATE = """Extract PECO-style data and 2×2 counts from this paper.

=== FILE NAME (may hint title) ===
{fname}

=== ABSTRACT (may be empty) ===
{abstract}

=== FULL TEXT ===
{full}

Return a single JSON object with these keys (use integers or null):
  title, year, journal, doi, population, exposure_or_intervention, comparator, outcomes,
  follow_up, sample_size_total, study_design, effect_measures, notes,
  a_elc_pos_cad_pos, b_elc_pos_cad_neg, c_elc_neg_cad_pos, d_elc_neg_cad_neg, p_value

a = +ELC & +CAD,  b = +ELC & −CAD,  c = −ELC & +CAD,  d = −ELC & −CAD.
If the table is present (e.g., '+ELC +CAD', '+ELC −CAD', '−ELC +CAD', '−ELC −CAD'), map counts.
Output only valid JSON.
"""

def call_llm(fname: str, abstract: str, full: str) -> dict:
    prompt = USER_TEMPLATE.format(fname=fname, abstract=abstract or "(none)", full=full or "(none)")
    last_err = None
    for attempt in range(1, MAX_RETRIES+1):
        try:
            resp = client.chat.completions.create(
                model=MODEL,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
            )
            out = resp.choices[0].message.content.strip()
            # Strip accidental fences
            if out.startswith("```"):
                out = out.strip("`")
                out = out.replace("json\n", "", 1)
            return json.loads(out)
        except Exception as e:
            last_err = e
            msg = str(e).lower()
            transient = any(k in msg for k in ["rate", "quota", "temporar", "timeout", "overload"])
            if transient and attempt < MAX_RETRIES:
                time.sleep(BACKOFF * attempt)
                continue
            raise RuntimeError(f"LLM failed ({attempt}/{MAX_RETRIES}): {e}") from e

def safe_get(d, k):
    v = d.get(k)
    return v if v is not None else ""
    # ---- 2x2 Table Parsing and OR/CI Calculation ----

def to_int(x):
    """Convert safely to integer or None."""
    try:
        return int(x) if x not in [None, "", "null", "None"] else None
    except:
        return None


def compute_or_from_2x2(a, b, c, d):
    """
    Compute Odds Ratio (OR), ln(OR), SE, and 95% CI using
    the Haldane–Anscombe correction to avoid zero-cell issues.
    """
    if None in (a, b, c, d):
        return None

    # Apply continuity correction
    aa, bb, cc, dd = a + 0.5, b + 0.5, c + 0.5, d + 0.5

    try:
        import math
        OR = (aa * dd) / (bb * cc)
        lnOR = math.log(OR)
        SE = (1 / aa + 1 / bb + 1 / cc + 1 / dd) ** 0.5
        z = 1.96
        ci_low = math.exp(lnOR - z * SE)
        ci_high = math.exp(lnOR + z * SE)
        return {"or": OR, "ln_or": lnOR, "se": SE, "ci_low": ci_low, "ci_high": ci_high}
    except Exception as e:
        print(f"⚠️ Error computing OR: {e}")
        return None

def main():
    ap = argparse.ArgumentParser(description="Extract PECO from PDFs → Excel/CSV")
    ap.add_argument("-i", "--input_dir", required=True, help="Folder containing PDFs")
    ap.add_argument("-o", "--output", default="peco_results.xlsx", help="Output Excel filename")
    ap.add_argument("--csv", default=None, help="Optional CSV filename (also write CSV)")
    ap.add_argument("--limit", type=int, default=None, help="Process only first N PDFs (for testing)")
    args = ap.parse_args()

    pdf_paths = sorted(glob.glob(os.path.join(args.input_dir, "*.pdf")))
    if not pdf_paths:
        print("No PDFs found in", args.input_dir)
        return
    if args.limit:
        pdf_paths = pdf_paths[:args.limit]
    rows = []

    print(f"🗂 Found {len(pdf_paths)} PDFs. Reading + extracting…")

    for p in tqdm(pdf_paths, unit="pdf"):
        fname = os.path.basename(p)

        # Forced OCR before reading text
        orig_p = p
        p = ensure_searchable_pdf_inline(p, lang="eng")
        if p != orig_p:
            print(f"🟢 OCR applied to: {fname}")

        # Always process the file (regardless of OCR)
        text = read_pdf_text(p)
        abstract, full = extract_abstract_then_full(text)

        try:
            data = call_llm(fname, abstract, full)
        except Exception as e:
            data = {
                "title": None, "year": None, "journal": None, "doi": None,
                "population": None, "exposure_or_intervention": None, "comparator": None,
                "outcomes": None, "follow_up": None, "sample_size_total": None,
                "study_design": None, "effect_measures": None,
                "a_elc_pos_cad_pos": None, "b_elc_pos_cad_neg": None,
                "c_elc_neg_cad_pos": None, "d_elc_neg_cad_neg": None,
                "p_value": None,
                "notes": f"#ERROR: {str(e)[:300]}",
            }

        # 2×2 counts (may be None)
        a = to_int(data.get("a_elc_pos_cad_pos"))
        b = to_int(data.get("b_elc_pos_cad_neg"))
        c = to_int(data.get("c_elc_neg_cad_pos"))
        d = to_int(data.get("d_elc_neg_cad_neg"))
        or_stats = compute_or_from_2x2(a, b, c, d) if all(x is not None for x in (a, b, c, d)) else None

        rows.append({
            "file": fname,
            "title": safe_get(data, "title"),
            "year": safe_get(data, "year"),
            "journal": safe_get(data, "journal"),
            "doi": safe_get(data, "doi"),
            "population": safe_get(data, "population"),
            "exposure_or_intervention": safe_get(data, "exposure_or_intervention"),
            "comparator": safe_get(data, "comparator"),
            "outcomes": safe_get(data, "outcomes"),
            "follow_up": safe_get(data, "follow_up"),
            "sample_size_total": safe_get(data, "sample_size_total"),
            "study_design": safe_get(data, "study_design"),
            "effect_measures": safe_get(data, "effect_measures"),
            "a_elc_pos_cad_pos": a,
            "b_elc_pos_cad_neg": b,
            "c_elc_neg_cad_pos": c,
            "d_elc_neg_cad_neg": d,
            "or": None if not or_stats else or_stats.get("or"),
            "ln_or": None if not or_stats else or_stats.get("ln_or"),
            "se": None if not or_stats else or_stats.get("se"),
            "ci_low": None if not or_stats else or_stats.get("ci_low"),
            "ci_high": None if not or_stats else or_stats.get("ci_high"),
            "p_value": safe_get(data, "p_value"),
            "notes": safe_get(data, "notes"),
        })

    df = pd.DataFrame(rows)

    # Write Excel + CSV
    xlsx = args.output
    df.to_excel(xlsx, index=False)
    print(f"✅ Excel saved: {xlsx}")
    csv = args.csv or os.path.splitext(xlsx)[0] + ".csv"
    df.to_csv(csv, index=False)
    print(f"✅ CSV saved:   {csv}")

if __name__ == "__main__":
    # Quick sanity check for key
    if not os.environ.get("OPENAI_API_KEY"):
        raise SystemExit("OPENAI_API_KEY not set. Run: export OPENAI_API_KEY='sk-...'")
    main()
