from PyQt5.QtCore import QThread, pyqtSignal
import threading
import numpy as np
import os

class ExportWorker(QThread):
    """Background worker to generate PDF exports without blocking UI.

    Runs in a separate thread and emits `finished(success, message)` when done.
    """
    finished = pyqtSignal(bool, str)
    progress = pyqtSignal(int, str)

    def __init__(self, viewer, filepath, volume_results):
        super().__init__()
        self.viewer = viewer
        self.filepath = filepath
        self.volume_results = volume_results
        self._cancel_event = threading.Event()

    def run(self):
        temp_images = []
        try:
            from reportlab.lib.pagesizes import letter
            from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
            from reportlab.lib.styles import getSampleStyleSheet
            from reportlab.lib import colors
            from PIL import Image as PILImage
            import matplotlib.pyplot as plt
            import math, uuid

            document = SimpleDocTemplate(self.filepath, pagesize=letter)
            styles = getSampleStyleSheet()
            story = []

            story.append(Paragraph("NeuroView MRI Volume Report", styles['Title']))
            story.append(Paragraph(f"<b>Source File:</b> {self.viewer.fileName or 'N/A'}", styles['Normal']))
            story.append(Paragraph(f"<b>Mask Configuration:</b> {self.viewer.label_config_path}", styles['Normal']))
            story.append(Spacer(1, 12))

            # 2D slices (central thumbnails)
            story.append(Paragraph("<b>2D Slices with Segmentation Mask Overlay</b>", styles['Heading2']))
            central_thumbs = []
            montages = []

            def _make_montage(items, thumb_w=300, thumb_h=300, cols=4, max_slices=15):
                # Sample items if too many
                n = len(items)
                if n == 0:
                    return None
                if n > max_slices:
                    indices = np.linspace(0, n - 1, max_slices, dtype=int)
                    items = [items[i] for i in indices]

                imgs = []
                for it in items:
                    try:
                        if isinstance(it, str):
                            im = PILImage.open(it).convert('RGB')
                        else:
                            im = PILImage.fromarray(it)
                        im.thumbnail((thumb_w, thumb_h), PILImage.LANCZOS)
                        bg = PILImage.new('RGB', (thumb_w, thumb_h), (255, 255, 255))
                        offset = ((thumb_w - im.width) // 2, (thumb_h - im.height) // 2)
                        bg.paste(im, offset)
                        imgs.append(bg)
                    except Exception:
                        continue

                if not imgs:
                    return None

                cols = min(cols, len(imgs))
                rows = math.ceil(len(imgs) / cols)
                montage = PILImage.new('RGB', (cols * thumb_w, rows * thumb_h), (255, 255, 255))
                for idx, im in enumerate(imgs):
                    r = idx // cols
                    c = idx % cols
                    montage.paste(im, (c * thumb_w, r * thumb_h))

                temp_path = os.path.join(tempfile.gettempdir(), f"montage_{uuid.uuid4().hex}.png")
                montage.save(temp_path)
                return temp_path

            for view in ['axial', 'coronal', 'sagittal']:
                if self._cancel_event.is_set():
                    self.finished.emit(False, "Export canceled by user")
                    return
                # central thumbnail
                central = self.viewer._create_2d_slice_snapshot(view, size=(200, 200))
                if isinstance(central, list):
                    pick = central[len(central) // 2]
                    if isinstance(pick, np.ndarray):
                        tmp = os.path.join(tempfile.gettempdir(), f"slice_tmp_{view}.png")
                        plt.imsave(tmp, pick)
                        temp_images.append(tmp)
                        central_thumbs.append(Image(tmp, width=150, height=150))
                    else:
                        temp_images.append(pick)
                        central_thumbs.append(Image(pick, width=150, height=150))
                elif isinstance(central, np.ndarray):
                    tmp = os.path.join(tempfile.gettempdir(), f"slice_tmp_{view}.png")
                    plt.imsave(tmp, central)
                    temp_images.append(tmp)
                    central_thumbs.append(Image(tmp, width=150, height=150))
                elif central:
                    temp_images.append(central)
                    central_thumbs.append(Image(central, width=150, height=150))

                # all-slices montage (prefer file paths)
                try:
                    all_res = _create_2d_slice_snapshot_mpl(self.viewer, view, size=(400, 400), all_slices=True, return_arrays=False)
                except Exception:
                    all_res = None

                if all_res:
                    # emit progress after collecting all-slices result for this axis
                    try:
                        self.progress.emit(20, f"Built all-slices for {view}")
                    except Exception:
                        pass
                    if isinstance(all_res, list):
                        montage_path = _make_montage(all_res, thumb_w=300, thumb_h=300, cols=4, max_slices=15)
                        if montage_path:
                            temp_images.append(montage_path)
                            montages.append((view, Image(montage_path, width=400, height=400)))
                    elif isinstance(all_res, np.ndarray):
                        tmp = os.path.join(tempfile.gettempdir(), f"slice_all_{view}.png")
                        plt.imsave(tmp, all_res)
                        temp_images.append(tmp)
                        montages.append((view, Image(tmp, width=400, height=400)))

            if central_thumbs:
                try:
                    self.progress.emit(60, "Added central thumbnails")
                except Exception:
                    pass
                story.append(Table([[Paragraph("Axial", styles['Code']), Paragraph("Coronal", styles['Code']), Paragraph("Sagittal", styles['Code'])], central_thumbs]))
                story.append(Spacer(1, 12))

            if montages:
                story.append(Paragraph("<b>All Slices Montages (per axis)</b>", styles['Heading2']))
                for view_name, img_obj in montages:
                    story.append(Paragraph(view_name.capitalize(), styles['Heading3']))
                    story.append(Table([[img_obj]]))
                    story.append(Spacer(1, 12))

            # 3D views and tables (reuse viewer logic) -- keep same as before
            if self.viewer.mask_data is not None:
                story.append(Paragraph("<b>3D Model: All Segmented Labels</b>", styles['Heading2']))
                all_3d_images = []
                for i in range(3):
                    path = self.viewer._create_3d_snapshot(label_value=None, angle_index=i, size=(200, 200))
                    if path:
                        temp_images.append(path)
                        all_3d_images.append(Image(path, width=150, height=150))

                if all_3d_images:
                    story.append(Table([all_3d_images]))
                    story.append(Spacer(1, 12))
                    try:
                        self.progress.emit(75, "Rendered 3D overview images")
                    except Exception:
                        pass

            story.append(Paragraph("<b>Volumetric Analysis Table</b>", styles['Heading2']))
            table_data = [["Label Name", "Volume (cm³)", "Volume (mm³)"]]
            for name, vol_cm3 in self.volume_results.items():
                vol_mm3 = vol_cm3 * 1000.0
                table_data.append([name, f"{vol_cm3:.3f}", f"{vol_mm3:.1f}"])

            table = Table(table_data)
            table.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, 0), colors.grey), ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke), ('ALIGN', (0, 0), (-1, -1), 'LEFT'), ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'), ('BOTTOMPADDING', (0, 0), (-1, 0), 12), ('BACKGROUND', (0, 1), (-1, -1), colors.beige), ('GRID', (0, 0), (-1, -1), 1, colors.black)]))
            story.append(table)
            story.append(Spacer(1, 12))

            if self.viewer.mask_data is not None and len(self.volume_results) > 0:
                story.append(Paragraph("<b>3D Models: Individual Labels</b>", styles['Heading2']))
                for label_val in self.viewer.label_map.keys():
                    if label_val in [0] or not (self.viewer.mask_data == label_val).any():
                        continue
                    label_name = self.viewer.label_map.get(label_val, f"Label_{label_val}")
                    story.append(Paragraph(f"<b>{label_name}</b>", styles['Heading3']))
                    individual_3d_images = []
                    for i in range(3):
                        path = self.viewer._create_3d_snapshot(label_val, angle_index=i, size=(150, 150))
                        if path:
                            temp_images.append(path)
                            individual_3d_images.append(Image(path, width=100, height=100))
                    if individual_3d_images:
                        story.append(Table([individual_3d_images]))
                        story.append(Spacer(1, 6))
                        try:
                            self.progress.emit(90, f"Added 3D images for {label_name}")
                        except Exception:
                            pass

            if self._cancel_event.is_set():
                self.finished.emit(False, "Export canceled by user")
                return
            document.build(story)
            self.progress.emit(100, "Finalizing PDF")
            self.finished.emit(True, f"Report successfully exported to {self.filepath}")

        except ImportError as ie:
            self.finished.emit(False, "PDF Library (reportlab) or Pillow not found. Please install required packages.")
        except Exception as e:
            self.finished.emit(False, f"An error occurred during PDF generation: {e}")
        finally:
            for path in temp_images:
                if os.path.exists(path):
                    try:
                        os.remove(path)
                    except OSError:
                        pass