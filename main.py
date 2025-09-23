from PyQt5 import QtWidgets, QtCore, QtGui
import sys
from camera_viewer.settings import Settings
from camera_viewer.settings_dialog import SettingsDialog
from camera_viewer.utils import get_camera_stream
import threading
import time
import cv2

class CameraWidget(QtWidgets.QLabel):
    def __init__(self, ip, user='', password='', port='554', flip_h=False, flip_v=False, name='', parent=None):
        super().__init__(parent)
        self.ip = ip
        self.user = user
        self.password = password
        self.port = port
        self.flip_h = flip_h
        self.flip_v = flip_v
        self.name = name
        self.setAlignment(QtCore.Qt.AlignCenter)
        self.setText(f"{ip}\n接続中...")
        self._stop = False
        self.frame = None
        self.thread = threading.Thread(target=self.update_frame, daemon=True)
        self.thread.start()

    def update_frame(self):
        auth = f"{self.user}:{self.password}@" if self.user and self.password else ''
        url = f"rtsp://{auth}{self.ip}:{self.port}/stream1"
        cap = cv2.VideoCapture(url)
        while not self._stop:
            ret, frame = cap.read()
            if ret:
                if self.flip_h:
                    frame = cv2.flip(frame, 1)
                if self.flip_v:
                    frame = cv2.flip(frame, 0)
                # カメラ名を左上に黒背景＋白文字で日本語対応描画
                if self.name:
                    try:
                        from PIL import ImageFont, ImageDraw, Image
                        import numpy as np
                        pil_img = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
                        font_path = "C:/Windows/Fonts/msgothic.ttc"
                        font = ImageFont.truetype(font_path, 28)
                        draw = ImageDraw.Draw(pil_img)
                        text_size = draw.textbbox((0,0), self.name, font=font)
                        x0, y0, x1, y1 = text_size
                        # 黒背景
                        draw.rectangle([8, 3, 8 + (x1-x0) + 8, 3 + (y1-y0) + 8], fill=(0,0,0,200))
                        draw.text((12, 7), self.name, font=font, fill=(255,255,255))
                        frame = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
                    except Exception as e:
                        cv2.putText(frame, self.name, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255,255,255), 2, cv2.LINE_AA)
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                h, w, ch = rgb.shape
                img = QtGui.QImage(rgb.data, w, h, ch * w, QtGui.QImage.Format_RGB888)
                pix = QtGui.QPixmap.fromImage(img)
                self.setPixmap(pix.scaled(self.width(), self.height(), QtCore.Qt.KeepAspectRatio))
            else:
                self.setText(f"{self.ip}\n取得失敗")
            time.sleep(1/20)
        cap.release()

    def close(self):
        self._stop = True

class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('イーサネットIPカメラマルチビューア')
        self.settings = Settings()
        self.init_ui()
        QtCore.QTimer.singleShot(100, self.showFullScreen)

    def init_ui(self):
        menubar = self.menuBar()
        # ボタンサイズ設定（1.5倍: 36x36px）
        btn_size = QtCore.QSize(36, 36)

        # 歯車アイコンの設定ボタン（左上）
        settings_action = QtWidgets.QAction(QtGui.QIcon('icons/gear.png'), '設定', self)
        settings_action.setToolTip('カメラ設定を開く')
        settings_action.setStatusTip('カメラ設定を開く')
        settings_action.triggered.connect(self.open_settings)
        self.settings_btn = QtWidgets.QToolButton(self)
        self.settings_btn.setDefaultAction(settings_action)
        self.settings_btn.setIconSize(btn_size)
        self.settings_btn.setFixedSize(btn_size)
        menubar.setCornerWidget(self.settings_btn, QtCore.Qt.TopLeftCorner)

        # フルスクリーン（ウィンドウモード）ボタン（右上の左側）
        self.window_btn = QtWidgets.QToolButton(self)
        self.window_btn.setIcon(QtGui.QIcon('icons/window.png'))
        self.window_btn.setIconSize(btn_size)
        self.window_btn.setFixedSize(btn_size)
        self.window_btn.setToolTip('ウィンドウモードに切替')
        self.window_btn.setStatusTip('ウィンドウモードに切替')
        self.window_btn.clicked.connect(self.toggle_window_mode)

        # 閉じるボタン（右上）
        self.close_btn = QtWidgets.QToolButton(self)
        self.close_btn.setIcon(QtGui.QIcon('icons/close.png'))
        self.close_btn.setIconSize(btn_size)
        self.close_btn.setFixedSize(btn_size)
        self.close_btn.setToolTip('アプリを終了')
        self.close_btn.setStatusTip('アプリを終了')
        self.close_btn.clicked.connect(self.close)

        # 右上にウィンドウモード・閉じるボタンを横並びで配置
        right_widget = QtWidgets.QWidget()
        right_layout = QtWidgets.QHBoxLayout(right_widget)
        right_layout.setContentsMargins(0,0,0,0)
        right_layout.setSpacing(0)
        right_layout.addWidget(self.window_btn)
        right_layout.addWidget(self.close_btn)
        menubar.setCornerWidget(right_widget, QtCore.Qt.TopRightCorner)

        self.cam_widgets = []
        self.cam_area = QtWidgets.QWidget()
        self.grid_layout = QtWidgets.QGridLayout(self.cam_area)
        self.grid_layout.setSpacing(4)
        self.setCentralWidget(self.cam_area)
        self.load_cameras()

    def load_cameras(self):
        # 既存ウィジェット削除
        for w in self.cam_widgets:
            w.close()
            self.grid_layout.removeWidget(w)
            w.deleteLater()
        self.cam_widgets.clear()
        # ONのカメラのみリスト化
        cam_data = []
        for ip, v in self.settings.get_cameras().items():
            name, flip_h, flip_v, enable, user, password, port = v
            if enable != '1':
                continue
            cam_data.append((ip, user, password, port, flip_h == '1', flip_v == '1', name))
        n = len(cam_data)
        if n == 0:
            return
        # 分割数計算（例: 2→1x2, 4→2x2, 5→2x3, 9→3x3）
        import math
        cols = math.ceil(math.sqrt(n))
        rows = math.ceil(n / cols)
        # グリッドに追加
        for idx, (ip, user, password, port, flip_h, flip_v, name) in enumerate(cam_data):
            widget = CameraWidget(ip, user, password, port, flip_h, flip_v, name)
            row = idx // cols
            col = idx % cols
            self.grid_layout.addWidget(widget, row, col)
            self.cam_widgets.append(widget)

    def open_settings(self):
        dlg = SettingsDialog(self.settings, self)
        if dlg.exec_():
            self.settings.load()
            self.load_cameras()
        # 設定変更後の再描画等

    def toggle_window_mode(self):
        if self.isFullScreen():
            self.showNormal()
            self.window_btn.setToolTip('全画面モードに切替')
            self.window_btn.setStatusTip('全画面モードに切替')
        else:
            self.showFullScreen()
            self.window_btn.setToolTip('ウィンドウモードに切替')
            self.window_btn.setStatusTip('ウィンドウモードに切替')

    def closeEvent(self, event):
        for w in self.cam_widgets:
            w.close()
        event.accept()

if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec_())
