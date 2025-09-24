from PyQt5 import QtWidgets, QtCore, QtGui
import sys
from camera_viewer.settings import Settings
from camera_viewer.settings_dialog import SettingsDialog
from camera_viewer.utils import get_camera_stream
import threading
import time
import cv2
import sip

class CameraWidget(QtWidgets.QLabel):
    def __init__(self, ip, user='', password='', port='554', flip_h=False, flip_v=False, name='', parent=None, stream='stream2'):
        super().__init__(parent)
        self.ip = ip
        self.user = user
        self.password = password
        self.port = port
        self.flip_h = flip_h
        self.flip_v = flip_v
        self.name = name
        self.stream = stream  # 'stream1' or 'stream2'
        self.setAlignment(QtCore.Qt.AlignCenter)
        self.setText(f"{self.name}\n接続中...")
        self._stop = False
        self._paused = False
        self._force_stream = None
        self.thread = threading.Thread(target=self.update_frame, daemon=True)
        self.thread.start()

    def set_paused(self, paused: bool):
        self._paused = paused

    def set_force_stream(self, stream):
        self._force_stream = stream

    def get_current_stream(self):
        return self._force_stream if self._force_stream else self.stream

    def update_frame(self):
        import weakref
        self_ref = weakref.ref(self)
        while not self._stop:
            if getattr(self, '_paused', False):
                time.sleep(0.1)
                continue
            stream = self.get_current_stream()
            auth = f"{self.user}:{self.password}@" if self.user and self.password else ''
            url = f"rtsp://{auth}{self.ip}:{self.port}/{stream}"
            cap = cv2.VideoCapture(url)
            while not self._stop and not getattr(self, '_paused', False):
                # stream切替要求があればbreak
                if self._force_stream and self._force_stream != stream:
                    break
                ret, frame = cap.read()
                if ret:
                    if self.flip_h:
                        frame = cv2.flip(frame, 1)
                    if self.flip_v:
                        frame = cv2.flip(frame, 0)
                    # カメラ名を左上に白文字＋黒背景で描画（日本語対応）
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
                            draw.rectangle([8, 3, 8 + (x1-x0) + 8, 3 + (y1-y0) + 8], fill=(0,0,0,200))
                            draw.text((12, 7), self.name, font=font, fill=(255,255,255))
                            frame = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
                        except Exception as e:
                            cv2.putText(frame, self.name, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255,255,255), 2, cv2.LINE_AA)
                    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    h, w, ch = rgb.shape
                    img = QtGui.QImage(rgb.data, w, h, ch * w, QtGui.QImage.Format_RGB888)
                    pix = QtGui.QPixmap.fromImage(img)
                    widget = self_ref()
                    if widget is not None:
                        widget.setPixmap(pix.scaled(widget.width(), widget.height(), QtCore.Qt.KeepAspectRatio))
                else:
                    widget = self_ref()
                    if widget is not None:
                        widget.setText(f"{self.ip}\n取得失敗")
                time.sleep(1/20)
            cap.release()

    def close(self):
        self._stop = True

    def mouseDoubleClickEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            self.parent().parent().show_camera_fullscreen(self)
        super().mouseDoubleClickEvent(event)

    def send_ptz_command(self, direction):
        # Tapo C200 PTZ制御（ONVIF利用）
        try:
            from onvif import ONVIFCamera
            ip = self.ip
            user = self.user
            password = self.password
            onvif_port = 2020  # Tapo C200のONVIFデフォルトポート
            camera = ONVIFCamera(ip, onvif_port, user, password)
            media = camera.create_media_service()
            ptz = camera.create_ptz_service()
            media_profile = media.GetProfiles()[0]
            token = media_profile.token
            # 現在位置取得
            status = ptz.GetStatus({'ProfileToken': token})
            pos = status.Position
            x = pos.PanTilt.x if pos and pos.PanTilt else 0
            y = pos.PanTilt.y if pos and pos.PanTilt else 0
            # 移動量
            step = 0.1
            if direction == 'up':
                y += step
            elif direction == 'down':
                y -= step
            elif direction == 'left':
                x += step  # ←左右を反転
            elif direction == 'right':
                x -= step  # ←左右を反転
            # 範囲制限（-1.0～1.0）
            x = max(-1.0, min(1.0, x))
            y = max(-1.0, min(1.0, y))
            req = ptz.create_type('AbsoluteMove')
            req.ProfileToken = token
            req.Position = {'PanTilt': {'x': x, 'y': y}}
            ptz.AbsoluteMove(req)
            return True
        except Exception as e:
            print(f"PTZコマンド送信失敗: {e}")
            return False

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
            widget = CameraWidget(ip, user, password, port, flip_h, flip_v, name, stream='stream2')
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

    def show_camera_fullscreen(self, cam_widget):
        for w in self.cam_widgets:
            if w is not cam_widget:
                w.set_paused(True)
        cam_widget.set_paused(False)
        cam_widget.set_force_stream('stream2')
        # 以前の画面遷移をやめて、ダイアログで全画面表示
        dlg = QtWidgets.QDialog(self)
        dlg.setWindowTitle(cam_widget.name or cam_widget.ip)
        dlg.setWindowFlags(dlg.windowFlags() | QtCore.Qt.Window)
        dlg.showFullScreen()
        main_layout = QtWidgets.QHBoxLayout(dlg)
        label = QtWidgets.QLabel()
        label.setAlignment(QtCore.Qt.AlignCenter)
        label.setMinimumSize(320, 240)
        main_layout.addWidget(label, stretch=1)
        sidebar = QtWidgets.QWidget()
        sidebar_layout = QtWidgets.QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(10, 40, 10, 40)
        sidebar_layout.setSpacing(20)
        btn_size = QtCore.QSize(56, 56)
        # 画質/速度トグルボタン（2行表示・他ボタンと同サイズ）
        toggle_btn = QtWidgets.QPushButton('画質優先\n(高画質)')
        toggle_btn.setCheckable(True)
        toggle_btn.setChecked(False)
        toggle_btn.setFixedSize(btn_size)
        toggle_btn.setToolTip('画質優先: stream1 / 速度優先: stream2')
        def toggle_stream():
            if toggle_btn.isChecked():
                toggle_btn.setText('速度優先\n(低遅延)')
                cam_widget.set_force_stream('stream2')
            else:
                toggle_btn.setText('画質優先\n(高画質)')
                cam_widget.set_force_stream('stream1')
        toggle_btn.clicked.connect(toggle_stream)
        sidebar_layout.addWidget(toggle_btn, alignment=QtCore.Qt.AlignTop)
        close_btn = QtWidgets.QPushButton()
        close_btn.setIcon(QtGui.QIcon('icons/close.png'))
        close_btn.setIconSize(btn_size)
        close_btn.setFixedSize(btn_size)
        close_btn.setToolTip('全画面を閉じる')
        close_btn.clicked.connect(dlg.accept)
        sidebar_layout.addWidget(close_btn, alignment=QtCore.Qt.AlignTop)
        up_btn = QtWidgets.QPushButton()
        up_btn.setIcon(QtGui.QIcon('icons/arrow_up.png'))
        up_btn.setIconSize(btn_size)
        up_btn.setFixedSize(btn_size)
        up_btn.clicked.connect(lambda: cam_widget.send_ptz_command('up'))
        sidebar_layout.addWidget(up_btn, alignment=QtCore.Qt.AlignTop)
        left_btn = QtWidgets.QPushButton()
        left_btn.setIcon(QtGui.QIcon('icons/arrow_left.png'))
        left_btn.setIconSize(btn_size)
        left_btn.setFixedSize(btn_size)
        left_btn.clicked.connect(lambda: cam_widget.send_ptz_command('left'))
        sidebar_layout.addWidget(left_btn, alignment=QtCore.Qt.AlignTop)
        right_btn = QtWidgets.QPushButton()
        right_btn.setIcon(QtGui.QIcon('icons/arrow_right.png'))
        right_btn.setIconSize(btn_size)
        right_btn.setFixedSize(btn_size)
        right_btn.clicked.connect(lambda: cam_widget.send_ptz_command('right'))
        sidebar_layout.addWidget(right_btn, alignment=QtCore.Qt.AlignTop)
        down_btn = QtWidgets.QPushButton()
        down_btn.setIcon(QtGui.QIcon('icons/arrow_down.png'))
        down_btn.setIconSize(btn_size)
        down_btn.setFixedSize(btn_size)
        down_btn.clicked.connect(lambda: cam_widget.send_ptz_command('down'))
        sidebar_layout.addWidget(down_btn, alignment=QtCore.Qt.AlignTop)
        sidebar_layout.addStretch(1)
        main_layout.addWidget(sidebar, stretch=0)
        def update():
            pix = cam_widget.pixmap()
            if pix and not pix.isNull():
                label.setPixmap(pix.scaled(label.width(), label.height(), QtCore.Qt.KeepAspectRatio))
        timer = QtCore.QTimer(dlg)
        timer.timeout.connect(update)
        timer.start(50)
        dlg.exec_()
        for w in self.cam_widgets:
            w.set_paused(False)
            w.set_force_stream(None)

    def closeEvent(self, event):
        for w in self.cam_widgets:
            w.close()
        event.accept()

if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec_())
