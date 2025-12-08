QSS_THEME = """
/* --- General Colors and Font --- */
QMainWindow, QWidget {
    background-color: #000000; /* Black body background */
    color: #E5E5E5; /* Light text */
    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    font-size: 10pt;
}

/* --- Sidebar Styling (neutral-900) --- */
/* Apply this style to the main left-hand widget/panel */
#leftPanel { 
    background-color: #171717; /* Very dark gray for sidebar */
    border-right: 1px solid #262626; /* neutral-800 border */
}

/* --- Group Boxes (Sections) --- */
QGroupBox {
    border: 1px solid #262626; /* Subtle border */
    margin-top: 20px;
    padding-top: 15px;
    padding-bottom: 5px;
    font-weight: bold;
    color: #94A3B8; /* Slate-400 for section headers */
}
QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 0 3px;
    background-color: #171717;
    margin-left: 10px;
}

/* --- Labels & Info --- */
QLabel {
    color: #E5E5E5;
}
/* Info panel box style (bg-neutral-800) */
#infoBox {
    background-color: #262626;
    border-radius: 4px;
    padding: 10px;
    color: #A3A3A3; /* neutral-400 */
}
#infoBox QLabel {
    color: #E5E5E5;
}

/* --- Buttons --- */
QPushButton {
    border: 1px solid #404040; /* darker border */
    border-radius: 4px;
    padding: 5px 10px;
    background-color: #262626; /* neutral-800 */
    color: #E5E5E5;
}
QPushButton:hover {
    background-color: #333333; /* slightly lighter on hover */
}
QPushButton:pressed {
    background-color: #404040;
}
QPushButton:disabled {
    background-color: #171717;
    color: #666666;
    border-color: #171717;
}
/* Primary Button Style (Load MRI - bg-sky-700) */
#btnLoadMRI {
    background-color: #0369A1; 
    border-color: #0EA5E9;
}
#btnLoadMRI:hover {
    background-color: #0EA5E9;
}


/* --- Dropdowns/Comboboxes (Select) --- */
QComboBox {
    border: 1px solid #262626;
    border-radius: 4px;
    padding: 4px;
    background-color: #262626;
    color: #E5E5E5;
}
QComboBox:hover {
    border: 1px solid #404040;
}
QComboBox QAbstractItemView {
    background-color: #262626;
    color: #E5E5E5;
    selection-background-color: #0EA5E9; /* Sky-500 accent */
}

/* --- Sliders (Range Input) --- */
QSlider::groove:horizontal {
    border: 0px;
    height: 4px;
    background: #404040; /* Dark track */
    border-radius: 2px;
}
QSlider::handle:horizontal {
    background: #0EA5E9; /* Sky-500 thumb */
    border: 0px;
    width: 16px;
    height: 16px;
    margin: -6px 0; /* center the thumb */
    border-radius: 8px;
}
QSlider::handle:horizontal:hover {
    background: #38BDF8; /* Sky-400 on hover */
}

/* --- SpinBoxes (Number Inputs) --- */
QSpinBox, QDoubleSpinBox {
    border: 1px solid #262626;
    border-radius: 4px;
    padding: 3px;
    background-color: #262626;
}
QSpinBox::up-button, QSpinBox::down-button {
    border-left: 1px solid #404040;
    width: 16px;
    background-color: #262626;
}
QSpinBox::up-button:hover, QSpinBox::down-button:hover {
    background-color: #404040;
}

/* --- Status Bar --- */
QStatusBar {
    background-color: #171717;
    border-top: 1px solid #262626;
}
"""

MAIN_STYLE = """
QWidget { 
    background-color: #222; 
    color: #EAEAEA; 
    font: 10pt "Segoe UI"; 
}
QPushButton { 
    background-color: #444; /* Slightly brighter button background */
    border: 1px solid #777; /* Higher contrast border */
    padding: 6px; 
    border-radius: 4px; 
    text-align: left; /* Aligns text/icons to the left */
}
QPushButton:hover { 
    background-color: #555; 
}
QGroupBox {
    font-weight: bold;
    border: 1px solid #777; /* Higher contrast border for visibility */
    border-radius: 5px;
    margin-top: 10px;
    padding-top: 10px;
    background-color: #2A2A2A; /* Subtle background for sections */
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 5px 0 5px;
    color: #B2FF00; /* Highlight group titles with a bright color */
}
QLabel {
    /* Ensure all labels, including instructions, are clearly visible */
    color: #CCC;
}
QCheckBox {
    padding: 3px 0;
}
QSlider::groove:horizontal {
    background: #555; /* Higher contrast groove */
    height: 6px; 
    border-radius: 3px;
}
QSlider::handle:horizontal {
    background: #B2FF00; /* Bright handle color */
    width: 16px;
    margin: -5px 0;
    border-radius: 8px;
}
QSlider::groove:vertical {
    background: #555;
    width: 6px;
    border-radius: 3px;
}
QSlider::handle:vertical {
    background: #B2FF00;
    height: 16px;
    margin: 0 -5px;
    border-radius: 8px;
}
"""