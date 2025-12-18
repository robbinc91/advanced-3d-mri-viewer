from PyQt5.QtWidgets import (QApplication, QMessageBox)
from src.mri_viewer import MRIViewer
import sys
from src.utils.check_imports import *
import traceback

if __name__ == '__main__':
    def excepthook(exc_type, exc_value, exc_tb):
        tb = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
        print("Error details:", tb)
        QMessageBox.critical(None, "Fatal Error", f"An unhandled error occurred: {exc_value}\n\nSee console for details.")
        sys.exit(1)
        
    sys.excepthook = excepthook

    app = QApplication(sys.argv)
    if not VTK_AVAILABLE:
        QMessageBox.critical(None, "Error", "VTK is not properly installed or configured.")
        sys.exit(1)

    if not NIBABEL_AVAILABLE:
        print("WARNING: NiBabel not found. File loading/saving will be disabled.")
    
    if not SIMPLEITK_AVAILABLE:
        print("WARNING: SimpleITK not found. N4 Bias Field Correction will be disabled.")

    viewer = MRIViewer()
    viewer.show()
    sys.exit(app.exec_())