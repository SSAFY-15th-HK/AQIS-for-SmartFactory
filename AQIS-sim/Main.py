from robodk import robolink
from robodk.robomath import *
import time
import math
import threading
import json
import uuid
from urllib import request, error

RDK = robolink.Robolink()
SCRIPT_ID = f"robodk-{uuid.uuid4().hex}"

# =========================================================
# Web UI / FastAPI 연동 설정
# =========================================================
# FastAPI 서버를 WSL 또는 Windows에서 실행한 뒤 주소를 맞추면 됨.
# 보통 같은 PC에서 실행하면 http://localhost:8000 사용.
API_BASE = "http://localhost:8000"
API_TIMEOUT = 0.3
ENABLE_WEB_UI_SYNC = True
COMMAND_POLL_DT = 0.25
RENDER_MIN_DT = 0.08
WEB_STATUS_MIN_DT = 0.5

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
TARGET_PICK = "Target 2"      # Red 감지 후 집는 위치
TARGET_MID = "Target 3"       # 로봇 중간 경유 위치
TARGET_PLACE = "Target 4"     # TurtleBot 위에 놓는 위치

# =========================================================
# 공정 파라미터
# =========================================================
# Red를 detect해서 컨베이어를 멈출 X 좌표
DETECT_X = 1400
DETECT_TOL = 10

# 컨베이어 연속 이동 속도 설정
CONVEYOR_SPEED = 250      # mm/s
CONVEYOR_DT = 0.03        # sec
CONVEYOR_DX = CONVEYOR_SPEED * CONVEYOR_DT

# 컨베이어 끝 / 낙하 설정
RELEASE_X = 2200
FALL_DEPTH = 100
GRAVITY = 2500
FALL_DT = 0.03

# 로봇 속도
ROBOT_SPEED = 100

# TurtleBot 이동 속도
AGV_SPEED = 350
AGV_DT = 0.03

# =========================================================
# 초기 박스 위치: 컨베이어 기준 local pose [X, Y, Z, RX, RY, RZ]
# =========================================================
INITIAL_POSES = {
    "Yellow": [200, 200, 0, 0, 0, 0],
    "Red":    [400, 200, 0, 0, 0, 0],
    "Green":  [600, 200, 0, 0, 0, 0],
    "Blue":   [800, 200, 0, 0, 0, 0],
}

# =========================================================
# TurtleBot 시작 위치 + 불량 저장 위치 경로 [X, Y, Z]
# =========================================================
AGV_START = [1210, -2510, 20]

# 마지막 좌표를 불량 저장 위치로 사용
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

# 병렬 실행 시 RoboDK API 충돌 방지용 Lock
RDK_LOCK = threading.RLock()
LAST_RENDER_AT = 0.0
LAST_STATUS_SENT_AT = 0.0
LAST_STATUS_PAYLOAD = None

# 같은 Python 스크립트 안의 공정 분기에는 RoboDK Param보다 로컬 상태를 우선 사용.
# 일부 RoboDK 실행 환경에서 RDK.setParam("KEY", "1") 후 RDK.getParam("KEY")가
# 바로 문자열 "1"로 돌아오지 않아 분기 오류가 생길 수 있다.
STATE = {
    "red_detected": False,
    "load_ready": False,
    "agv_done": False,
    "conveyor_done": False,
    "paused": False,
    "stop_requested": False,
    "reset_requested": False,
    "last_command": None,
}
DETECTED_NAMES = set()

# =========================================================
# Web UI 연동 유틸
# =========================================================
class StopRequested(Exception):
    pass


class ResetRequested(Exception):
    pass


def api_request(method, path, payload=None, log_fail=True):
    """FastAPI 서버와 통신한다. 실패해도 RoboDK 시뮬레이션 자체는 계속 실행한다."""
    if not ENABLE_WEB_UI_SYNC:
        return None

    url = API_BASE + path
    data = None
    headers = {}

    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    try:
        req = request.Request(url, data=data, headers=headers, method=method)
        with request.urlopen(req, timeout=API_TIMEOUT) as res:
            raw = res.read().decode("utf-8")
            if raw:
                return json.loads(raw)
            return None
    except Exception as exc:
        if log_fail:
            print(f"[WEB_UI] {method} 실패: {path} / {exc}")
        return None


def api_post(path, payload=None):
    return api_request("POST", path, payload)


def api_get(path, log_fail=True):
    return api_request("GET", path, None, log_fail=log_fail)


def notify_web_status(stage, message="", running=True, red_x=None, force=False):
    global LAST_STATUS_PAYLOAD, LAST_STATUS_SENT_AT

    payload = {
        "script_id": SCRIPT_ID,
        "connected": True,
        "running": running,
        "stage": stage,
        "message": message,
    }
    if red_x is not None:
        payload["red_x"] = red_x

    now = time.monotonic()
    with RDK_LOCK:
        if (
            not force
            and payload == LAST_STATUS_PAYLOAD
            and now - LAST_STATUS_SENT_AT < WEB_STATUS_MIN_DT
        ):
            return
        LAST_STATUS_PAYLOAD = payload.copy()
        LAST_STATUS_SENT_AT = now

    api_post("/api/robodk/status", payload)


def notify_web_reset():
    print("[WEB_UI] RoboDK Reset 상태 전송")
    notify_web_status("RESET", "RoboDK scene reset", running=False, force=True)


def notify_web_detection(color_name, x, result):
    color = color_name.lower()
    is_defect = result == "defect"
    print(f"[WEB_UI] Detection 이벤트 전송: {color} / {result} / X={x:.1f}")
    api_post(
        "/api/sim/detection",
        {
            "part_id": f"robodk_{color}_{int(time.time() * 1000)}",
            "color": color,
            "result": result,
            "source": "robodk",
            "script_id": SCRIPT_ID,
            "confidence": 0.99 if is_defect else 0.96,
            "x": x,
        },
    )


def mark_detected_once(name):
    with RDK_LOCK:
        if name in DETECTED_NAMES:
            return False
        DETECTED_NAMES.add(name)
        return True


def notify_web_agv_dispatch():
    print("[WEB_UI] AGV Dispatch 이벤트 전송")
    api_post("/api/sim/agv/dispatch", {"source": "robodk", "script_id": SCRIPT_ID})


def notify_web_agv_state(status, message="", waypoint_index=None, waypoint_total=None, position=None):
    payload = {
        "source": "robodk",
        "script_id": SCRIPT_ID,
        "status": status,
        "message": message,
    }
    if waypoint_index is not None:
        payload["waypoint_index"] = waypoint_index
    if waypoint_total is not None:
        payload["waypoint_total"] = waypoint_total
    if position is not None:
        payload["x"] = position[0]
        payload["y"] = position[1]
        payload["z"] = position[2]
    api_post("/api/sim/agv/state", payload)


def notify_web_stop():
    print("[WEB_UI] RoboDK Stop 상태 전송")
    notify_web_status("STOPPED", "RoboDK sequence stopped", running=False, force=True)


def apply_command(command):
    if not command:
        return
    with RDK_LOCK:
        STATE["last_command"] = command
        if command == "PAUSE":
            STATE["paused"] = True
        elif command == "START":
            STATE["paused"] = False
        elif command == "STOP":
            STATE["paused"] = False
            STATE["stop_requested"] = True
        elif command == "RESET":
            STATE["paused"] = False
            STATE["reset_requested"] = True
        elif command == "DISPATCH_AGV":
            # 실제 AGV 이동은 Red 적재 후 Main 시퀀스에서 수행한다. 여기서는 명령 수신만 기록.
            pass
    print(f"[WEB_UI] Command 수신: {command}")


def poll_web_command_once(log_fail=False):
    data = api_get(f"/api/robodk/command?script_id={SCRIPT_ID}", log_fail=log_fail)
    if isinstance(data, dict):
        apply_command(data.get("command"))


def command_listener_worker():
    print("[WEB_UI] Web command listener 시작")
    while True:
        poll_web_command_once(log_fail=False)
        with RDK_LOCK:
            if STATE["stop_requested"] or STATE["reset_requested"]:
                break
        time.sleep(COMMAND_POLL_DT)
    print("[WEB_UI] Web command listener 종료")


def wait_if_paused_or_interrupted():
    while True:
        with RDK_LOCK:
            if STATE["stop_requested"]:
                raise StopRequested()
            if STATE["reset_requested"]:
                raise ResetRequested()
            paused = STATE["paused"]
        if not paused:
            return
        notify_web_status("PAUSED", "RoboDK sequence paused", running=False)
        time.sleep(COMMAND_POLL_DT)


def controlled_sleep(seconds):
    end_time = time.time() + seconds
    while time.time() < end_time:
        wait_if_paused_or_interrupted()
        time.sleep(min(COMMAND_POLL_DT, max(0, end_time - time.time())))


def wait_for_web_start_command():
    print("[WEB_UI] Web UI에서 Simulation Start를 누를 때까지 대기합니다.")
    notify_web_status("READY", "Waiting for Web UI START", running=False, force=True)
    while True:
        poll_web_command_once(log_fail=True)
        with RDK_LOCK:
            command = STATE["last_command"]
            if command == "START":
                STATE["last_command"] = None
                STATE["stop_requested"] = False
                STATE["reset_requested"] = False
                STATE["paused"] = False
                return
        time.sleep(COMMAND_POLL_DT)

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


def get_local_x(item):
    xyz = get_local_xyz(item)
    return xyz[0]


def move_box_local_x(box, dx):
    with RDK_LOCK:
        xyz = Pose_2_TxyzRxyz(box.Pose())
        xyz[0] += dx
        box.setPose(TxyzRxyz_2_Pose(xyz))


def safe_render(force=False):
    global LAST_RENDER_AT

    now = time.monotonic()
    with RDK_LOCK:
        if not force and now - LAST_RENDER_AT < RENDER_MIN_DT:
            return
        RDK.Render()
        LAST_RENDER_AT = now

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
            make_pose(AGV_START[0], AGV_START[1], AGV_START[2], start_yaw)
        )

    safe_render()
    print("[RESET] TurtleBot 시작 위치 세팅 완료")


def reset_robot():
    print("[RESET] UR5 Home 이동")

    with RDK_LOCK:
        robot.setSpeed(ROBOT_SPEED)

    wait_if_paused_or_interrupted()
    robot.MoveJ(home)
    print("[RESET] UR5 Home 이동 완료")


def reset_scene():
    print("\n========== 1. Scene Reset ==========")

    notify_web_reset()

    reset_boxes()
    reset_agv()
    reset_robot()

    with RDK_LOCK:
        STATE["red_detected"] = False
        STATE["load_ready"] = False
        STATE["agv_done"] = False
        STATE["conveyor_done"] = False
        STATE["stop_requested"] = False
        STATE["reset_requested"] = False
        DETECTED_NAMES.clear()
        RDK.setParam("RED_DETECTED", "0")
        RDK.setParam("LOAD_READY", "0")
        RDK.setParam("AGV_DONE", "0")
        RDK.setParam("CONVEYOR_DONE", "0")

    controlled_sleep(0.5)

# =========================================================
# 컨베이어 연속 이동: Red가 X=1400에 도달하면 정지
# =========================================================
def conveyor_until_red_detect():
    print("\n========== 2. Conveyor Move Until Red Detect ==========")
    print(f"[CONVEYOR] Detect 기준 X = {DETECT_X} (정상/불량 모두 처리)")
    notify_web_status("CONVEYOR", "Conveyor moving and vision detection active", running=True)

    active_names = BOX_NAMES[:]
    while True:
        wait_if_paused_or_interrupted()
        # 컨베이어 위 활성 박스들을 계속 이동. 200mm 단위 정지가 아니라 연속 이동.
        for name in active_names:
            move_box_local_x(boxes[name], CONVEYOR_DX)

        safe_render()
        controlled_sleep(CONVEYOR_DT)

        for name in active_names:
            x = get_local_x(boxes[name])
            if x >= DETECT_X - DETECT_TOL and mark_detected_once(name):
                if name == "Red":
                    print(f"[DETECT] Red 불량 감지됨. Red X = {x:.1f}")
                    print("[CONVEYOR] Red pick을 위해 컨베이어 정지")

                    with RDK_LOCK:
                        STATE["red_detected"] = True
                        RDK.setParam("RED_DETECTED", "1")

                    notify_web_detection("Red", x, "defect")
                    notify_web_status("RED_DETECTED", "Red defect detected; conveyor stopped for UR5 pick", running=True, red_x=x)
                    print("[CONVEYOR] Red detect 단계 완료")
                    return
                else:
                    print(f"[DETECT] {name} 정상 감지됨. X = {x:.1f}")
                    notify_web_detection(name, x, "normal")

        red_x = get_local_x(red_box)
        if red_x > RELEASE_X:
            raise Exception(
                f"[ERROR] Red가 감지되지 않고 RELEASE_X를 지났습니다. "
                f"현재 Red X={red_x:.1f}, DETECT_X={DETECT_X}"
            )

# =========================================================
# UR5가 Red를 집어서 TurtleBot 위에 적재
# =========================================================
def pick_red_to_turtlebot():
    print("\n========== 3. UR5 Pick Red -> TurtleBot ==========")
    notify_web_status("UR5_PICK", "UR5 picking red defect to TurtleBot", running=True)

    with RDK_LOCK:
        red_detected = STATE["red_detected"]

    if not red_detected:
        raise Exception("[UR5] Red가 detect되지 않았습니다. Pick 동작을 중단합니다.")

    with RDK_LOCK:
        robot.setSpeed(ROBOT_SPEED)

    print("[UR5] Home 이동")
    wait_if_paused_or_interrupted()
    robot.MoveJ(home)

    print("[UR5] Pick 위치 이동")
    wait_if_paused_or_interrupted()
    robot.MoveJ(target_pick)
    controlled_sleep(0.3)

    print("[UR5] Red 흡착")
    with RDK_LOCK:
        red_abs_pose = red_box.PoseAbs()
        red_box.setParentStatic(tool)
        red_box.setPoseAbs(red_abs_pose)

    safe_render()
    controlled_sleep(0.3)

    print("[UR5] 중간 위치 이동")
    wait_if_paused_or_interrupted()
    robot.MoveJ(target_mid)

    print("[UR5] TurtleBot 위 Place 위치 이동")
    wait_if_paused_or_interrupted()
    robot.MoveJ(target_place)
    controlled_sleep(0.3)

    print("[UR5] Red를 TurtleBot 위에 놓기")
    with RDK_LOCK:
        red_abs_pose = red_box.PoseAbs()
        red_box.setParentStatic(turtle_base)
        red_box.setPoseAbs(red_abs_pose)

    safe_render()
    controlled_sleep(0.3)

    print("[UR5] 중간 위치 복귀")
    wait_if_paused_or_interrupted()
    robot.MoveJ(target_mid)

    print("[UR5] Home 복귀")
    wait_if_paused_or_interrupted()
    robot.MoveJ(home)

    with RDK_LOCK:
        STATE["load_ready"] = True
        RDK.setParam("LOAD_READY", "1")

    notify_web_agv_dispatch()
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

        safe_render()

        controlled_sleep(FALL_DT)

    print(f"[CONVEYOR] {name}: 낙하 완료")

# =========================================================
# 병렬 작업 1: Red 제외 나머지 박스 컨베이어 계속 이동
# =========================================================
def conveyor_rest_worker():
    print("\n========== Parallel A. Conveyor Rest Start ==========")
    notify_web_status("CONVEYOR_REST", "Normal parts continue to conveyor end", running=True)

    active_names = ["Yellow", "Green", "Blue"]

    while len(active_names) > 0:
        for name in active_names:
            move_box_local_x(boxes[name], CONVEYOR_DX)

        safe_render()
        controlled_sleep(CONVEYOR_DT)

        arrived = []

        for name in active_names:
            x = get_local_x(boxes[name])
            if x >= DETECT_X - DETECT_TOL and mark_detected_once(name):
                print(f"[DETECT] {name} 정상 감지됨. X = {x:.1f}")
                notify_web_detection(name, x, "normal")

            if x >= RELEASE_X:
                arrived.append(name)

        for name in arrived:
            active_names.remove(name)
            detach_and_fall(name)

    with RDK_LOCK:
        STATE["conveyor_done"] = True
        RDK.setParam("CONVEYOR_DONE", "1")

    print("[CONVEYOR] 나머지 박스 이동 완료. CONVEYOR_DONE = 1")

# =========================================================
# TurtleBot 부드러운 절대좌표 이동
# =========================================================
def move_smooth_abs(item, target_pose, speed=350, dt=0.03):
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

        now = [start[j] + (target[j] - start[j]) * ratio for j in range(6)]

        with RDK_LOCK:
            item.setPoseAbs(TxyzRxyz_2_Pose(now))

        safe_render()

        controlled_sleep(dt)

    with RDK_LOCK:
        return Pose_2_TxyzRxyz(item.PoseAbs())

# =========================================================
# 병렬 작업 2: TurtleBot이 불량 저장 위치로 이동
# =========================================================
def agv_to_defect_storage_worker():
    print("\n========== Parallel B. TurtleBot To Defect Storage Start ==========")
    notify_web_status("AGV_MOVING", "TurtleBot moving to defect storage", running=True)

    with RDK_LOCK:
        load_ready = STATE["load_ready"]

    if not load_ready:
        print("[AGV] LOAD_READY가 1이 아닙니다. TurtleBot 이동 취소.")
        return

    print("[AGV] Red 적재 확인. 불량 저장 위치로 이동 시작")
    notify_web_agv_state(
        "MOVING_TO_DEFECT_BIN",
        "TurtleBot started moving to defect storage.",
        waypoint_index=0,
        waypoint_total=len(DEFECT_STORAGE_PATH),
        position=AGV_START,
    )

    current = AGV_START

    for idx, wp in enumerate(DEFECT_STORAGE_PATH):
        yaw = calc_yaw_deg(current, wp)
        target_pose = make_pose(wp[0], wp[1], wp[2], yaw)

        print(
            f"[AGV] Waypoint {idx + 1} 이동: "
            f"X={wp[0]}, Y={wp[1]}, Z={wp[2]}, Yaw={yaw:.1f}"
        )

        final_pose = move_smooth_abs(turtle_base, target_pose, speed=AGV_SPEED, dt=AGV_DT)
        notify_web_agv_state(
            "MOVING_TO_DEFECT_BIN",
            f"TurtleBot reached waypoint {idx + 1}/{len(DEFECT_STORAGE_PATH)}.",
            waypoint_index=idx + 1,
            waypoint_total=len(DEFECT_STORAGE_PATH),
            position=final_pose[:3],
        )
        current = wp

    with RDK_LOCK:
        STATE["agv_done"] = True
        RDK.setParam("AGV_DONE", "1")

    notify_web_agv_state(
        "COMPLETED",
        "TurtleBot arrived at defect storage.",
        waypoint_index=len(DEFECT_STORAGE_PATH),
        waypoint_total=len(DEFECT_STORAGE_PATH),
        position=DEFECT_STORAGE_PATH[-1],
    )
    print("[AGV] 불량 저장 위치 도착. AGV_DONE = 1")

# =========================================================
# TurtleBot과 컨베이어 병렬 실행
# =========================================================
def run_parallel_agv_and_conveyor():
    print("\n========== 4. Parallel Process Start ==========")
    print("[PARALLEL] TurtleBot 이동과 컨베이어 이동을 동시에 실행합니다.")

    errors = []

    def run_worker(worker):
        try:
            worker()
        except Exception as exc:
            with RDK_LOCK:
                errors.append(exc)
                STATE["stop_requested"] = True

    agv_thread = threading.Thread(target=run_worker, args=(agv_to_defect_storage_worker,), name="AGVThread")
    conveyor_thread = threading.Thread(target=run_worker, args=(conveyor_rest_worker,), name="ConveyorThread")

    agv_thread.start()
    conveyor_thread.start()

    agv_thread.join()
    conveyor_thread.join()

    if errors:
        raise errors[0]

    print("[PARALLEL] TurtleBot 이동과 컨베이어 이동 모두 완료")

# =========================================================
# Main Sequence
# =========================================================
def run_sequence_once():
    reset_scene()

    # 1. 컨베이어가 계속 이동하면서 정상품도 detect 처리하고, Red가 X=1400에서 detect되면 정지
    conveyor_until_red_detect()

    # 2. UR5가 Red를 집어서 TurtleBot 위로 이동
    pick_red_to_turtlebot()

    # 3. Red 적재 후 TurtleBot 이동 + 컨베이어 이동 병렬 실행
    run_parallel_agv_and_conveyor()


def main():
    check_all_items()

    print("\n==============================================")
    print("AQIS RoboDK Main Sequence + Web UI Control/Sync Start")
    print("==============================================")

    while True:
        wait_for_web_start_command()
        listener = threading.Thread(target=command_listener_worker, name="WebCommandThread", daemon=True)
        listener.start()

        try:
            notify_web_status("RUNNING", "RoboDK sequence started by Web UI", running=True)
            run_sequence_once()
            notify_web_status("DONE", "RoboDK sequence completed", running=False)
            print("\n==============================================")
            print("AQIS RoboDK Main Sequence + Web UI Sync Done")
            print("==============================================")
        except ResetRequested:
            print("[WEB_UI] Reset command 처리: 장면 초기화 후 다시 START 대기")
            reset_scene()
            notify_web_status("READY", "Reset done. Waiting for Web UI START", running=False)
        except StopRequested:
            print("[WEB_UI] Stop command 처리: 시퀀스 중지 후 다시 START 대기")
            notify_web_stop()
        finally:
            with RDK_LOCK:
                STATE["stop_requested"] = True
            listener.join(timeout=1.0)
            with RDK_LOCK:
                STATE["stop_requested"] = False
                STATE["reset_requested"] = False
                STATE["paused"] = False
                STATE["last_command"] = None


main()
