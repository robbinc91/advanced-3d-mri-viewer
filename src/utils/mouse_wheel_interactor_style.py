from src.utils.check_imports import *
import math

class MouseWheelInteractorStyle(vtk.vtkInteractorStyleImage):
    def __init__(self, parent=None, view_name=None):
        self.parent = parent
        self.view_name = view_name

        self.is_panning = False
        self.last_mouse_pos = (0, 0)

        self.AddObserver(vtk.vtkCommand.MouseWheelForwardEvent, self.on_mouse_wheel_forward)
        self.AddObserver(vtk.vtkCommand.MouseWheelBackwardEvent, self.on_mouse_wheel_backward)
        

        self.AddObserver("LeftButtonPressEvent", self.on_left_button_press)
        self.AddObserver("LeftButtonReleaseEvent", self.on_left_button_release)
        self.AddObserver("MouseMoveEvent", self.on_mouse_move)

        self.AutoAdjustCameraClippingRangeOff() 
        self.SetInteractionModeToImageSlicing()

    def on_left_button_press(self, obj, event):
        # Store initial position for seeking and start pan flag
        self.last_mouse_pos = self.GetInteractor().GetEventPosition()
        self.is_panning = True
        
        # Do NOT call base class OnLeftButtonDown yet. 
        # We will handle the first click's Seek logic in Release/Move.

    def on_left_button_release(self, obj, event):
        """
        If the mouse hasn't moved much (no drag), treat it as a SEEK (crosshair jump).
        Otherwise, reset the pan flag.
        """
        current_pos = self.GetInteractor().GetEventPosition()
        dx = abs(current_pos[0] - self.last_mouse_pos[0])
        dy = abs(current_pos[1] - self.last_mouse_pos[1])

        # If movement is negligible (e.g., less than 5 pixels), perform SEEK
        if dx < 5 and dy < 5:
            self._seek_to_position(current_pos)
            
        self.is_panning = False
        self.OnLeftButtonUp()

    def _update_crosshairs_from_world_pos(self, world_pos):
        """
        Dynamically calculates and updates the crosshair coordinates 
        in all views based on the new center point during a pan.
        """
        D, H, W = self.parent.mri_data.shape
        view_name = self.view_name
        
        # Start with the currently known slice index for the depth dimension
        new_x = self.parent.current_slice['sagittal']
        new_y = self.parent.current_slice['coronal']
        new_z = self.parent.current_slice['axial']

        # Map World Coordinates to Voxel Indices
        # We determine which two axes are moving based on the current view (view_name)
        if view_name == 'axial':
            new_x = int(math.floor(world_pos[0]))
            new_y = int(math.floor(world_pos[1]))
            
        elif view_name == 'coronal':
            new_x = int(math.floor(world_pos[0]))
            new_z = int(math.floor(world_pos[1]))
            
        elif view_name == 'sagittal':
            new_y = int(math.floor(world_pos[0]))
            new_z = int(math.floor(world_pos[1]))
        
        # Apply Bounds Checking
        new_x = max(0, min(new_x, W - 1))
        new_y = max(0, min(new_y, H - 1))
        new_z = max(0, min(new_z, D - 1))
        
        # *** KEY DIFFERENCE: Update the internal state directly, not the sliders ***
        self.parent.current_slice['sagittal'] = new_x
        self.parent.current_slice['coronal'] = new_y
        self.parent.current_slice['axial'] = new_z
        
        # Trigger crosshair redraw in all views
        self.parent._update_crosshair_sync() 
        self.parent.statusBar().showMessage(f"Pan Center: X:{new_x}, Y:{new_y}, Z:{new_z}")

    def on_mouse_move(self, obj, event):
        if not self.is_panning or self.parent.mri_data is None:
            self.OnMouseMove()
            return
        
        # --- Robust Renderer Retrieval (from previous fix) ---
        ren_win = self.GetInteractor().GetRenderWindow()
        if ren_win is None:
            self.OnMouseMove()
            return
            
        renderer = ren_win.GetRenderers().GetFirstRenderer()
        if renderer is None:
            self.OnMouseMove()
            return
        # -----------------------------------------------------

        # 1. Perform the Pan
        self.Pan()
        
        # 2. Dynamic Crosshair Update (IPS)
        # Determine the center of the view (where the crosshair should be relative to the image)
        
        # We use the center of the screen in display coordinates
        size = ren_win.GetSize()
        center_display_x, center_display_y = size[0] / 2, size[1] / 2
        
        # Convert Center Display Coords to World Coords
        renderer.SetDisplayPoint(center_display_x, center_display_y, 0)
        renderer.DisplayToWorld()
        world_pos = renderer.GetWorldPoint()

        if all(math.isfinite(coord) for coord in world_pos):
            self._update_crosshairs_from_world_pos(world_pos)
        
        # 3. Finalize Move Event
        self.last_mouse_pos = self.GetInteractor().GetEventPosition()
        self.GetInteractor().GetRenderWindow().Render()
        self.OnMouseMove()

    # --- SEEK LOGIC (Adapted from previous on_left_click) ---
    def _seek_to_position(self, display_pos):
        """Performs the crosshair jump/sync logic."""
        
        D, H, W = self.parent.mri_data.shape # Z, Y, X dimensions
        view_name = self.view_name
        
        ren_win = self.GetInteractor().GetRenderWindow()
        renderer = ren_win.GetRenderers().GetFirstRenderer()

        # 1. Convert Display Coords to World Coords (Inverse Transform)
        renderer.SetDisplayPoint(display_pos[0], display_pos[1], 0)
        renderer.DisplayToWorld()
        world_pos = renderer.GetWorldPoint()

        if not all(math.isfinite(coord) for coord in world_pos):
            return
            
        # 2. Map World Coordinates to Voxel Indices
        new_x, new_y, new_z = (self.parent.current_slice['sagittal'], 
                               self.parent.current_slice['coronal'], 
                               self.parent.current_slice['axial'])

        if view_name == 'axial':
            new_x = int(math.floor(world_pos[0]))
            new_y = int(math.floor(world_pos[1]))
        elif view_name == 'coronal':
            new_x = int(math.floor(world_pos[0]))
            new_z = int(math.floor(world_pos[1]))
        elif view_name == 'sagittal':
            new_y = int(math.floor(world_pos[0]))
            new_z = int(math.floor(world_pos[1]))
        
        # 3. Apply Bounds Checking
        new_x = max(0, min(new_x, W - 1))
        new_y = max(0, min(new_y, H - 1))
        new_z = max(0, min(new_z, D - 1))
        
        # 4. CRITICAL FIX: Block Signals
        self.parent.sagittal_slider.blockSignals(True)
        self.parent.coronal_slider.blockSignals(True)
        self.parent.axial_slider.blockSignals(True)

        # 5. Update and Unblock
        self.parent.sagittal_slider.setValue(new_x)
        self.parent.coronal_slider.setValue(new_y)
        self.parent.axial_slider.setValue(new_z)

        self.parent.sagittal_slider.blockSignals(False)
        self.parent.coronal_slider.blockSignals(False)
        self.parent.axial_slider.blockSignals(False)

        # 6. Manually trigger the single update
        self.parent.update_2d_views()
        self.parent.statusBar().showMessage(f"Navigated to X:{new_x}, Y:{new_y}, Z:{new_z}")
    
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