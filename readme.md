🧠 Advanced 3D MRI Viewer

![Screenshot](docs/screenshot.png)

⚠️ Project Status: Work in Progress ⚠️

This project is under active development. While core functionality is stable, please anticipate potential bugs, and note that features are subject to change. Contributions and feedback are warmly welcomed!

Overview

A cutting-edge, feature-rich medical imaging viewer built with Python, designed for visualizing 3D MRI volumetric data and corresponding segmentation masks. This application serves as an evolving, powerful platform for researchers, clinicians, and students to inspect and analyze NIfTI-formatted medical data.

Tech Stack Highlights:

VTK for high-performance 3D rendering and volumetric visualization.

PyQt5 for a sleek, modern, and intuitive graphical user interface.

NiBabel for robust NIfTI file handling.

✨ Key Features & Functionalities

This viewer is a comprehensive inspection tool packed with essential features for medical image analysis, categorized for easy reference:

🖼️ Core Visualization & Navigation

Four-Panel Layout: Simultaneous and linked viewing of 3D volumetric rendering alongside 2D Axial, Sagittal, and Coronal slices.

Crosshair Synchronization: A dynamic, yellow crosshair is drawn across the 2D slices to visually indicate the current position of the orthogonal viewing planes.

Slice Navigation: Smoothly navigate through slices using vertical sliders and the mouse wheel on any 2D view.

NIfTI File Support: Seamlessly load MRI and segmentation masks (.nii or .nii.gz formats).

🎨 Rendering & Display Controls

Colormap Selection: Easily switch between various volumetric and 2D slice color maps (e.g., Grayscale, Hot Metal, Bone) via a dedicated dropdown.

Window/Level Controls: Interactive sliders to adjust the contrast (Window) and brightness (Level) of the MRI image data for enhanced visual inspection.

Rendering Options: Toggle the 3D volume rendering mode for different visual effects (e.g., shading on/off).

🎭 Mask & Annotation Tools

Toggle Mask: Quickly show/hide the 3D mask actors and the 2D mask overlays.

Mask Opacity: Fine-tune the transparency of both the 3D mask and 2D overlays using a dedicated slider.

Annotations: Functionality to add, visualize, and clear simple point annotations in 3D and on the 2D slices.

⚙️ Image Processing & Filtering

Pre- and Post-Filtering: Apply standard image filters to the volumetric data before and after primary processing.

Filter Strength Adjustment: A spin box allows for precise control of filter parameters (e.g., sigma for Gaussian filtering).

Available Filters:

Denoising: Gaussian, Median, Bilateral, and Total Variation (TV) Denoising.

Morphology: Erosion, Dilation, Opening, and Closing operations.

💻 Utilities & UI

Dark UI: A polished, dark-themed user interface provides an optimal viewing environment for medical images.

Fullscreen Mode: Maximize any of the four views with a dedicated button; exit quickly with the Escape key shortcut.

Export Screenshot: Save the currently visible view (3D view by default, or active fullscreen) as a high-quality .png file.

🚀 Installation

Getting the viewer up and running is straightforward. Ensure you have Python 3.6+ installed and then use pip to install the required libraries:

pip install -r requirements.txt 


Roadmap

[ ] Measurement Tools: Implement tools for measuring distance, area, and angles in 2D views.

[ ] ROI Analysis: Add functionality to calculate statistics (e.g., mean intensity, volume) for segmented regions.

[ ] DICOM Support: Expand file support to include loading DICOM series.

[ ] UI Enhancements: Custom color maps for segmentations, dockable widgets, etc.