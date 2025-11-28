#!/usr/bin/env python3
import sys
import traceback
import numpy as np
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QHBoxLayout, QGridLayout, QGroupBox, QPushButton,
                             QLabel, QScrollArea, QStatusBar, QMessageBox,
                             QFileDialog, QSpinBox, QSlider, QCheckBox,
                             QStackedLayout, QShortcut, QSplitter)
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
        self.mask_actors_3d = [] # Store multiple 3D mask actors
        self.mask_lut = None # Lookup table for mask color
        self.unique_mask_values = None # Store unique values in mask
        
        # Fullscreen state
        self.exit_fullscreen_btn = None
        self.current_fullscreen_view_name = None
        self.fullscreen_container = None # To hold the fullscreen widget

        self.crosshair_actors = {'axial': [], 'sagittal': [], 'coronal': []}
        self.annotations = [] # List of {'position': (x, y, z), 'text': str, 'actor': vtkActor}
        self.annotation_mode = False # Flag to enable/disable point-and-click

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
        self.btn_export = QPushButton("Export Screenshot")
        
        file_layout.addWidget(self.btn_load_mri)
        file_layout.addWidget(self.btn_load_mask)
        file_layout.addWidget(self.btn_export)
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
        self.volume_rendering_check.setChecked(False)
        self.volume_rendering_check.stateChanged.connect(self.toggle_rendering_mode)
        render_layout.addWidget(self.volume_rendering_check)
        
        render_group.setLayout(render_layout)

        annotation_group = QGroupBox("Annotations")
        anno_layout = QVBoxLayout()
        
        self.btn_toggle_anno = QPushButton("Toggle Annotation Mode (Click 3D View)")
        self.btn_toggle_anno.setCheckable(True)
        self.btn_toggle_anno.toggled.connect(self.toggle_annotation_mode)
        
        anno_layout.addWidget(self.btn_toggle_anno)
        annotation_group.setLayout(anno_layout)
        
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
        layout.addWidget(annotation_group)
        layout.addWidget(info_group)
        layout.addStretch()
        
        # Connect signals
        self.btn_load_mri.clicked.connect(self.load_mri)
        self.btn_load_mask.clicked.connect(self.load_mask)
        self.btn_export.clicked.connect(self.export_screenshot)
        
        return panel
    
    def toggle_annotation_mode(self, checked):
        """Enables/disables the mode for adding annotations via mouse clicks."""
        self.annotation_mode = checked
        if checked:
            self.statusBar().showMessage("Annotation Mode ON: Click on the 3D view to place a point.")
            self._setup_3d_picker()
        else:
            self.statusBar().showMessage("Annotation Mode OFF.")
            # Restore default 3D interactor style (vtk.vtkInteractorStyleTrackballCamera)
            # Assuming your default style for the 3D view is TrackballCamera (common for 3D)
            # You might need to change the 3D view setup to explicitly set/store the original style.
            default_style = vtk.vtkInteractorStyleTrackballCamera()
            self.vtk_widgets['3d'].SetInteractorStyle(default_style)
            default_style.SetDefaultRenderer(self.renderers['3d'])


    def _setup_3d_picker(self):
        """Sets up a Picker and a custom observation for mouse click events on the 3D view."""
        picker = vtk.vtkCellPicker()
        picker.SetTolerance(0.005) # tolerance for picking
        
        # A simple interactor style for observation only (can be a sub-class if needed)
        interactor_style = vtk.vtkInteractorStyleTrackballCamera()
        interactor_style.SetDefaultRenderer(self.renderers['3d'])
        
        # We use a custom lambda function to connect the Left Button Press event
        def on_left_click(obj, event):
            if not self.annotation_mode:
                # If mode is off, defer to default trackball behavior
                obj.OnLeftButtonDown() 
                return
            
            click_pos = self.vtk_widgets['3d'].GetRenderWindow().GetInteractor().GetEventPosition()
            
            # Use the picker to find the 3D coordinate on the volume surface
            # Note: We pick against the MRI volume, which is not an actor but a volume.
            # Picking directly on a vtkVolume is complex. A simpler way is to pick 
            # the coordinates in the background (no actor) and project onto the plane.
            # For simplicity here, we'll try to find the picked coordinate in the 3D scene.
            
            # VTK's standard picking doesn't work well on vtkSmartVolumeMapper.
            # We must use a vtkVolumePicker.
            volume_picker = vtk.vtkVolumePicker()
            volume_picker.Pick(click_pos[0], click_pos[1], 0.0, self.renderers['3d'])
            
            world_pos = volume_picker.GetPickPosition()
            
            if world_pos and self.mri_data is not None:
                # Convert world position (X, Y, Z) to image index (I, J, K)
                # Assuming simple 1:1 scaling and origin at (0, 0, 0)
                image_idx = (int(world_pos[0]), int(world_pos[1]), int(world_pos[2]))
                
                # Check if the pick is within bounds
                W, H, D = self.mri_data.shape[2], self.mri_data.shape[1], self.mri_data.shape[0]
                if 0 <= image_idx[0] < W and 0 <= image_idx[1] < H and 0 <= image_idx[2] < D:
                    self._prompt_and_add_annotation(image_idx)
                else:
                    self.statusBar().showMessage("Annotation point is outside the volume boundaries.")
            
            # Always handle the event to prevent default behavior if in annotation mode
            self.vtk_widgets['3d'].GetRenderWindow().Render()

        # Set the custom handler for the left button click
        self.vtk_widgets['3d'].SetInteractorStyle(interactor_style)
        interactor_style.AddObserver(vtk.vtkCommand.LeftButtonPressEvent, on_left_click)

    def _prompt_and_add_annotation(self, image_idx):
        """Prompts user for text and adds the annotation at the given index."""
        from PyQt5.QtWidgets import QInputDialog
        
        text, ok = QInputDialog.getText(self, 'Add Annotation', 'Annotation Text:')
        
        if ok and text:
            # 1. Create VTK Text Actor
            label_actor = vtk.vtkBillboardTextActor3D()
            label_actor.SetInput(text)
            label_actor.SetPosition(image_idx[0], image_idx[1], image_idx[2]) # X, Y, Z index
            
            prop = label_actor.GetTextProperty()
            prop.SetColor(1.0, 1.0, 0.0) # Yellow text
            prop.SetFontSize(16)
            
            # 2. Add to 3D View
            self.renderers['3d'].AddActor(label_actor)
            
            # 3. Store Data
            self.annotations.append({
                'position': image_idx, 
                'text': text, 
                'actor': label_actor
            })
            
            # 4. Update 2D Slices
            self.update_2d_views()
            self.vtk_widgets['3d'].GetRenderWindow().Render()
            self.statusBar().showMessage(f"Annotation added at {image_idx}: '{text}'")


    def _update_annotations_on_2d_slices(self):
        """Draws small circles/dots on 2D slices corresponding to annotations."""
        
        # Helper to create a small sphere/point actor
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
        
        # Get all 2D renderers
        views_2d = ['axial', 'sagittal', 'coronal']
        
        # Clear existing annotation actors from 2D views (assuming they are stored separately)
        # Note: We need a better way to track and clear these than RemoveAllViewProps(),
        # which would remove the MRI image actor itself.
        # Since we use RemoveAllViewProps() in the slice update functions, 
        # we can just re-add the annotation actors after the MRI/Mask actors.
        
        for view_name in views_2d:
            renderer = self.renderers[view_name]
            # Get the current actors (MRI and Mask)
            mri_actor = renderer.GetActors().GetLastItem() # Simple assumption
            
            # Re-draw the slice and then add the annotation points

            for anno in self.annotations:
                x, y, z = anno['position']
                
                # Create a temporary point actor for the specific slice view
                point_actor = create_point_actor(anno['position'])
                
                # Check if the annotation falls on the current slice plane
                # Tolerance is set to 1.0 (meaning it's visible if it's on the slice)
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
                    # In 2D views, annotations are added as points in the *image space*.
                    # This relies on the camera/mapper projecting the 3D point correctly.
                    # This is complex when using vtkImageReslice for 2D views as they
                    # flatten the 3D coordinates. 
                    
                    # Simpler method: Add the point actor to the 3D renderer. Since 
                    # vtkImageReslice's output is 2D, adding 3D actors (like our point) 
                    # directly to the 2D renderer won't work easily.
                    
                    # *CORRECT APPROACH:* The 2D slice views are only meant to show 
                    # the 2D slice plane. The simple text annotation is often only shown 
                    # in the 3D view, while the 2D slices show the intersection point.
                    
                    # Re-purposing the point actor created above (which is 3D)
                    renderer.AddActor(point_actor)
                    
            self.vtk_widgets[view_name].GetRenderWindow().Render()

    def export_screenshot(self):
        """Opens a file dialog and saves the currently visible view (3D view) as a PNG."""
        if self.mri_data is None:
            QMessageBox.warning(self, "Warning", "Please load an MRI file before exporting.")
            return

        if self.stacked_layout.currentIndex() == 1 and self.current_fullscreen_view_name:
            # If in fullscreen mode, capture the fullscreen view
            target_view_name = self.current_fullscreen_view_name
        else:
            # Otherwise, capture the 3D view (or perhaps the Axial view)
            target_view_name = '3d'
            
        # Ensure the selected view exists
        if target_view_name not in self.vtk_widgets:
            QMessageBox.critical(self, "Error", "Selected view is not available for export.")
            return

        render_window = self.vtk_widgets.get(target_view_name).GetRenderWindow()

        # Use the 3D view's render window by default
        #target_view_name = '3d'
        #render_window = self.vtk_widgets.get(target_view_name).GetRenderWindow()
        
        if not render_window:
            self.statusBar().showMessage("Error: Could not find a render window to export.")
            return

        # 1. Open File Dialog
        filename, _ = QFileDialog.getSaveFileName(
            self, 
            "Save Screenshot", 
            f"{target_view_name}_screenshot.png", 
            "PNG Image (*.png);;JPEG Image (*.jpg);;All Files (*)"
        )

        if not filename:
            self.statusBar().showMessage("Export cancelled.")
            return
        
        self.statusBar().showMessage(f"Exporting screenshot to: {filename}...")

        try:
            # 2. Capture the Render Window content
            window_to_image = vtk.vtkWindowToImageFilter()
            window_to_image.SetInput(render_window)
            # Set to True for higher resolution capture, but slower
            # window_to_image.SetMagnification(1) 
            window_to_image.Update()

            # 3. Write the image to a file (PNG format)
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
            # Give the content area a robust object name for easy lookup later
            content_area.setObjectName(f"{view_name}_content_area") 
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
            
            # Note: VTK uses (Width, Height, Depth) which corresponds to (X, Y, Z) in image space
            # NiBabel/NumPy data is often (Depth, Height, Width) or (Z, Y, X)
            depth, height, width = self.mri_data.shape
            
            self.image_data = vtk.vtkImageData()
            self.image_data.SetDimensions(width, height, depth) # X, Y, Z
            self.image_data.AllocateScalars(vtk.VTK_FLOAT, 1)
            
            # Populate VTK image data from NumPy array (careful with indexing)
            for z in range(depth):
                for y in range(height):
                    for x in range(width):
                        # NumPy: [Z, Y, X] -> VTK: (X, Y, Z)
                        self.image_data.SetScalarComponentFromDouble(x, y, z, 0, self.mri_data[z, y, x])
            
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
        
        # Consistent set of colors for mask labels
        colors = [
            (1, 0, 0), (0, 1, 0), (0, 0, 1), (1, 1, 0), (1, 0, 1),
            (0, 1, 1), (1, 0.5, 0), (0.5, 0, 1), (0, 0.5, 0),
        ]
        
        # Create 3D visualization for each unique, non-zero label
        for label_value in self.unique_mask_values:
            # 1. Marching Cubes to extract the surface of the label
            marching_cubes = vtk.vtkMarchingCubes()
            marching_cubes.SetInputData(self.mask_image_data)
            marching_cubes.SetValue(0, label_value)
            marching_cubes.ComputeNormalsOn()
            
            # 2. Smoother filter for a better appearance
            smoother = vtk.vtkWindowedSincPolyDataFilter()
            smoother.SetInputConnection(marching_cubes.GetOutputPort())
            smoother.SetNumberOfIterations(50)
            smoother.SetPassBand(0.05)
            smoother.FeatureEdgeSmoothingOff()
            smoother.BoundarySmoothingOff()
            smoother.NonManifoldSmoothingOn()
            smoother.NormalizeCoordinatesOn()

            # 3. Mapper and Actor
            mapper = vtk.vtkPolyDataMapper()
            mapper.SetInputConnection(smoother.GetOutputPort())
            mapper.ScalarVisibilityOff()
            
            actor = vtk.vtkActor()
            actor.SetMapper(mapper)
            
            # 4. Set color and initial opacity
            color_idx = int(label_value) % len(colors)
            r, g, b = colors[color_idx]
            actor.GetProperty().SetColor(r, g, b)
            # Use current slider value for initial opacity
            actor.GetProperty().SetOpacity(self.mask_opacity_slider.value() / 100.0) 
            
            self.renderers['3d'].AddActor(actor)
            self.mask_actors_3d.append(actor)
        
        # Setup Lookup Table (LUT) for 2D mask visualization
        self.mask_lut = vtk.vtkLookupTable()
        max_label = max(self.unique_mask_values) if len(self.unique_mask_values) > 0 else 1
        max_label_int = int(max_label) + 1
        
        self.mask_lut.SetRange(0, max_label)
        self.mask_lut.SetNumberOfTableValues(max_label_int)
        
        for i in range(max_label_int):
            if i == 0:
                # Black/transparent for background (label 0)
                self.mask_lut.SetTableValue(i, 0, 0, 0, 0)
            else:
                # Colored, opaque for labels > 0
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
        
        # 3D opacity update is separate since SetVisibility handles show/hide
        if state == Qt.Checked:
            self.update_mask_opacity(self.mask_opacity_slider.value())
        
        self.update_2d_views()

        
        self.vtk_widgets['3d'].GetRenderWindow().Render()
    
    def build_main_display(self):
        """Builds the main display area using QSplitter for flexible resizing."""
        
        # 1. Container for the four views (3D, Axial, Sagittal, Coronal)
        views_container = QWidget()
        views_layout = QVBoxLayout(views_container)
        views_layout.setContentsMargins(0, 0, 0, 0)
        views_layout.setSpacing(5) # Set spacing between widgets

        # --- Top Half: 3D View and Axial View (Vertical Split) ---
        top_splitter = QSplitter(Qt.Orientation.Horizontal)
        top_splitter.addWidget(self.vtk_widgets['3d'])
        top_splitter.addWidget(self.vtk_widgets['axial'])
        
        # --- Bottom Half: Sagittal and Coronal Views (Horizontal Split) ---
        bottom_splitter = QSplitter(Qt.Orientation.Horizontal)
        bottom_splitter.addWidget(self.vtk_widgets['sagittal'])
        bottom_splitter.addWidget(self.vtk_widgets['coronal'])

        # Set initial sizes for better balance (e.g., 50/50 split)
        # This prevents one pane from collapsing initially.
        top_splitter.setSizes([self.width() / 2, self.width() / 2])
        bottom_splitter.setSizes([self.width() / 2, self.width() / 2])
        
        # --- Main Layout: Stack the two splitters vertically ---
        
        # Vertical Splitter: Contains the top row (3D/Axial) and the bottom row (Sagittal/Coronal)
        main_splitter = QSplitter(Qt.Orientation.Vertical)
        main_splitter.addWidget(top_splitter)
        main_splitter.addWidget(bottom_splitter)
        
        views_layout.addWidget(main_splitter)
        
        # Set initial size ratios for the vertical split (e.g., 50/50 split)
        main_splitter.setSizes([self.height() / 2, self.height() / 2])

        return views_container
    def update_mask_opacity(self, value):
        opacity = value / 100.0
        
        # Update 3D mask opacity
        for actor in self.mask_actors_3d:
            actor.GetProperty().SetOpacity(opacity)
            
        self.vtk_widgets['3d'].GetRenderWindow().Render()
        
        # Update 2D mask opacity (requires re-rendering slices)
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
        # Update all 2D slices based on current slider positions
        self.update_axial_slice(self.axial_slider.value())
        self.update_sagittal_slice(self.sagittal_slider.value())
        self.update_coronal_slice(self.coronal_slider.value())

        self._update_annotations_on_2d_slices()
    
    def update_axial_slice(self, value):
        if self.mri_data is None: return
        
        self.axial_slider.setValue(value)
        self.current_slice['axial'] = value
        
        # --- 1. Update MRI and Mask Actors (Existing Logic) ---
        # The Axial plane is orthogonal to the Z-axis (Depth/Slice index)
        # Reslice matrix for Axial: (X->X, Y->Y, Z->Z slice)
        reslice = vtk.vtkImageReslice()
        reslice.SetInputData(self.image_data)
        reslice.SetOutputDimensionality(2)
        reslice.SetResliceAxesDirectionCosines(1, 0, 0, 0, 1, 0, 0, 0, 1)
        reslice.SetResliceAxesOrigin(0, 0, value) # Slice origin on Z-axis
        
        # ... (mri_actor setup)
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
            # ... (mask_actor setup using mask_reslice and color_map)
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

        # --- 2. Update Crosshairs in other views ---
        self._update_crosshair_sync()

    def update_sagittal_slice(self, value):
        if self.mri_data is None: return
        
        self.sagittal_slider.setValue(value)
        self.current_slice['sagittal'] = value
        
        # The Sagittal plane is orthogonal to the X-axis (Width/Column index)
        # Reslice matrix for Sagittal: (Y->X, Z->Y, X->Z slice)
        reslice = vtk.vtkImageReslice()
        reslice.SetInputData(self.image_data)
        reslice.SetOutputDimensionality(2)
        reslice.SetResliceAxesDirectionCosines(0, 1, 0, 0, 0, 1, 1, 0, 0)
        reslice.SetResliceAxesOrigin(value, 0, 0) # Slice origin on X-axis
        
        # ... (mri_actor and mask_actor setup, same logic as axial but using the Sagittal reslice)
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

        # --- 2. Update Crosshairs in other views ---
        self._update_crosshair_sync()

    def update_coronal_slice(self, value):
        if self.mri_data is None: return
        
        self.coronal_slider.setValue(value)
        self.current_slice['coronal'] = value
        
        # The Coronal plane is orthogonal to the Y-axis (Height/Row index)
        # Reslice matrix for Coronal: (X->X, Z->Y, Y->Z slice)
        reslice = vtk.vtkImageReslice()
        reslice.SetInputData(self.image_data)
        reslice.SetOutputDimensionality(2)
        reslice.SetResliceAxesDirectionCosines(1, 0, 0, 0, 0, 1, 0, 1, 0)
        reslice.SetResliceAxesOrigin(0, value, 0) # Slice origin on Y-axis
        
        # ... (mri_actor and mask_actor setup, same logic as axial/sagittal but using the Coronal reslice)
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

        # --- 2. Update Crosshairs in other views ---
        self._update_crosshair_sync()
    
    def _create_crosshair_actor(self, x_pos, y_pos, x_max, y_max):
        """
        Creates a pair of orthogonal lines (crosshair) at (x_pos, y_pos) 
        within the image extent (0, x_max) x (0, y_max).
        """
        crosshair_color = (1.0, 1.0, 0.0) # Bright Yellow
        line_width = 2
        
        # 1. Geometry: Two lines forming the cross
        points = vtk.vtkPoints()
        # Horizontal line (spanning X-axis, centered at y_pos)
        points.InsertNextPoint(0, y_pos, 0)
        points.InsertNextPoint(x_max, y_pos, 0)
        # Vertical line (spanning Y-axis, centered at x_pos)
        points.InsertNextPoint(x_pos, 0, 0)
        points.InsertNextPoint(x_pos, y_max, 0)

        lines = vtk.vtkCellArray()
        # Horizontal line: from point 0 to 1
        line1 = vtk.vtkLine()
        line1.GetPointIds().SetId(0, 0)
        line1.GetPointIds().SetId(1, 1)
        # Vertical line: from point 2 to 3
        line2 = vtk.vtkLine()
        line2.GetPointIds().SetId(0, 2)
        line2.GetPointIds().SetId(1, 3)
        
        lines.InsertNextCell(line1)
        lines.InsertNextCell(line2)

        polydata = vtk.vtkPolyData()
        polydata.SetPoints(points)
        polydata.SetLines(lines)

        # 2. Mapper
        mapper = vtk.vtkPolyDataMapper()
        mapper.SetInputData(polydata)

        # 3. Actor
        actor = vtk.vtkActor()
        actor.SetMapper(mapper)
        actor.GetProperty().SetColor(crosshair_color)
        actor.GetProperty().SetLineWidth(line_width)
        return actor


    def _update_crosshair_sync(self):
        if self.mri_data is None: return
        
        D, H, W = self.mri_data.shape # Z, Y, X dimensions
        
        # Current slice indices (I, J, K)
        Z_slice = self.current_slice['axial']
        X_slice = self.current_slice['sagittal']
        Y_slice = self.current_slice['coronal']
        
        # Remove old crosshair actors first
        for view_name in ['axial', 'sagittal', 'coronal']:
            renderer = self.renderers[view_name]
            for actor in self.crosshair_actors[view_name]:
                renderer.RemoveActor(actor)
            self.crosshair_actors[view_name] = []

        # --- Axial View (Shows XY plane, Z is fixed) ---
        # The crosshair shows the position of the Sagittal (X) and Coronal (Y) planes.
        # X-coordinate is Sagittal slice index, Y-coordinate is Coronal slice index.
        # Image extent is (0, W) x (0, H)
        # Note: Your VTK Image is (X, Y, Z) = (W, H, D). Axial view shows (X, Y).
        # We draw the crosshair on the Axial image plane:
        axial_ch_actor = self._create_crosshair_actor(X_slice, Y_slice, W, H)
        self.renderers['axial'].AddActor(axial_ch_actor)
        self.crosshair_actors['axial'].append(axial_ch_actor)

        # --- Sagittal View (Shows YZ plane, X is fixed) ---
        # The crosshair shows the position of the Axial (Z) and Coronal (Y) planes.
        # X-axis in sagittal view corresponds to Y (Coronal index).
        # Y-axis in sagittal view corresponds to Z (Axial index).
        # Image extent is (0, H) x (0, D)
        sagittal_ch_actor = self._create_crosshair_actor(Y_slice, Z_slice, H, D)
        self.renderers['sagittal'].AddActor(sagittal_ch_actor)
        self.crosshair_actors['sagittal'].append(sagittal_ch_actor)

        # --- Coronal View (Shows XZ plane, Y is fixed) ---
        # The crosshair shows the position of the Axial (Z) and Sagittal (X) planes.
        # X-axis in coronal view corresponds to X (Sagittal index).
        # Y-axis in coronal view corresponds to Z (Axial index).
        # Image extent is (0, W) x (0, D)
        coronal_ch_actor = self._create_crosshair_actor(X_slice, Z_slice, W, D)
        self.renderers['coronal'].AddActor(coronal_ch_actor)
        self.crosshair_actors['coronal'].append(coronal_ch_actor)

        # Render all updated views
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
        """Switches main view to fullscreen for the selected view."""
        # If already in fullscreen, exit first
        if self.stacked_layout.currentIndex() != 0:
            self.exit_fullscreen_mode()
            return

        container = self.view_containers.get(view_name)
        vtk_widget = self.vtk_widgets.get(view_name)
        
        if container and vtk_widget:
            self.current_fullscreen_view_name = view_name
            
            # 1. Temporarily remove the container from the grid layout
            self.view_grid.removeWidget(container)
            
            # 2. Create the fullscreen container (Page 1 in stacked layout)
            self.fullscreen_container = QWidget()
            fullscreen_layout = QVBoxLayout(self.fullscreen_container)
            fullscreen_layout.setContentsMargins(0, 0, 0, 0)
            
            # 3. Create a clean exit bar (replaces status bar use)
            exit_bar = QWidget()
            exit_bar_layout = QHBoxLayout(exit_bar)
            exit_bar_layout.setContentsMargins(10, 5, 10, 5)
            exit_bar_layout.addStretch()
            # Use a slightly larger, colored button for high visibility
            self.exit_fullscreen_btn = QPushButton(f"Exit Fullscreen: {view_name.capitalize()} (Esc)")
            self.exit_fullscreen_btn.setStyleSheet("""
                QPushButton { background-color: #f44336; color: white; border: none; border-radius: 4px; padding: 5px 15px; font-weight: bold; }
                QPushButton:hover { background-color: #d32f2f; }
            """)
            self.exit_fullscreen_btn.clicked.connect(self.exit_fullscreen_mode)
            exit_bar_layout.addWidget(self.exit_fullscreen_btn)
            
            # 4. Add the exit bar and the original container to the fullscreen widget
            fullscreen_layout.addWidget(exit_bar)
            container.setParent(self.fullscreen_container) # Set parent to the fullscreen container
            fullscreen_layout.addWidget(container)
            
            # 5. Switch stacked layout to the fullscreen view
            self.stacked_layout.addWidget(self.fullscreen_container)
            self.stacked_layout.setCurrentWidget(self.fullscreen_container)
            
            self.statusBar().showMessage(f"Fullscreen: {view_name.capitalize()} View")

    def exit_fullscreen_mode(self):
        """Switches back to the normal 2x2 grid view."""
        if self.stacked_layout.currentIndex() == 0 or self.current_fullscreen_view_name is None:
            return

        view_name = self.current_fullscreen_view_name
        container = self.view_containers.get(view_name)

        if container and self.fullscreen_container:
            
            # 1. Take the original container out of the fullscreen layout
            # and clear its parent so it can be re-added to the grid
            self.fullscreen_container.layout().removeWidget(container)
            container.setParent(None) 

            # 2. Switch back to the normal grid view (index 0)
            self.stacked_layout.setCurrentIndex(0)

            # 3. Re-add the original container to the correct position in the grid layout
            row, col = self.view_grid_positions[view_name]
            self.view_grid.addWidget(container, row, col)
            
            # 4. Clean up the temporary fullscreen widget and state
            self.stacked_layout.removeWidget(self.fullscreen_container)
            self.fullscreen_container.deleteLater()
            self.fullscreen_container = None
            self.current_fullscreen_view_name = None
            self.exit_fullscreen_btn = None
            self.statusBar().showMessage("Ready")
            
            # 5. Ensure render window is resized and re-rendered in its original context
            vtk_widget = self.vtk_widgets.get(view_name)
            if vtk_widget:
                # Use QTimer to delay render until the widget is fully back in the layout
                QTimer.singleShot(100, lambda: vtk_widget.GetRenderWindow().Render())


if __name__ == '__main__':
    # Add a custom exception hook for better debugging with PyQt
    def excepthook(exc_type, exc_value, exc_tb):
        tb = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
        print("Error details:", tb)
        QMessageBox.critical(None, "Fatal Error", f"An unhandled error occurred: {exc_value}\n\nSee console for details.")
        sys.exit(1)
        
    sys.excepthook = excepthook

    app = QApplication(sys.argv)
    # Check VTK availability immediately before instantiation
    if not VTK_AVAILABLE:
        QMessageBox.critical(None, "Error", "VTK is not properly installed or configured.")
        sys.exit(1)

    # Check NIBABEL availability but allow running without it (file loading disabled)
    if not NIBABEL_AVAILABLE:
        print("WARNING: NiBabel not found. File loading will be disabled.")

    viewer = MRIViewer()
    viewer.show()
    sys.exit(app.exec_())