import os
import sys
from pathlib import Path
from PyQt5 import QtCore, QtGui, QtWidgets

if getattr(sys, 'frozen', False):
    PROJECT_ROOT = Path(sys.executable).parent
else:
    PROJECT_ROOT = Path(__file__).resolve().parent
    
PANEL_BG = "#AEAEAE"
INPUT_BG = "#D0D0D0"
BASE_BG = "#A4A4A4"
HOVER_GREEN = "#00FF00"
PRESS_GREEN = "#00CC00"
HOVER_RED = "#FF0000"
PRESS_RED = "#CC0000"
FONT_FAMILY = "Forum"

def get_3d_border(sunken=False, width=2):
    if sunken:
        return f"border-top: {width}px solid #606060; border-left: {width}px solid #606060; border-bottom: {width}px solid #E0E0E0; border-right: {width}px solid #E0E0E0;"
    return f"border-top: {width}px solid #E0E0E0; border-left: {width}px solid #E0E0E0; border-bottom: {width}px solid #606060; border-right: {width}px solid #606060;"

def get_btn_style(hover_bg=HOVER_GREEN, press_bg=PRESS_GREEN):
    return f"""
        QPushButton, QToolButton {{
            background-color: {PANEL_BG};
            {get_3d_border(False, 2)}
            color: black;
            font-family: "{FONT_FAMILY}";
        }}
        QPushButton:hover, QToolButton:hover {{ background-color: {hover_bg}; }}
        QPushButton:pressed, QToolButton:pressed {{ background-color: {press_bg}; {get_3d_border(True, 2)} }}
    """

class DottedHeaderFrame(QtWidgets.QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(QtCore.Qt.WA_StyledBackground, True)
        self.setStyleSheet(f"QFrame {{ background-color: {PANEL_BG}; {get_3d_border(False, 2)} }}")

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QtGui.QPainter(self)
        pen_dark = QtGui.QPen(QtGui.QColor('#606060'))
        pen_dark.setStyle(QtCore.Qt.CustomDashLine)
        pen_dark.setDashPattern([6, 4]) 
        pen_light = QtGui.QPen(QtGui.QColor('#E0E0E0'))
        pen_light.setStyle(QtCore.Qt.CustomDashLine)
        pen_light.setDashPattern([6, 4]) 
        w, h = self.width(), self.height()
        offset = 2
        painter.setPen(pen_dark)
        painter.drawRect(offset, offset, w - offset*2 - 1, h - offset*2 - 1)
        painter.setPen(pen_light)
        painter.drawRect(offset + 1, offset + 1, w - offset*2 - 1, h - offset*2 - 1)

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
        layout.setSpacing(4)
        
        icon_label = QtWidgets.QLabel()
        icon_label.setStyleSheet("border: none; background: transparent;")
        ico_path = PROJECT_ROOT / "icon.ico"
        if ico_path.exists():
            pix = QtGui.QPixmap(str(ico_path)).scaled(18, 18, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation)
            icon_label.setPixmap(pix)
        layout.addWidget(icon_label)
        
        self.title_label = QtWidgets.QLabel(title)
        self.title_label.setStyleSheet(f'color: black; font: 10pt "{FONT_FAMILY}"; border: none; background: transparent;')
        layout.addWidget(self.title_label)
        
        layout.addStretch()
        
        self.close_btn = QtWidgets.QPushButton("X")
        self.close_btn.setFixedSize(24, 24)
        self.close_btn.setCursor(QtCore.Qt.PointingHandCursor)
        self.close_btn.setFocusPolicy(QtCore.Qt.NoFocus)
        self.close_btn.setStyleSheet(get_btn_style(HOVER_RED, PRESS_RED) + "QPushButton { font-weight: bold; font-size: 9pt; }")
        layout.addWidget(self.close_btn)
        
        self.close_btn.clicked.connect(parent.reject)

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton: self.drag_pos = event.globalPos() - self.parent_window.frameGeometry().topLeft()
    def mouseMoveEvent(self, event):
        if self.drag_pos is not None and event.buttons() == QtCore.Qt.LeftButton: self.parent_window.move(event.globalPos() - self.drag_pos)
    def mouseReleaseEvent(self, event): self.drag_pos = None

class CustomFileDialog(QtWidgets.QDialog):
    def __init__(self, parent, title="FILE BROWSER", mode="open", start_dir="", ext_filter=".dme"):
        super().__init__(parent)
        self.mode = mode
        if isinstance(ext_filter, str):
            self.ext_filter =[ext_filter.lower()]
        else:
            self.ext_filter =[ext.lower() for ext in ext_filter]
        self.selected_file = ""
        
        p = Path(start_dir) if start_dir else PROJECT_ROOT
        self.current_dir = p.parent if p.is_file() else p
        if not self.current_dir.exists():
            self.current_dir = PROJECT_ROOT
            
        self.setWindowFlags(QtCore.Qt.FramelessWindowHint | QtCore.Qt.Dialog)
        self.setStyleSheet(f"QDialog {{ background-color: {PANEL_BG}; {get_3d_border(False, 3)} }}")
        self.resize(550, 480)
        
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(6)
        
        header_frame = DottedHeaderFrame(self)
        header_layout = QtWidgets.QVBoxLayout(header_frame)
        header_layout.setContentsMargins(4, 4, 4, 4)
        self.title_bar = DialogTitleBar(self, title)
        header_layout.addWidget(self.title_bar)
        layout.addWidget(header_frame)
        
        path_row = QtWidgets.QHBoxLayout()
        self.btn_up = QtWidgets.QPushButton("▲ UP")
        self.btn_up.setFixedSize(60, 28)
        self.btn_up.setCursor(QtCore.Qt.PointingHandCursor)
        self.btn_up.setStyleSheet(get_btn_style() + "QPushButton { font-size: 10pt; font-weight: bold; }")
        self.btn_up.clicked.connect(self.go_up)
        
        self.path_lbl = QtWidgets.QLineEdit()
        self.path_lbl.setReadOnly(True)
        self.path_lbl.setStyleSheet(f"QLineEdit {{ background-color: {INPUT_BG}; {get_3d_border(True, 2)} font: 10pt '{FONT_FAMILY}'; padding: 2px; color: black; }}")
        
        path_row.addWidget(self.btn_up)
        path_row.addWidget(self.path_lbl)
        layout.addLayout(path_row)
        
        sunken_frame = QtWidgets.QFrame()
        bg_path = PROJECT_ROOT / "materials" / "gui" / "bg.png"
        bg_path_str = str(bg_path).replace('\\', '/') if bg_path.exists() else ""
        bg_style = f"background-image: url({bg_path_str}); background-repeat: repeat;" if bg_path_str else f"background-color: {BASE_BG};"
        sunken_frame.setStyleSheet(f"QFrame {{ {bg_style} {get_3d_border(True, 3)} }}")
        sunken_layout = QtWidgets.QVBoxLayout(sunken_frame)
        sunken_layout.setContentsMargins(4, 4, 4, 4)
        
        self.file_list = QtWidgets.QListWidget()
        
        # Делаем шрифт жирным и читаемым для всех элементов по умолчанию
        self.file_list.setFont(QtGui.QFont(FONT_FAMILY, 11, QtGui.QFont.Bold))
        
        self.file_list.setStyleSheet(f"""
            QListWidget {{ 
                background: transparent; /* Прозрачный фон, чтобы видеть текстуру bg.png */
                border: none; 
                outline: none; 
            }}
            QListWidget::item {{ 
                background-color: {PANEL_BG}; /* Цвет самой пластины */
                {get_3d_border(False, 2)}     /* Выпуклые 3D грани */
                margin: 3px 4px;              /* Отступы между пластинами */
                padding: 6px;                 /* Внутренний отступ текста */
                color: black;
            }}
            QListWidget::item:hover {{ 
                background-color: {HOVER_GREEN}; 
            }}
            QListWidget::item:selected {{ 
                background-color: {PRESS_GREEN}; 
                {get_3d_border(True, 2)}      /* Вдавленные 3D грани при клике */
                color: black; 
            }}
            
            /* Стили скроллбара оставляем как есть */
            QScrollBar:vertical {{ border: 1px solid #606060; background: #C0C0C0; width: 16px; margin: 16px 0 16px 0; }}
            QScrollBar::handle:vertical {{ background: {PANEL_BG}; {get_3d_border(False, 1)} min-height: 20px; }}
            QScrollBar::add-line:vertical {{ {get_3d_border(False, 1)} background: {PANEL_BG}; height: 16px; subcontrol-position: bottom; subcontrol-origin: margin; }}
            QScrollBar::sub-line:vertical {{ {get_3d_border(False, 1)} background: {PANEL_BG}; height: 16px; subcontrol-position: top; subcontrol-origin: margin; }}
        """)
        self.file_list.itemClicked.connect(self.on_item_clicked)
        self.file_list.itemDoubleClicked.connect(self.on_item_double_clicked)
        sunken_layout.addWidget(self.file_list)
        layout.addWidget(sunken_frame)
        
        bot_row = QtWidgets.QHBoxLayout()
        lbl_fn = QtWidgets.QLabel("Filename:")
        lbl_fn.setStyleSheet(f"font: 11pt '{FONT_FAMILY}'; color: black; font-weight: bold;")
        
        self.name_edit = QtWidgets.QLineEdit()
        self.name_edit.setStyleSheet(f"QLineEdit {{ background-color: {INPUT_BG}; {get_3d_border(True, 2)} font: 11pt '{FONT_FAMILY}'; padding: 4px; color: black; }}")
        if mode == "save" and p.is_file():
            self.name_edit.setText(p.name)
        
        action_btn_text = "SAVE" if mode == "save" else "OPEN"
        self.btn_action = QtWidgets.QPushButton(action_btn_text)
        self.btn_action.setFixedSize(100, 32)
        self.btn_action.setCursor(QtCore.Qt.PointingHandCursor)
        self.btn_action.setStyleSheet(get_btn_style() + "QPushButton { font-size: 11pt; font-weight: bold; }")
        self.btn_action.clicked.connect(self.accept_action)
        
        self.btn_cancel = QtWidgets.QPushButton("CANCEL")
        self.btn_cancel.setFixedSize(100, 32)
        self.btn_cancel.setCursor(QtCore.Qt.PointingHandCursor)
        self.btn_cancel.setStyleSheet(get_btn_style(HOVER_RED, PRESS_RED) + "QPushButton { font-size: 11pt; font-weight: bold; }")
        self.btn_cancel.clicked.connect(self.reject)
        
        bot_row.addWidget(lbl_fn)
        bot_row.addWidget(self.name_edit)
        bot_row.addWidget(self.btn_action)
        bot_row.addWidget(self.btn_cancel)
        layout.addLayout(bot_row)
        
        self.refresh_list()
        
    def go_up(self):
        if self.current_dir.parent != self.current_dir:
            self.current_dir = self.current_dir.parent
            self.refresh_list()
            self.name_edit.clear()
            
    def refresh_list(self):
        self.file_list.clear()
        self.path_lbl.setText(str(self.current_dir))
        
        try: items = list(self.current_dir.iterdir())
        except PermissionError: items = []
            
        dirs = sorted([d for d in items if d.is_dir()])
        files = sorted([f for f in items if f.is_file() and (".*" in self.ext_filter or f.suffix.lower() in self.ext_filter)])
        
        for d in dirs:
            item = QtWidgets.QListWidgetItem(f"[DIR]  {d.name}")
            item.setData(QtCore.Qt.UserRole, d)
            item.setForeground(QtGui.QColor("#404040"))
            font = item.font(); font.setBold(True); item.setFont(font)
            self.file_list.addItem(item)
            
        for f in files:
            item = QtWidgets.QListWidgetItem(f"       {f.name}")
            item.setData(QtCore.Qt.UserRole, f)
            item.setForeground(QtGui.QColor("#000000"))
            self.file_list.addItem(item)
            
    def on_item_clicked(self, item):
        data = item.data(QtCore.Qt.UserRole)
        if isinstance(data, Path) and data.is_file():
            self.name_edit.setText(data.name)
            
    def on_item_double_clicked(self, item):
        data = item.data(QtCore.Qt.UserRole)
        if isinstance(data, Path):
            if data.is_dir():
                self.current_dir = data
                self.refresh_list()
                self.name_edit.clear()
            elif data.is_file():
                self.name_edit.setText(data.name)
                self.accept_action()
                
    def accept_action(self):
        name = self.name_edit.text().strip()
        if not name: return
        p = Path(name)
        target_path = p if p.is_absolute() else self.current_dir / name
        if ".*" not in self.ext_filter:
            if not any(target_path.name.lower().endswith(ext) for ext in self.ext_filter):
                target_path = target_path.with_name(target_path.name + self.ext_filter[0])
        self.selected_file = str(target_path)
        self.accept()