# PRIMA (OCR Branch)

PRIMA is a Python-based, LLM-assisted pipeline for rapid systematic reviews and meta-analyses.  
This branch adds a **forced OCR pre-pass** to reliably extract text from **scanned or non-searchable PDFs**.

If your PDFs already contain selectable text, use the **main branch** instead.

---

## AI-Assisted Meta-Analysis Extractor  
**PDF → PECO + 2×2 → Excel / CSV (OCR-enabled)**

This command-line tool ingests a folder of biomedical PDFs, extracts structured study data using a large language model, optionally parses 2×2 contingency tables, computes odds ratios, and exports results to Excel and CSV for downstream analysis.

---

## What This Version Does

For each PDF, the pipeline will:

1. **Run an OCR pre-pass** using OCRmyPDF (`--force-ocr`) when available  
2. **Extract text** (prefers PyMuPDF; falls back to pdfminer.six)  
3. **Send full-text content to an LLM** using a strict JSON schema  
4. **Extract structured fields**, including:
   - Citation: `title`, `year`, `journal`, `doi`
   - Study design & metadata
   - PECO-style fields:
     - `population`
     - `exposure_or_intervention`
     - `comparator`
     - `outcomes`
   - Optional 2×2 counts (if reported):
     - `a_elc_pos_cad_pos`
     - `b_elc_pos_cad_neg`
     - `c_elc_neg_cad_pos`
     - `d_elc_neg_cad_neg`
5. **Compute effect statistics** (when a,b,c,d are present):
   - Odds ratio (`or`)
   - log(OR), standard error, 95% CI
6. **Export results** to:
   - Excel (`.xlsx`, default)
   - CSV (`.csv`, optional)

---

## Key Difference From Main Branch

| Feature | Main Branch | OCR Branch |
|------|-----------|-----------|
| OCR support | ❌ No | ✅ Yes |
| Handles scanned PDFs | ❌ | ✅ Yes |
| Overwrites PDFs | ❌ No | ❌ No (uses temp files) |
| Runtime | Faster | Slower |

---

## Requirements

### System Requirements
- Python 3.10+ (3.11 recommended)
- macOS, Linux, or Windows
- OpenAI API key

### OCR Dependencies (Recommended for This Branch)
- **OCRmyPDF**
- **Tesseract**

### Python Dependencies
- `openai`
- `pandas`
- `openpyxl`
- `tqdm`
- `pymupdf` (preferred)
- `pdfminer.six` (fallback)

---

## Installation

### 1) Clone the repository
```bash
git clone https://github.com/hunterdeturk/PRIMA.git
cd PRIMA
```
### 2) Create and activate a virtual environment
```bash
python3 -m venv .venv
source .venv/bin/activate
```
### 3) Install Python dependencies
```bash
pip install --upgrade pip
pip install openai pandas openpyxl tqdm pymupdf pdfminer.six
```
### 4) Install OCR dependencies
```bash
macOS (Homebrew)

/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
brew install tesseract ocrmypdf
```

⸻

### Configuration

Set your OpenAI API key
```bash
export OPENAI_API_KEY="YOUR_API_KEY"
```
Optional: specify a model (defaults to gpt-5 if unset):
```bash
export OPENAI_MODEL="gpt-5"
```

⸻

## Usage

### Folder structure example
```bash
project/
  pdf_to_peco_OCR.py
  papers/
    study1.pdf
    study2.pdf
```
### Basic run (Excel output)
```bash
python3 pdf_to_peco_OCR.py -i papers -o peco_results.xlsx
```
### Excel + CSV output
```bash
python3 pdf_to_peco_OCR.py -i papers -o peco_results.xlsx --csv peco_results.csv
```
### Limit number of PDFs (for testing)
```bash
python3 pdf_to_peco_OCR.py -i papers --limit 3
```

⸻

## Notes & Limitations
 - If ocrmypdf is not installed, the script will still run but skip OCR.
 - OCR output is written to temporary directories (ocr_*).
If processing many PDFs, you may want to periodically clean these up.
 - OCR quality depends on scan resolution and document quality.
 - Extracted effect measures should always be manually verified before publication.

⸻

## Intended Use

PRIMA is designed as a research assistance tool to reduce manual labor during systematic reviews and meta-analyses.
It does not replace critical appraisal or human verification.

⸻


