#!/usr/bin/env python3
import sys
import traceback
import numpy as np
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QHBoxLayout, QGridLayout, QGroupBox, QPushButton,
                             QLabel, QScrollArea, QStatusBar, QMessageBox,
                             QFileDialog, QSpinBox, QSlider, QCheckBox,
                             QStackedLayout, QShortcut)
from PyQt5.QtGui import QKeySequence
from style import MAIN_STYLE

# Import VTK with error handling
try:
    import vtk
    from vtkmodules.qt.QVTKRenderWindowInteractor import QVTKRenderWindowInteractor
    VTK_AVAILABLE = True
except ImportError as e:
    print(f"VTK import error: {e}")
    VTK_AVAILABLE = False

# Import NiBabel for MRI file loading
try:
    import nibabel as nib
    NIBABEL_AVAILABLE = True
except ImportError:
    print("NiBabel not available. Install with: pip install nibabel")
    NIBABEL_AVAILABLE = False

# Custom interactor style for mouse wheel navigation
class MouseWheelInteractorStyle(vtk.vtkInteractorStyleImage):
    def __init__(self, parent=None, view_name=None):
        self.parent = parent
        self.view_name = view_name
        self.AddObserver(vtk.vtkCommand.MouseWheelForwardEvent, self.on_mouse_wheel_forward)
        self.AddObserver(vtk.vtkCommand.MouseWheelBackwardEvent, self.on_mouse_wheel_backward)
    
    def on_mouse_wheel_forward(self, obj, event):
        if self.parent and self.view_name:
            if self.view_name == 'axial':
                current = self.parent.axial_slider.value()
                max_val = self.parent.axial_slider.maximum()
                new_val = min(current + 1, max_val)
                self.parent.axial_slider.setValue(new_val)
                self.parent.update_axial_slice(new_val)
            elif self.view_name == 'sagittal':
                current = self.parent.sagittal_slider.value()
                max_val = self.parent.sagittal_slider.maximum()
                new_val = min(current + 1, max_val)
                self.parent.sagittal_slider.setValue(new_val)
                self.parent.update_sagittal_slice(new_val)
            elif self.view_name == 'coronal':
                current = self.parent.coronal_slider.value()
                max_val = self.parent.coronal_slider.maximum()
                new_val = min(current + 1, max_val)
                self.parent.coronal_slider.setValue(new_val)
                self.parent.update_coronal_slice(new_val)
    
    def on_mouse_wheel_backward(self, obj, event):
        if self.parent and self.view_name:
            if self.view_name == 'axial':
                current = self.parent.axial_slider.value()
                min_val = self.parent.axial_slider.minimum()
                new_val = max(current - 1, min_val)
                self.parent.axial_slider.setValue(new_val)
                self.parent.update_axial_slice(new_val)
            elif self.view_name == 'sagittal':
                current = self.parent.sagittal_slider.value()
                min_val = self.parent.sagittal_slider.minimum()
                new_val = max(current - 1, min_val)
                self.parent.sagittal_slider.setValue(new_val)
                self.parent.update_sagittal_slice(new_val)
            elif self.view_name == 'coronal':
                current = self.parent.coronal_slider.value()
                min_val = self.parent.coronal_slider.minimum()
                new_val = max(current - 1, min_val)
                self.parent.coronal_slider.setValue(new_val)
                self.parent.update_coronal_slice(new_val)

class MRIViewer(QMainWindow):
    def __init__(self):
        print("Initializing MRIViewer...")
        super().__init__()
        
        if not VTK_AVAILABLE:
            QMessageBox.critical(None, "Error", "VTK is not properly installed!")
            sys.exit(1)
        
        self.setWindowTitle("MRI Viewer")
        self.resize(1400, 900)
        
        # Data holders
        self.mri_data = None
        self.mask_data = None
        self.mri_header = None
        self.mask_header = None
        self.current_slice = {'axial': 0, 'sagittal': 0, 'coronal': 0}
        self.vtk_widgets = {}
        self.renderers = {}
        self.view_containers = {} # To hold each view's top-level container widget
        
        # VTK objects for MRI
        self.image_data = None
        self.volume_property = None
        self.volume_mapper = None
        self.volume = None
        
        # VTK objects for Mask
        self.mask_image_data = None
        self.mask_actors_3d = []  # Store multiple 3D mask actors
        self.mask_lut = None  # Lookup table for mask color
        self.unique_mask_values = None  # Store unique values in mask
        
        # Fullscreen state
        self.exit_fullscreen_btn = None
        self.current_fullscreen_view_name = None
        self.fullscreen_container = None # To hold the fullscreen widget

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
    
    def build_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Use a stacked layout to switch between normal and fullscreen views
        self.stacked_layout = QStackedLayout(central_widget)
        
        # --- Page 0: Normal Grid View ---
        normal_view_widget = QWidget()
        normal_layout = QHBoxLayout(normal_view_widget)
        
        # Left panel
        left_panel = self.build_left_panel()
        normal_layout.addWidget(left_panel, 1)
        
        # Right panel with the new 2x2 grid
        right_panel = self.build_vis_grid()
        normal_layout.addWidget(right_panel, 4)
        
        self.stacked_layout.addWidget(normal_view_widget)
        
        self.setStatusBar(QStatusBar())
        self.statusBar().showMessage("Ready")
    
    def build_left_panel(self):
        panel = QWidget()
        layout = QVBoxLayout(panel)
        
        # File group
        file_group = QGroupBox("File Operations")
        file_layout = QVBoxLayout()
        
        self.btn_load_mri = QPushButton("Load MRI")
        self.btn_load_mask = QPushButton("Load Mask")
        
        file_layout.addWidget(self.btn_load_mri)
        file_layout.addWidget(self.btn_load_mask)
        file_group.setLayout(file_layout)
        
        # Mask controls
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
        
        # Rendering options
        render_group = QGroupBox("Rendering Options")
        render_layout = QVBoxLayout()
        
        self.volume_rendering_check = QCheckBox("Volume Rendering")
        self.volume_rendering_check.setChecked(True)
        self.volume_rendering_check.stateChanged.connect(self.toggle_rendering_mode)
        render_layout.addWidget(self.volume_rendering_check)
        
        render_group.setLayout(render_layout)
        
        # Instructions
        info_group = QGroupBox("Navigation")
        info_layout = QVBoxLayout()
        info_layout.addWidget(QLabel("> Use mouse wheel to navigate slices"))
        info_layout.addWidget(QLabel("> Left click and drag to pan"))
        info_layout.addWidget(QLabel("> Right click and drag to zoom"))
        info_layout.addWidget(QLabel("> Use scroll bars on each view"))
        info_group.setLayout(info_layout)
        
        layout.addWidget(file_group)
        layout.addWidget(mask_group)
        layout.addWidget(render_group)
        layout.addWidget(info_group)
        layout.addStretch()
        
        # Connect signals
        self.btn_load_mri.clicked.connect(self.load_mri)
        self.btn_load_mask.clicked.connect(self.load_mask)
        
        return panel

    def build_vis_grid(self):
        """Builds the 2x2 grid of views."""
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
            print(f"Creating {view_name} view...")

            view_panel = QWidget()
            view_panel_layout = QVBoxLayout(view_panel)
            view_panel_layout.setContentsMargins(2, 2, 2, 2)
            view_panel_layout.setSpacing(2)

            # --- Create the title bar with the fullscreen button ---
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
                QPushButton { 
                    background-color: rgba(50, 50, 50, 150); 
                    color: white; 
                    border-radius: 12px; 
                    font-weight: bold;
                }
                QPushButton:hover { background-color: rgba(70, 70, 70, 200); }
            """)
            fullscreen_btn.clicked.connect(lambda checked, v=view_name: self.toggle_fullscreen(v))
            title_bar_layout.addWidget(fullscreen_btn)
            view_panel_layout.addWidget(title_bar)

            # --- Create the content area ---
            content_area = QWidget()
            content_layout = QHBoxLayout(content_area)
            content_layout.setContentsMargins(0, 0, 0, 0)
            content_layout.setSpacing(2)

            # Create the VTK widget and its renderer
            vtk_widget = QVTKRenderWindowInteractor()
            renderer = vtk.vtkRenderer()
            renderer.SetBackground(0.1, 0.1, 0.1)
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

            # Add the slider for 2D views
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
            
            # Store the top-level container for hiding/showing
            self.view_containers[view_name] = view_panel
            grid.addWidget(view_panel, row, col)

        return grid_widget

    def apply_style(self):
        self.setStyleSheet(MAIN_STYLE)
    
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
            
            img = nib.load(filepath)
            self.mri_data = img.get_fdata()
            self.mri_header = img.header
            
            depth, height, width = self.mri_data.shape
            
            self.image_data = vtk.vtkImageData()
            self.image_data.SetDimensions(width, height, depth)
            self.image_data.AllocateScalars(vtk.VTK_FLOAT, 1)
            
            for z in range(depth):
                for y in range(height):
                    for x in range(width):
                        self.image_data.SetScalarComponentFromDouble(x, y, z, 0, self.mri_data[z, y, x])
            
            self.axial_slider.setRange(0, depth-1)
            self.axial_slider.setValue(depth//2)
            self.sagittal_slider.setRange(0, width-1)
            self.sagittal_slider.setValue(width//2)
            self.coronal_slider.setRange(0, height-1)
            self.coronal_slider.setValue(height//2)
            
            self.setup_3d_view()
            self.update_2d_views()
            
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
            
            for z in range(depth):
                for y in range(height):
                    for x in range(width):
                        self.mask_image_data.SetScalarComponentFromDouble(x, y, z, 0, self.mask_data[z, y, x])
            
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
            actor.GetProperty().SetOpacity(0.8)
            
            self.renderers['3d'].AddActor(actor)
            self.mask_actors_3d.append(actor)
        
        self.mask_lut = vtk.vtkLookupTable()
        self.mask_lut.SetRange(0, max(self.unique_mask_values) if len(self.unique_mask_values) > 0 else 1)
        
        max_label = max(self.unique_mask_values) if len(self.unique_mask_values) > 0 else 1
        max_label_int = int(max_label) + 1
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
        for actor in self.mask_actors_3d:
            actor.SetVisibility(state == Qt.Checked)
        
        self.update_2d_views()
        self.vtk_widgets['3d'].GetRenderWindow().Render()
    
    def update_mask_opacity(self, value):
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
    
    def update_axial_slice(self, value):
        if self.mri_data is None: return
        
        self.axial_slider.setValue(value)
        self.current_slice['axial'] = value
        depth, height, width = self.mri_data.shape
        
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
    
    def update_sagittal_slice(self, value):
        if self.mri_data is None: return
        
        self.sagittal_slider.setValue(value)
        self.current_slice['sagittal'] = value
        depth, height, width = self.mri_data.shape
        
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
    
    def update_coronal_slice(self, value):
        if self.mri_data is None: return
        
        self.coronal_slider.setValue(value)
        self.current_slice['coronal'] = value
        depth, height, width = self.mri_data.shape
        
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
        """Switches main view to fullscreen for the selected view."""
        if self.stacked_layout.currentIndex() != 0:
            self.exit_fullscreen_mode()
            return

        container = self.view_containers.get(view_name)
        vtk_widget = self.vtk_widgets.get(view_name)
        if container and vtk_widget:
            self.current_fullscreen_view_name = view_name
            
            # Hide the original container in the grid
            container.hide()
            
            # Create a new, simple container for fullscreen
            self.fullscreen_container = QWidget()
            fullscreen_layout = QVBoxLayout(self.fullscreen_container)
            fullscreen_layout.setContentsMargins(0, 0, 0, 0)
            
            # Move the VTK widget to the new container
            vtk_widget.setParent(self.fullscreen_container)
            fullscreen_layout.addWidget(vtk_widget)
            
            # Add to stacked layout and show
            self.stacked_layout.addWidget(self.fullscreen_container)
            self.stacked_layout.setCurrentWidget(self.fullscreen_container)
            
            # Add the exit button to the status bar
            self.exit_fullscreen_btn = QPushButton("Exit Fullscreen (Esc)")
            self.exit_fullscreen_btn.clicked.connect(self.exit_fullscreen_mode)
            self.statusBar().addPermanentWidget(self.exit_fullscreen_btn)
            self.statusBar().showMessage(f"Fullscreen: {view_name.capitalize()} View")

    def exit_fullscreen_mode(self):
        """Switches back to the normal 2x2 grid view."""
        if self.stacked_layout.currentIndex() == 0 or self.current_fullscreen_view_name is None:
            return
        
        view_name = self.current_fullscreen_view_name
        container = self.view_containers.get(view_name)
        vtk_widget = self.vtk_widgets.get(view_name)

        if container and vtk_widget and self.fullscreen_container:
            # Remove the VTK widget from the fullscreen container
            self.fullscreen_container.layout().removeWidget(vtk_widget)
            
            # Move the VTK widget back to its original container's layout
            # We need to find the content_area widget inside the container
            content_area = container.findChild(QWidget, "content_area") # This is not robust, let's find it differently
            # A better way is to get the layout of the container, then the layout's item at index 1 (content_area), then its widget
            content_area_widget = container.layout().itemAt(1).widget()
            content_area_widget.layout().addWidget(vtk_widget)
            
            # Show the original container again
            container.show()
            
            # Clean up the now-empty fullscreen container
            self.stacked_layout.removeWidget(self.fullscreen_container)
            self.fullscreen_container.deleteLater()
            self.fullscreen_container = None

        # Switch back to the main grid view
        self.stacked_layout.setCurrentIndex(0)
        
        # Clean up the status bar
        if self.exit_fullscreen_btn:
            self.statusBar().removeWidget(self.exit_fullscreen_btn)
            self.exit_fullscreen_btn.deleteLater()
            self.exit_fullscreen_btn = None
        
        self.statusBar().showMessage("Ready")
        self.current_fullscreen_view_name = None


def main():
    print("Starting application...")
    
    try:
        app = QApplication(sys.argv)
        print("QApplication created")
        
        viewer = MRIViewer()
        print("MRIViewer created")
        
        viewer.show()
        print("Window shown")
        
        for name, widget in viewer.vtk_widgets.items():
            print(f"Initializing {name} widget...")
            widget.Initialize()
            widget.Start()
        
        print("Starting event loop...")
        return app.exec_()
    except Exception as e:
        print(f"Fatal error: {e}")
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())