# AGENTS.md - Development Guidelines for MRI Viewer

## Project Overview

Python 3.8+ desktop application for visualizing 3D MRI volumetric data and segmentation masks. Uses PyQt5 for GUI, VTK for 3D rendering, and NiBabel for NIfTI file handling. The application is located in the `src/` directory with the entry point at `main.py`.

## Build, Lint, and Test Commands

### Running the Application
```bash
python main.py
```

### Dependencies Installation
```bash
pip install -r requirements.txt
pip install matplotlib pillow reportlab pyvista nibabel vtk
```

### Testing
```bash
# Run all tests
python test.py

# Run a specific test class
python -m pytest test.py::TestClassName -v

# Run a specific test method
python -m pytest test.py::TestClassName::test_method_name -v

# Run tests with verbose output
python -m unittest test -v
```

### No Linting Configuration
This project does not currently have formal linting (flake8, pylint) or formatting (black, ruff) configured. When adding linting:
- Use `ruff check .` for linting
- Use `ruff format .` for formatting
- Run both before committing

## Code Style Guidelines

### Imports
- Organize imports in three sections: stdlib, third-party, local modules
- Use wildcard imports sparingly; prefer explicit imports
- Put optional dependency imports in try/except blocks with descriptive messages
- Example pattern for optional dependencies:
```python
try:
    import nibabel as nib
    NIBABEL_AVAILABLE = True
except ImportError:
    print("NiBabel not available. Install with: pip install nibabel")
    NIBABEL_AVAILABLE = False
```

### Python Version
- Target Python 3.8+ (compatible with 3.8-3.10 for imaging stacks)

### Naming Conventions
- **Classes**: PascalCase (e.g., `MRIViewer`, `ExportWorker`)
- **Functions/variables**: snake_case (e.g., `load_label_config`, `mri_data`)
- **Constants**: UPPER_SNAKE_CASE (e.g., `MAX_HISTORY`, `VTK_AVAILABLE`)
- **Private methods**: prefix with underscore (e.g., `_create_2d_slice_snapshot_mpl`)
- **Qt widget names**: Use object names set via `setObjectName()` for QSS styling

### Types and Type Hints
- Add type hints for function signatures where beneficial
- Use Python's built-in types or typing module (e.g., `List`, `Dict`, `Optional`)
- Docstrings should document parameters, return values, and exceptions

### Error Handling
- Use try/except blocks with specific exception types when possible
- Include meaningful error messages that help with debugging
- Use traceback for unexpected errors in development:
```python
try:
    # operation
except Exception as e:
    traceback.print_exc()
    QMessageBox.critical(self, "Error", f"Failed to {action}: {str(e)}")
```
- Use `sys.excepthook` in main.py to catch fatal exceptions

### Docstrings
- Use triple double quotes for docstrings
- Include: description, parameters, return value, any exceptions raised
- Keep line length to 88 characters max (matches ruff/Black default)

### Qt and GUI Patterns
- Subclass from Qt widgets (e.g., `class MRIViewer(QMainWindow)`)
- Use signals for cross-thread communication (e.g., `progress = pyqtSignal(int, str)`)
- Run blocking operations in QThreads to keep UI responsive
- Use `QTimer.singleShot(0, self.method)` for deferred initialization
- Follow the existing pattern in `export_worker.py` for background workers

### File Organization
- Main GUI logic: `src/mri_viewer.py`
- Utility modules: `src/utils/` directory
- UI styles: `src/utils/style.py` (QSS themes)
- Export workers: `src/utils/export_worker.py`
- Entry point: `main.py` in repository root

### Qt Style Sheets (QSS)
- Store themes in `src/utils/style.py` as constants (e.g., `QSS_THEME`)
- Use object names for styling (e.g., `#leftPanel`, `#infoBox`)
- Follow the existing dark theme pattern in `MAIN_STYLE`

### MRI Data Handling
- Use NiBabel for NIfTI file loading (`nib.load()`)
- Access data via `nib_file.get_fdata()` for float arrays
- Access header via `nib_file.header`
- Access affine matrix via `nib_file.affine`
- Store label configurations in JSON format (see `label_config.json`)

### 3D Rendering
- Use VTK for 3D visualization with `QVTKRenderWindowInteractor`
- For 3D snapshots, prefer PyVista implementation in `snapshots.py` (`_create_3d_snapshot_pv`)
- Use `vtk.util.numpy_support` for efficient numpy-to-VTK array transfers

### UI Layout Patterns
- Use QSplitter for resizable panels (see `build_ui()` in mri_viewer.py)
- Use QStackedLayout for switching between views
- Use QGroupBox for organizing related controls with titles
- Use QStatusBar for status messages (see `statusBar().showMessage()`)

### Logging and Debugging
- Use `print()` with descriptive messages during development
- Include method/function names in debug output
- Use f-strings for formatted output: `print(f"Loaded {count} items")`
- Use traceback for exception details

### Git Commit Messages
- Use conventional commits format: `type(scope): description`
- Types: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`
- Example: `feat(mri_viewer): add label configuration save/load`

### Performance Considerations
- Transfer large arrays to VTK using `numpy_to_vtk` (no Python loops)
- Crop and process masks per-label for marching cubes to reduce memory
- Run export operations in background threads (QThread) to keep UI responsive
- Use `QApplication.processEvents()` during long operations if threading not feasible

### Testing Patterns
- Test classes inherit from `unittest.TestCase`
- Use `setUp()` method for test initialization
- Mock VTK and PyQt5 imports when testing non-GUI logic
- Test file operations with temporary files using `tempfile` module
