import os
import sys
from pathlib import Path
from PyQt5 import QtCore, QtGui, QtWidgets
from custom_file_dialog import CustomFileDialog

if getattr(sys, 'frozen', False):
    PROJECT_ROOT = Path(sys.executable).parent
else:
    PROJECT_ROOT = Path(__file__).resolve().parent

PANEL_BG = "#AEAEAE"
INPUT_BG = "#D0D0D0"
FONT_FAMILY = "Forum"

def get_3d_border(sunken=False, width=2):
    if sunken:
        return f"border-top: {width}px solid #606060; border-left: {width}px solid #606060; border-bottom: {width}px solid #E0E0E0; border-right: {width}px solid #E0E0E0;"
    return f"border-top: {width}px solid #E0E0E0; border-left: {width}px solid #E0E0E0; border-bottom: {width}px solid #606060; border-right: {width}px solid #606060;"

def get_btn_style():
    return f"""
        QPushButton {{ background-color: {PANEL_BG}; {get_3d_border(False, 2)} color: black; font-family: "{FONT_FAMILY}"; font-weight: bold; }}
        QPushButton:hover {{ background-color: #00FF00; }}
        QPushButton:pressed {{ background-color: #00CC00; {get_3d_border(True, 2)} }}
    """

def get_checkbox_style():
    return f"""
        QCheckBox {{ color: black; font: bold 11pt '{FONT_FAMILY}'; outline: none; margin: 4px 0px; }}
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

class GeneralSettingsDialog(QtWidgets.QDialog):
    def __init__(self, parent_window):
        super().__init__(parent_window)
        self.main_window = parent_window
        self.setWindowFlags(QtCore.Qt.FramelessWindowHint | QtCore.Qt.Dialog)
        self.setStyleSheet(f"QDialog {{ background-color: {PANEL_BG}; {get_3d_border(False, 3)} }}")
        self.resize(450, 380)
        
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(6)
        
        header = QtWidgets.QWidget()
        header.setFixedHeight(28)
        h_layout = QtWidgets.QHBoxLayout(header)
        h_layout.setContentsMargins(6, 0, 6, 0)
        
        lbl_title = QtWidgets.QLabel("GENERAL SETTINGS")
        lbl_title.setStyleSheet(f"color: black; font: bold 10pt '{FONT_FAMILY}';")
        h_layout.addWidget(lbl_title)
        h_layout.addStretch()
        
        btn_close = QtWidgets.QPushButton("X")
        btn_close.setFixedSize(24, 24)
        btn_close.setCursor(QtCore.Qt.PointingHandCursor)
        btn_close.setStyleSheet(get_btn_style())
        btn_close.clicked.connect(self.reject)
        h_layout.addWidget(btn_close)
        layout.addWidget(header)
        

        content = QtWidgets.QFrame()
        content.setStyleSheet(f"QFrame {{ background-color: #C0C0C0; {get_3d_border(True, 2)} }}")
        c_layout = QtWidgets.QVBoxLayout(content)
        
        config = self.main_window.app_config
        
        w_layout = QtWidgets.QHBoxLayout()
        w_lbl = QtWidgets.QLabel("Window Mode:")
        w_lbl.setStyleSheet(f"font: 11pt '{FONT_FAMILY}'; color: black;")
        self.combo_win = QtWidgets.QComboBox()
        self.combo_win.addItems(["Windowed", "Fullscreen"])
        self.combo_win.setCurrentText(config.get("window_mode", "Windowed"))
        self.combo_win.setStyleSheet(f"background-color: {INPUT_BG}; color: black; {get_3d_border(True, 1)}")
        w_layout.addWidget(w_lbl); w_layout.addWidget(self.combo_win)
        c_layout.addLayout(w_layout)
        
        d_layout = QtWidgets.QHBoxLayout()
        d_lbl = QtWidgets.QLabel("Delete Type:")
        d_lbl.setStyleSheet(f"font: 11pt '{FONT_FAMILY}'; color: black;")
        self.combo_del = QtWidgets.QComboBox()
        self.combo_del.addItems(["Fast Delete", "Animated Deletion"])
        self.combo_del.setCurrentText(config.get("delete_type", "Fast Delete"))
        self.combo_del.setStyleSheet(f"background-color: {INPUT_BG}; color: black; {get_3d_border(True, 1)}")
        d_layout.addWidget(d_lbl); d_layout.addWidget(self.combo_del)
        c_layout.addLayout(d_layout)
        
        self.chk_snd = QtWidgets.QCheckBox("Disable app sounds")
        self.chk_mus = QtWidgets.QCheckBox("Disable music")
        self.chk_del = QtWidgets.QCheckBox("Disable delete sound")
        for chk, key in[(self.chk_snd, "disable_app_sounds"), (self.chk_mus, "disable_music"), (self.chk_del, "disable_delete_sound")]:
            chk.setStyleSheet(get_checkbox_style())
            chk.setCursor(QtCore.Qt.PointingHandCursor)
            chk.setChecked(config.get(key, False))
            c_layout.addWidget(chk)
            
        c_layout.addSpacing(10)
        
        s_layout = QtWidgets.QHBoxLayout()
        s_lbl = QtWidgets.QLabel("World Skybox:")
        s_lbl.setStyleSheet(f"font: 11pt '{FONT_FAMILY}'; color: black;")
        self.sky_path = QtWidgets.QLineEdit(config.get("world_skybox", ""))
        self.sky_path.setStyleSheet(f"background-color: {INPUT_BG}; color: black; {get_3d_border(True, 1)}")
        btn_sky = QtWidgets.QPushButton("...")
        btn_sky.setFixedSize(30, 24)
        btn_sky.setStyleSheet(get_btn_style())
        btn_sky.clicked.connect(self.pick_skybox)
        s_layout.addWidget(s_lbl); s_layout.addWidget(self.sky_path); s_layout.addWidget(btn_sky)
        c_layout.addLayout(s_layout)
        
        c_layout.addSpacing(15)
        lbl_warn = QtWidgets.QLabel("Warning! This settings will only effect local editor instance,\nand will not have effect on Server side of the void.")
        lbl_warn.setWordWrap(True)
        lbl_warn.setStyleSheet(f"font: bold 10pt '{FONT_FAMILY}'; color: #CC4400;")
        c_layout.addWidget(lbl_warn)
        
        c_layout.addStretch()
        layout.addWidget(content)
        
        btn_apply = QtWidgets.QPushButton("SAVE & APPLY")
        btn_apply.setFixedHeight(35)
        btn_apply.setCursor(QtCore.Qt.PointingHandCursor)
        btn_apply.setStyleSheet(get_btn_style())
        btn_apply.clicked.connect(self.save_settings)
        layout.addWidget(btn_apply)
        
    def pick_skybox(self):
        start_dir = str(PROJECT_ROOT / "materials")
        dlg = CustomFileDialog(self, "SELECT SKYBOX", "open", start_dir, (".png", ".jpg", ".jpeg", ".bmp"))
        if dlg.exec_() == QtWidgets.QDialog.Accepted:
            path = dlg.selected_file
            if path:
                self.sky_path.setText(path)
        
    def save_settings(self):
        cfg = self.main_window.app_config
        cfg["window_mode"] = self.combo_win.currentText()
        cfg["delete_type"] = self.combo_del.currentText()
        cfg["disable_app_sounds"] = self.chk_snd.isChecked()
        cfg["disable_music"] = self.chk_mus.isChecked()
        cfg["disable_delete_sound"] = self.chk_del.isChecked()
        cfg["world_skybox"] = self.sky_path.text()
        
        self.main_window.save_config()
        self.main_window.apply_general_settings()
        self.accept()