#!/usr/bin/env python3
import sys
import traceback
import numpy as np
from PyQt5.QtCore import Qt, QTimer

from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QHBoxLayout, QGridLayout, QGroupBox, QPushButton,
                             QLabel, QScrollArea, QStatusBar, QMessageBox,
                             QFileDialog, QSpinBox, QSlider, QCheckBox,
                             QStackedLayout, QShortcut, QSplitter, QComboBox,
                             QDoubleSpinBox, QScrollArea)
from PyQt5.QtGui import QKeySequence
from src.utils.style import MAIN_STYLE, QSS_THEME
from vtk.util import numpy_support # Add to imports
import json
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
import traceback
import vtk # Assuming this is already imported
# --- Import Dependencies ---
from src.utils.check_imports import *
from src.utils.mouse_wheel_interactor_style import MouseWheelInteractorStyle
from src.utils.snapshots import _create_2d_slice_snapshot_mpl, _create_3d_snapshot_pv
from src.utils.export_worker import ExportWorker



class MRIViewer(QMainWindow):
    def __init__(self):
        print("Initializing MRIViewer...")
        super().__init__()
        
        if not VTK_AVAILABLE:
            QMessageBox.critical(None, "Error", "VTK is not properly installed!")
            sys.exit(1)
        
        self.setWindowTitle("MRI Viewer Pro - Full Clinical Suite")
        self.resize(1400, 950)
        
        # Data holders
        self.mri_data = None
        self.mask_data = None

        self.fileName = None
        self.header = None
        self.affine = None

        # Persistent storage for label map
        self.label_config_path = "label_config.json"
        self.label_map = {} # {voxel_value (int): "Label Name" (str)}
        self.load_label_config() # Attempt to load config on startup

        self.mri_header = None
        self.mri_affine = None # To store the affine matrix
        self.mask_header = None
        self.current_slice = {'axial': 0, 'sagittal': 0, 'coronal': 0}
        self.vtk_widgets = {}
        self.renderers = {}
        self.view_containers = {} 
        
        # Undo/Redo Stack
        self.history_stack = [] 
        self.MAX_HISTORY = 10 
        
        # VTK objects for MRI
        self.image_data = None
        self.volume_property = None
        self.volume_mapper = None
        self.volume = None
        
        # VTK objects for Mask
        self.mask_image_data = None
        self.mask_actors_3d = [] 
        self.mask_lut = None 
        self.unique_mask_values = None 
        
        # Fullscreen state
        self.exit_fullscreen_btn = None
        self.current_fullscreen_view_name = None
        self.fullscreen_container = None 

        self.crosshair_actors = {'axial': [], 'sagittal': [], 'coronal': []}
        self.annotations = [] 
        self.annotation_mode = False


        try:
            print("Building UI...")
            self.build_ui()
            self.apply_style()
            self.setup_shortcuts()
            print("UI built successfully")
        except Exception as e:
            print(f"Error building UI: {e}")
            traceback.print_exc()
            QMessageBox.critical(self, "UI Error", f"Failed to build UI: {str(e)}")
            sys.exit(1)

    def load_label_config(self, filepath=None):
        """Loads the label configuration from a JSON file."""
        if filepath:
            self.label_config_path = filepath
        
        try:
            with open(self.label_config_path, 'r') as f:
                # Load JSON and convert keys to integers, as JSON saves them as strings
                data = json.load(f)
                self.label_map = {int(k): v for k, v in data.items()}
            self.statusBar().showMessage(f"Loaded label config from: {self.label_config_path}")
            return True
        except FileNotFoundError:
            self.statusBar().showMessage(f"Label config file not found. Using default empty map.")
            self.label_map = {}
            return False
        

    def save_label_config(self):
        """Saves the current label map to the persistent JSON file."""
        try:
            # We save keys as strings, standard for JSON
            with open(self.label_config_path, 'w') as f:
                json.dump(self.label_map, f, indent=4)
            self.statusBar().showMessage(f"Saved label config to: {self.label_config_path}")
        except Exception as e:
            QMessageBox.critical(self, "Config Error", f"Failed to save label config: {e}")

    def prompt_load_label_config(self):
        """Prompts the user to select and load a JSON label config file."""
        filepath, _ = QFileDialog.getOpenFileName(
            self, "Load Label Configuration", "", "JSON Files (*.json)"
        )
        if filepath:
            self.load_label_config(filepath)

    def prompt_save_label_config(self):
        """Prompts the user to select a path to save the current label config file."""
        filepath, _ = QFileDialog.getSaveFileName(
            self, "Save Label Configuration", self.label_config_path, "JSON Files (*.json)"
        )
        if filepath:
            self.label_config_path = filepath
            self.save_label_config()

    def calculate_label_volumes(self):
        """
        Calculates the volume for each label found in the loaded mask_data.
        
        Returns:
            A dictionary {label_name: volume_cm3}
        """
        if self.mask_data is None:
            QMessageBox.warning(self, "Reporting Error", "No segmentation mask data loaded.")
            return {}
        
        if self.header is None:
            QMessageBox.warning(self, "Reporting Error", 
                                "Cannot calculate volume: NiBabel header (voxel size) is missing.")
            return {}

        # 1. Get Voxel Dimensions
        try:
            # NiBabel headers store voxel sizes in qform_code/sform_code
            # pixdim[1:4] is typically used for spatial dimensions (mm or similar)
            voxel_dims = self.header.get_zooms()[:3]
            voxel_volume_mm3 = voxel_dims[0] * voxel_dims[1] * voxel_dims[2]
            # Convert mm³ to cm³ (1 cm³ = 1000 mm³)
            voxel_volume_cm3 = voxel_volume_mm3 / 1000.0
        except Exception as e:
            QMessageBox.critical(self, "Volume Error", f"Failed to read voxel dimensions: {e}")
            return {}

        # 2. Count Voxels for each unique label value
        unique_labels, counts = np.unique(self.mask_data, return_counts=True)
        volume_results = {}
        
        # 3. Calculate Volume and Map Names
        for label_val, count in zip(unique_labels, counts):
            # Skip label 0, which is typically the background
            if label_val == 0:
                continue

            # Get the name from the config map, or use the integer value as a fallback
            label_name = self.label_map.get(label_val, f"Label_{label_val} (UNMAPPED)")
            
            # Volume = Voxel Count * Volume per Voxel
            volume_cm3 = count * voxel_volume_cm3
            
            volume_results[label_name] = volume_cm3
            
        return volume_results

    def export_volume_report(self):
        """Calculates volumes and exports a PDF report, including images."""
        
        volume_results = self.calculate_label_volumes()
        if not volume_results:
            self.statusBar().showMessage("Export failed: No valid volumes calculated.")
            return

        # Prompt user for save location
        default_filename = f"MRI_Volume_Report_{self.fileName or 'Untitled'}.pdf"
        filepath, _ = QFileDialog.getSaveFileName(
            self, "Export Volume Report", default_filename, "PDF Files (*.pdf)"
        )

        # If user canceled the save dialog, abort cleanly
        if not filepath:
            try:
                self.btn_export_report.setEnabled(True)
            except Exception:
                pass
            self.statusBar().showMessage("Export canceled")
            return

        # Run the export (including montage generation) in a background thread
        # to avoid blocking the UI. The ExportWorker performs the heavy work and
        # emits a finished signal when done. Keep a reference on self to avoid
        # the QThread object being garbage-collected while running.
        try:
            worker = ExportWorker(self, filepath, volume_results)
        except Exception as e:
            QMessageBox.critical(self, "Export Error", f"Failed to initialize export worker: {e}")
            return

        # Store worker reference so Python/GIL doesn't garbage-collect it
        self._export_worker = worker

        # Disable export button while running
        try:
            self.btn_export_report.setEnabled(False)
        except Exception:
            pass

        def _on_finished(success, message):
            try:
                self.btn_export_report.setEnabled(True)
                self.btn_cancel_export.setEnabled(False)
            except Exception:
                pass
            # Clean up reference and schedule deletion
            try:
                if hasattr(self, '_export_worker') and self._export_worker is worker:
                    # Give the thread object a chance to be deleted later
                    self._export_worker.deleteLater()
                    self._export_worker = None
            except Exception:
                pass

            if success:
                self.statusBar().showMessage(message)
                QMessageBox.information(self, "Export Success", message)
            else:
                self.statusBar().showMessage("Export failed.")
                QMessageBox.critical(self, "Export Error", message)

        # Ensure cancel button is disabled if worker already finished immediately
        try:
            if not getattr(self, '_export_worker', None) or not getattr(self, '_export_worker', None).isRunning():
                self.btn_cancel_export.setEnabled(False)
        except Exception:
            pass

        worker.finished.connect(_on_finished)
        # connect progress updates to status bar
        try:
            worker.progress.connect(lambda p, msg: self.statusBar().showMessage(f"Export: {p}% - {msg}"))
        except Exception:
            pass

        try:
            worker.start()
        except Exception as e:
            # Ensure button is re-enabled and reference cleaned
            try:
                self.btn_export_report.setEnabled(True)
            except Exception:
                pass
            try:
                if hasattr(self, '_export_worker'):
                    self._export_worker = None
            except Exception:
                pass
            QMessageBox.critical(self, "Export Error", f"Failed to start export worker: {e}")
            return
        # enable cancel button once worker started
        try:
            self.btn_cancel_export.setEnabled(True)
        except Exception:
            pass
        
    def _on_cancel_export_clicked(self):
        """Signal the running export worker to cancel."""
        worker = getattr(self, '_export_worker', None)
        if worker is None:
            self.statusBar().showMessage("No export in progress")
            return
        try:
            worker._cancel_event.set()
            self.statusBar().showMessage("Export cancellation requested...")
            try:
                self.btn_cancel_export.setEnabled(False)
            except Exception:
                pass
        except Exception as e:
            QMessageBox.warning(self, "Cancel Error", f"Failed to request cancellation: {e}")
    
    def build_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        self.stacked_layout = QStackedLayout(central_widget)
        
        # --- Page 0: Normal Grid View ---
        normal_view_widget = QWidget()
        normal_layout = QHBoxLayout(normal_view_widget)
        
        left_panel = self.build_left_panel()
        normal_layout.addWidget(left_panel, 1)
        
        right_panel = self.build_vis_grid()
        normal_layout.addWidget(right_panel, 4)
        
        self.stacked_layout.addWidget(normal_view_widget)
        
        self.setStatusBar(QStatusBar())
        self.statusBar().showMessage("Ready")

    def closeEvent(self, event):
        """Ensure background export worker finishes before closing to avoid
        'QThread: Destroyed while thread is still running' crashes."""
        worker = getattr(self, '_export_worker', None)
        if worker is not None and worker.isRunning():
            # Inform user and wait briefly for the thread to finish
            self.statusBar().showMessage("Waiting for export to finish...")
            # Wait up to 10 seconds
            # If user requested cancellation via UI, signal the worker
            try:
                if hasattr(self, 'btn_cancel_export') and self.btn_cancel_export.isEnabled():
                    self._export_worker._cancel_event.set()
            except Exception:
                pass
            worker.wait(10000)
            if worker.isRunning():
                QMessageBox.warning(self, "Close Warning", "Export is still running. Close will proceed and terminate the worker.")
        super().closeEvent(event)
    
    def build_left_panel(self):
        panel = QWidget()
        panel.setObjectName("leftPanel")
        layout = QVBoxLayout(panel)
        
        # --- File Operations ---
        file_group = QGroupBox("File Operations")
        file_layout = QVBoxLayout()
        
        self.btn_load_mri = QPushButton("Load MRI")
        self.btn_load_mri.setObjectName("btnLoadMRI")
        self.btn_load_mask = QPushButton("Load Mask")
        self.btn_export_screenshot = QPushButton("Export Screenshot")
        self.btn_export_mri_data = QPushButton("Export Modified MRI (.nii.gz)")
        
        file_layout.addWidget(self.btn_load_mri)
        file_layout.addWidget(self.btn_load_mask)
        file_layout.addWidget(self.btn_export_screenshot)
        file_layout.addWidget(self.btn_export_mri_data)
        file_group.setLayout(file_layout)
        
        # --- Clinical Image Processing ---
        proc_group = QGroupBox("Clinical Image Processing")
        proc_layout = QVBoxLayout()
        
        # 1. Parameter Input (General)
        proc_layout.addWidget(QLabel("Global Param (Thresh/Gamma/Sigma/Size):"))
        self.proc_param_spin = QDoubleSpinBox()
        self.proc_param_spin.setRange(0.01, 50000.00)
        self.proc_param_spin.setValue(1.0) # Default sensible for gamma/sigma
        self.proc_param_spin.setSingleStep(0.1)
        proc_layout.addWidget(self.proc_param_spin)

        # NEW: N-Classes Input for Multi-Otsu
        self.n_classes_group = QWidget()
        n_classes_layout = QVBoxLayout(self.n_classes_group)
        n_classes_layout.setContentsMargins(0, 5, 0, 5)

        n_classes_layout.addWidget(QLabel("Multi-Otsu Classes (2-10):"))
        self.n_classes_spin = QSpinBox()
        self.n_classes_spin.setRange(2, 10)
        self.n_classes_spin.setValue(3)
        self.n_classes_spin.setSingleStep(1)
        n_classes_layout.addWidget(self.n_classes_spin)

        proc_layout.addWidget(self.n_classes_group)
        self.n_classes_group.setVisible(False) # Start hidden
        
        # 2. Histogram & Filters
        proc_layout.addWidget(QLabel("Enhancement & Filtering:"))
        self.combo_hist = QComboBox()
        self.combo_hist.addItems([
            "Select Operation...",
            "--- Contrast ---",
            "1. T1-Optimized CLAHE (Adaptive)",
            "2. Global Histogram Equalization",
            "3. Gamma Correction (Brighten)",
            "4. Gamma Correction (Darken)",
            "5. Sigmoid Contrast Stretch",
            "6. Rescale Intensity (Min/Max Norm)",
            "--- Filtering / Denoising ---",
            "7. Unsharp Masking (Sharpen Edges)",
            "8. Total Variation Denoising (Preserve Edges)",
            "9. Gaussian Smoothing (Reduce Noise)",
            "10. 3D Median Filter (Edge-Preserving Noise)",
            "11. Morphological Erosion (Skull-Strip Proxy)",
            "--- Bias Field Correction ---", 
            "12. N4 Bias Field Correction (Requires SimpleITK)" 
        ])
        proc_layout.addWidget(self.combo_hist)
        
        # 3. CLAHE Controls
        self.clahe_group = QWidget()
        clahe_layout = QVBoxLayout(self.clahe_group)
        clahe_layout.setContentsMargins(0,0,0,0)
        
        h_layout1 = QHBoxLayout()
        h_layout1.addWidget(QLabel("CLAHE Clip:"))
        self.clahe_clip = QDoubleSpinBox()
        self.clahe_clip.setRange(0.001, 0.1)
        self.clahe_clip.setSingleStep(0.005)
        self.clahe_clip.setValue(0.015) 
        self.clahe_clip.setDecimals(3)
        h_layout1.addWidget(self.clahe_clip)
        clahe_layout.addLayout(h_layout1)

        h_layout2 = QHBoxLayout()
        h_layout2.addWidget(QLabel("Tile Grid:"))
        self.clahe_tile = QSpinBox()
        self.clahe_tile.setRange(4, 64)
        self.clahe_tile.setValue(16) 
        h_layout2.addWidget(self.clahe_tile)
        clahe_layout.addLayout(h_layout2)
        
        proc_layout.addWidget(self.clahe_group)
        self.combo_hist.currentIndexChanged.connect(self.toggle_clahe_controls)
        self.clahe_group.setVisible(False) 

        self.btn_apply_hist = QPushButton("Apply Operation")
        self.btn_apply_hist.clicked.connect(self.apply_histogram_op)
        proc_layout.addWidget(self.btn_apply_hist)
        
        # 4. Thresholding Ops
        proc_layout.addWidget(QLabel("Thresholding & Segmentation:"))
        self.combo_thresh = QComboBox()
        self.combo_thresh.addItems([
            "Select Operation...",
            "--- Manual ---",
            "1. Binary Threshold (Manual)",
            "2. Binary Inverted (Manual)",
            "3. Truncate (Cap Values)",
            "4. Range Pass (Mid-tones)",
            "--- Automated (Global) ---",
            "5. Otsu's Method (2 Classes)",
            "6. Li's Method (2 Classes)",
            "7. Multi-Otsu (N Classes)",
            "--- Automated (Local) ---",
            "8. Local Adaptive (Gaussian Block)"
        ])
        proc_layout.addWidget(self.combo_thresh)
        
        # Connect to toggle the N-Classes input
        self.combo_thresh.currentIndexChanged.connect(self.toggle_n_classes_controls) 
        
        self.btn_apply_thresh = QPushButton("Apply Threshold")
        self.btn_apply_thresh.clicked.connect(self.apply_threshold_op)
        proc_layout.addWidget(self.btn_apply_thresh)
        
        # 5. Conversion Button (NEW FEATURE)
        self.btn_to_int = QPushButton("Convert to Integer Labels")
        self.btn_to_int.setStyleSheet("background-color: #004d40; color: white;")
        proc_layout.addWidget(self.btn_to_int)

        # Undo
        self.btn_undo = QPushButton("Undo Last Edit")
        self.btn_undo.setStyleSheet("background-color: #8B0000; color: white;")
        self.btn_undo.setEnabled(False)
        self.btn_undo.clicked.connect(self.undo_last_operation)
        proc_layout.addWidget(self.btn_undo)
        
        proc_group.setLayout(proc_layout)

        # --- Mask Controls ---
        mask_group = QGroupBox("Mask Controls")
        mask_layout = QVBoxLayout()
        
        self.show_mask_check = QCheckBox("Show Mask")
        self.show_mask_check.stateChanged.connect(self.toggle_mask_visibility)
        self.show_mask_check.setEnabled(False)
        
        mask_opacity_layout = QHBoxLayout()
        mask_opacity_layout.addWidget(QLabel("Opacity:"))
        self.mask_opacity_slider = QSlider(Qt.Horizontal)
        self.mask_opacity_slider.setRange(0, 100)
        self.mask_opacity_slider.setValue(60)
        self.mask_opacity_slider.valueChanged.connect(self.update_mask_opacity)
        self.mask_opacity_slider.setEnabled(False)
        mask_opacity_layout.addWidget(self.mask_opacity_slider)
        
        mask_layout.addWidget(self.show_mask_check)
        mask_layout.addLayout(mask_opacity_layout)
        mask_group.setLayout(mask_layout)
        

        # --- Optimization 4: Window/Level Presets ---
        #wl_group = QGroupBox("Window / Level (Contrast)")
        #wl_layout = QVBoxLayout()
        
        #wl_layout.addWidget(QLabel("Clinical Presets:"))
        #self.combo_wl = QComboBox()
        #self.combo_wl.addItems([
        #    "Select Preset...",
        #    "Full Dynamic Range (Default)",
        #    "Brain (High Contrast)",
        #    "Soft Tissue (Wide)",
        #    "Bone / Hard Structure",
        #    "Stroke (Narrow)",
        #])
        #self.combo_wl.currentIndexChanged.connect(self.apply_wl_preset)
        #wl_layout.addWidget(self.combo_wl)
        
        # Add a custom slider for manual W/L fine tuning if desired
        # (For brevity, just the dropdown is shown here)
        
        #wl_group.setLayout(wl_layout)
        #layout.addWidget(wl_group) # Add to main left panel layout


        # --- Rendering Options ---
        render_group = QGroupBox("Rendering Options")
        render_layout = QVBoxLayout()
        
        self.volume_rendering_check = QCheckBox("Volume Rendering")
        self.volume_rendering_check.setChecked(False)
        self.volume_rendering_check.stateChanged.connect(self.toggle_rendering_mode)
        render_layout.addWidget(self.volume_rendering_check)
        
        render_group.setLayout(render_layout)

        annotation_group = QGroupBox("Annotations")
        anno_layout = QVBoxLayout()
        
        self.btn_toggle_anno = QPushButton("Toggle Annotation Mode")
        self.btn_toggle_anno.setCheckable(True)
        self.btn_toggle_anno.toggled.connect(self.toggle_annotation_mode)
        
        anno_layout.addWidget(self.btn_toggle_anno)
        annotation_group.setLayout(anno_layout)
        
        layout.addWidget(file_group)
        layout.addWidget(proc_group)
        layout.addWidget(mask_group)
        layout.addWidget(render_group)
        #layout.addWidget(annotation_group)
        layout.addStretch()

        # --- NEW: Reporting & Configuration Group ---
        report_group = QGroupBox("Reporting & Configuration")
        report_layout = QVBoxLayout()
        # Button to load a custom JSON label config
        btn_load_config = QPushButton("Load Label Config (JSON)")
        btn_load_config.clicked.connect(self.prompt_load_label_config)
        report_layout.addWidget(btn_load_config)
        # Button to save the current label config
        btn_save_config = QPushButton("Save Current Label Config")
        btn_save_config.clicked.connect(self.prompt_save_label_config)
        report_layout.addWidget(btn_save_config)
        report_layout.addWidget(QLabel("---"))
        # Button to export the final PDF report
        self.btn_export_report = QPushButton("Export Volume Report (PDF)")
        self.btn_export_report.clicked.connect(self.export_volume_report)
        # Cancel export button (disabled until export starts)
        self.btn_cancel_export = QPushButton("Cancel Export")
        self.btn_cancel_export.setEnabled(False)
        self.btn_cancel_export.clicked.connect(self._on_cancel_export_clicked)
        # You may want to disable this if self.mask_data is None
        report_layout.addWidget(self.btn_export_report)
        report_layout.addWidget(self.btn_cancel_export)

        report_group.setLayout(report_layout)
        layout.addWidget(report_group)
        layout.addStretch()


        
        # Connect signals
        self.btn_load_mri.clicked.connect(self.load_mri)
        self.btn_load_mask.clicked.connect(self.load_mask)
        self.btn_export_screenshot.clicked.connect(self.export_screenshot)
        self.btn_export_mri_data.clicked.connect(self.export_modified_mri)
        self.btn_to_int.clicked.connect(self.convert_to_integer_labels) # NEW CONNECTION
        

        
        return panel

    def apply_wl_preset(self, index):
        """
        Optimization 4: Applies Window/Level presets using percentiles.
        This is more robust for MRI than hardcoded values.
        """
        if self.mri_data is None: return
        txt = self.combo_wl.currentText()
        if "Select" in txt: return

        data = self.mri_data
        # Calculate percentiles for robust min/max ignoring outliers
        p_min, p_max = np.min(data), np.max(data)
        p1, p99 = np.percentile(data, (1, 99))
        mean_val = np.mean(data)
        
        # Determine Target Window (Width) and Level (Center)
        if "Full Dynamic Range" in txt:
            target_window = p_max - p_min
            target_level = (p_max + p_min) / 2
            
        elif "Brain" in txt:
            # High contrast: Focus on the middle 80% of data
            # Narrower window = Higher contrast
            target_window = (p99 - p1) * 0.6 
            target_level = mean_val
            
        elif "Soft Tissue" in txt:
            # Wider window to see variations
            target_window = (p99 - p1) * 1.2
            target_level = mean_val
            
        elif "Stroke" in txt:
            # Very narrow window to distinguish slight intensity changes
            target_window = (p99 - p1) * 0.3
            target_level = mean_val
            
        elif "Bone" in txt:
            # Focus on the very bright signals
            target_window = (p_max - p_min) * 0.3
            target_level = p99
            
        else:
            return

        # Apply to all 2D Views
        for view in ['axial', 'sagittal', 'coronal']:
            renderer = self.renderers[view]
            actors = renderer.GetActors()
            actors.InitTraversal()
            actor = actors.GetNextActor()
            # The first actor is usually the MRI ImageActor
            if actor:
                actor.GetProperty().SetColorWindow(target_window)
                actor.GetProperty().SetColorLevel(target_level)
                
        self.update_2d_views()
        self.statusBar().showMessage(f"Applied Preset: {txt} (W: {target_window:.1f}, L: {target_level:.1f})")
    
    def toggle_clahe_controls(self, index):
        # Index 2 is CLAHE (due to separator)
        is_clahe = ("CLAHE" in self.combo_hist.currentText())
        self.clahe_group.setVisible(is_clahe)

    def toggle_n_classes_controls(self, index):
        """Toggles visibility of N-classes spin box for Multi-Otsu."""
        is_multi_otsu = ("Multi-Otsu" in self.combo_thresh.currentText())
        self.n_classes_group.setVisible(is_multi_otsu)
        
    # ---------------------------------------------------------
    # Processing & Undo Logic
    # ---------------------------------------------------------

    def convert_to_integer_labels(self):
        """
        Rounds current mri_data to the nearest integer and converts the datatype 
        to unsigned 16-bit integer (np.uint16), suitable for segmentation maps.
        """
        if self.mri_data is None:
            QMessageBox.warning(self, "Warning", "No MRI data loaded to convert.")
            return

        self.push_to_history()
        self.statusBar().showMessage("Converting image data to integer labels...")
        QApplication.setOverrideCursor(Qt.WaitCursor)

        try:
            data = self.mri_data.copy().astype(np.float64) # Work on a copy as float64

            # 1. Ensure all values are non-negative before rounding
            # This handles cases where segmentation might output slight negative floats
            min_val = np.min(data)
            if min_val < 0:
                data -= min_val
                self.statusBar().showMessage("Warning: Negative values found and shifted to be non-negative before casting.")
                
            # 2. Round to the nearest integer
            rounded_data = np.rint(data)

            # 3. Cast to uint16 (standard for most segmentation labels)
            self.mri_data = rounded_data.astype(np.uint16)

            # 4. Update the visualization
            self.update_vtk_data()
            
            self.statusBar().showMessage(f"Conversion complete. Data type: {self.mri_data.dtype}, Min: {np.min(self.mri_data)}, Max: {np.max(self.mri_data)}")
            
        except Exception as e:
            QMessageBox.critical(self, "Conversion Error", f"Failed to convert to integer labels: {str(e)}")
            self.undo_last_operation()
        finally:
            QApplication.restoreOverrideCursor()
    
    def push_to_history(self):
        """Saves current state to history stack."""
        if self.mri_data is not None:
            self.history_stack.append(np.copy(self.mri_data))
            if len(self.history_stack) > self.MAX_HISTORY:
                self.history_stack.pop(0) 
            self.btn_undo.setEnabled(True)
            self.statusBar().showMessage("State saved to history.")

    def undo_last_operation(self):
        """Restores the previous state."""
        if not self.history_stack:
            return
            
        self.statusBar().showMessage("Undoing last operation...")
        previous_data = self.history_stack.pop()
        self.mri_data = previous_data
        
        self.update_vtk_data()
        
        if not self.history_stack:
            self.btn_undo.setEnabled(False)
            
        self.statusBar().showMessage("Undo successful.")

    

    def update_vtk_data(self):
        """Refreshes the VTK ImageData from self.mri_data numpy array using numpy_support."""
        if self.mri_data is None: return

        # 1. Normalize Data Types for VTK
        # VTK is sensitive to C-contiguous vs Fortran-contiguous arrays. 
        # We transpose to match VTK's coordinate system if necessary, but typically
        # flattening C-ordered numpy matches VTK point data if dimensions are set right.
        if self.mri_data.dtype == np.uint16:
            vtk_type = vtk.VTK_UNSIGNED_SHORT
        else:
            self.mri_data = self.mri_data.astype(np.float32) # Standardize float
            vtk_type = vtk.VTK_FLOAT

        depth, height, width = self.mri_data.shape # Z, Y, X order in Numpy

        # 2. Efficiently create/update VTK object
        if self.image_data is None:
            self.image_data = vtk.vtkImageData()
        
        self.image_data.SetDimensions(width, height, depth) # VTK uses X, Y, Z
        self.image_data.AllocateScalars(vtk_type, 1)

        # 3. The "Magic": Convert Numpy -> VTK without loops
        # ravel(order='C') flattens row-major. 
        # Note: You might need to check if your view is flipped. 
        # If so, use np.flip() on the axis before flattening.
        flat_data = self.mri_data.ravel(order='C') 
        vtk_array = numpy_support.numpy_to_vtk(num_array=flat_data, deep=True, array_type=vtk_type)
        self.image_data.GetPointData().SetScalars(vtk_array)
        
        self.image_data.Modified()

        # Update Histogram/Transfer Functions (Keep your existing logic here)
        if self.volume_property:
            min_val = np.min(self.mri_data)
            max_val = np.max(self.mri_data)
            # ... (Rest of your transfer function logic) ...

        self.update_2d_views()
        self.vtk_widgets['3d'].GetRenderWindow().Render()
        
    def apply_n4_bias_field_correction(self, data):
        """Applies N4 Bias Field Correction using SimpleITK."""
        if not SIMPLEITK_AVAILABLE:
            QMessageBox.critical(self, "Error", "SimpleITK is required for N4 Bias Field Correction.")
            return data
            
        try:
            # 1. Convert numpy array to SimpleITK Image
            sitk_image = sitk.GetImageFromArray(data.astype(np.float32))
            
            # 2. Setup N4
            corrector = sitk.N4BiasFieldCorrectionImageFilter()
            
            # 3. Configure and Execute (Reduced iterations for speed/demo)
            corrector.SetMaximumNumberOfIterations([5, 5, 5, 5])
            
            corrected_image = corrector.Execute(sitk_image)
            
            # 4. Convert back to numpy
            new_data = sitk.GetArrayFromImage(corrected_image)
            
            # 5. Optional: Rescale to original intensity range
            new_min = np.min(new_data)
            new_max = np.max(new_data)
            orig_min = np.min(data)
            orig_max = np.max(data)
            
            if new_max > new_min:
                new_data = ((new_data - new_min) / (new_max - new_min)) * (orig_max - orig_min) + orig_min
            
            self.statusBar().showMessage("N4 Bias Field Correction applied (5 iterations).")
            return new_data
            
        except Exception as e:
            QMessageBox.critical(self, "N4 Error", f"N4 BFC failed: {str(e)}\nEnsure SimpleITK is installed correctly.")
            traceback.print_exc()
            return data # Return original data on failure


    def set_window_level(self, preset):
        # Example for CT (Hounsfield Units) or normalized MRI
        presets = {
            'Brain': (80, 40), # Window 80, Level 40
            'Bone': (2000, 500),
            'Soft Tissue': (400, 50)
        }
        if preset in presets:
            w, l = presets[preset]
            # In VTK, ColorWindow = w, ColorLevel = l
            for view in ['axial', 'sagittal', 'coronal']:
                actors = self.renderers[view].GetActors()
                actors.InitTraversal()
                actor = actors.GetNextActor()
                if actor:
                    actor.GetProperty().SetColorWindow(w)
                    actor.GetProperty().SetColorLevel(l)
            self.update_2d_views()

    def on_processing_finished(self, new_data):
        self.setCursor(Qt.ArrowCursor)
        self.push_to_history()
        self.mri_data = new_data
        self.update_vtk_data()
        self.statusBar().showMessage("Processing Complete")
        
    def apply_histogram_op(self):
        if self.mri_data is None: return
        if not SKIMAGE_AVAILABLE and "N4" not in self.combo_hist.currentText():
            QMessageBox.warning(self, "Error", "Scikit-image/Scipy is required for most operations.")
            return

        txt = self.combo_hist.currentText()
        if "Select" in txt or "---" in txt: return
        
        self.push_to_history()
        self.statusBar().showMessage(f"Applying: {txt}...")
        QApplication.setOverrideCursor(Qt.WaitCursor)
        
        data = self.mri_data.astype(np.float64)
        min_v = np.min(data)
        max_v = np.max(data)
        param = self.proc_param_spin.value()
                    
        try:
            # --- BIAS FIELD CORRECTION ---
            if "N4 Bias Field Correction" in txt:
                if not SIMPLEITK_AVAILABLE:
                    QMessageBox.critical(self, "Error", "SimpleITK is required for N4 Bias Field Correction.")
                    return # Exit if dependency is missing
                self.mri_data = self.apply_n4_bias_field_correction(data)
                
            # --- CONTRAST ---
            
            # 1. T1-Optimized CLAHE
            elif "CLAHE" in txt:
                # Normalize 0-1
                data_norm = (data - min_v) / (max_v - min_v + 1e-8)
                clip_lim = self.clahe_clip.value()
                tile_s = self.clahe_tile.value()
                
                processed_slices = []
                for i in range(data.shape[0]):
                    slice_img = data_norm[i, :, :]
                    k_h = max(1, slice_img.shape[0] // tile_s)
                    k_w = max(1, slice_img.shape[1] // tile_s)
                    enhanced_slice = exposure.equalize_adapthist(
                        slice_img, kernel_size=(k_h, k_w), clip_limit=clip_lim
                    )
                    processed_slices.append(enhanced_slice)
                
                new_data = np.stack(processed_slices, axis=0)
                self.mri_data = new_data * (max_v - min_v) + min_v

            # 2. Global Equalization
            elif "Global Histogram" in txt:
                hist, bins = np.histogram(data.flatten(), 256, density=True)
                cdf = hist.cumsum()
                cdf = (cdf - cdf.min()) * (max_v - min_v) / (cdf.max() - cdf.min()) + min_v
                flat = data.flatten()
                new_data = np.interp(flat, bins[:-1], cdf)
                self.mri_data = new_data.reshape(data.shape)

            # 3. Gamma Brighten
            elif "Gamma Correction (Brighten)" in txt:
                gamma = 0.5 
                norm = (data - min_v) / (max_v - min_v + 1e-5)
                res = np.power(norm, gamma)
                self.mri_data = res * (max_v - min_v) + min_v

            # 4. Gamma Darken
            elif "Gamma Correction (Darken)" in txt:
                gamma = 2.0 
                norm = (data - min_v) / (max_v - min_v + 1e-5)
                res = np.power(norm, gamma)
                self.mri_data = res * (max_v - min_v) + min_v

            # 5. Sigmoid
            elif "Sigmoid" in txt:
                mean = np.mean(data)
                gain = 10 / (max_v - min_v) 
                self.mri_data = (max_v - min_v) * (1 / (1 + np.exp(-gain * (data - mean)))) + min_v
                
            # 6. Rescale Intensity (Normalization)
            elif "Rescale Intensity" in txt:
                # Stretches intensity to fill 0-param range or min/max
                p1, p99 = np.percentile(data, (2, 98))
                self.mri_data = exposure.rescale_intensity(data, in_range=(p1, p99))

            # --- FILTERING ---

            # 7. Unsharp Masking
            elif "Unsharp Masking" in txt:
                # Radius = param (e.g., 1.0), Amount = 1.0
                self.mri_data = filters.unsharp_mask(data, radius=param, amount=1.0) * max_v

            # 8. Total Variation Denoising
            elif "Total Variation" in txt:
                # Weight = param (lower is less smoothing)
                # This is heavy, apply slice by slice or limited iterations
                weight = 0.1 * param 
                self.mri_data = restoration.denoise_tv_chambolle(data, weight=weight) * max_v

            # 9. Gaussian Smoothing
            elif "Gaussian Smoothing" in txt:
                # Sigma = param
                self.mri_data = ndimage.gaussian_filter(data, sigma=param)

            # 10. 3D Median Filter
            elif "3D Median Filter" in txt:
                # Use param as radius/size (e.g., 3 is common)
                size = max(3, int(param))
                if size % 2 == 0: size += 1 # Ensure odd size
                self.mri_data = ndimage.median_filter(data, size=size)

            # 11. Morphological Erosion
            elif "Morphological Erosion" in txt:
                # Use simple diamond structure
                # Warning: 3D erosion is slow
                # Apply slice-by-slice for speed
                struct = morphology.disk(max(1, int(param)))
                processed_slices = []
                for i in range(data.shape[0]):
                    processed_slices.append(morphology.erosion(data[i,:,:], struct))
                self.mri_data = np.stack(processed_slices, axis=0)
            
            # --- FALLBACK ---
            else:
                self.statusBar().showMessage("Invalid operation selected.")
                QApplication.restoreOverrideCursor()
                return

            self.update_vtk_data()
            if not self.statusBar().currentMessage().startswith("N4"):
                self.statusBar().showMessage("Operation applied successfully.")
            
        except Exception as e:
            QMessageBox.critical(self, "Processing Error", str(e))
            traceback.print_exc()
            self.undo_last_operation() 
        finally:
            QApplication.restoreOverrideCursor()

    def apply_threshold_op(self):
        if self.mri_data is None: return
        if not SKIMAGE_AVAILABLE:
            QMessageBox.warning(self, "Error", "Scikit-image required.")
            return

        txt = self.combo_thresh.currentText()
        if "Select" in txt or "---" in txt: return
        
        param_val = self.proc_param_spin.value()
        
        self.push_to_history()
        self.statusBar().showMessage(f"Applying: {txt}...")
        QApplication.setOverrideCursor(Qt.WaitCursor)
        
        data = self.mri_data.copy()
        max_v = np.max(data)
        
        try:
            # --- MANUAL ---
            if "Binary Threshold (Manual)" in txt:
                self.mri_data = np.where(data > param_val, max_v, 0.0)

            elif "Binary Inverted (Manual)" in txt:
                self.mri_data = np.where(data > param_val, 0.0, max_v)

            elif "Truncate (Cap Values)" in txt:
                self.mri_data = np.where(data > param_val, param_val, data)

            elif "Range Pass (Mid-tones)" in txt:
                # Bandpass: param to param*2
                upper = param_val * 2.0
                mask = (data >= param_val) & (data <= upper)
                self.mri_data = np.where(mask, data, 0.0)

            # --- AUTOMATED (2 Classes) ---
            elif "Otsu's Method" in txt:
                thresh = filters.threshold_otsu(data)
                self.statusBar().showMessage(f"Otsu Calculated Threshold: {thresh:.2f}")
                self.mri_data = np.where(data > thresh, max_v, 0.0)
            
            elif "Li's Method" in txt:
                # Minimum Cross Entropy
                thresh = filters.threshold_li(data)
                self.statusBar().showMessage(f"Li Calculated Threshold: {thresh:.2f}")
                self.mri_data = np.where(data > thresh, max_v, 0.0)
            
            # --- AUTOMATED (N Classes) ---
            elif "Multi-Otsu" in txt:
                n_classes = self.n_classes_spin.value()
                
                # Calculate the thresholds
                # This returns N-1 thresholds for N classes
                thresholds = filters.threshold_multiotsu(data, classes=n_classes) 
                
                # Apply the segmentation
                # np.digitize returns indices [0, 1, ..., N] for N classes + 1 low-value bin
                indices = np.digitize(data, bins=thresholds)
                
                # Map indices to distinct intensity levels for visualization
                # We use the indices as the integer labels directly
                # If the original data was floating point, the indices array will be integer.
                self.mri_data = indices.astype(np.float64) # Keep as float temporarily for VTK/next ops
                
                # Display thresholds found
                thresh_str = ", ".join([f"{t:.2f}" for t in thresholds])
                self.statusBar().showMessage(f"Multi-Otsu calculated {n_classes} classes with thresholds: {thresh_str}")

            # --- AUTOMATED (Local) ---
            elif "Local Adaptive" in txt:
                # Adaptive Thresholding (Gaussian)
                # block_size must be odd
                blk = int(param_val)
                if blk % 2 == 0: blk += 1
                if blk < 3: blk = 3
                
                # Apply slice-by-slice
                processed_slices = []
                for i in range(data.shape[0]):
                    sl = data[i,:,:]
                    # Normalize slice to 0-1 for local threshold
                    sl_max = np.max(sl)
                    if sl_max > 0:
                        local_thresh = filters.threshold_local(sl, blk, method='gaussian')
                        processed_slices.append((sl > local_thresh) * max_v)
                    else:
                        processed_slices.append(sl)
                self.mri_data = np.stack(processed_slices, axis=0)

            self.update_vtk_data()
            if "Calculated" not in self.statusBar().currentMessage():
                self.statusBar().showMessage("Threshold applied.")

        except Exception as e:
            QMessageBox.critical(self, "Processing Error", str(e))
            self.undo_last_operation()
        finally:
            QApplication.restoreOverrideCursor()

    # ---------------------------------------------------------
    # Existing Functionality (Annotations, Display, Loaders, Exports)
    # ---------------------------------------------------------
    
    def export_modified_mri(self):
        """Exports the current self.mri_data array as a new NIfTI file."""
        if self.mri_data is None:
            QMessageBox.warning(self, "Warning", "No MRI data loaded to export.")
            return

        if not NIBABEL_AVAILABLE:
            QMessageBox.critical(self, "Error", "NiBabel is required to export NIfTI files.")
            return
            
        # FIX: Check for the stored affine matrix directly
        if self.mri_affine is None:
             QMessageBox.critical(self, "Error", "Original MRI affine matrix is missing. Cannot preserve spatial information.")
             return

        filename, _ = QFileDialog.getSaveFileName(
            self, "Save Modified MRI", "modified_mri.nii.gz", 
            "NIfTI Files (*.nii.gz);;All Files (*)"
        )

        if not filename:
            self.statusBar().showMessage("Export cancelled.")
            return
            
        self.statusBar().showMessage(f"Exporting modified MRI data to: {filename}...")
        QApplication.setOverrideCursor(Qt.WaitCursor)
        
        try:
            # Determine the appropriate dtype for NIfTI
            if self.mri_data.dtype in [np.uint16, np.int16, np.uint32, np.int32]:
                # Use the integer dtype for segmentation export
                export_dtype = self.mri_data.dtype
            else:
                # Default to float32 for general intensity data
                export_dtype = np.float32

            # 1. Create a new NIfTI image object
            # Use the current data and the stored affine matrix
            new_img = nib.Nifti1Image(self.mri_data.astype(export_dtype), self.mri_affine)
            
            # 2. Save the image
            nib.save(new_img, filename)
            
            self.statusBar().showMessage(f"Successfully exported modified MRI to: {filename}")
            QMessageBox.information(self, "Export Success", f"Modified MRI data saved as:\n{filename}")
            
        except Exception as e:
            self.statusBar().showMessage("Export failed.")
            QMessageBox.critical(self, "Export Error", f"Failed to save NIfTI file: {str(e)}")
            traceback.print_exc()
            
        finally:
            QApplication.restoreOverrideCursor()

    def toggle_annotation_mode(self, checked):
        self.annotation_mode = checked
        if checked:
            self.statusBar().showMessage("Annotation Mode ON: Click on the 3D view to place a point.")
            self._setup_3d_picker()
        else:
            self.statusBar().showMessage("Annotation Mode OFF.")
            default_style = vtk.vtkInteractorStyleTrackballCamera()
            self.vtk_widgets['3d'].SetInteractorStyle(default_style)
            default_style.SetDefaultRenderer(self.renderers['3d'])

    def _setup_3d_picker(self):
        picker = vtk.vtkCellPicker()
        picker.SetTolerance(0.005)
        
        interactor_style = vtk.vtkInteractorStyleTrackballCamera()
        interactor_style.SetDefaultRenderer(self.renderers['3d'])
        
        def on_right_click(obj, event):
            if not self.annotation_mode:
                obj.OnLeftButtonDown() 
                return
            
            click_pos = self.vtk_widgets['3d'].GetRenderWindow().GetInteractor().GetEventPosition()
            volume_picker = vtk.vtkVolumePicker()
            volume_picker.Pick(click_pos[0], click_pos[1], 0.0, self.renderers['3d'])
            
            world_pos = volume_picker.GetPickPosition()
            
            if world_pos and self.mri_data is not None:
                image_idx = (int(world_pos[0]), int(world_pos[1]), int(world_pos[2]))
                D, H, W = self.mri_data.shape # Z, Y, X
                # Check for bounds (VTK uses X, Y, Z, Nibabel uses Z, Y, X)
                if 0 <= image_idx[0] < W and 0 <= image_idx[1] < H and 0 <= image_idx[2] < D:
                    self._prompt_and_add_annotation(image_idx)
                else:
                    self.statusBar().showMessage("Annotation point is outside the volume boundaries.")
            
            self.vtk_widgets['3d'].GetRenderWindow().Render()

        self.vtk_widgets['3d'].SetInteractorStyle(interactor_style)
        interactor_style.AddObserver(vtk.vtkCommand.RightButtonPressEvent, on_right_click)

    def _prompt_and_add_annotation(self, image_idx):
        from PyQt5.QtWidgets import QInputDialog
        text, ok = QInputDialog.getText(self, 'Add Annotation', 'Annotation Text:')
        
        if ok and text:
            label_actor = vtk.vtkBillboardTextActor3D()
            label_actor.SetInput(text)
            label_actor.SetPosition(image_idx[0], image_idx[1], image_idx[2])
            
            prop = label_actor.GetTextProperty()
            prop.SetColor(1.0, 1.0, 0.0) 
            prop.SetFontSize(16)
            
            self.renderers['3d'].AddActor(label_actor)
            
            self.annotations.append({
                'position': image_idx, 
                'text': text, 
                'actor': label_actor
            })
            
            self.update_2d_views()
            self.vtk_widgets['3d'].GetRenderWindow().Render()
            self.statusBar().showMessage(f"Annotation added at {image_idx}: '{text}'")

    def _update_annotations_on_2d_slices(self):
        def create_point_actor(pos, radius=1.5, color=(1.0, 0.0, 1.0)):
            sphere = vtk.vtkSphereSource()
            sphere.SetCenter(pos[0], pos[1], pos[2])
            sphere.SetRadius(radius)
            sphere.Update()
            mapper = vtk.vtkPolyDataMapper()
            mapper.SetInputConnection(sphere.GetOutputPort())
            actor = vtk.vtkActor()
            actor.SetMapper(mapper)
            actor.GetProperty().SetColor(color)
            return actor
        
        views_2d = ['axial', 'sagittal', 'coronal']
        
        for view_name in views_2d:
            renderer = self.renderers[view_name]
            # Clear existing point actors (non-persistent)
            props_to_remove = [p for p in renderer.GetViewProps() if isinstance(p, vtk.vtkActor)]
            for p in props_to_remove:
                renderer.RemoveActor(p)
                
            for anno in self.annotations:
                x, y, z = anno['position']
                point_actor = create_point_actor(anno['position'])
                tolerance = 1.0 
                is_visible = False
                
                current_slice_index = self.current_slice[view_name]
                
                if view_name == 'axial' and abs(z - current_slice_index) < tolerance:
                    is_visible = True
                elif view_name == 'sagittal' and abs(x - current_slice_index) < tolerance:
                    is_visible = True
                elif view_name == 'coronal' and abs(y - current_slice_index) < tolerance:
                    is_visible = True
                    
                if is_visible:
                    renderer.AddActor(point_actor)
                    
            self.vtk_widgets[view_name].GetRenderWindow().Render()

    def export_screenshot(self):
        if self.mri_data is None:
            QMessageBox.warning(self, "Warning", "Please load an MRI file before exporting.")
            return

        if self.stacked_layout.currentIndex() == 1 and self.current_fullscreen_view_name:
            target_view_name = self.current_fullscreen_view_name
        else:
            target_view_name = '3d'
            
        if target_view_name not in self.vtk_widgets:
            QMessageBox.critical(self, "Error", "Selected view is not available for export.")
            return

        render_window = self.vtk_widgets.get(target_view_name).GetRenderWindow()
        
        if not render_window:
            self.statusBar().showMessage("Error: Could not find a render window to export.")
            return

        filename, _ = QFileDialog.getSaveFileName(
            self, "Save Screenshot", f"{target_view_name}_screenshot.png", 
            "PNG Image (*.png);;JPEG Image (*.jpg);;All Files (*)"
        )

        if not filename:
            self.statusBar().showMessage("Export cancelled.")
            return
        
        try:
            window_to_image = vtk.vtkWindowToImageFilter()
            window_to_image.SetInput(render_window)
            window_to_image.Update()

            writer = vtk.vtkPNGWriter()
            writer.SetFileName(filename)
            writer.SetInputConnection(window_to_image.GetOutputPort())
            writer.Write()

            self.statusBar().showMessage(f"Successfully exported screenshot to: {filename}")
            QMessageBox.information(self, "Export Success", f"Screenshot saved as:\n{filename}")
            
        except Exception as e:
            self.statusBar().showMessage("Export failed.")
            QMessageBox.critical(self, "Export Error", f"Failed to save image: {str(e)}")
            traceback.print_exc()
            
    def build_vis_grid(self):
        grid_widget = QWidget()
        grid = QGridLayout(grid_widget)
        grid.setSpacing(2)

        self.view_grid = grid
        self.view_grid_positions = {
            'axial': (0, 0),
            'sagittal': (0, 1),
            '3d': (1, 0),
            'coronal': (1, 1)
        }

        for view_name, (row, col) in self.view_grid_positions.items():
            view_panel = QWidget()
            view_panel_layout = QVBoxLayout(view_panel)
            view_panel_layout.setContentsMargins(2, 2, 2, 2)
            view_panel_layout.setSpacing(2)

            title_bar = QWidget()
            title_bar_layout = QHBoxLayout(title_bar)
            title_bar_layout.setContentsMargins(0, 0, 0, 0)

            label = QLabel(view_name.capitalize())
            label.setStyleSheet("font-weight: bold; color: #ccc;")
            title_bar_layout.addWidget(label)
            title_bar_layout.addStretch()

            fullscreen_btn = QPushButton("?")
            fullscreen_btn.setFixedSize(24, 24)
            fullscreen_btn.setToolTip("Fullscreen")
            fullscreen_btn.setStyleSheet("""
                QPushButton { background-color: rgba(50, 50, 50, 150); color: white; border-radius: 12px; font-weight: bold; }
                QPushButton:hover { background-color: rgba(70, 70, 70, 200); }
            """)
            fullscreen_btn.clicked.connect(lambda checked, v=view_name: self.toggle_fullscreen(v))
            title_bar_layout.addWidget(fullscreen_btn)
            view_panel_layout.addWidget(title_bar)

            content_area = QWidget()
            content_area.setObjectName(f"{view_name}_content_area") 
            content_layout = QHBoxLayout(content_area)
            content_layout.setContentsMargins(0, 0, 0, 0)
            content_layout.setSpacing(2)

            vtk_widget = QVTKRenderWindowInteractor()
            renderer = vtk.vtkRenderer()
            renderer.SetBackground(0, 0, 0)
            renderer.SetUseDepthPeeling(True)
            renderer.SetMaximumNumberOfPeels(100)
            renderer.SetOcclusionRatio(0.1)
            vtk_widget.GetRenderWindow().AddRenderer(renderer)
            
            self.vtk_widgets[view_name] = vtk_widget
            self.renderers[view_name] = renderer

            if view_name in ['axial', 'sagittal', 'coronal']:
                interactor_style = MouseWheelInteractorStyle(self, view_name)
                vtk_widget.SetInteractorStyle(interactor_style)

            content_layout.addWidget(vtk_widget)

            if view_name in ['axial', 'sagittal', 'coronal']:
                scroll_bar = QSlider(Qt.Vertical)
                scroll_bar.setMinimum(0)
                scroll_bar.setMaximum(100)
                scroll_bar.setValue(50)
                scroll_bar.setTickPosition(QSlider.TicksBothSides)
                scroll_bar.setTickInterval(10)
                
                if view_name == 'axial':
                    self.axial_slider = scroll_bar
                    scroll_bar.valueChanged.connect(self.update_axial_slice)
                elif view_name == 'sagittal':
                    self.sagittal_slider = scroll_bar
                    scroll_bar.valueChanged.connect(self.update_sagittal_slice)
                elif view_name == 'coronal':
                    self.coronal_slider = scroll_bar
                    scroll_bar.valueChanged.connect(self.update_coronal_slice)
                
                content_layout.addWidget(scroll_bar)

            view_panel_layout.addWidget(content_area)
            self.view_containers[view_name] = view_panel
            grid.addWidget(view_panel, row, col)

        return grid_widget

    def apply_style(self):
        #self.setStyleSheet(MAIN_STYLE)
        self.setStyleSheet(QSS_THEME)

    
    def setup_shortcuts(self):
        self.exit_shortcut = QShortcut(QKeySequence(Qt.Key_Escape), self)
        self.exit_shortcut.activated.connect(self.exit_fullscreen_mode)

    def closeEvent(self, event):
        for widget in self.vtk_widgets.values():
            widget.GetRenderWindow().Finalize()
        super().closeEvent(event)
    
    def clear_mask(self):
        self.mask_data = None
        self.mask_header = None
        self.unique_mask_values = None
        
        for actor in self.mask_actors_3d:
            self.renderers['3d'].RemoveActor(actor)
        self.mask_actors_3d = []
        
        self.show_mask_check.setEnabled(False)
        self.show_mask_check.setChecked(False)
        self.mask_opacity_slider.setEnabled(False)
        
        self.update_2d_views()
        self.vtk_widgets['3d'].GetRenderWindow().Render()
    
    def load_mri(self):
        if not NIBABEL_AVAILABLE:
            QMessageBox.warning(self, "Warning", "NiBabel is not installed. Cannot load MRI files.")
            return
            
        filepath, _ = QFileDialog.getOpenFileName(
            self, "Open MRI File", "", 
            "MRI Files (*.nii *.nii.gz *.dcm *.img *.hdr);;NIfTI Files (*.nii *.nii.gz);;All Files (*)")
        
        if not filepath:
            return
        
        try:
            self.statusBar().showMessage(f"Loading MRI from: {filepath}")
            self.clear_mask()
            self.history_stack = [] 
            self.btn_undo.setEnabled(False)
            
            img = nib.load(filepath)
            #img = nib.as_closest_canonical(img)

            self.mri_data = img.get_fdata()
            self.mri_header = img.header
            self.mri_affine = img.affine # Store the affine matrix from the image object

            self.header = img.header
            self.affine = img.affine
            
            depth, height, width = self.mri_data.shape
            
            # Use the shared update method to setup image_data and visualization
            self.update_vtk_data()
            
            self.axial_slider.setRange(0, depth-1)
            self.axial_slider.setValue(depth//2)
            self.sagittal_slider.setRange(0, width-1)
            self.sagittal_slider.setValue(width//2)
            self.coronal_slider.setRange(0, height-1)
            self.coronal_slider.setValue(height//2)
            
            self.setup_3d_view()
            self.update_2d_views()
            self._update_crosshair_sync()
            
            self.statusBar().showMessage(f"Loaded MRI: {depth}x{height}x{width}")
            
        except Exception as e:
            self.statusBar().showMessage("Failed to load MRI")
            QMessageBox.critical(self, "Error", f"Failed to load MRI file: {str(e)}")
            traceback.print_exc()
    
    def load_mask(self):
        if not NIBABEL_AVAILABLE:
            QMessageBox.warning(self, "Warning", "NiBabel is not installed. Cannot load mask files.")
            return
            
        if self.mri_data is None:
            QMessageBox.warning(self, "Warning", "Please load an MRI file first.")
            return
            
        filepath, _ = QFileDialog.getOpenFileName(
            self, "Open Mask File", "", 
            "Mask Files (*.nii *.nii.gz *.dcm *.img *.hdr);;NIfTI Files (*.nii *.nii.gz);;All Files (*)")
        
        if not filepath:
            return
        
        try:
            self.statusBar().showMessage(f"Loading mask from: {filepath}")
            img = nib.load(filepath)
            mask_data = img.get_fdata()

            #self.header = mask_img.header
            #self.affine = mask_img.affine
            
            if mask_data.shape != self.mri_data.shape:
                QMessageBox.critical(self, "Error", 
                    f"Mask dimensions {mask_data.shape} do not match MRI dimensions {self.mri_data.shape}")
                return
            
            self.mask_data = mask_data.astype(np.uint16)
            self.mask_header = img.header
            
            self.unique_mask_values = np.unique(self.mask_data)
            self.unique_mask_values = self.unique_mask_values[self.unique_mask_values > 0]
            
            self.mask_image_data = vtk.vtkImageData()
            depth, height, width = self.mask_data.shape
            self.mask_image_data.SetDimensions(width, height, depth)
            self.mask_image_data.AllocateScalars(vtk.VTK_UNSIGNED_SHORT, 1)
            # Fast path: convert NumPy array to VTK array in one shot instead of
            # looping over every voxel (which is extremely slow for large volumes).
            # Ensure the array is C-contiguous and flattened in the same ordering
            # used when setting VTK dimensions (X, Y, Z).
            from vtk.util import numpy_support
            mask_contig = np.ascontiguousarray(self.mask_data)
            flat = mask_contig.ravel(order='C')
            vtk_arr = numpy_support.numpy_to_vtk(num_array=flat, deep=True, array_type=vtk.VTK_UNSIGNED_SHORT)
            self.mask_image_data.GetPointData().SetScalars(vtk_arr)
            
            self.setup_mask_visualization()
            
            self.show_mask_check.setEnabled(True)
            self.show_mask_check.setChecked(True)
            self.mask_opacity_slider.setEnabled(True)
            
            num_labels = len(self.unique_mask_values)
            self.statusBar().showMessage(f"Loaded mask with {num_labels} labels: {depth}x{height}x{width}")
            QMessageBox.information(self, "Success", f"Successfully loaded mask with {num_labels} labels")
            
        except Exception as e:
            self.statusBar().showMessage("Failed to load mask")
            QMessageBox.critical(self, "Error", f"Failed to load mask file: {str(e)}")
            traceback.print_exc()
    
    def setup_mask_visualization(self):
        for actor in self.mask_actors_3d:
            self.renderers['3d'].RemoveActor(actor)
        self.mask_actors_3d = []
        
        colors = [
            (1, 0, 0), (0, 1, 0), (0, 0, 1), (1, 1, 0), (1, 0, 1),
            (0, 1, 1), (1, 0.5, 0), (0.5, 0, 1), (0, 0.5, 0),
        ]
        
        for label_value in self.unique_mask_values:
            marching_cubes = vtk.vtkMarchingCubes()
            marching_cubes.SetInputData(self.mask_image_data)
            marching_cubes.SetValue(0, label_value)
            marching_cubes.ComputeNormalsOn()
            
            smoother = vtk.vtkWindowedSincPolyDataFilter()
            smoother.SetInputConnection(marching_cubes.GetOutputPort())
            smoother.SetNumberOfIterations(50)
            smoother.SetPassBand(0.05)
            smoother.FeatureEdgeSmoothingOff()
            smoother.BoundarySmoothingOff()
            smoother.NonManifoldSmoothingOn()
            smoother.NormalizeCoordinatesOn()

            mapper = vtk.vtkPolyDataMapper()
            mapper.SetInputConnection(smoother.GetOutputPort())
            mapper.ScalarVisibilityOff()
            
            actor = vtk.vtkActor()
            actor.SetMapper(mapper)
            
            color_idx = int(label_value) % len(colors)
            r, g, b = colors[color_idx]
            actor.GetProperty().SetColor(r, g, b)
            actor.GetProperty().SetOpacity(self.mask_opacity_slider.value() / 100.0) 
            
            self.renderers['3d'].AddActor(actor)
            self.mask_actors_3d.append(actor)
        
        self.mask_lut = vtk.vtkLookupTable()
        max_label = max(self.unique_mask_values) if len(self.unique_mask_values) > 0 else 1
        max_label_int = int(max_label) + 1
        
        self.mask_lut.SetRange(0, max_label)
        self.mask_lut.SetNumberOfTableValues(max_label_int)
        
        for i in range(max_label_int):
            if i == 0:
                self.mask_lut.SetTableValue(i, 0, 0, 0, 0)
            else:
                color_idx = i % len(colors)
                r, g, b = colors[color_idx]
                self.mask_lut.SetTableValue(i, r, g, b, 1)
        
        self.mask_lut.Build()
        
        self.update_2d_views()
        self.vtk_widgets['3d'].GetRenderWindow().Render()
    
    def toggle_mask_visibility(self, state):
        opacity = self.mask_opacity_slider.value() / 100.0
        
        for actor in self.mask_actors_3d:
            actor.SetVisibility(state == Qt.Checked)
        
        if state == Qt.Checked:
            self.update_mask_opacity(self.mask_opacity_slider.value())
        
        self.update_2d_views()
        self.vtk_widgets['3d'].GetRenderWindow().Render()
    
    def update_mask_opacity(self, value):
        opacity = value / 100.0
        for actor in self.mask_actors_3d:
            actor.GetProperty().SetOpacity(opacity)
            
        self.vtk_widgets['3d'].GetRenderWindow().Render()
        self.update_2d_views()
    
    def setup_3d_view(self):
        renderer = self.renderers['3d']
        renderer.RemoveAllViewProps()
        
        self.volume_property = vtk.vtkVolumeProperty()
        self.volume_property.ShadeOn()
        self.volume_property.SetInterpolationTypeToLinear()
        
        color_tf = vtk.vtkColorTransferFunction()
        opacity_tf = vtk.vtkPiecewiseFunction()
        
        min_val = np.min(self.mri_data)
        max_val = np.max(self.mri_data)
        color_tf.AddRGBPoint(min_val, 0.0, 0.0, 0.0)
        color_tf.AddRGBPoint(max_val, 1.0, 1.0, 1.0)
        
        opacity_tf.AddPoint(min_val, 0.0)
        opacity_tf.AddPoint(max_val * 0.2, 0.0)
        opacity_tf.AddPoint(max_val * 0.7, 0.2)
        opacity_tf.AddPoint(max_val, 0.8)
        
        self.volume_property.SetColor(color_tf)
        self.volume_property.SetScalarOpacity(opacity_tf)
        
        self.volume_mapper = vtk.vtkSmartVolumeMapper()
        self.volume_mapper.SetInputData(self.image_data)
        self.volume_mapper.SetRequestedRenderModeToGPU() # Request GPU raycasting

        def StartInteraction(obj, event):
            self.volume_mapper.SetAutoAdjustSampleDistances(1)
            self.volume_mapper.SetInteractiveUpdateRate(5.0) # Allow dropping frames to keep up
            
        # High quality render when stopped
        def EndInteraction(obj, event):
            self.volume_mapper.SetAutoAdjustSampleDistances(0)
            self.vtk_widgets['3d'].GetRenderWindow().Render()

        # Attach to the 3D interactor
        interactor = self.vtk_widgets['3d'].GetRenderWindow().GetInteractor()
        interactor.AddObserver("StartInteractionEvent", StartInteraction)
        interactor.AddObserver("EndInteractionEvent", EndInteraction)
        
        self.volume = vtk.vtkVolume()
        self.volume.SetMapper(self.volume_mapper)
        self.volume.SetProperty(self.volume_property)
        
        renderer.AddVolume(self.volume)
        renderer.ResetCamera()
        
        self.vtk_widgets['3d'].GetRenderWindow().Render()
    
    def update_2d_views(self):
        self.update_axial_slice(self.axial_slider.value())
        self.update_sagittal_slice(self.sagittal_slider.value())
        self.update_coronal_slice(self.coronal_slider.value())
        self._update_annotations_on_2d_slices()
    
    def update_axial_slice(self, value):
        if self.mri_data is None: return
        
        self.axial_slider.setValue(value)
        self.current_slice['axial'] = value
        
        reslice = vtk.vtkImageReslice()
        reslice.SetInputData(self.image_data)
        reslice.SetOutputDimensionality(2)
        reslice.SetResliceAxesDirectionCosines(1, 0, 0, 0, 1, 0, 0, 0, 1)
        reslice.SetResliceAxesOrigin(0, 0, value) 
        
        mri_actor = vtk.vtkImageActor()
        mri_actor.GetMapper().SetInputConnection(reslice.GetOutputPort())
        min_val = np.min(self.mri_data)
        max_val = np.max(self.mri_data)
        window = max_val - min_val
        level = (max_val + min_val) / 2
        mri_actor.GetProperty().SetColorWindow(window)
        mri_actor.GetProperty().SetColorLevel(level)
        
        mask_actor = None
        if self.mask_data is not None and self.show_mask_check.isChecked():
            mask_reslice = vtk.vtkImageReslice()
            mask_reslice.SetInputData(self.mask_image_data)
            mask_reslice.SetOutputDimensionality(2)
            mask_reslice.SetResliceAxesDirectionCosines(1, 0, 0, 0, 1, 0, 0, 0, 1)
            mask_reslice.SetResliceAxesOrigin(0, 0, value)
            color_map = vtk.vtkImageMapToColors()
            color_map.SetLookupTable(self.mask_lut)
            color_map.SetInputConnection(mask_reslice.GetOutputPort())
            color_map.SetOutputFormatToRGBA()
            mask_actor = vtk.vtkImageActor()
            mask_actor.GetMapper().SetInputConnection(color_map.GetOutputPort())
            mask_actor.GetProperty().SetOpacity(self.mask_opacity_slider.value() / 100.0)

        renderer = self.renderers['axial']
        renderer.RemoveAllViewProps()
        renderer.AddActor(mri_actor)
        if mask_actor:
            renderer.AddActor(mask_actor)
        
        renderer.ResetCamera()
        self.vtk_widgets['axial'].GetRenderWindow().Render()
        self._update_crosshair_sync()

    def update_sagittal_slice(self, value):
        if self.mri_data is None: return
        
        self.sagittal_slider.setValue(value)
        self.current_slice['sagittal'] = value
        
        reslice = vtk.vtkImageReslice()
        reslice.SetInputData(self.image_data)
        reslice.SetOutputDimensionality(2)
        reslice.SetResliceAxesDirectionCosines(0, 1, 0, 0, 0, 1, 1, 0, 0)
        reslice.SetResliceAxesOrigin(value, 0, 0) 
        
        mri_actor = vtk.vtkImageActor()
        mri_actor.GetMapper().SetInputConnection(reslice.GetOutputPort())
        min_val = np.min(self.mri_data)
        max_val = np.max(self.mri_data)
        window = max_val - min_val
        level = (max_val + min_val) / 2
        mri_actor.GetProperty().SetColorWindow(window)
        mri_actor.GetProperty().SetColorLevel(level)
        
        mask_actor = None
        if self.mask_data is not None and self.show_mask_check.isChecked():
            mask_reslice = vtk.vtkImageReslice()
            mask_reslice.SetInputData(self.mask_image_data)
            mask_reslice.SetOutputDimensionality(2)
            mask_reslice.SetResliceAxesDirectionCosines(0, 1, 0, 0, 0, 1, 1, 0, 0)
            mask_reslice.SetResliceAxesOrigin(value, 0, 0)
            color_map = vtk.vtkImageMapToColors()
            color_map.SetLookupTable(self.mask_lut)
            color_map.SetInputConnection(mask_reslice.GetOutputPort())
            color_map.SetOutputFormatToRGBA()
            mask_actor = vtk.vtkImageActor()
            mask_actor.GetMapper().SetInputConnection(color_map.GetOutputPort())
            mask_actor.GetProperty().SetOpacity(self.mask_opacity_slider.value() / 100.0)

        renderer = self.renderers['sagittal']
        renderer.RemoveAllViewProps()
        renderer.AddActor(mri_actor)
        if mask_actor:
            renderer.AddActor(mask_actor)
        
        renderer.ResetCamera()
        self.vtk_widgets['sagittal'].GetRenderWindow().Render()
        self._update_crosshair_sync()

    def update_coronal_slice(self, value):
        if self.mri_data is None: return
        
        self.coronal_slider.setValue(value)
        self.current_slice['coronal'] = value
        
        reslice = vtk.vtkImageReslice()
        reslice.SetInputData(self.image_data)
        reslice.SetOutputDimensionality(2)
        reslice.SetResliceAxesDirectionCosines(1, 0, 0, 0, 0, 1, 0, 1, 0)
        reslice.SetResliceAxesOrigin(0, value, 0) 
        
        mri_actor = vtk.vtkImageActor()
        mri_actor.GetMapper().SetInputConnection(reslice.GetOutputPort())
        min_val = np.min(self.mri_data)
        max_val = np.max(self.mri_data)
        window = max_val - min_val
        level = (max_val + min_val) / 2
        mri_actor.GetProperty().SetColorWindow(window)
        mri_actor.GetProperty().SetColorLevel(level)
        
        mask_actor = None
        if self.mask_data is not None and self.show_mask_check.isChecked():
            mask_reslice = vtk.vtkImageReslice()
            mask_reslice.SetInputData(self.mask_image_data)
            mask_reslice.SetOutputDimensionality(2)
            mask_reslice.SetResliceAxesDirectionCosines(1, 0, 0, 0, 0, 1, 0, 1, 0)
            mask_reslice.SetResliceAxesOrigin(0, value, 0)
            color_map = vtk.vtkImageMapToColors()
            color_map.SetLookupTable(self.mask_lut)
            color_map.SetInputConnection(mask_reslice.GetOutputPort())
            color_map.SetOutputFormatToRGBA()
            mask_actor = vtk.vtkImageActor()
            mask_actor.GetMapper().SetInputConnection(color_map.GetOutputPort())
            mask_actor.GetProperty().SetOpacity(self.mask_opacity_slider.value() / 100.0)
            
        renderer = self.renderers['coronal']
        renderer.RemoveAllViewProps()
        renderer.AddActor(mri_actor)
        if mask_actor:
            renderer.AddActor(mask_actor)
        
        renderer.ResetCamera()
        self.vtk_widgets['coronal'].GetRenderWindow().Render()
        self._update_crosshair_sync()
    
            
    def _create_crosshair_actor(self, x_pos, y_pos, x_max, y_max):
        crosshair_color = (0.05, 0.65, 0.9)
        line_width = 2
        
        points = vtk.vtkPoints()
        points.InsertNextPoint(0, y_pos, 0)
        points.InsertNextPoint(x_max, y_pos, 0)
        points.InsertNextPoint(x_pos, 0, 0)
        points.InsertNextPoint(x_pos, y_max, 0)

        lines = vtk.vtkCellArray()
        line1 = vtk.vtkLine()
        line1.GetPointIds().SetId(0, 0)
        line1.GetPointIds().SetId(1, 1)
        line2 = vtk.vtkLine()
        line2.GetPointIds().SetId(0, 2)
        line2.GetPointIds().SetId(1, 3)
        
        lines.InsertNextCell(line1)
        lines.InsertNextCell(line2)

        polydata = vtk.vtkPolyData()
        polydata.SetPoints(points)
        polydata.SetLines(lines)

        mapper = vtk.vtkPolyDataMapper()
        mapper.SetInputData(polydata)

        actor = vtk.vtkActor()
        actor.SetMapper(mapper)
        actor.GetProperty().SetColor(crosshair_color)
        actor.GetProperty().SetLineWidth(line_width)
        return actor

    def _update_crosshair_sync(self):
        if self.mri_data is None: return
        
        D, H, W = self.mri_data.shape
        Z_slice = self.current_slice['axial']
        X_slice = self.current_slice['sagittal']
        Y_slice = self.current_slice['coronal']
        
        for view_name in ['axial', 'sagittal', 'coronal']:
            renderer = self.renderers[view_name]
            for actor in self.crosshair_actors[view_name]:
                renderer.RemoveActor(actor)
            self.crosshair_actors[view_name] = []

        axial_ch_actor = self._create_crosshair_actor(X_slice, Y_slice, W, H)
        self.renderers['axial'].AddActor(axial_ch_actor)
        self.crosshair_actors['axial'].append(axial_ch_actor)

        sagittal_ch_actor = self._create_crosshair_actor(Y_slice, Z_slice, H, D)
        self.renderers['sagittal'].AddActor(sagittal_ch_actor)
        self.crosshair_actors['sagittal'].append(sagittal_ch_actor)

        coronal_ch_actor = self._create_crosshair_actor(X_slice, Z_slice, W, D)
        self.renderers['coronal'].AddActor(coronal_ch_actor)
        self.crosshair_actors['coronal'].append(coronal_ch_actor)

        for view_name in ['axial', 'sagittal', 'coronal']:
            self.vtk_widgets[view_name].GetRenderWindow().Render()


    def toggle_rendering_mode(self, state):
        if self.volume is None: return
            
        if state == Qt.Checked:
            self.volume_property.ShadeOn()
            self.volume_property.SetInterpolationTypeToLinear()
        else:
            self.volume_property.ShadeOff()
            self.volume_property.SetInterpolationTypeToNearest()
        
        self.vtk_widgets['3d'].GetRenderWindow().Render()

    def toggle_fullscreen(self, view_name):
        if self.stacked_layout.currentIndex() != 0:
            self.exit_fullscreen_mode()
            return

        container = self.view_containers.get(view_name)
        if container:
            self.current_fullscreen_view_name = view_name
            self.view_grid.removeWidget(container)
            
            self.fullscreen_container = QWidget()
            fullscreen_layout = QVBoxLayout(self.fullscreen_container)
            fullscreen_layout.setContentsMargins(0, 0, 0, 0)
            
            exit_bar = QWidget()
            exit_bar_layout = QHBoxLayout(exit_bar)
            exit_bar_layout.setContentsMargins(10, 5, 10, 5)
            exit_bar_layout.addStretch()
            self.exit_fullscreen_btn = QPushButton(f"Exit Fullscreen: {view_name.capitalize()} (Esc)")
            self.exit_fullscreen_btn.setStyleSheet("""
                QPushButton { background-color: #f44336; color: white; border: none; border-radius: 4px; padding: 5px 15px; font-weight: bold; }
                QPushButton:hover { background-color: #d32f2f; }
            """)
            self.exit_fullscreen_btn.clicked.connect(self.exit_fullscreen_mode)
            exit_bar_layout.addWidget(self.exit_fullscreen_btn)
            
            fullscreen_layout.addWidget(exit_bar)
            container.setParent(self.fullscreen_container)
            fullscreen_layout.addWidget(container)
            
            self.stacked_layout.addWidget(self.fullscreen_container)
            self.stacked_layout.setCurrentWidget(self.fullscreen_container)
            self.statusBar().showMessage(f"Fullscreen: {view_name.capitalize()} View")

    def exit_fullscreen_mode(self):
        if self.stacked_layout.currentIndex() == 0 or self.current_fullscreen_view_name is None:
            return

        view_name = self.current_fullscreen_view_name
        container = self.view_containers.get(view_name)

        if container and self.fullscreen_container:
            self.fullscreen_container.layout().removeWidget(container)
            container.setParent(None) 
            self.stacked_layout.setCurrentIndex(0)
            row, col = self.view_grid_positions[view_name]
            self.view_grid.addWidget(container, row, col)
            
            self.stacked_layout.removeWidget(self.fullscreen_container)
            self.fullscreen_container.deleteLater()
            self.fullscreen_container = None
            self.current_fullscreen_view_name = None
            self.exit_fullscreen_btn = None
            self.statusBar().showMessage("Ready")
            
            vtk_widget = self.vtk_widgets.get(view_name)
            if vtk_widget:
                QTimer.singleShot(100, lambda: vtk_widget.GetRenderWindow().Render())

    def _get_representative_slice_index(self):
        """Returns a central index for all three axes."""
        if self.mri_data is None: return {'axial': 0, 'coronal': 0, 'sagittal': 0}
        D, H, W = self.mri_data.shape # Z, Y, X
        return {
            'axial': D // 2,
            'coronal': H // 2,
            'sagittal': W // 2,
        }

    _create_2d_slice_snapshot = _create_2d_slice_snapshot_mpl

    _create_3d_snapshot = _create_3d_snapshot_pv
