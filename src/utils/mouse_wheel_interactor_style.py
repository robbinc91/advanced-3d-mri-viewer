from src.utils.check_imports import *
import math

class MouseWheelInteractorStyle(vtk.vtkInteractorStyleImage):
    def __init__(self, parent=None, view_name=None):
        # Initialize parent class explicitly
        super().__init__()
        
        self.parent = parent
        self.view_name = view_name

        self.is_dragging = False # Renamed from is_panning for clarity

        # Wheel events for slice scrolling
        self.AddObserver(vtk.vtkCommand.MouseWheelForwardEvent, self.on_mouse_wheel_forward)
        self.AddObserver(vtk.vtkCommand.MouseWheelBackwardEvent, self.on_mouse_wheel_backward)
        
        # Mouse events for crosshair seeking
        self.AddObserver("LeftButtonPressEvent", self.on_left_button_press)
        self.AddObserver("LeftButtonReleaseEvent", self.on_left_button_release)
        self.AddObserver("MouseMoveEvent", self.on_mouse_move)

        self.AutoAdjustCameraClippingRangeOff() 
        self.SetInteractionModeToImageSlicing()

    def on_left_button_press(self, obj, event):
        """Start tracking the mouse drag."""
        self.is_dragging = True
        
        # Update crosshair immediately on click
        self._seek_to_mouse_position()
        
        # Do NOT call base OnLeftButtonDown to prevent default window/leveling or panning
        # unless you want that behavior mixed in.

    def on_left_button_release(self, obj, event):
        """Stop tracking."""
        self.is_dragging = False
        self.OnLeftButtonUp()

    def on_mouse_move(self, obj, event):
        """
        If dragging, update the slice (crosshair) to match the mouse position.
        """
        if self.is_dragging and self.parent.mri_data is not None:
            self._seek_to_mouse_position()
            self.GetInteractor().GetRenderWindow().Render()
        else:
            # Pass through to base class (e.g., for hover events or other interactions)
            self.OnMouseMove()

    def _seek_to_mouse_position(self):
        """
        Gets the current mouse position in display coordinates, 
        converts it to world coordinates, and updates the slices.
        """
        # 1. Get Mouse Position
        event_pos = self.GetInteractor().GetEventPosition()
        
        # 2. Convert to World Coordinates
        ren_win = self.GetInteractor().GetRenderWindow()
        if not ren_win: return
        renderer = ren_win.GetRenderers().GetFirstRenderer()
        if not renderer: return

        renderer.SetDisplayPoint(event_pos[0], event_pos[1], 0)
        renderer.DisplayToWorld()
        world_pos = renderer.GetWorldPoint()

        # Check for valid coordinates
        if not all(math.isfinite(coord) for coord in world_pos):
            return

        # 3. Map World Coordinates to Voxel Indices
        # Start with current indices
        new_x = self.parent.current_slice['sagittal']
        new_y = self.parent.current_slice['coronal']
        new_z = self.parent.current_slice['axial']
        
        D, H, W = self.parent.mri_data.shape

        # Update specific axes based on the view orientation
        if self.view_name == 'axial':
            new_x = int(math.floor(world_pos[0]))
            new_y = int(math.floor(world_pos[1]))
        elif self.view_name == 'coronal':
            new_x = int(math.floor(world_pos[0]))
            new_z = int(math.floor(world_pos[1]))
        elif self.view_name == 'sagittal':
            new_y = int(math.floor(world_pos[0]))
            new_z = int(math.floor(world_pos[1]))
        
        # 4. Bounds Checking
        new_x = max(0, min(new_x, W - 1))
        new_y = max(0, min(new_y, H - 1))
        new_z = max(0, min(new_z, D - 1))
        
        # 5. Update Parent Sliders (Blocking signals to prevent recursion)
        self.parent.sagittal_slider.blockSignals(True)
        self.parent.coronal_slider.blockSignals(True)
        self.parent.axial_slider.blockSignals(True)

        self.parent.sagittal_slider.setValue(new_x)
        self.parent.coronal_slider.setValue(new_y)
        self.parent.axial_slider.setValue(new_z)
        
        # Update internal state
        self.parent.current_slice['sagittal'] = new_x
        self.parent.current_slice['coronal'] = new_y
        self.parent.current_slice['axial'] = new_z

        self.parent.sagittal_slider.blockSignals(False)
        self.parent.coronal_slider.blockSignals(False)
        self.parent.axial_slider.blockSignals(False)

        # 6. Trigger Sync
        # Using the parent's sync method to update all other views
        self.parent.update_2d_views() 
        self.parent.statusBar().showMessage(f"Voxel: {new_x}, {new_y}, {new_z}")

    def on_mouse_wheel_forward(self, obj, event):
        self._adjust_slice(1)
    
    def on_mouse_wheel_backward(self, obj, event):
        self._adjust_slice(-1)

    def _adjust_slice(self, delta):
        if not self.parent or not self.view_name: return
        
        slider = None
        updater = None
        
        if self.view_name == 'axial':
            slider = self.parent.axial_slider
            updater = self.parent.update_axial_slice
        elif self.view_name == 'sagittal':
            slider = self.parent.sagittal_slider
            updater = self.parent.update_sagittal_slice
        elif self.view_name == 'coronal':
            slider = self.parent.coronal_slider
            updater = self.parent.update_coronal_slice
            
        if slider:
            val = slider.value() + delta
            val = max(slider.minimum(), min(slider.maximum(), val))
            slider.setValue(val)
            updater(val)