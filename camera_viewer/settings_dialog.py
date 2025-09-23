from PyQt5 import QtWidgets, QtCore, QtGui
import sys
import os
from camera_viewer.settings import Settings

class SettingsDialog(QtWidgets.QDialog):
    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.setWindowTitle('カメラ設定')
        self.settings = settings
        self.layout = QtWidgets.QVBoxLayout(self)
        self.table = QtWidgets.QTableWidget(0, 9)
        self.table.setHorizontalHeaderLabels(['IP', '名前', 'ユーザー', 'パスワード', 'ポート', '左右反転', '上下反転', '表示', '削除'])
        self.layout.addWidget(self.table)
        self.add_btn = QtWidgets.QPushButton('追加')
        self.save_btn = QtWidgets.QPushButton('保存')
        self.layout.addWidget(self.add_btn)
        self.layout.addWidget(self.save_btn)
        self.add_btn.clicked.connect(self.add_row)
        self.save_btn.clicked.connect(self.save)
        self.load_table()

    def load_table(self):
        self.table.setRowCount(0)
        for ip, v in self.settings.get_cameras().items():
            name, flip_h, flip_v, enable, user, password, port = v
            self.add_row(ip, name, user, password, port, flip_h == '1', flip_v == '1', enable == '1')

    def add_row(self, ip='', name='', user='', password='', port='554', flip_h=False, flip_v=False, enable=True):
        row = self.table.rowCount()
        self.table.insertRow(row)
        self.table.setItem(row, 0, QtWidgets.QTableWidgetItem(ip))
        self.table.setItem(row, 1, QtWidgets.QTableWidgetItem(name))
        self.table.setItem(row, 2, QtWidgets.QTableWidgetItem(user))
        self.table.setItem(row, 3, QtWidgets.QTableWidgetItem(password))
        self.table.setItem(row, 4, QtWidgets.QTableWidgetItem(str(port)))
        flip_h_cb = QtWidgets.QCheckBox()
        flip_h_cb.setChecked(flip_h)
        self.table.setCellWidget(row, 5, flip_h_cb)
        flip_v_cb = QtWidgets.QCheckBox()
        flip_v_cb.setChecked(flip_v)
        self.table.setCellWidget(row, 6, flip_v_cb)
        enable_cb = QtWidgets.QCheckBox()
        enable_cb.setChecked(enable)
        self.table.setCellWidget(row, 7, enable_cb)
        del_btn = QtWidgets.QPushButton('削除')
        del_btn.clicked.connect(lambda: self.table.removeRow(row))
        self.table.setCellWidget(row, 8, del_btn)

    def save(self):
        self.settings.config['Cameras'] = {}
        for row in range(self.table.rowCount()):
            ip = self.table.item(row, 0).text()
            name = self.table.item(row, 1).text()
            user = self.table.item(row, 2).text()
            password = self.table.item(row, 3).text()
            port = self.table.item(row, 4).text() or '554'
            flip_h = self.table.cellWidget(row, 5).isChecked()
            flip_v = self.table.cellWidget(row, 6).isChecked()
            enable = self.table.cellWidget(row, 7).isChecked()
            self.settings.set_camera(ip, name, flip_h, flip_v, enable, user, password, port)
        self.settings.save()
        self.accept()

if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    settings = Settings()
    dlg = SettingsDialog(settings)
    dlg.exec_()
