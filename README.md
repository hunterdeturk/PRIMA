# PRIMA
PRIMA is a Python-based, LLM-assisted pipeline for rapid systematic reviews and meta-analyses. Using GPT-5.0, it processes local PDFs, extracts structured study data, and outputs CSV/Excel tables, benchmarked against published CAD meta-analyses.

# AI-Assisted Meta-Analysis Extractor (PDF → PECO + 2×2 → Excel/CSV)

A lightweight command-line pipeline that ingests a folder of biomedical PDFs, extracts structured study metadata + PECO fields using an LLM, optionally pulls 2×2 contingency table counts, and exports a tidy dataset to Excel/CSV for downstream meta-analysis (R/RevMan).

## What this does
Given a folder of PDFs, the script will:

1. **Read each PDF** (prefers PyMuPDF; falls back to pdfminer.six)
2. **Send extracted text to an LLM** (via OpenAI API) with a strict JSON schema prompt
3. **Return structured fields**, typically:
   - Citation fields: `title`, `year`, `journal`, `doi`
   - Study descriptors: `study_design`, `sample_size_total`, `follow_up`
   - PECO-style fields: `population`, `exposure_or_intervention`, `comparator`, `outcomes`
   - Optional 2×2 fields (if present in the paper): `a`, `b`, `c`, `d`
4. **Compute effect stats from 2×2** (when `a,b,c,d` are present):
   - `or`, `ln_or`, `se`, `ci_low`, `ci_high` (with continuity correction if needed)
5. **Export results** to:
   - `.xlsx` (default)
   - `.csv` (optional flag)

## Requirements

- macOS / Linux / Windows
- Python 3.10+ (3.11 recommended; 3.13 works but may be fussier with wheels)
- An OpenAI API key


## Quick Start

### 1) Clone the repo

```bash
git clone https://github.com/hunterdeturk/PRIMA.git
cd PRIMA
```
### 2) Create + activate a virtual environment
```bash
python3 -m venv .venv
source .venv/bin/activate
```
Confirm you see (.venv) in your terminal prompt.

### 3) Install dependencies
```bash

pip install --upgrade pip
pip install openai pandas openpyxl tqdm pdfminer.six pdfplumber pymupdf

pip install --upgrade pip
pip install openai pandas openpyxl tqdm pdfminer.six pdfplumber pymupdf
```
### 4) Set your OpenAI API key
```bash

export OPENAI_API_KEY="YOUR_KEY_HERE"

export OPENAI_API_KEY="YOUR_KEY_HERE"
```

Optional: pick a model (defaults to gpt-5 if your script uses that default)
```bash

export OPENAI_MODEL="gpt-5"
```

### 5) Put PDFs in a folder
```bash

project/
  pdf_to_peco.py
  papers/
    paper1.pdf
    paper2.pdf
    ...
```

### 6) Run the script
```bash

Basic run (Excel output):

python3 PDF_TO_PECO.py -i papers -o peco_results.xlsx

Excel + CSV:
python3 pdf_to_peco.py -i papers -o peco_results.xlsx --csv peco_results.csv
```


### Output columns (typical)

Your output file will include one row per PDF, with fields similar to:
```bash
	•	file
	•	title, year, journal, doi
	•	population
	•	exposure_or_intervention
	•	comparator
	•	outcomes
	•	follow_up
	•	sample_size_total
	•	study_design
	•	effect_measures
	•	notes
```

If your prompt/script supports 2×2 extraction, you’ll also see:
```bash 
	•	a_elc_pos_cad_pos
	•	b_elc_pos_cad_neg
	•	c_elc_neg_cad_pos
	•	d_elc_neg_cad_neg
```

And derived statistics:
```bash
	•	or
	•	ln_or
	•	se
	•	ci_low
	•	ci_high
	•	p_value (if extracted or reported; otherwise blank/null)
```
