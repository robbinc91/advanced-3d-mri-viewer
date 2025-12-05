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