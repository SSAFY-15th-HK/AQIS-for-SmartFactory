from robodk import robolink
from robodk.robomath import *
import time
import math
import threading

RDK = robolink.Robolink()

# =========================================================
# RoboDK 아이템 이름
# =========================================================
ROBOT_NAME = "UR5"
TOOL_NAME = "OnRobot VG10 Vacuum Gripper"

CONV_BASE_NAME = "Conveyor Belt (2m) Base"
MAIN_FRAME_NAME = "MainFrame"

TURTLE_NAME = "turtlebot Base"

BOX_NAMES = ["Yellow", "Red", "Green", "Blue"]

TARGET_HOME = "Home"
TARGET_PICK = "Target 2"      # Red X=1400 감지 후 집는 위치
TARGET_MID = "Target 3"       # 로봇 중간 경유 위치
TARGET_PLACE = "Target 4"     # TurtleBot 위에 놓는 위치

# =========================================================
# 공정 파라미터
# =========================================================

# Red를 detect해서 컨베이어를 멈출 X 좌표
DETECT_X = 1400.0

# 컨베이어 이동 속도 설정
# 값이 클수록 빠름
CONVEYOR_SPEED = 250.0      # mm/s
CONVEYOR_DT = 0.03          # sec
CONVEYOR_DX = CONVEYOR_SPEED * CONVEYOR_DT

# 컨베이어 끝 / 낙하 설정
RELEASE_X = 2200.0
FALL_DEPTH = 100.0
GRAVITY = 2500.0
FALL_DT = 0.03

# 로봇 속도
ROBOT_SPEED = 100

# TurtleBot 이동 속도
AGV_SPEED = 350.0
AGV_DT = 0.03

# =========================================================
# 초기 박스 위치
# 컨베이어 기준 local pose
# [X, Y, Z, RX, RY, RZ]
# =========================================================
INITIAL_POSES = {
    "Yellow": [200, 200, 0, 0, 0, 0],
    "Red":    [400, 200, 0, 0, 0, 0],
    "Green":  [600, 200, 0, 0, 0, 0],
    "Blue":   [800, 200, 0, 0, 0, 0],
}

# =========================================================
# TurtleBot 시작 위치 + 불량 저장 위치 경로
# [X, Y, Z]
# =========================================================
AGV_START = [1210, -2510, 20]

# 현재 Prog2에서 쓰던 경로를 불량 저장 위치 이동 경로로 사용
# 마지막 좌표가 불량 저장 위치라고 보면 됨
DEFECT_STORAGE_PATH = [
    [2560, -1140, 20],   # Frame 5
    [-340, -780, 20],    # Frame 4
    [330, -380, 20],     # Frame 3
    [1960, -450, 20],    # Frame 2
    [2640, -20, 20],     # Frame 1 / 불량 저장 위치
]
# =========================================================
# RoboDK 아이템 찾기
# =========================================================
robot = RDK.Item(ROBOT_NAME)
tool = RDK.Item(TOOL_NAME)

conv_base = RDK.Item(CONV_BASE_NAME)
main_frame = RDK.Item(MAIN_FRAME_NAME)

turtle_base = RDK.Item(TURTLE_NAME)

home = RDK.Item(TARGET_HOME)
target_pick = RDK.Item(TARGET_PICK)
target_mid = RDK.Item(TARGET_MID)
target_place = RDK.Item(TARGET_PLACE)

boxes = {}
for name in BOX_NAMES:
    boxes[name] = RDK.Item(name)

red_box = boxes["Red"]

# =========================================================
# 병렬 실행 시 RoboDK API 충돌 방지용 Lock
# =========================================================
RDK_LOCK = threading.RLock()

# =========================================================
# 내부 상태 이벤트
# RoboDK setParam/getParam 대신 Python Event 사용
# =========================================================
red_detected_event = threading.Event()
load_ready_event = threading.Event()
agv_done_event = threading.Event()
conveyor_done_event = threading.Event()

# =========================================================
# 검증 함수
# =========================================================
def check(item, name):
    if not item.Valid():
        raise Exception(f"'{name}' 을 찾을 수 없습니다. RoboDK 왼쪽 트리 이름을 확인하세요.")

def check_all_items():
    check(robot, ROBOT_NAME)
    check(tool, TOOL_NAME)

    check(conv_base, CONV_BASE_NAME)
    check(main_frame, MAIN_FRAME_NAME)

    check(turtle_base, TURTLE_NAME)

    check(home, TARGET_HOME)
    check(target_pick, TARGET_PICK)
    check(target_mid, TARGET_MID)
    check(target_place, TARGET_PLACE)

    for name, box in boxes.items():
        check(box, name)

# =========================================================
# Pose / 좌표 유틸
# =========================================================
def make_pose(x, y, z, yaw_deg=0):
    return transl(x, y, z) * rotz(math.radians(yaw_deg))

def calc_yaw_deg(p1, p2):
    dx = p2[0] - p1[0]
    dy = p2[1] - p1[1]
    return math.degrees(math.atan2(dy, dx))

def get_local_xyz(item):
    with RDK_LOCK:
        return Pose_2_TxyzRxyz(item.Pose())

def set_local_xyz(item, xyzrxyz):
    with RDK_LOCK:
        item.setPose(TxyzRxyz_2_Pose(xyzrxyz))

def get_local_x(item):
    xyz = get_local_xyz(item)
    return xyz[0]

def move_box_local_x(box, dx):
    with RDK_LOCK:
        xyz = Pose_2_TxyzRxyz(box.Pose())
        xyz[0] += dx
        box.setPose(TxyzRxyz_2_Pose(xyz))

def safe_render():
    with RDK_LOCK:
        RDK.Render()

# =========================================================
# 초기화
# =========================================================
def set_box_parent_to_conveyor(box):
    with RDK_LOCK:
        abs_pose = box.PoseAbs()
        box.setParentStatic(conv_base)
        box.setPoseAbs(abs_pose)

def reset_boxes():
    print("[RESET] 박스 초기 위치 세팅")

    for name, box in boxes.items():
        with RDK_LOCK:
            box.setVisible(True)

        set_box_parent_to_conveyor(box)

        with RDK_LOCK:
            box.setPose(TxyzRxyz_2_Pose(INITIAL_POSES[name]))

    safe_render()
    print("[RESET] 박스 초기 위치 세팅 완료")

def reset_agv():
    print("[RESET] TurtleBot 시작 위치 세팅")

    start_yaw = calc_yaw_deg(AGV_START, DEFECT_STORAGE_PATH[0])

    with RDK_LOCK:
        turtle_base.setPoseAbs(
            make_pose(
                AGV_START[0],
                AGV_START[1],
                AGV_START[2],
                start_yaw
            )
        )

    safe_render()
    print("[RESET] TurtleBot 시작 위치 세팅 완료")

def reset_robot():
    print("[RESET] UR5 Home 이동")

    with RDK_LOCK:
        robot.setSpeed(ROBOT_SPEED)

    robot.MoveJ(home)

    print("[RESET] UR5 Home 이동 완료")

def reset_scene():
    print("\n========== 1. Scene Reset ==========")

    red_detected_event.clear()
    load_ready_event.clear()
    agv_done_event.clear()
    conveyor_done_event.clear()

    reset_boxes()
    reset_agv()
    reset_robot()
    # RoboDK Station Param도 표시용으로만 세팅
    # 실제 로직 판단은 Python Event로 처리
    with RDK_LOCK:
        RDK.setParam("RED_DETECTED", "0")
        RDK.setParam("LOAD_READY", "0")
        RDK.setParam("AGV_DONE", "0")
        RDK.setParam("CONVEYOR_DONE", "0")

    time.sleep(0.5)

# =========================================================
# 컨베이어 연속 이동
# Red가 X=1400에 도달하면 정지
# 200mm씩 멈추는 방식이 아니라 계속 이동
# =========================================================
def conveyor_until_red_detect():
    print("\n========== 2. Conveyor Move Until Red Detect ==========")
    print(f"[CONVEYOR] Red detect 기준 X = {DETECT_X}")

    active_names = BOX_NAMES[:]

    while True:
        red_x_before = get_local_x(red_box)

        # 이번 스텝에서 Red가 DETECT_X를 넘어갈 예정이면,
        # 정확히 DETECT_X까지만 이동시키고 정지
        if red_x_before + CONVEYOR_DX >= DETECT_X:
            remaining_dx = DETECT_X - red_x_before

            if remaining_dx < 0:
                remaining_dx = 0

            for name in active_names:
                move_box_local_x(boxes[name], remaining_dx)

            safe_render()

            red_x_after = get_local_x(red_box)
            print(f"[DETECT] Red 감지됨. Red X = {red_x_after:.1f}")
            print("[CONVEYOR] 컨베이어 정지")

            red_detected_event.set()

            with RDK_LOCK:
                RDK.setParam("RED_DETECTED", "1")

            break

        # 일반 연속 이동
        for name in active_names:
            move_box_local_x(boxes[name], CONVEYOR_DX)

        safe_render()
        time.sleep(CONVEYOR_DT)

        red_x = get_local_x(red_box)

        # 안전 종료
        if red_x > RELEASE_X:
            raise Exception(
                f"[ERROR] Red가 감지되지 않고 RELEASE_X를 지났습니다. "
                f"현재 Red X={red_x:.1f}, DETECT_X={DETECT_X}"
            )

    print("[CONVEYOR] Red detect 단계 완료")

# =========================================================
# UR5가 Red를 집어서 TurtleBot 위에 적재
# =========================================================
def pick_red_to_turtlebot():
    print("\n========== 3. UR5 Pick Red -> TurtleBot ==========")

    if not red_detected_event.is_set():
        raise Exception("[UR5] Red가 detect되지 않았습니다. Pick 동작을 중단합니다.")

    with RDK_LOCK:
        robot.setSpeed(ROBOT_SPEED)

    print("[UR5] Home 이동")
    robot.MoveJ(home)

    print("[UR5] Pick 위치 이동")
    robot.MoveJ(target_pick)
    time.sleep(0.3)

    print("[UR5] Red 흡착")
    with RDK_LOCK:
        red_abs_pose = red_box.PoseAbs()
        red_box.setParentStatic(tool)
        red_box.setPoseAbs(red_abs_pose)

    safe_render()
    time.sleep(0.3)

    print("[UR5] 중간 위치 이동")
    robot.MoveJ(target_mid)

    print("[UR5] TurtleBot 위 Place 위치 이동")
    robot.MoveJ(target_place)
    time.sleep(0.3)

    print("[UR5] Red를 TurtleBot 위에 놓기")
    with RDK_LOCK:
        red_abs_pose = red_box.PoseAbs()
        red_box.setParentStatic(turtle_base)
        red_box.setPoseAbs(red_abs_pose)

    safe_render()
    time.sleep(0.3)

    print("[UR5] 중간 위치 복귀")
    robot.MoveJ(target_mid)

    print("[UR5] Home 복귀")
    robot.MoveJ(home)

    load_ready_event.set()

    with RDK_LOCK:
        RDK.setParam("LOAD_READY", "1")

    print("[UR5] Red 적재 완료. LOAD_READY = 1")

# =========================================================
# 박스 낙하 연출
# =========================================================
def detach_and_fall(name):
    box = boxes[name]

    print(f"[CONVEYOR] {name}: 컨베이어 끝 도달. 낙하 시작")

    with RDK_LOCK:
        abs_pose = box.PoseAbs()
        box.setParentStatic(main_frame)
        box.setPoseAbs(abs_pose)

        xyz = Pose_2_TxyzRxyz(box.PoseAbs())
        start_z = xyz[2]

    velocity = 0.0

    while xyz[2] > start_z - FALL_DEPTH:
        velocity += GRAVITY * FALL_DT
        xyz[2] -= velocity * FALL_DT
        xyz[0] += 30 * FALL_DT

        with RDK_LOCK:
            box.setPoseAbs(TxyzRxyz_2_Pose(xyz))
            RDK.Render()

        time.sleep(FALL_DT)
        print(f"[CONVEYOR] {name}: 낙하 완료")

# =========================================================
# 병렬 작업 1
# Red 제외 나머지 박스 컨베이어 계속 이동
# =========================================================
def conveyor_rest_worker():
    print("\n========== Parallel A. Conveyor Rest Start ==========")

    # Red는 TurtleBot에 실렸으므로 제외
    active_names = ["Yellow", "Green", "Blue"]

    while len(active_names) > 0:
        for name in active_names:
            move_box_local_x(boxes[name], CONVEYOR_DX)

        safe_render()
        time.sleep(CONVEYOR_DT)

        arrived = []

        for name in active_names:
            x = get_local_x(boxes[name])

            if x >= RELEASE_X:
                arrived.append(name)

        for name in arrived:
            active_names.remove(name)
            detach_and_fall(name)

    conveyor_done_event.set()

    with RDK_LOCK:
        RDK.setParam("CONVEYOR_DONE", "1")

    print("[CONVEYOR] 나머지 박스 이동 완료. CONVEYOR_DONE = 1")

# =========================================================
# TurtleBot 부드러운 이동
# =========================================================
def move_smooth_abs(item, target_pose, speed=350.0, dt=0.03):
    with RDK_LOCK:
        start_pose = item.PoseAbs()

    start = Pose_2_TxyzRxyz(start_pose)
    target = Pose_2_TxyzRxyz(target_pose)

    dx = target[0] - start[0]
    dy = target[1] - start[1]

    dist = math.sqrt(dx * dx + dy * dy)
    steps = max(1, int(dist / (speed * dt)))

    for i in range(1, steps + 1):
        ratio = i / steps

        now = [
            start[j] + (target[j] - start[j]) * ratio
            for j in range(6)
        ]

        with RDK_LOCK:
            item.setPoseAbs(TxyzRxyz_2_Pose(now))
            RDK.Render()

        time.sleep(dt)

# =========================================================
# 병렬 작업 2
# TurtleBot이 불량 저장 위치로 이동
# =========================================================
def agv_to_defect_storage_worker():
    print("\n========== Parallel B. TurtleBot To Defect Storage Start ==========")

    if not load_ready_event.is_set():
        print("[AGV] LOAD_READY가 아닙니다. TurtleBot 이동 취소.")
        return

    print("[AGV] Red 적재 확인. 불량 저장 위치로 이동 시작")

    current = AGV_START[:]

    for idx, wp in enumerate(DEFECT_STORAGE_PATH):

        target_pose = make_pose(
            wp[0],
            wp[1],
            wp[2],
            0
        )

        print(
            f"[AGV] Waypoint {idx + 1} 이동: "
            f"X={wp[0]}, Y={wp[1]}, Z={wp[2]}, Yaw={0}"
        )

        move_smooth_abs(
            turtle_base,
            target_pose,
            speed=AGV_SPEED,
            dt=AGV_DT
        )

        current = wp[:]

    agv_done_event.set()

    with RDK_LOCK:
        RDK.setParam("AGV_DONE", "1")

    print("[AGV] 불량 저장 위치 도착. AGV_DONE = 1")

# =========================================================
# TurtleBot과 컨베이어 병렬 실행
# =========================================================
def run_parallel_agv_and_conveyor():
    print("\n========== 4. Parallel Process Start ==========")
    print("[PARALLEL] TurtleBot 이동과 컨베이어 이동을 동시에 실행합니다.")

    agv_thread = threading.Thread(target=agv_to_defect_storage_worker)
    conveyor_thread = threading.Thread(target=conveyor_rest_worker)

    agv_thread.start()
    conveyor_thread.start()

    agv_thread.join()
    conveyor_thread.join()

    print("[PARALLEL] TurtleBot 이동과 컨베이어 이동 모두 완료")

# =========================================================
# Main Sequence
# =========================================================
def main():
    check_all_items()

    print("\n==============================================")
    print("AQIS RoboDK Main Sequence Start")
    print("==============================================")

    reset_scene()

    # 1. 컨베이어가 계속 이동하다가 Red가 X=1400에서 detect되면 정지
    conveyor_until_red_detect()
    # 2. UR5가 Red를 집어서 TurtleBot 위로 이동
    pick_red_to_turtlebot()

    # 3. Red 적재 후 TurtleBot 이동 + 컨베이어 이동 병렬 실행
    run_parallel_agv_and_conveyor()

    print("\n==============================================")
    print("AQIS RoboDK Main Sequence Done")
    print("==============================================")

main()