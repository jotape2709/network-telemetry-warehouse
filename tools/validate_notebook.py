from pathlib import Path

import matplotlib
import nbformat


matplotlib.use("Agg")
root = Path(__file__).resolve().parents[1]
path = root / "notebooks" / "01_warehouse_analysis.ipynb"
notebook = nbformat.read(path, as_version=4)
nbformat.validate(notebook)
namespace: dict[str, object] = {"__name__": "__main__"}
for cell in notebook.cells:
    if cell.cell_type == "code":
        exec(compile(cell.source, str(path), "exec"), namespace)
required = ["TL;DR", "Context & methods", "Data quality", "Results", "Takeaways"]
markdown = "\n".join(cell.source for cell in notebook.cells if cell.cell_type == "markdown")
missing = [section for section in required if section not in markdown]
if missing:
    raise ValueError(f"Missing sections: {missing}")
print("Notebook structure and code cells validated top to bottom.")

