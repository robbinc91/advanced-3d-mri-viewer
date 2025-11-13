MAIN_STYLE = """
QWidget { 
    background-color: #222; 
    color: #EAEAEA; 
    font: 10pt "Segoe UI"; 
}
QPushButton { 
    background-color: #3A3A3A; 
    border: 1px solid #555; 
    padding: 6px; 
    border-radius: 4px; 
}
QPushButton:hover { 
    background-color: #484848; 
}
QGroupBox {
    font-weight: bold;
    border: 1px solid #555;
    border-radius: 5px;
    margin-top: 10px;
    padding-top: 10px;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 5px 0 5px;
}
QSlider::groove:horizontal {
    background: #3A3A3A;
    height: 4px;
    border-radius: 2px;
}
QSlider::handle:horizontal {
    background: #CACACA;
    width: 16px;
    margin: -6px 0;
    border-radius: 8px;
}
QSlider::groove:vertical {
    background: #3A3A3A;
    width: 4px;
    border-radius: 2px;
}
QSlider::handle:vertical {
    background: #CACACA;
    height: 16px;
    margin: 0 -6px;
    border-radius: 8px;
}
"""