🧠 Advanced 3D MRI Viewer

![Screenshot](docs/screenshot.png)

⚠️ Project Status: Work in Progress ⚠️

This project is under active development. While core functionality is stable, please anticipate potential bugs, and note that features are subject to change. Contributions and feedback are warmly welcomed!

Overview

A cutting-edge, feature-rich medical imaging viewer built with Python, designed for visualizing 3D MRI volumetric data and corresponding segmentation masks. This application serves as an evolving, powerful platform for researchers, clinicians, and students to inspect and analyze NIfTI-formatted medical data.

Tech Stack Highlights:

VTK for high-performance 3D rendering and volumetric visualization.

PyQt5 for a sleek, modern, and intuitive graphical user interface.

NiBabel for robust NIfTI file handling.


⚠️ Project Status: Active Development — Stable Core, Evolving Features

This repository is a practical, researcher-friendly MRI viewer built in Python. It combines high-performance 3D visualization with robust 2D slice inspection and a growing set of export and analysis utilities. The project is useful for prototyping, teaching, and lightweight clinical research workflows.

---

## What makes this viewer interesting

- Fast volume and surface rendering with both VTK and PyVista pipelines.
- Modern Qt-based GUI with a four-panel synchronized view (3D + axial/coronal/sagittal).
- Export-first design: built-in screenshot capture, high-fidelity PDF reporting with montages, and responsive background export with progress and cancellation.

---

## Quick Features Summary (What it currently does)

- UI & Navigation
	- Four linked views: 3D rendering + Axial/Coronal/Sagittal 2D slices.
	- Crosshair synchronization across 2D views.
	- Slice navigation via sliders and mouse wheel.

- 2D Snapshot & Slicing
	- Central-slice snapshots exported as PNG.
	- `create_all_2d_slices` and `_create_2d_slice_snapshot_mpl` support producing ALL slices per axis.
	- Optionally return images as Numpy arrays (`return_arrays=True`) or as temporary PNG files.
	- When generating full-axis slice lists, the code filters out empty slices (only includes slices where the mask is present).
	- Aspect-ratio preserving thumbnails and sampling (montage selection can sample up to a configurable maximum — by default we sample up to 15 slices evenly).

- 3D Snapshot & Surface Extraction
	- Pure-PyVista implementation (`_create_3d_snapshot_pv`) using `skimage.measure.marching_cubes` for per-label surface extraction (no VTK dependency inside that helper).
	- A VTK-based 3D snapshot pipeline is also present and used across the viewer.

- Export & Reporting
	- `export_volume_report` builds a multi-page PDF (using ReportLab) with:
		- Central thumbnails for each axis,
		- Per-axis montages of selected slices (preserving aspect ratio),
		- Volumetric analysis table (per-label volumes),
		- 3D overview images and per-label 3D snapshots.
	- Export runs in a background `QThread` (`ExportWorker`) so the UI stays responsive.
	- Visible progress bar and status messages show export progress.
	- Export can be canceled via a dedicated "Cancel Export" button; the worker checks a cancellation event and aborts gracefully.
	- Temporary images used during export are cleaned up after the PDF is built.

- Performance & Internals
	- Large-array transfers to VTK are performed with `vtk.util.numpy_support.numpy_to_vtk` (no Python-level loops), improving responsiveness when updating VTK image data.
	- Optimized mask handling: crops and marching-cubes per-label to reduce memory and speed up mesh generation.

- Image Processing Utilities
	- Several common filters and preprocessing steps are available (Gaussian smoothing, denoising, morphological ops, N4 bias correction via SimpleITK when installed).

---

## Installation

This project targets Python 3.8+ (many imaging stacks work best on 3.8–3.10). Start by creating a virtual environment and installing required packages.

Basic required dependencies are listed in `requirements.txt`, but several optional packages enable enhanced features (PDF export, montage creation, PyVista rendering, etc.).

Recommended install (includes optional extras used by export and PyVista):

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install matplotlib pillow reportlab pyvista nibabel
```

Notes:
- `vtk` can be tricky to install on some platforms; prefer `pip install vtk` or use conda packages if you run into issues.
- `pyvista` is optional but required for the PyVista-based 3D snapshot helper.

---

## Quickstart (Run the viewer)

```bash
python main.py
```

Load an MRI (`.nii`/`.nii.gz`) and (optionally) a segmentation mask. Use the left panel controls to toggle masks, adjust window/level, apply filters, and export reports.

---

## Development notes & architecture

- `src/mri_viewer.py` — main GUI, VTK integration, file IO, export orchestration, and application logic.
- `src/utils/snapshots.py` — helpers for 2D slice rendering (Matplotlib/Agg) and 3D snapshots (PyVista & VTK versions).
- `src/utils/*` — utility modules (style, mouse-wheel interactor, import checks, etc.).

Export details:
- The PDF export is implemented in `ExportWorker` (a `QThread`) to avoid blocking the main thread.
- Montages are created with Pillow when available; otherwise the exporter falls back to central thumbnails.
- The exporter supports cancellation and reports progress via a `progress` signal; the main UI shows a `QProgressBar`.

---

## Contribution & Roadmap

We welcome issues, PRs, and ideas. Possible next steps:

- Measurement tools (distance/angle/ROI stats) integrated into the 2D views.
- DICOM series import and more robust metadata handling.
- More interactive segmentation editing and label management.
- GPU-accelerated rendering or asynchronous IO for extremely large datasets.

If you want help implementing any of the items above, open an issue or a draft PR and we can iterate together.

---

Enjoy exploring MRI data — and tell us what you build with it!
