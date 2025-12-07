MAIN_STYLE = """
QWidget {
    background-color: #1b1b1b;
    color: #E8E8E8;
    font: 9pt "Segoe UI";
}

/* Left panel scroll area */
QScrollArea#left_panel_scroll {
    background-color: transparent;
    border: none;
}

QPushButton {
    background-color: #2f2f33;
    border: 1px solid #3d3d42;
    padding: 5px 8px;
    border-radius: 6px;
    text-align: left;
}
QPushButton:hover {
    background-color: #38383d;
}

QGroupBox {
    font-weight: 600;
    border: 1px solid #2e2e33;
    border-radius: 6px;
    margin-top: 8px;
    padding: 6px 8px 8px 8px;
    background-color: #212125;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 8px;
    padding: 0 4px;
    color: #8FD14F;
    font-size: 9pt;
}

QLabel {
    color: #dcdcdc;
    font-size: 9pt;
}

QCheckBox {
    padding: 2px 0;
}

/* Sliders: thinner groove and compact handle */
QSlider::groove:horizontal {
    background: #333;
    height: 5px;
    border-radius: 3px;
}
QSlider::handle:horizontal {
    background: #6FC3A6;
    width: 12px;
    margin: -4px 0;
    border-radius: 6px;
}
QSlider::groove:vertical {
    background: #333;
    width: 5px;
    border-radius: 3px;
}
QSlider::handle:vertical {
    background: #6FC3A6;
    height: 12px;
    margin: 0 -4px;
    border-radius: 6px;
}

QSpinBox, QDoubleSpinBox, QComboBox {
    background-color: #232327;
    border: 1px solid #2f2f33;
    padding: 4px;
    border-radius: 4px;
    min-height: 22px;
}

/* Tweak group spacing for denser layout */
QGroupBox QWidget { margin-top: 4px; }

/* Subtle separators for clarity */
QGroupBox::indicator { margin-left: 6px; }

/* Make tooltips easier to read */
QToolTip { background-color: #2b2b2b; color: #fff; border: 1px solid #555; }
"""