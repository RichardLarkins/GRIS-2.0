import os
import random
from pathlib import Path
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtWidgets import QFileDialog, QColorDialog

PANEL_BG = "#AEAEAE"
INPUT_BG = "#D0D0D0"
FONT_FAMILY = "Forum"

def get_3d_border(sunken=False, width=2):
    if sunken:
        return f"border-top: {width}px solid #606060; border-left: {width}px solid #606060; border-bottom: {width}px solid #E0E0E0; border-right: {width}px solid #E0E0E0;"
    return f"border-top: {width}px solid #E0E0E0; border-left: {width}px solid #E0E0E0; border-bottom: {width}px solid #606060; border-right: {width}px solid #606060;"

def get_btn_style():
    return f"""
        QPushButton {{
            background-color: {PANEL_BG};
            {get_3d_border(False, 2)}
            color: black;
            font-family: "{FONT_FAMILY}";
            font-weight: bold;
        }}
        QPushButton:hover {{ background-color: #00FF00; }}
        QPushButton:pressed {{ background-color: #00CC00; {get_3d_border(True, 2)} }}
    """

def get_checkbox_style():
    return f"""
        QCheckBox {{ color: black; font: bold 10pt '{FONT_FAMILY}'; outline: none; margin: 4px 0px; }}
        QCheckBox::indicator {{ 
            width: 14px; height: 14px; background-color: #D0D0D0; 
            border-top: 2px solid #606060; border-left: 2px solid #606060; 
            border-bottom: 2px solid #E0E0E0; border-right: 2px solid #E0E0E0; 
        }}
        QCheckBox::indicator:checked {{ background-color: #00FF00; }}
        QCheckBox::indicator:pressed {{ 
            background-color: #00CC00; 
            border-top: 2px solid #E0E0E0; border-left: 2px solid #E0E0E0; 
            border-bottom: 2px solid #606060; border-right: 2px solid #606060; 
        }}
    """

class DialogTitleBar(QtWidgets.QWidget):
    def __init__(self, parent, title="Dialog"):
        super().__init__(parent)
        self.parent_window = parent
        self.setFixedHeight(28)
        self.setAttribute(QtCore.Qt.WA_StyledBackground, True)
        self.setStyleSheet("background-color: transparent;")
        self.drag_pos = None
        
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(6, 0, 6, 0)
        
        self.title_label = QtWidgets.QLabel(title)
        self.title_label.setStyleSheet(f'color: black; font: 10pt "{FONT_FAMILY}"; font-weight: bold; border: none;')
        layout.addWidget(self.title_label)
        layout.addStretch()
        
        self.close_btn = QtWidgets.QPushButton("X")
        self.close_btn.setFixedSize(24, 24)
        self.close_btn.setCursor(QtCore.Qt.PointingHandCursor)
        self.close_btn.setStyleSheet(get_btn_style())
        layout.addWidget(self.close_btn)
        self.close_btn.clicked.connect(parent.reject)

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton: self.drag_pos = event.globalPos() - self.parent_window.frameGeometry().topLeft()
    def mouseMoveEvent(self, event):
        if self.drag_pos is not None and event.buttons() == QtCore.Qt.LeftButton: self.parent_window.move(event.globalPos() - self.drag_pos)
    def mouseReleaseEvent(self, event): self.drag_pos = None

class AISettingsDialog(QtWidgets.QDialog):
    def __init__(self, parent, target_object):
        super().__init__(parent)
        self.target = target_object
        self.setWindowFlags(QtCore.Qt.FramelessWindowHint | QtCore.Qt.Dialog)
        self.setStyleSheet(f"QDialog {{ background-color: {PANEL_BG}; {get_3d_border(False, 3)} }}")
        self.resize(450, 500)
        
        if getattr(self.target, 'ai_type', "None") == "None":
            self.target.ai_type = "DMNPC_TLEET_WDYMS"
            
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(6)
        
        self.title_bar = DialogTitleBar(self, "AI SETTINGS")
        layout.addWidget(self.title_bar)
        
        content_frame = QtWidgets.QFrame()
        content_frame.setStyleSheet(f"QFrame {{ background-color: #C0C0C0; {get_3d_border(True, 2)} }}")
        c_layout = QtWidgets.QVBoxLayout(content_frame)
        
        type_layout = QtWidgets.QHBoxLayout()
        lbl_type = QtWidgets.QLabel("AI Entity Type:")
        lbl_type.setStyleSheet(f"font: 11pt '{FONT_FAMILY}'; color: black;")
        self.combo_type = QtWidgets.QComboBox()
        self.combo_type.setStyleSheet(f"background-color: {INPUT_BG}; color: black; font: 10pt '{FONT_FAMILY}'; {get_3d_border(True, 1)}")
        self.combo_type.addItems(["FSKY_CAPTURE_CBSGY", "DMNPC_TLEET_WDYMS", "Siuef"])
        self.combo_type.setCurrentText(self.target.ai_type)
        self.combo_type.currentTextChanged.connect(self.on_type_changed)
        type_layout.addWidget(lbl_type)
        type_layout.addWidget(self.combo_type)
        c_layout.addLayout(type_layout)
        
        c_layout.addSpacing(10)
        
        self.stack = QtWidgets.QStackedWidget()
        self.page_fsky = self.build_fsky_page()
        self.page_dmnpc = self.build_dmnpc_page()
        self.page_sillycone = self.build_sillycone_page()
        
        self.stack.addWidget(self.page_fsky)
        self.stack.addWidget(self.page_dmnpc)
        self.stack.addWidget(self.page_sillycone)
        c_layout.addWidget(self.stack)
        
        layout.addWidget(content_frame)
        
        btn_apply = QtWidgets.QPushButton("APPLY TO ENTITY")
        btn_apply.setFixedHeight(35)
        btn_apply.setCursor(QtCore.Qt.PointingHandCursor)
        btn_apply.setStyleSheet(get_btn_style())
        btn_apply.clicked.connect(self.apply_settings)
        layout.addWidget(btn_apply)
        
        self.console_timer = QtCore.QTimer(self)
        self.console_timer.timeout.connect(self.update_console)
        self.console_timer.start(100)
        
        self.on_type_changed(self.target.ai_type)

    def create_sound_picker(self, label_text, config_key):
        layout = QtWidgets.QHBoxLayout()
        lbl = QtWidgets.QLabel(label_text)
        lbl.setStyleSheet(f"font: 10pt '{FONT_FAMILY}'; color: black;")
        path_input = QtWidgets.QLineEdit(self.target.ai_config.get(config_key, ""))
        path_input.setStyleSheet(f"background-color: {INPUT_BG}; color: black; {get_3d_border(True, 1)}")
        btn = QtWidgets.QPushButton("...")
        btn.setFixedSize(30, 24)
        btn.setStyleSheet(get_btn_style())
        btn.clicked.connect(lambda: self.pick_sound(path_input))
        layout.addWidget(lbl)
        layout.addWidget(path_input)
        layout.addWidget(btn)
        return layout, path_input

    def pick_sound(self, line_edit):
        path, _ = QFileDialog.getOpenFileName(self, "Select Sound", "", "Audio Files (*.wav *.mp3 *.ogg)")
        if path: line_edit.setText(path)

    def build_fsky_page(self):
        page = QtWidgets.QWidget()
        l = QtWidgets.QVBoxLayout(page)
        l.setContentsMargins(0,0,0,0)
        
        self.fsky_ignore_col = QtWidgets.QCheckBox("Ignore Brush Collision (Shortest Path)")
        self.fsky_ignore_col.setStyleSheet(get_checkbox_style())
        self.fsky_ignore_col.setCursor(QtCore.Qt.PointingHandCursor)
        self.fsky_ignore_col.setChecked(self.target.ai_config.get("fsky_ignore_col", False))
        l.addWidget(self.fsky_ignore_col)
        
        rad_l = QtWidgets.QHBoxLayout()
        rad_lbl = QtWidgets.QLabel("DMNPC Notice Radius:")
        rad_lbl.setStyleSheet(f"font: 10pt '{FONT_FAMILY}'; color: black;")
        self.fsky_radius = QtWidgets.QDoubleSpinBox()
        self.fsky_radius.setStyleSheet(f"background-color: {INPUT_BG}; color: black; {get_3d_border(True, 1)}")
        self.fsky_radius.setRange(1.0, 100.0)
        self.fsky_radius.setValue(self.target.ai_config.get("fsky_radius", 15.0))
        rad_l.addWidget(rad_lbl); rad_l.addWidget(self.fsky_radius)
        l.addLayout(rad_l)
        
        snd1, self.fsky_pass = self.create_sound_picker("Passive Cycle Sound:", "fsky_pass")
        snd2, self.fsky_cap = self.create_sound_picker("CAPTURE Sound:", "fsky_cap")
        snd3, self.fsky_not1 = self.create_sound_picker("Notice Sound 1:", "fsky_not1")
        snd4, self.fsky_not2 = self.create_sound_picker("Notice Sound 2:", "fsky_not2")
        l.addLayout(snd1); l.addLayout(snd2); l.addLayout(snd3); l.addLayout(snd4)
        
        l.addSpacing(10)
        lbl_c = QtWidgets.QLabel("METAL_REG- DIAGNOSTICS")
        lbl_c.setStyleSheet(f"font: bold 10pt '{FONT_FAMILY}'; color: #404040;")
        l.addWidget(lbl_c)
        
        self.console_box = QtWidgets.QLabel("INIT...")
        self.console_box.setStyleSheet(f"background-color: black; color: #00FF00; font-family: 'Courier New'; font-weight: bold; font-size: 10pt; padding: 4px; {get_3d_border(True, 2)}")
        self.console_box.setFixedHeight(40)
        l.addWidget(self.console_box)
        l.addStretch()
        return page

    def build_dmnpc_page(self):
        page = QtWidgets.QWidget()
        l = QtWidgets.QVBoxLayout(page)
        l.setContentsMargins(0,0,0,0)
        
        phys_l = QtWidgets.QHBoxLayout()
        phys_lbl = QtWidgets.QLabel("Physics Shape:")
        phys_lbl.setStyleSheet(f"font: 10pt '{FONT_FAMILY}'; color: black;")
        self.dmnpc_phys = QtWidgets.QComboBox()
        self.dmnpc_phys.addItems(["GRIS shape", "Model"])
        self.dmnpc_phys.setStyleSheet(f"background-color: {INPUT_BG}; color: black; {get_3d_border(True, 1)}")
        self.dmnpc_phys.setCurrentText(self.target.ai_config.get("dmnpc_phys", "GRIS shape"))
        phys_l.addWidget(phys_lbl); phys_l.addWidget(self.dmnpc_phys)
        l.addLayout(phys_l)
        
        snd1, self.dmnpc_pass = self.create_sound_picker("Passive Sound:", "dmnpc_pass")
        snd2, self.dmnpc_dmg = self.create_sound_picker("Damage Sound:", "dmnpc_dmg")
        snd3, self.dmnpc_death = self.create_sound_picker("Death Sound:", "dmnpc_death")
        l.addLayout(snd1); l.addLayout(snd2); l.addLayout(snd3)
        l.addStretch()
        return page

    def build_sillycone_page(self):
        page = QtWidgets.QWidget()
        l = QtWidgets.QVBoxLayout(page)
        l.setContentsMargins(0,0,0,0)
        
        self.sil_speech = QtWidgets.QCheckBox("Enable chat for this entity?")
        self.sil_speech.setStyleSheet(get_checkbox_style() + "QCheckBox { color: #CC6600; }")
        self.sil_speech.setCursor(QtCore.Qt.PointingHandCursor)
        self.sil_speech.setChecked(self.target.ai_config.get("sil_speech", False))
        l.addWidget(self.sil_speech)
        
        col_l = QtWidgets.QHBoxLayout()
        self.sil_custom_col = QtWidgets.QCheckBox("Enable unique color for this entity?")
        self.sil_custom_col.setStyleSheet(get_checkbox_style() + "QCheckBox { color: #0066CC; }")
        self.sil_custom_col.setCursor(QtCore.Qt.PointingHandCursor)
        self.sil_custom_col.setChecked(self.target.ai_config.get("sil_custom_col", False))
        
        self.sil_color_btn = QtWidgets.QPushButton("Pick Color")
        self.sil_color_btn.setStyleSheet(get_btn_style())
        self.current_sil_color = self.target.ai_config.get("sil_color", (0.5, 0.5, 0.5))
        self.sil_color_btn.clicked.connect(self.pick_sil_color)
        col_l.addWidget(self.sil_custom_col); col_l.addWidget(self.sil_color_btn)
        l.addLayout(col_l)
        
        snd1, self.sil_pass = self.create_sound_picker("Passive Sound:", "sil_pass")
        snd2, self.sil_dmg = self.create_sound_picker("Damage Sound:", "sil_dmg")
        snd3, self.sil_death = self.create_sound_picker("Death Sound:", "sil_death")
        l.addLayout(snd1); l.addLayout(snd2); l.addLayout(snd3)
        l.addStretch()
        return page
        
    def pick_sil_color(self):
        dlg = QColorDialog(self)
        if dlg.exec_() == QColorDialog.Accepted:
            c = dlg.selectedColor()
            self.current_sil_color = (c.redF(), c.greenF(), c.blueF())

    def on_type_changed(self, text):
        idx =["FSKY_CAPTURE_CBSGY", "DMNPC_TLEET_WDYMS", "Siuef"].index(text)
        self.stack.setCurrentIndex(idx)

    def update_console(self):
        if self.combo_type.currentText() == "FSKY_CAPTURE_CBSGY" and hasattr(self.target, 'metal_reg_state'):
            self.console_box.setText(f"METAL_REG-[{self.target.metal_reg_state}]")

    def apply_settings(self):
        t = self.combo_type.currentText()
        self.target.ai_type = t
        
        if t == "FSKY_CAPTURE_CBSGY":
            self.target.ai_config = {
                "fsky_ignore_col": self.fsky_ignore_col.isChecked(),
                "fsky_radius": self.fsky_radius.value(),
                "fsky_pass": self.fsky_pass.text(),
                "fsky_cap": self.fsky_cap.text(),
                "fsky_not1": self.fsky_not1.text(),
                "fsky_not2": self.fsky_not2.text()
            }
        elif t == "DMNPC_TLEET_WDYMS":
            self.target.ai_config = {
                "dmnpc_phys": self.dmnpc_phys.currentText(),
                "dmnpc_pass": self.dmnpc_pass.text(),
                "dmnpc_dmg": self.dmnpc_dmg.text(),
                "dmnpc_death": self.dmnpc_death.text()
            }
        elif t == "Siuef":
            self.target.ai_config = {
                "sil_speech": self.sil_speech.isChecked(),
                "sil_custom_col": self.sil_custom_col.isChecked(),
                "sil_color": self.current_sil_color,
                "sil_pass": self.sil_pass.text(),
                "sil_dmg": self.sil_dmg.text(),
                "sil_death": self.sil_death.text()
            }
            self.target.type = "Cone"
            self.target.scale =[1.0, 1.0, 1.0]
            if not self.target.ai_config["sil_custom_col"]:
                self.target.color = (0.5, 0.5, 0.5) 
            else:
                self.target.color = self.current_sil_color
                
        self.accept()