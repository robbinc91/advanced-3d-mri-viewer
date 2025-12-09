import matplotlib.pyplot as plt
import matplotlib
import os
import tempfile
import numpy as np
# Note: Ensure 'matplotlib' is installed for this to work.

def _create_2d_slice_snapshot_mpl(self, view_name, size=(300, 300)):
    """
    Generates a 2D snapshot using Matplotlib, avoiding np.nan for stability.
    Returns the path to the saved PNG image.
    """
    if self.mri_data is None: return None

    indices = self._get_representative_slice_index()
    z, y, x = indices['axial'], indices['coronal'], indices['sagittal']
    
    # 1. Extract the slices (using transpose/swapaxes to correct orientation)
    if view_name == 'axial':
        mri_slice = self.mri_data[z, :, :]
        mask_slice = self.mask_data[z, :, :] if self.mask_data is not None else None
    elif view_name == 'coronal':
        # Y-slice (D, H, W) -> D, W. Transpose for correct vertical orientation.
        mri_slice = self.mri_data[:, y, :].T 
        mask_slice = self.mask_data[:, y, :].T if self.mask_data is not None else None
    elif view_name == 'sagittal':
        # X-slice (D, H, W) -> D, H. Transpose for correct vertical orientation.
        mri_slice = self.mri_data[:, :, x].T 
        mask_slice = self.mask_data[:, :, x].T if self.mask_data is not None else None

    # 2. Setup Plot
    # Convert pixels to inches (assuming 100 dpi scaling)
    fig, ax = plt.subplots(figsize=(size[0] / 100, size[1] / 100), dpi=100) 
    
    # Ensure no padding, labels, or axes
    ax.axis('off')
    fig.subplots_adjust(left=0, right=1, top=1, bottom=0)

    # 3. Plot MRI Data
    # Use 'gray' colormap and find appropriate vmin/vmax for scaling
    ax.imshow(mri_slice, cmap='gray', vmin=np.min(mri_slice), vmax=np.max(mri_slice))

    # 4. Plot Mask Overlay (Using full import name matplotlib.colors)
    if mask_slice is not None:
        
        unique_labels = np.unique(mask_slice[mask_slice != 0])
        num_labels = len(unique_labels)
        
        # Use a list of distinct colors (e.g., from the 'tab10' colormap, max 10 labels)
        base_colors = plt.cm.get_cmap('tab10')
        
        # 4a. Create the list of colors: Index 0 must be transparent
        cmap_list = [(0.0, 0.0, 0.0, 0.0)] # Index 0: Fully transparent (R, G, B, A)
        
        # Generate colors for labels 1, 2, 3...
        for i, label in enumerate(unique_labels):
            # Get a distinct color from the base colormap and set opacity to 0.6
            r, g, b, _ = base_colors(i % 10) 
            cmap_list.append((r, g, b, 0.6))
        
        # Use the correct full name for the import
        new_cmap = matplotlib.colors.ListedColormap(cmap_list) 
        
        # 4b. Use Boundary Norm for discrete coloring
        # The bounds must be set for N+1 discrete colors (N labels + 1 background)
        bounds = np.arange(num_labels + 2) - 0.5 
        # Use the correct full name for the import
        norm = matplotlib.colors.BoundaryNorm(bounds, new_cmap.N) 
        
        # 4c. Plot the mask over the MRI. 
        ax.imshow(mask_slice, cmap=new_cmap, norm=norm, interpolation='nearest')

    # 5. Save Snapshot
    temp_path = os.path.join(tempfile.gettempdir(), f"slice_mpl_{view_name}.png")
    fig.savefig(temp_path, format='png', dpi=100, bbox_inches='tight', pad_inches=0)
    plt.close(fig) # Crucial for releasing memory
    
    return temp_path



import pyvista as pv
from skimage.measure import marching_cubes
import os
import tempfile
import numpy as np

def _create_3d_snapshot_pv(self, label_value=None, angle_index=0, size=(400, 400)):
    # ... (Bounding Box calculation, same as the last VTK version) ...

    # Setup the PyVista Plotter for off-screen rendering
    pl = pv.Plotter(off_screen=True, window_size=size)
    pl.set_background('black')

    # ... (Labels to render logic) ...
    
    for current_label_value in labels_to_render:
        
        # ... (Bounding Box calculation and cropping) ...
        # Ensure you have 'min_x', 'min_y', 'min_z' for translation
        
        # 1. Mesh Generation using Scikit-image (D, H, W order)
        try:
            verts, faces, normals, values = marching_cubes(cropped_data, level=0.5)
        except ValueError:
            # Handle cases where no surface is found (empty label)
            continue
            
        # 2. Create PyVista mesh
        # PyVista/VTK uses a slightly different face format, so adjust
        faces_pyvista = np.concatenate([np.full((faces.shape[0], 1), 3), faces], axis=1).flatten()
        mesh = pv.PolyData(verts, faces_pyvista)
        
        # 3. Apply Transform/Translation
        # Vertices are currently at the origin (0,0,0) of the cropped volume
        mesh.translate([min_x, min_y, min_z], inplace=True)

        # 4. Set Color (Golden Ratio approach for distinct colors)
        hue = (current_label_value * 0.6180339887) % 1.0 
        
        # PyVista uses 0-1 RGB
        # Use an external library or custom function to map hue to RGB (e.g., skimage.color.hsv2rgb)
        # For simplicity, we'll assign a basic PyVista color:
        colors = ['red', 'lime', 'blue', 'yellow', 'cyan', 'magenta']
        color = colors[(current_label_value - 1) % len(colors)]
        
        # 5. Add mesh to plotter
        pl.add_mesh(mesh, color=color, opacity=0.9, smooth_shading=True)

    # 6. Camera Setup
    pl.camera_position = pl.show(reset_camera=True, auto_close=False, return_viewer=True).camera_position
    
    # Apply specific angle transform (Azimuth, Elevation)
    az, el, roll = angles[angle_index % 3] # angles from the original code
    pl.camera.azimuth = az
    pl.camera.elevation = el
    
    # 7. Snapshot and Cleanup
    temp_path = os.path.join(tempfile.gettempdir(), f"3d_pv_{label_value or 'all'}_{angle_index}.png")
    pl.screenshot(temp_path)
    pl.close()
    
    return temp_path



def _create_2d_slice_snapshot(self, view_name, size=(300, 300)):
        """
        Generates a 2D snapshot of the specified central slice with mask overlay
        using vtkImageReslice to ensure orientation is correctly handled.
        Returns the path to the saved PNG image.
        """
        if self.mri_data is None: return None

        indices = self._get_representative_slice_index()
        z_idx, y_idx, x_idx = indices['axial'], indices['coronal'], indices['sagittal']
        
        # 1. Setup Off-Screen Renderer
        renderWindow = vtk.vtkRenderWindow()
        renderWindow.SetOffScreenRendering(1)
        renderWindow.SetSize(size)
        renderer = vtk.vtkRenderer()
        renderWindow.AddRenderer(renderer)
        
        # 2. Base Importer for MRI Data
        importer = vtk.vtkImageImport()
        mri_data_contiguous = self.mri_data.copy()
        importer.SetImportVoidPointer(mri_data_contiguous, mri_data_contiguous.nbytes)
        importer.SetDataScalarTypeToFloat()
        importer.SetNumberOfScalarComponents(1)
        # Note: Assuming VTK input order X, Y, Z (W, H, D in numpy shape)
        importer.SetDataExtent(0, self.mri_data.shape[2] - 1, 
                               0, self.mri_data.shape[1] - 1, 
                               0, self.mri_data.shape[0] - 1)
        importer.SetWholeExtent(importer.GetDataExtent())
        importer.Update()
        
        # 3. Setup Reslice Transformation Matrix
        # This matrix defines the coordinate system of the slice plane.
        matrix = vtk.vtkMatrix4x4()
        matrix.Identity() 

        # The reslicer extracts a single slice from the new Z=0 plane (default).
        # We manipulate the matrix's translation component (column 3) to select the desired slice index.
        
        if view_name == 'axial':
            # Axial (Z-slice). Keep X, Y, Z axes, just translate Z to the desired slice index.
            matrix.SetElement(2, 3, z_idx) 
        
        elif view_name == 'coronal':
            # Coronal (Y-slice). Map X -> X, Z -> -Y, Y -> Z.
            matrix.SetElement(1, 1, 0)
            matrix.SetElement(1, 2, -1)  # Z-axis becomes the negative Y-axis of the slice
            matrix.SetElement(2, 1, 1)   # Y-axis becomes the Z-axis of the slice
            matrix.SetElement(2, 3, y_idx) # Translate along the new Z-axis (which was Y)
            
        elif view_name == 'sagittal':
            # Sagittal (X-slice). Map Y -> X, X -> -Y, Z -> Z.
            matrix.SetElement(0, 0, 0)
            matrix.SetElement(0, 1, 1)   # Y-axis becomes the X-axis of the slice
            matrix.SetElement(1, 0, -1)  # X-axis becomes the negative Y-axis of the slice
            matrix.SetElement(2, 3, x_idx) # Translate along the new Z-axis (which was X)

        # 4. Apply Reslice Filter to MRI Data
        reslice_mri = vtk.vtkImageReslice()
        reslice_mri.SetInputConnection(importer.GetOutputPort())
        reslice_mri.SetResliceAxes(matrix)
        reslice_mri.SetOutputDimensionality(2) # Ensures we get a 2D plane
        reslice_mri.Update()
        
        # 5. Add MRI Slice Actor
        slice_actor = vtk.vtkImageActor()
        slice_actor.GetMapper().SetInputConnection(reslice_mri.GetOutputPort())
        renderer.AddActor(slice_actor)
        
        # 6. Handle Mask Overlay
        if self.mask_data is not None:
            # Re-run the reslice with the mask data
            mask_importer = vtk.vtkImageImport()
            mask_data_contiguous = self.mask_data.copy()
            mask_importer.SetImportVoidPointer(mask_data_contiguous, mask_data_contiguous.nbytes)
            mask_importer.SetDataScalarTypeToUnsignedShort()
            mask_importer.SetNumberOfScalarComponents(1)
            mask_importer.SetDataExtent(importer.GetDataExtent())
            mask_importer.SetWholeExtent(importer.GetDataExtent())
            mask_importer.Update()
            
            # Apply Reslice Filter to Mask Data (using the same matrix)
            reslice_mask = vtk.vtkImageReslice()
            reslice_mask.SetInputConnection(mask_importer.GetOutputPort())
            reslice_mask.SetResliceAxes(matrix)
            reslice_mask.SetOutputDimensionality(2)
            reslice_mask.Update()
            
            # Color the mask data
            mask_lut = vtk.vtkLookupTable()
            mask_lut.SetNumberOfTableValues(256)
            mask_lut.Build()
            mask_lut.SetTableValue(1, 1.0, 0.0, 0.0, 0.6)
            mask_lut.SetTableValue(2, 0.0, 1.0, 0.0, 0.6)
            mask_lut.SetTableValue(3, 0.0, 0.0, 1.0, 0.6)

            mask_colorer = vtk.vtkImageMapToColors()
            mask_colorer.SetInputConnection(reslice_mask.GetOutputPort()) # Use reslice output
            mask_colorer.SetLookupTable(mask_lut)
            mask_colorer.PassAlphaToOutputOn()
            
            # Add Mask Actor (using vtkImageSlice for alpha blending)
            mask_mapper = vtk.vtkImageSliceMapper()
            mask_mapper.SetInputConnection(mask_colorer.GetOutputPort())
            mask_actor = vtk.vtkImageSlice()
            mask_actor.SetMapper(mask_mapper)
            renderer.AddActor(mask_actor)


        # 7. Finalize Camera and Snapshot
        renderer.ResetCamera()
        renderer.Render()
        
        w2if = vtk.vtkWindowToImageFilter()
        w2if.SetInput(renderWindow)
        w2if.Update()

        temp_path = os.path.join(tempfile.gettempdir(), f"slice_{view_name}.png")
        writer = vtk.vtkPNGWriter()
        writer.SetFileName(temp_path)
        writer.SetInputConnection(w2if.GetOutputPort())
        writer.Write()
        
        # Clean up
        renderer.RemoveAllViewProps()
        renderWindow.Finalize()
        del renderWindow, renderer, w2if, writer
        
        return temp_path

def _create_3d_snapshot(self, label_value=None, angle_index=0, size=(400, 400)):
    """
    Generates a 3D snapshot from a specific angle.
    label_value=None renders all labels.
    angle_index (0, 1, 2) corresponds to a different camera view.
    Returns the path to the saved PNG image.
    """
    if self.mask_data is None: return None

    # 1. Setup Off-Screen Renderer
    renderWindow = vtk.vtkRenderWindow()
    renderWindow.SetOffScreenRendering(1)
    renderWindow.SetSize(size)
    renderer = vtk.vtkRenderer()
    renderWindow.AddRenderer(renderer)
    renderer.SetBackground(0.0, 0.0, 0.0) # Black background

    # 2. Filter Mask Data for Label (if specified)
    if label_value is not None:
        # Create a binary array where only the target label is 1
        data_to_render = (self.mask_data == label_value).astype(np.float32)
    else:
        # Render all labels (using the mask data itself, converted to float)
        data_to_render = self.mask_data.astype(np.float32)
        
    # --- FIX: Ensure Contiguity for the data being passed to Marching Cubes ---
    data_to_render_contiguous = data_to_render.copy()
    # --------------------------------------------------------------------------

    # 3. VTK Pipeline (Marching Cubes for Surface)
    importer = vtk.vtkImageImport()
    importer.SetDataScalarTypeToFloat()
    importer.SetNumberOfScalarComponents(1)
    
    # Use the contiguous copy
    importer.SetImportVoidPointer(data_to_render_contiguous, data_to_render_contiguous.nbytes)
    
    importer.SetDataExtent(0, data_to_render.shape[2] - 1, 
                            0, data_to_render.shape[1] - 1, 
                            0, data_to_render.shape[0] - 1)
    importer.SetWholeExtent(importer.GetDataExtent())
    importer.Update()
    
    # ... (rest of the VTK pipeline remains the same) ...
    
    # Use Marching Cubes to extract the surface
    mc = vtk.vtkMarchingCubes()
    mc.SetInputConnection(importer.GetOutputPort())
    mc.SetValue(0, 0.5) # Isosurface at 0.5 (separating 0 from 1)
    
    # Smoother appearance
    smoother = vtk.vtkSmoothPolyDataFilter()
    smoother.SetInputConnection(mc.GetOutputPort())
    smoother.SetNumberOfIterations(10)
    
    # Mapper and Actor
    mapper = vtk.vtkPolyDataMapper()
    mapper.SetInputConnection(smoother.GetOutputPort())
    
    actor = vtk.vtkActor()
    actor.SetMapper(mapper)
    
    # Set color based on label (e.g., green for all/unknown, specific color for individual)
    if label_value is None:
        actor.GetProperty().SetColor(0.2, 0.8, 0.2) # Light Green for All
    else:
        # Simple color mapping for individual labels
        hue = (label_value * 0.6180339887) % 1.0 # Golden ratio color
        color = vtk.vtkColorTransferFunction()
        color.AddRGBPoint(0.0, 1.0, 1.0, 1.0)
        color.AddRGBPoint(1.0, hue, 1.0 - hue, 0.5)
        r, g, b = color.GetColor(1.0)
        actor.GetProperty().SetColor(r, g, b)
        
    renderer.AddActor(actor)

    # 4. Camera Setup
    renderer.ResetCamera()
    camera = renderer.GetActiveCamera()
    
    # Define 3 distinct viewing angles
    angles = [
        (0, 0, 0),        # Front View
        (45, 15, 0),      # Oblique Top-Right View
        (90, 0, 0),       # Left Profile View
    ]
    
    az, el, roll = angles[angle_index % 3]
    camera.Azimuth(az)
    camera.Elevation(el)
    camera.Roll(roll)
    renderer.ResetCameraClippingRange()
    renderer.Render()

    # 5. Snapshot and Cleanup
    w2if = vtk.vtkWindowToImageFilter()
    w2if.SetInput(renderWindow)
    w2if.Update()

    temp_path = os.path.join(tempfile.gettempdir(), f"3d_{label_value or 'all'}_{angle_index}.png")
    writer = vtk.vtkPNGWriter()
    writer.SetFileName(temp_path)
    writer.SetInputConnection(w2if.GetOutputPort())
    writer.Write()
    
    renderer.RemoveAllViewProps()
    renderWindow.Finalize()
    del renderWindow, renderer, w2if, writer
    
    return temp_path