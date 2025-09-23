from PyQt5 import QtWidgets, QtCore, QtGui
import sys
from camera_viewer.settings import Settings
from camera_viewer.settings_dialog import SettingsDialog
from camera_viewer.utils import get_camera_stream
import threading
import time
import cv2

class CameraWidget(QtWidgets.QLabel):
    def __init__(self, ip, user='', password='', port='554', flip_h=False, flip_v=False, parent=None):
        super().__init__(parent)
        self.ip = ip
        self.user = user
        self.password = password
        self.port = port
        self.flip_h = flip_h
        self.flip_v = flip_v
        self.setAlignment(QtCore.Qt.AlignCenter)
        self.setText(f"{ip}\n接続中...")
        self._stop = False
        self.thread = threading.Thread(target=self.update_frame, daemon=True)
        self.thread.start()

    def update_frame(self):
        # RTSP URL（ユーザー名・パスワード・ポート対応）
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
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                h, w, ch = rgb.shape
                img = QtGui.QImage(rgb.data, w, h, ch * w, QtGui.QImage.Format_RGB888)
                pix = QtGui.QPixmap.fromImage(img)
                self.setPixmap(pix.scaled(self.width(), self.height(), QtCore.Qt.KeepAspectRatio))
            else:
                self.setText(f"{self.ip}\n取得失敗")
            time.sleep(1/20)  # 20fps
        cap.release()

    def close(self):
        self._stop = True

class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('イーサネットIPカメラマルチビューア')
        self.settings = Settings()
        self.init_ui()

    def init_ui(self):
        menubar = self.menuBar()
        settings_action = QtWidgets.QAction('設定', self)
        settings_action.triggered.connect(self.open_settings)
        menubar.addAction(settings_action)
        # カメラ表示用ウィジェット
        self.cam_widgets = []
        self.cam_area = QtWidgets.QWidget()
        self.cam_layout = QtWidgets.QVBoxLayout(self.cam_area)
        self.setCentralWidget(self.cam_area)
        self.load_cameras()

    def load_cameras(self):
        # 既存ウィジェット削除
        for w in self.cam_widgets:
            w.close()
            self.cam_layout.removeWidget(w)
            w.deleteLater()
        self.cam_widgets.clear()
        # ONのカメラのみ表示
        for ip, v in self.settings.get_cameras().items():
            name, flip_h, flip_v, enable, user, password, port = v
            if enable != '1':
                continue
            widget = CameraWidget(ip, user, password, port, flip_h == '1', flip_v == '1')
            self.cam_layout.addWidget(widget)
            self.cam_widgets.append(widget)

    def open_settings(self):
        dlg = SettingsDialog(self.settings, self)
        if dlg.exec_():
            self.settings.load()
            self.load_cameras()
        # 設定変更後の再描画等

    def closeEvent(self, event):
        for w in self.cam_widgets:
            w.close()
        event.accept()

if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec_())
