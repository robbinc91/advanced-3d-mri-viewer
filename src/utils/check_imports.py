# 1. VTK
try:
    import vtk
    from vtkmodules.qt.QVTKRenderWindowInteractor import QVTKRenderWindowInteractor
    VTK_AVAILABLE = True
except ImportError as e:
    print(f"VTK import error: {e}")
    VTK_AVAILABLE = False

# 2. NiBabel (IO)
try:
    import nibabel as nib
    NIBABEL_AVAILABLE = True
except ImportError:
    print("NiBabel not available. Install with: pip install nibabel")
    NIBABEL_AVAILABLE = False

# 3. Scikit-Image & Scipy (Advanced Processing)
try:
    from skimage import exposure, filters, morphology, restoration, util
    from scipy import ndimage
    SKIMAGE_AVAILABLE = True
except ImportError:
    print("Scikit-Image/Scipy not available. Advanced features disabled. Install: pip install scikit-image scipy")
    SKIMAGE_AVAILABLE = False

# 4. SimpleITK (N4 Bias Field Correction)
try:
    import SimpleITK as sitk
    SIMPLEITK_AVAILABLE = True
except ImportError:
    print("SimpleITK not available. N4 Bias Correction disabled. Install: pip install SimpleITK")
    SIMPLEITK_AVAILABLE = False