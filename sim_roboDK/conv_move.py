from robodk import robolink
from robodk.robomath import *
import time

RDK = robolink.Robolink()

# =========================
# 이름 설정
# =========================
CONV_BASE_NAME = "Conveyor Belt (2m) Base"
MAIN_FRAME_NAME = "MainFrame"

BOX_NAMES = ["Yellow", "Red", "Green", "Blue"]

conv_base = RDK.Item(CONV_BASE_NAME)
main_frame = RDK.Item(MAIN_FRAME_NAME)

if not conv_base.Valid():
    raise Exception("Conveyor Belt (2m) Base를 찾을 수 없습니다.")

if not main_frame.Valid():
    raise Exception("MainFrame을 찾을 수 없습니다. 왼쪽 트리 이름을 확인하세요.")

boxes = {}

for name in BOX_NAMES:
    box = RDK.Item(name)
    if not box.Valid():
        raise Exception(f"{name} 박스를 찾을 수 없습니다.")
    boxes[name] = box


# =========================
# 초기 위치
# 현재 화면 기준 예상값
# 필요하면 여기 숫자만 수정하면 됨
# [X, Y, Z, RX, RY, RZ]
# =========================
INITIAL_POSES = {
    "Yellow": [200, 200, 0, 0, 0, 0],
    "Red":    [400, 200, 0, 0, 0, 0],
    "Green":  [600, 200, 0, 0, 0, 0],
    "Blue":   [800, 200, 0, 0, 0, 0],
}

# =========================
# 컨베이어 설정
# =========================
STEP_X = 200          # 한 번에 200mm 이동
SUB_STEP = 10         # 10mm씩 나눠서 부드럽게 이동
MOVE_DELAY = 0.02
STOP_DELAY = 0.4

PICK_X = 1000         # 나중에 로봇팔 Pick 위치
BELT_END_X = 2000     # 벨트 끝
RELEASE_X = 2200      # 벨트 끝보다 조금 더 나가면 떨어짐

FALL_DEPTH = 100      # 떨어지는 깊이
GRAVITY = 2500        # 낙하 가속도 느낌, mm/s^2
FALL_DT = 0.03


# =========================
# 유틸 함수
# =========================
def set_box_parent_to_conveyor(box):
    abs_pose = box.PoseAbs()
    box.setParentStatic(conv_base)
    box.setPoseAbs(abs_pose)


def reset_boxes():
    for name, box in boxes.items():
        box.setVisible(True)

        # 다시 컨베이어 기준으로 종속
        set_box_parent_to_conveyor(box)

        # 컨베이어 기준 초기 위치로 세팅
        box.setPose(TxyzRxyz_2_Pose(INITIAL_POSES[name]))

    RDK.Render()
    print("박스 초기 위치 세팅 완료")


def get_local_xyz(box):
    return Pose_2_TxyzRxyz(box.Pose())


def set_local_xyz(box, xyzrxyz):
    box.setPose(TxyzRxyz_2_Pose(xyzrxyz))


def get_local_x(box):
    return get_local_xyz(box)[0]


def move_box_local_x(box, dx):
    xyz = get_local_xyz(box)
    xyz[0] += dx
    set_local_xyz(box, xyz)


def move_conveyor_200(active_names):
    """
    컨베이어를 200mm 이동.
    실제로는 박스들을 10mm씩 나눠 이동시켜서 부드럽게 보이게 함.
    """
    count = int(abs(STEP_X) / SUB_STEP)
    dx = SUB_STEP if STEP_X > 0 else -SUB_STEP

    for _ in range(count):
        for name in active_names:
            move_box_local_x(boxes[name], dx)

        RDK.Render()
        time.sleep(MOVE_DELAY)


def detach_and_fall(name):
    """
    컨베이어 끝을 지난 박스를 MainFrame 기준으로 바꾸고,
    Z값을 점점 낮춰서 중력처럼 떨어지는 연출.
    """
    box = boxes[name]

    print(f"{name}: 컨베이어 종속 해제 후 낙하 시작")

    # 현재 절대 위치 저장
    abs_pose = box.PoseAbs()

    # 컨베이어에서 분리해서 MainFrame 아래로 이동
    box.setParentStatic(main_frame)
    box.setPoseAbs(abs_pose)

    # 절대좌표 기준으로 떨어뜨리기
    xyz = Pose_2_TxyzRxyz(box.PoseAbs())
    start_z = xyz[2]

    velocity = 0.0

    while xyz[2] > start_z - FALL_DEPTH:
        velocity += GRAVITY * FALL_DT
        xyz[2] -= velocity * FALL_DT

        # 벨트에서 튀어나가는 느낌을 조금 주고 싶으면 X도 살짝 이동
        xyz[0] += 30 * FALL_DT

        box.setPoseAbs(TxyzRxyz_2_Pose(xyz))

        RDK.Render()
        time.sleep(FALL_DT)

    print(f"{name}: 낙하 완료")


# =========================
# 실행
# =========================
reset_boxes()

active_names = BOX_NAMES[:]
cycle = 0

print("컨베이어 이동 시작")

while len(active_names) > 0:
    cycle += 1

    print(f"\nCycle {cycle}: 컨베이어 200mm 이동")
    move_conveyor_200(active_names)

    print("컨베이어 정지")
    time.sleep(STOP_DELAY)

    # 나중에 로봇팔 넣을 때 확인용
    for name in active_names:
        x = get_local_x(boxes[name])
        if abs(x - PICK_X) <= 20:
            print(f"{name}이 Pick 위치 X={PICK_X} 근처에 있음")

    # 벨트 끝보다 조금 더 나간 박스는 떨어뜨림
    arrived = []

    for name in active_names:
        x = get_local_x(boxes[name])

        if x >= RELEASE_X:
            arrived.append(name)

    for name in arrived:
        active_names.remove(name)
        detach_and_fall(name)

    if cycle > 30:
        print("안전 종료: cycle이 너무 많습니다. STEP_X 방향을 확인하세요.")
        break

print("\n컨베이어 테스트 완료")