# `docs/report/` — CRISP-DM Report

LaTeX sources for the project report. [`report.tex`](report.tex) is the
top-level document; one `.tex` fragment per CRISP-DM phase is included from
it.

| Phase | Source |
| --- | --- |
| Business Understanding | [`business_understanding.tex`](business_understanding.tex) |
| Data Understanding | [`data_understanding.tex`](data_understanding.tex) |
| Data Preparation | [`data_preparation.tex`](data_preparation.tex) |
| Modeling | [`modeling.tex`](modeling.tex) |
| Evaluation | [`evaluation.tex`](evaluation.tex) |
| Deployment | [`deployment.tex`](deployment.tex) |

Compiled output: [`report.pdf`](report.pdf).

## Building

`report.tex` sets `\graphicspath{{../../}}` so figures are read from the
project-root [`figures/`](../../figures/README.md) tree. Build from this
folder:

```bash
cd docs/report
pdflatex report.tex
pdflatex report.tex   # second pass for cross-references
```
