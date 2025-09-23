import configparser
import os

CONFIG_PATH = os.path.join(os.path.expanduser('~'), 'camera_viewer.ini')

class Settings:
    def __init__(self, path=CONFIG_PATH):
        self.path = path
        self.config = configparser.ConfigParser()
        self.load()

    def load(self):
        if os.path.exists(self.path):
            self.config.read(self.path, encoding='utf-8')
        else:
            self.config['Cameras'] = {}
            self.config['General'] = {'fps': '20', 'save_dir': os.path.join(os.path.expanduser('~'), 'Pictures')}

    def save(self):
        with open(self.path, 'w', encoding='utf-8') as f:
            self.config.write(f)

    def get_cameras(self):
        # 旧形式との互換性維持
        cams = {}
        for ip, v in self.config['Cameras'].items():
            parts = v.split('|')
            if len(parts) == 7:
                name, flip_h, flip_v, enable, user, password, port = parts
            elif len(parts) == 6:
                name, flip_h, flip_v, enable, user, password = parts
                port = '554'
            else:
                name, flip_h, flip_v, enable = parts
                user = password = ''
                port = '554'
            cams[ip] = (name, flip_h, flip_v, enable, user, password, port)
        return cams

    def get_general(self):
        return self.config['General']

    def set_camera(self, ip, name, flip_h=False, flip_v=False, enable=True, user='', password='', port='554'):
        self.config['Cameras'][ip] = f"{name}|{int(flip_h)}|{int(flip_v)}|{int(enable)}|{user}|{password}|{port}"

    def remove_camera(self, ip):
        if ip in self.config['Cameras']:
            del self.config['Cameras'][ip]

    def set_general(self, key, value):
        self.config['General'][key] = str(value)
