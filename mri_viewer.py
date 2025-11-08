import sys
import vtk
from vtk.util import numpy_support as nps
import numpy as np
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QPushButton, QFileDialog, QSlider, QLabel, QFrame, QGridLayout, QComboBox)
from PyQt5.QtCore import Qt
from vtk.qt.QVTKRenderWindowInteractor import QVTKRenderWindowInteractor

# A dark theme stylesheet for a professional look
STYLE_SHEET = """
QWidget {
    background-color: #2E2E2E;
    color: #F0F0F0;
    font-family: Arial, sans-serif;
}
QMainWindow {
    background-color: #202020;
}
QFrame#control_panel {
    background-color: #383838;
    border-radius: 5px;
}
QPushButton, QComboBox {
    background-color: #555555;
    border: 1px solid #777777;
    padding: 8px;
    border-radius: 5px;
    font-size: 13px;
}
QPushButton:hover, QComboBox:hover {
    background-color: #6E6E6E;
}
QComboBox::drop-down {
    border: none;
}
QComboBox QAbstractItemView {
    background-color: #555555;
    border: 1px solid #777777;
    selection-background-color: #6E6E6E;
}
QSlider::groove:horizontal {
    border: 1px solid #5A5A5A;
    height: 4px;
    background: #4A4A4A;
    margin: 2px 0;
    border-radius: 2px;
}
QSlider::handle:horizontal {
    background: #DDDDDD;
    border: 1px solid #AAAAAA;
    width: 16px;
    margin: -6px 0;
    border-radius: 8px;
}
QLabel {
    padding-top: 5px;
    font-weight: bold;
    font-size: 14px;
}
QLabel#view_label {
    background-color: #404040;
    color: #CCCCCC;
    font-size: 12px;
    padding: 4px;
    border-radius: 3px;
}
QVTKRenderWindowInteractor {
    border: 1px solid #444444;
}
"""

class MRIViewer(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Advanced 3D MRI Viewer")
        self.setGeometry(100, 100, 1400, 900)

        # Predefined colors for segmentation labels
        self.LABEL_COLORS = [
            (1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0), (1.0, 1.0, 0.0),
            (0.0, 1.0, 1.0), (1.0, 0.0, 1.0), (1.0, 0.5, 0.0), (0.5, 0.0, 1.0),
        ]

        # --- Data holders and VTK objects ---
        self.mri_image_data = None
        self.mask_image_data = None
        self.mri_volume_actor = None
        self.mask_surface_actors = []
        self.mask_lookup_table = None
        self.slice_actors = {}
        self.mask_slice_actors = {}
        self.renderers_2d = {}
        self.vtk_widgets_2d = {}

        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QHBoxLayout(self.central_widget)

        self.setup_control_panel()
        self.setup_visualization_grid()
        self.show()

    def setup_control_panel(self):
        control_frame = QFrame()
        control_frame.setObjectName("control_panel")
        control_frame.setFixedWidth(280)
        self.control_layout = QVBoxLayout(control_frame)
        self.control_layout.setContentsMargins(15, 15, 15, 15)

        # --- File Loading ---
        btn_load_mri = QPushButton("Load MRI (.nii, .nii.gz)"); btn_load_mri.clicked.connect(self.load_mri)
        btn_load_mask = QPushButton("Load Mask (.nii, .nii.gz)"); btn_load_mask.clicked.connect(self.load_mask)
        self.control_layout.addWidget(btn_load_mri); self.control_layout.addWidget(btn_load_mask)
        self.control_layout.addSpacing(20)

        # --- 3D View Controls ---
        self.view_toggle_label = QLabel("3D View Mode")
        self.view_toggle_combo = QComboBox(); self.view_toggle_combo.currentTextChanged.connect(self.update_3d_visibility)
        self.control_layout.addWidget(self.view_toggle_label); self.control_layout.addWidget(self.view_toggle_combo)
        self.opacity_3d_label = QLabel("3D Mask Opacity")
        self.opacity_slider_3d = QSlider(Qt.Horizontal); self.opacity_slider_3d.setRange(0, 100); self.opacity_slider_3d.setValue(40)
        self.opacity_slider_3d.valueChanged.connect(self.update_mask_opacity_3d)
        self.control_layout.addWidget(self.opacity_3d_label); self.control_layout.addWidget(self.opacity_slider_3d)
        self.control_layout.addSpacing(20)

        # --- 2D View Controls ---
        self.opacity_mri_2d_label = QLabel("2D MRI Opacity")
        self.opacity_slider_mri_2d = QSlider(Qt.Horizontal); self.opacity_slider_mri_2d.setRange(0, 100); self.opacity_slider_mri_2d.setValue(100)
        self.opacity_slider_mri_2d.valueChanged.connect(self.update_mri_opacity_2d)
        self.control_layout.addWidget(self.opacity_mri_2d_label); self.control_layout.addWidget(self.opacity_slider_mri_2d)
        
        self.opacity_2d_label = QLabel("2D Overlay Opacity")
        self.opacity_slider_2d = QSlider(Qt.Horizontal); self.opacity_slider_2d.setRange(0, 100); self.opacity_slider_2d.setValue(40)
        self.opacity_slider_2d.valueChanged.connect(self.update_mask_opacity_2d)
        self.control_layout.addWidget(self.opacity_2d_label); self.control_layout.addWidget(self.opacity_slider_2d)
        self.control_layout.addSpacing(20)

        # --- Slice Controls ---
        self.slice_controls = QWidget()
        slice_layout = QVBoxLayout(self.slice_controls); slice_layout.setContentsMargins(0,0,0,0)
        self.axial_slider = self._create_slice_slider("Axial Slice", slice_layout, 'axial')
        self.sagittal_slider = self._create_slice_slider("Sagittal Slice", slice_layout, 'sagittal')
        self.coronal_slider = self._create_slice_slider("Coronal Slice", slice_layout, 'coronal')
        self.control_layout.addWidget(self.slice_controls)

        self.control_layout.addStretch(1)
        self.main_layout.addWidget(control_frame)
        self._set_initial_control_visibility()

    def _set_initial_control_visibility(self):
        self.view_toggle_label.hide(); self.view_toggle_combo.hide()
        self.opacity_3d_label.hide(); self.opacity_slider_3d.hide()
        self.opacity_2d_label.hide(); self.opacity_slider_2d.hide()
        self.opacity_mri_2d_label.hide(); self.opacity_slider_mri_2d.hide()
        self.slice_controls.hide()
    
    def _create_slice_slider(self, name, layout, view_name):
        label = QLabel(name); slider = QSlider(Qt.Horizontal)
        slider.valueChanged.connect(lambda val: self.update_slice(view_name, val))
        layout.addWidget(label); layout.addWidget(slider)
        return slider

    def setup_visualization_grid(self):
        vis_widget = QWidget(); self.vis_layout = QGridLayout(vis_widget); self.vis_layout.setSpacing(5)
        self.vtkWidget_3d = QVTKRenderWindowInteractor(); self.renderer_3d = vtk.vtkRenderer(); self.renderer_3d.SetBackground(0.1, 0.1, 0.15)
        self.vtkWidget_3d.GetRenderWindow().AddRenderer(self.renderer_3d)
        frames = {name: self._create_2d_view_widget(name) for name in ['axial', 'sagittal', 'coronal']}
        self.vis_layout.addWidget(self.vtkWidget_3d, 0, 0); self.vis_layout.addWidget(frames['axial'], 0, 1)
        self.vis_layout.addWidget(frames['sagittal'], 1, 0); self.vis_layout.addWidget(frames['coronal'], 1, 1)
        self.main_layout.addWidget(vis_widget)

    def _create_2d_view_widget(self, view_name):
        frame = QFrame(); layout = QVBoxLayout(frame); layout.setContentsMargins(0, 0, 0, 0); layout.setSpacing(2)
        label = QLabel(f"{view_name.capitalize()} View"); label.setObjectName("view_label"); label.setAlignment(Qt.AlignCenter)
        vtkWidget = QVTKRenderWindowInteractor(frame); renderer = vtk.vtkRenderer(); renderer.SetBackground(0.1, 0.1, 0.1)
        vtkWidget.GetRenderWindow().AddRenderer(renderer)
        layout.addWidget(label); layout.addWidget(vtkWidget)
        self.vtk_widgets_2d[view_name] = vtkWidget; self.renderers_2d[view_name] = renderer
        return frame

    def load_nifti_file(self, file_path):
        try:
            reader = vtk.vtkNIFTIImageReader(); reader.SetFileName(file_path); reader.Update()
            return reader.GetOutput()
        except Exception as e:
            print(f"VTK Error: Could not read NIfTI file '{file_path}'.\nDetails: {e}"); return None

    def load_mri(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Open MRI File", "", "NIfTI Files (*.nii *.nii.gz)")
        if not file_path: return
        self.clear_mask()
        self.mri_image_data = self.load_nifti_file(file_path)
        if not self.mri_image_data: return
        self.setup_3d_volume(); self.setup_2d_views()
        # Update UI visibility
        self.view_toggle_label.show(); self.view_toggle_combo.show()
        self.opacity_mri_2d_label.show(); self.opacity_slider_mri_2d.show()
        self.view_toggle_combo.blockSignals(True)
        self.view_toggle_combo.clear(); self.view_toggle_combo.addItem("MRI Only")
        self.view_toggle_combo.blockSignals(False)
        self.renderer_3d.ResetCamera(); self.vtkWidget_3d.GetRenderWindow().Render()

    def setup_3d_volume(self):
        if self.mri_volume_actor: self.renderer_3d.RemoveVolume(self.mri_volume_actor)
        scalar_range = self.mri_image_data.GetScalarRange()
        mapper = vtk.vtkSmartVolumeMapper(); mapper.SetInputData(self.mri_image_data)
        color_func = vtk.vtkColorTransferFunction(); opacity_func = vtk.vtkPiecewiseFunction()
        color_func.AddRGBPoint(scalar_range[0], 0, 0, 0)
        color_func.AddRGBPoint(scalar_range[0] + 0.5 * (scalar_range[1] - scalar_range[0]), 0.9, 0.4, 0.2)
        color_func.AddRGBPoint(scalar_range[1], 1, 1, 0.9)
        opacity_func.AddPoint(scalar_range[0], 0.0)
        opacity_func.AddPoint(scalar_range[0] + 0.5 * (scalar_range[1] - scalar_range[0]), 0.15)
        opacity_func.AddPoint(scalar_range[1], 0.3)
        prop = vtk.vtkVolumeProperty(); prop.SetColor(color_func); prop.SetScalarOpacity(opacity_func)
        prop.SetInterpolationTypeToLinear(); prop.ShadeOn()
        self.mri_volume_actor = vtk.vtkVolume(); self.mri_volume_actor.SetMapper(mapper); self.mri_volume_actor.SetProperty(prop)
        self.renderer_3d.AddVolume(self.mri_volume_actor)

    def setup_2d_views(self):
        for renderer in self.renderers_2d.values(): renderer.RemoveAllViewProps()
        dims = self.mri_image_data.GetDimensions()
        for view_name, slider, max_slice in [('axial', self.axial_slider, dims[2]-1), ('sagittal', self.sagittal_slider, dims[0]-1), ('coronal', self.coronal_slider, dims[1]-1)]:
            self._configure_slice_view(view_name, slider, max_slice)
        self.slice_controls.show()

    def _configure_slice_view(self, view_name, slider, max_slice):
        actor = vtk.vtkImageActor(); actor.GetMapper().SetInputData(self.mri_image_data)
        self.slice_actors[view_name] = actor
        self.renderers_2d[view_name].AddActor(actor)
        slider.setRange(0, max_slice); slider.setValue(max_slice // 2)
        self.update_slice(view_name, max_slice // 2)

    def update_slice(self, view_name, slice_idx):
        if self.mri_image_data is None: return
        if view_name in self.slice_actors:
            self._set_actor_slice(self.slice_actors[view_name], view_name, slice_idx, self.mri_image_data.GetDimensions())
        if view_name in self.mask_slice_actors:
            self._set_actor_slice(self.mask_slice_actors[view_name], view_name, slice_idx, self.mask_image_data.GetDimensions())
        renderer, camera, center = self.renderers_2d[view_name], self.renderers_2d[view_name].GetActiveCamera(), self.mri_image_data.GetCenter()
        if view_name == 'axial':
            camera.SetFocalPoint(center[0], center[1], slice_idx); camera.SetPosition(center[0], center[1], slice_idx + 500); camera.SetViewUp(0, 1, 0)
        elif view_name == 'sagittal':
            camera.SetFocalPoint(slice_idx, center[1], center[2]); camera.SetPosition(slice_idx + 500, center[1], center[2]); camera.SetViewUp(0, 0, 1)
        elif view_name == 'coronal':
            camera.SetFocalPoint(center[0], slice_idx, center[2]); camera.SetPosition(center[0], slice_idx - 500, center[2]); camera.SetViewUp(0, 0, 1)
        renderer.ResetCamera(); renderer.ResetCameraClippingRange(); self.vtk_widgets_2d[view_name].GetRenderWindow().Render()

    def _set_actor_slice(self, actor, view_name, slice_idx, dims):
        if view_name == 'axial': actor.SetDisplayExtent(0, dims[0]-1, 0, dims[1]-1, slice_idx, slice_idx)
        elif view_name == 'sagittal': actor.SetDisplayExtent(slice_idx, slice_idx, 0, dims[1]-1, 0, dims[2]-1)
        elif view_name == 'coronal': actor.SetDisplayExtent(0, dims[0]-1, slice_idx, slice_idx, 0, dims[2]-1)

    def load_mask(self):
        if not self.mri_image_data: print("Please load an MRI scan first."); return
        file_path, _ = QFileDialog.getOpenFileName(self, "Open Mask File", "", "NIfTI Files (*.nii *.nii.gz)")
        if not file_path: return
        self.clear_mask(); self.mask_image_data = self.load_nifti_file(file_path)
        if not self.mask_image_data: return

        dims = self.mask_image_data.GetDimensions()
        scalars = self.mask_image_data.GetPointData().GetScalars()
        numpy_array = nps.vtk_to_numpy(scalars).reshape(dims[2], dims[1], dims[0]).transpose(2,1,0)
        unique_labels = np.unique(numpy_array)
        self.unique_labels = [label for label in unique_labels if label > 0]

        for i, label in enumerate(self.unique_labels):
            mc = vtk.vtkDiscreteMarchingCubes(); mc.SetInputData(self.mask_image_data); mc.SetValue(0, label)
            smoother = vtk.vtkSmoothPolyDataFilter(); smoother.SetInputConnection(mc.GetOutputPort()); smoother.SetNumberOfIterations(15)
            mapper = vtk.vtkPolyDataMapper(); mapper.SetInputConnection(smoother.GetOutputPort())
            actor = vtk.vtkActor(); actor.SetMapper(mapper)
            color = self.LABEL_COLORS[i % len(self.LABEL_COLORS)]; actor.GetProperty().SetColor(color)
            self.mask_surface_actors.append(actor); self.renderer_3d.AddActor(actor)
        
        self.setup_2d_mask_overlays()
        self.opacity_3d_label.show(); self.opacity_slider_3d.show()
        self.opacity_2d_label.show(); self.opacity_slider_2d.show()
        self.view_toggle_combo.blockSignals(True); self.view_toggle_combo.addItems(["MRI + Mask", "Mask Only"])
        self.view_toggle_combo.setCurrentText("MRI + Mask"); self.view_toggle_combo.blockSignals(False)
        self.update_3d_visibility("MRI + Mask")
        self.update_mask_opacity_3d(self.opacity_slider_3d.value())
        self.vtkWidget_3d.GetRenderWindow().Render()

    def setup_2d_mask_overlays(self):
        max_label = int(max(self.unique_labels)) if self.unique_labels else 0
        opacity = self.opacity_slider_2d.value() / 100.0
        self.mask_lookup_table = vtk.vtkLookupTable(); self.mask_lookup_table.SetNumberOfTableValues(max_label + 1)
        self.mask_lookup_table.SetRange(0, max_label)
        self.mask_lookup_table.SetTableValue(0, 0, 0, 0, 0)
        for i, label in enumerate(self.unique_labels):
            color = self.LABEL_COLORS[i % len(self.LABEL_COLORS)]
            self.mask_lookup_table.SetTableValue(int(label), color[0], color[1], color[2], opacity)
        self.mask_lookup_table.Build()
        color_mapper = vtk.vtkImageMapToColors(); color_mapper.SetLookupTable(self.mask_lookup_table); color_mapper.SetInputData(self.mask_image_data)
        color_mapper.Update()
        for view_name in ['axial', 'sagittal', 'coronal']:
            actor = vtk.vtkImageActor(); actor.GetMapper().SetInputData(color_mapper.GetOutput())
            self.mask_slice_actors[view_name] = actor; self.renderers_2d[view_name].AddActor(actor)
            slider = getattr(self, f"{view_name}_slider"); self.update_slice(view_name, slider.value())

    def update_mri_opacity_2d(self, value):
        opacity = value / 100.0
        for actor in self.slice_actors.values():
            actor.GetProperty().SetOpacity(opacity)
        for widget in self.vtk_widgets_2d.values():
            widget.GetRenderWindow().Render()

    def update_mask_opacity_3d(self, value):
        opacity = value / 100.0
        if self.mask_surface_actors:
            for actor in self.mask_surface_actors:
                actor.GetProperty().SetOpacity(opacity)
            self.vtkWidget_3d.GetRenderWindow().Render()
    
    def update_mask_opacity_2d(self, value):
        opacity = value / 100.0
        if self.mask_lookup_table:
            for i, label in enumerate(self.unique_labels):
                color = self.LABEL_COLORS[i % len(self.LABEL_COLORS)]
                self.mask_lookup_table.SetTableValue(int(label), color[0], color[1], color[2], opacity)
            self.mask_lookup_table.Build()
            for widget in self.vtk_widgets_2d.values():
                widget.GetRenderWindow().Render()

    def update_3d_visibility(self, text):
        if not self.mri_volume_actor: return
        mri_visible = "MRI" in text; mask_visible = "Mask" in text
        self.mri_volume_actor.SetVisibility(mri_visible)
        for actor in self.mask_surface_actors: actor.SetVisibility(mask_visible)
        self.vtkWidget_3d.GetRenderWindow().Render()

    def clear_mask(self):
        for actor in self.mask_surface_actors: self.renderer_3d.RemoveActor(actor)
        self.mask_surface_actors.clear()
        for view_name, actor in self.mask_slice_actors.items():
            if actor: self.renderers_2d[view_name].RemoveActor(actor)
        self.mask_slice_actors.clear()
        self.mask_image_data, self.mask_lookup_table = None, None
        self.opacity_3d_label.hide(); self.opacity_slider_3d.hide()
        self.opacity_2d_label.hide(); self.opacity_slider_2d.hide()
        if self.mri_image_data:
            self.view_toggle_combo.blockSignals(True)
            self.view_toggle_combo.clear(); self.view_toggle_combo.addItem("MRI Only")
            self.view_toggle_combo.blockSignals(False)
            self.update_3d_visibility("MRI Only")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyleSheet(STYLE_SHEET)
    window = MRIViewer()
    sys.exit(app.exec_())