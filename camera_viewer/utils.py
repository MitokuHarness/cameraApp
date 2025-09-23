import cv2

def get_camera_stream(ip, flip_h=False, flip_v=False):
    cap = cv2.VideoCapture(f'rtsp://{ip}')
    if not cap.isOpened():
        return None
    def get_frame():
        ret, frame = cap.read()
        if not ret:
            return None
        if flip_h:
            frame = cv2.flip(frame, 1)
        if flip_v:
            frame = cv2.flip(frame, 0)
        return frame
    return get_frame
