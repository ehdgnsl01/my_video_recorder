import cv2 as cv
import datetime

# --- 전역 변수 (flip/crop 관련) ---
flip_enabled = False            # 오른쪽 화살표로 토글
crop_select_mode = False        # z 키로 crop 선택 모드 활성화/해제
confirmed_crop_rect = None      # 최종 crop 영역 (None이면 전체 프레임 사용)
mouse_xy = (0, 0)               # 현재 마우스 위치

# crop zoom 박스 관련 설정 (영역 크기는 반경 단위)
zoom_level = 10                 # 확대 배율
zoom_box_radius = 20            # crop할 영역의 반경 (픽셀 단위)
zoom_box_margin = 10            # zoom 박스를 붙일 위치 여백

def mouse_callback(event, x, y, flags, param):
    global mouse_xy
    mouse_xy = (x, y)

# --- 기본 설정 ---
video_file = 0  # 웹캠 사용
target_format = 'avi'
target_fourcc = 'XVID'

# 웹캠 열기
video = cv.VideoCapture(video_file)
assert video.isOpened(), 'Cannot read the given video'

# VideoWriter 객체 미리 생성 (아직 open되지 않음)
target = cv.VideoWriter()

# 먼저 한 프레임을 읽어 영상의 크기와 컬러 여부 확인
ret, img = video.read()
if not ret:
    print("No frame captured from video source.")
    exit(1)
orig_h, orig_w, *_ = img.shape
is_color = (img.ndim > 2) and (img.shape[2] > 1)

# FPS 값 가져오기 (만약 FPS가 0이면 기본 30으로 설정)
fps = video.get(cv.CAP_PROP_FPS)
if fps == 0:
    fps = 30
wait_msec = int(1000 / fps)

recording = False  # 초기엔 preview 모드

# 미리보기 창 생성 및 마우스 콜백 등록
cv.namedWindow('Video Player')
cv.setMouseCallback('Video Player', mouse_callback)

while True:
    ret, img = video.read()
    if not ret:
        break

    # 원본 프레임을 복사하여 변환에 사용할 프레임
    frame_transformed = img.copy()

    # flip 적용 (좌우반전)
    if flip_enabled:
        frame_transformed = cv.flip(frame_transformed, 1)

    # 만약 최종 crop 영역이 확정되어 있다면, 그 영역으로 프레임을 잘라냄
    if confirmed_crop_rect is not None:
        x, y, w, h = confirmed_crop_rect
        # 좌표 보정: 프레임 범위 내에서만 crop
        x = max(0, x)
        y = max(0, y)
        w = min(w, frame_transformed.shape[1] - x)
        h = min(h, frame_transformed.shape[0] - y)
        frame_transformed = frame_transformed[y:y+h, x:x+w]

    # 최종 표시용 이미지 (녹화 파일에는 오버레이 제외)
    display_img = frame_transformed.copy()

    # crop 선택 모드일 때: 현재 마우스 위치에서 zoom 박스를 추출해 미리보기 창에 표시
    if crop_select_mode:
        h_disp, w_disp = frame_transformed.shape[:2]
        # 마우스 위치가 충분히 떨어져 있어야 crop 가능
        if (mouse_xy[0] >= zoom_box_radius and mouse_xy[0] < (w_disp - zoom_box_radius) and 
            mouse_xy[1] >= zoom_box_radius and mouse_xy[1] < (h_disp - zoom_box_radius)):
            # 현재 마우스 위치 주변의 작은 영역 crop
            crop_img = frame_transformed[mouse_xy[1]-zoom_box_radius:mouse_xy[1]+zoom_box_radius,
                                         mouse_xy[0]-zoom_box_radius:mouse_xy[0]+zoom_box_radius]
            # 확대 (zoom) 처리
            zoom_box = cv.resize(crop_img, None, fx=zoom_level, fy=zoom_level, interpolation=cv.INTER_NEAREST)
            # 붙일 위치 (좌측 상단 여백)
            s = zoom_box_margin
            e_y = s + zoom_box.shape[0]
            e_x = s + zoom_box.shape[1]
            # zoom 박스 영역에 오버레이 (화면에 표시)
            display_img[s:e_y, s:e_x] = zoom_box

            # 또한, zoom 박스 경계 표시 (녹색)
            cv.rectangle(display_img, (s, s), (e_x-1, e_y-1), (0, 255, 0), 2)

    # 녹화 중이면 미리보기 창에 빨간 테두리 표시
    if recording:
        cv.rectangle(display_img, (0, 0), (display_img.shape[1]-1, display_img.shape[0]-1), (0, 0, 255), 2)

    cv.imshow('Video Player', display_img)
    key = cv.waitKey(wait_msec) & 0xFF

    if key == 27:  # ESC 키: 종료
        break
    elif key == 32:  # 스페이스바: 녹화 모드 토글
        if recording:
            recording = False
            target.release()
            print("Recording stopped.")
        else:
            recording = True
            # 녹화 시작 시점: 현재 프레임(변환 후)의 크기로 VideoWriter 열기
            rec_h, rec_w = frame_transformed.shape[:2]
            target_file = datetime.datetime.now().strftime("record_%Y%m%d_%H%M%S.") + target_format
            target.open(target_file, cv.VideoWriter_fourcc(*target_fourcc), fps, (rec_w, rec_h), is_color)
            assert target.isOpened(), 'Cannot open the given video, ' + target_file + '.'
            print("Recording started:", target_file)
    elif key == ord('x'):  # x 키로 좌우반전 토글
        flip_enabled = not flip_enabled
        print("Flip mode:", "ON" if flip_enabled else "OFF")
    elif key == ord('z'):
        # z 키를 눌렀을 때 crop 선택 모드 토글 (두 번째 누르면 해제)
        if crop_select_mode:
            crop_select_mode = False
            confirmed_crop_rect = None  # crop 영역 적용 취소 (전체 프레임 사용)
            print("Crop mode disabled.")
        else:
            crop_select_mode = True
            print("Crop mode enabled. Use mouse to preview crop region; press 'z' again to cancel crop.")
    # 녹화 중이면 기록 (녹화 파일에는 오버레이나 zoom 박스 없이 원본 변환된 프레임 기록)
    if recording:
        target.write(frame_transformed)

video.release()
cv.destroyAllWindows()
