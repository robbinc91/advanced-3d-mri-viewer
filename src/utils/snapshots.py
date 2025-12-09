import matplotlib.pyplot as plt
import matplotlib
import os
import tempfile
import numpy as np
# Use the Agg backend canvas explicitly for off-screen rendering
from matplotlib.backends.backend_agg import FigureCanvasAgg
# Note: Ensure 'matplotlib' is installed for this to work.


def _create_2d_slice_snapshot_mpl(self, view_name, size=(300, 300), all_slices=True, return_arrays=False):
    """
    Generates a 2D snapshot using Matplotlib.

    By default (all_slices=False) this returns a single PNG path containing the
    representative (central) slice for `view_name` (keeps existing behavior).

    If `all_slices=True` the function will produce an array (or list of image
    paths) for every slice along the requested axis. Use `return_arrays=True`
    to get the images as a numpy array of RGB values instead of saved PNG
    files. The returned shape for arrays is (N, H, W, 3) with dtype uint8.

    Note: producing arrays for all slices can be memory heavy for large volumes.
    """
    if self.mri_data is None:
        return None

    D, H, W = self.mri_data.shape

    def render_slice_to_array(mri_slice, mask_slice=None):
        fig, ax = plt.subplots(figsize=(size[0] / 100, size[1] / 100), dpi=100)
        ax.axis('off')
        fig.subplots_adjust(left=0, right=1, top=1, bottom=0)

        # Plot base MRI slice
        mn, mx = np.min(mri_slice), np.max(mri_slice)
        if mn == mx:
            ax.imshow(mri_slice, cmap='gray')
        else:
            ax.imshow(mri_slice, cmap='gray', vmin=mn, vmax=mx)

        # Overlay mask if present
        if mask_slice is not None:
            unique_labels = np.unique(mask_slice[mask_slice != 0])
            base_colors = plt.cm.get_cmap('tab10')
            cmap_list = [(0.0, 0.0, 0.0, 0.0)]
            for i, label in enumerate(unique_labels):
                r, g, b, _ = base_colors(i % 10)
                cmap_list.append((r, g, b, 0.6))
            new_cmap = matplotlib.colors.ListedColormap(cmap_list)
            bounds = np.arange(len(unique_labels) + 2) - 0.5
            norm = matplotlib.colors.BoundaryNorm(bounds, new_cmap.N)
            ax.imshow(mask_slice, cmap=new_cmap, norm=norm, interpolation='nearest')

        # Draw canvas using Agg and capture as RGB numpy array. Using the
        # Agg canvas avoids backend-specific missing methods (e.g., when the
        # Qt backend is active the FigureCanvasQTAgg may not expose
        # `tostring_rgb`).
        canvas = FigureCanvasAgg(fig)
        # Use print_to_buffer which reliably returns an RGBA buffer and size
        buf, (w, h) = canvas.print_to_buffer()
        arr = np.frombuffer(buf, dtype=np.uint8).reshape((h, w, 4))
        # Drop alpha channel -> RGB
        img = arr[:, :, :3].copy()
        plt.close(fig)
        return img

    # If user requested all slices for a particular axis
    if all_slices:
        imgs = []
        if view_name == 'axial':
            for z in range(D):
                mri_slice = self.mri_data[z, :, :]
                mask_slice = self.mask_data[z, :, :] if self.mask_data is not None else None
                # Only include slices where the mask is present (non-zero)
                if self.mask_data is not None:
                    if mask_slice is None or not mask_slice.any():
                        continue
                imgs.append(render_slice_to_array(mri_slice, mask_slice))

        elif view_name == 'coronal':
            for y in range(H):
                mri_slice = self.mri_data[:, y, :].T
                mask_slice = self.mask_data[:, y, :].T if self.mask_data is not None else None
                if self.mask_data is not None:
                    if mask_slice is None or not mask_slice.any():
                        continue
                imgs.append(render_slice_to_array(mri_slice, mask_slice))

        elif view_name == 'sagittal':
            for x in range(W):
                mri_slice = self.mri_data[:, :, x].T
                mask_slice = self.mask_data[:, :, x].T if self.mask_data is not None else None
                if self.mask_data is not None:
                    if mask_slice is None or not mask_slice.any():
                        continue
                imgs.append(render_slice_to_array(mri_slice, mask_slice))

        if return_arrays:
            return np.stack(imgs, axis=0).astype(np.uint8)
        else:
            # Save temp files for each slice and return their paths
            paths = []
            for idx, img in enumerate(imgs):
                temp_path = os.path.join(tempfile.gettempdir(), f"slice_mpl_{view_name}_{idx}.png")
                plt.imsave(temp_path, img)
                paths.append(temp_path)
            return paths

    # Default behavior: single representative slice (central)
    indices = self._get_representative_slice_index()
    z, y, x = indices['axial'], indices['coronal'], indices['sagittal']

    if view_name == 'axial':
        mri_slice = self.mri_data[z, :, :]
        mask_slice = self.mask_data[z, :, :] if self.mask_data is not None else None
    elif view_name == 'coronal':
        mri_slice = self.mri_data[:, y, :].T
        mask_slice = self.mask_data[:, y, :].T if self.mask_data is not None else None
    elif view_name == 'sagittal':
        mri_slice = self.mri_data[:, :, x].T
        mask_slice = self.mask_data[:, :, x].T if self.mask_data is not None else None

    img = render_slice_to_array(mri_slice, mask_slice)
    temp_path = os.path.join(tempfile.gettempdir(), f"slice_mpl_{view_name}.png")
    plt.imsave(temp_path, img)
    return temp_path


def create_all_2d_slices(self, size=(300, 300), return_arrays=False):
    """
    Convenience helper: returns all slices for every axis.

    Returns a dict with keys `'axial'`, `'coronal'`, `'sagittal'` mapping to either
    lists of temp image paths (default) or stacked numpy arrays when
    `return_arrays=True`.
    """
    results = {}
    for view in ('axial', 'coronal', 'sagittal'):
        res = _create_2d_slice_snapshot_mpl(self, view, size=size, all_slices=True, return_arrays=return_arrays)
        results[view] = res
    return results



import pyvista as pv
from skimage.measure import marching_cubes
import os
import tempfile
import numpy as np

def _create_3d_snapshot_pv(self, label_value=None, angle_index=0, size=(400, 400)):
    """
    PyVista-based 3D snapshot helper.

    This module previously contained an incomplete PyVista implementation that
    referenced undefined variables (e.g. `labels_to_render`, `angles`,
    `cropped_data`, `min_x`/`min_y`/`min_z`). The repository already contains a
    working VTK-based implementation `_create_3d_snapshot` below. To avoid
    duplicated/unfinished logic and the NameError, use the VTK implementation
    as a reliable fallback.
    """
    # Pure PyVista implementation (no VTK usage).
    # Steps:
    #  - Determine labels to render
    #  - For each label, compute a tight bounding box and run marching_cubes on the
    #    cropped volume (faster and uses less memory)
    #  - Respect voxel spacing when creating meshes
    #  - Render off-screen and save screenshot
    if self.mask_data is None:
        return None

    # Determine voxel spacing (try mask header, then mri header, else default)
    spacing = (1.0, 1.0, 1.0)
    try:
        header = getattr(self, 'mask_header', None) or getattr(self, 'mri_header', None)
        if header is not None:
            zooms = header.get_zooms()[:3]
            if len(zooms) == 3:
                spacing = tuple(float(z) for z in zooms)
    except Exception:
        spacing = (1.0, 1.0, 1.0)

    # Decide which labels to render
    if label_value is None:
        unique = np.unique(self.mask_data)
        labels_to_render = unique[unique != 0]
    else:
        labels_to_render = [label_value]

    if len(labels_to_render) == 0:
        return None

    pl = pv.Plotter(off_screen=True, window_size=size)
    pl.set_background('black')

    cmap = plt.cm.get_cmap('tab10')

    D, H, W = self.mask_data.shape

    for i, current_label_value in enumerate(labels_to_render):
        # Create binary volume and skip empty labels
        mask_binary = (self.mask_data == int(current_label_value))
        if not mask_binary.any():
            continue

        # Compute bounding box of the label (z, y, x)
        nz = np.where(mask_binary)
        min_z, max_z = nz[0].min(), nz[0].max()
        min_y, max_y = nz[1].min(), nz[1].max()
        min_x, max_x = nz[2].min(), nz[2].max()

        # Add a one-voxel padding (clamp to volume)
        pad = 1
        min_z = max(0, min_z - pad)
        min_y = max(0, min_y - pad)
        min_x = max(0, min_x - pad)
        max_z = min(D - 1, max_z + pad)
        max_y = min(H - 1, max_y + pad)
        max_x = min(W - 1, max_x + pad)

        # Crop the binary volume to the bounding box
        cropped = mask_binary[min_z:max_z + 1, min_y:max_y + 1, min_x:max_x + 1].astype(np.uint8)

        # Run marching cubes on the cropped volume using spacing
        try:
            verts, faces, normals, values = marching_cubes(cropped, level=0.5, spacing=spacing)
        except Exception:
            continue

        # marching_cubes returns verts in (z,y,x) order; PyVista expects (x,y,z)
        verts = np.asarray(verts)
        # Add the offset (min indices * spacing) to move to global coordinates
        offset = np.array([min_z * spacing[0], min_y * spacing[1], min_x * spacing[2]])
        verts = verts + offset
        # Reorder to x,y,z
        verts = verts[:, [2, 1, 0]]

        # Convert faces to PyVista/VTK format (n_vertices, v0, v1, v2) flattened
        faces_pyvista = np.hstack([np.full((faces.shape[0], 1), 3, dtype=np.int64), faces]).astype(np.int64)
        faces_pyvista = faces_pyvista.flatten()

        mesh = pv.PolyData(verts, faces_pyvista)

        # Color selection via colormap for distinct labels
        r, g, b, _ = cmap(i % 10)
        pl.add_mesh(mesh, color=(r, g, b), opacity=0.9, smooth_shading=True)

    # Camera presets: XY (top), isometric, XZ (side)
    which = angle_index % 3
    if which == 0:
        pl.view_xy()
    elif which == 1:
        pl.view_isometric()
    else:
        pl.view_xz()

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