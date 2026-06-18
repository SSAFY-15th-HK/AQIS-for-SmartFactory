import { FormEvent, useEffect, useMemo, useState } from "react";

type AqisEvent = {
  type: string;
  data: Record<string, any>;
};

type MapState = {
  image: string;
  width: number;
  height: number;
  resolution: number;
  origin: { x: number; y: number; yaw: number };
  stamp: number;
};

type TurtlebotPose = {
  source: string;
  x: number;
  y: number;
  z: number;
  yaw: number;
  stamp: number;
};

type DobotJoint = {
  name: string;
  position_rad: number;
  position_deg: number;
};

type DobotStatus = {
  joints?: DobotJoint[];
  tcp_pose?: { x: number; y: number; z: number; yaw: number };
  raw_pose?: { x: number | null; y: number | null; z: number | null; r: number | null };
  alarms?: number[];
  gripper_status?: string;
  stamp?: number;
};

type Stats = {
  system_status: string;
  session_total: number;
  session_defects: number;
  normal_count: number;
  defect_rate: number;
  defect_bin_load: number;
  defect_threshold: number;
  agv_status: string;
  recent_detections: Array<Record<string, any>>;
};

type ProcessStatus = {
  running: boolean;
  pid: number | null;
  returncode: number | null;
};

type RuntimeConfig = {
  realsense_stream_url: string;
  turtlebot_view_url: string;
  ros_enabled: boolean;
};

const API_BASE =
  import.meta.env.VITE_API_BASE ?? `${window.location.protocol}//${window.location.hostname}:8000`;
const WS_URL = API_BASE.replace(/^http/, "ws") + "/ws";

const initialStats: Stats = {
  system_status: "STOPPED",
  session_total: 0,
  session_defects: 0,
  normal_count: 0,
  defect_rate: 0,
  defect_bin_load: 0,
  defect_threshold: 1,
  agv_status: "IDLE",
  recent_detections: [],
};

function ageLabel(stamp?: number): string {
  if (!stamp) return "no signal";
  const age = Math.max(0, Date.now() / 1000 - stamp);
  if (age < 1) return "live";
  return `${age.toFixed(0)}s ago`;
}

function stale(stamp?: number, limit = 5): boolean {
  if (!stamp) return true;
  return Date.now() / 1000 - stamp > limit;
}

function percent(value: number): string {
  return `${(value * 100).toFixed(1)}%`;
}

function fixed(value: number | null | undefined, digits = 2): string {
  return typeof value === "number" && Number.isFinite(value) ? value.toFixed(digits) : "-";
}

function tone(value: string): string {
  const normalized = value.toLowerCase();
  if (normalized.includes("error") || normalized.includes("stop") || normalized.includes("offline")) return "danger";
  if (normalized.includes("running") || normalized.includes("live") || normalized.includes("idle")) return "ok";
  return "muted";
}

export default function App() {
  const [connected, setConnected] = useState(false);
  const [events, setEvents] = useState<AqisEvent[]>([]);
  const [map, setMap] = useState<MapState | null>(null);
  const [pose, setPose] = useState<TurtlebotPose | null>(null);
  const [dobot, setDobot] = useState<DobotStatus>({});
  const [stats, setStats] = useState<Stats>(initialStats);
  const [process, setProcess] = useState<ProcessStatus>({ running: false, pid: null, returncode: null });
  const [config, setConfig] = useState<RuntimeConfig>({
    realsense_stream_url: "http://localhost:8080/stream",
    turtlebot_view_url: "http://localhost:8081/stream",
    ros_enabled: false,
  });
  const [pending, setPending] = useState(false);
  const [text, setText] = useState("");
  const [responses, setResponses] = useState<AqisEvent[]>([]);

  useEffect(() => {
    let closed = false;
    let reconnectTimer = 0;
    let ws: WebSocket | null = null;

    function connect() {
      ws = new WebSocket(WS_URL);
      ws.onopen = () => setConnected(true);
      ws.onerror = () => setConnected(false);
      ws.onclose = () => {
        setConnected(false);
        if (!closed) {
          reconnectTimer = window.setTimeout(connect, 1200);
        }
      };
      ws.onmessage = (message) => {
        const event = JSON.parse(message.data) as AqisEvent;
        setEvents((prev) => [event, ...prev].slice(0, 24));

        if (event.type === "runtime_config") {
          setConfig((prev) => ({ ...prev, ...(event.data as RuntimeConfig) }));
        }
        if (event.type === "system_status" || event.type === "sim_status") {
          setStats((prev) => ({ ...prev, ...(event.data as Partial<Stats>) }));
        }
        if (event.type === "aqis_process") {
          setProcess((prev) => ({ ...prev, ...(event.data as ProcessStatus) }));
        }
        if (event.type === "map_update") {
          setMap(event.data as MapState);
        }
        if (event.type === "turtlebot_pose") {
          setPose(event.data as TurtlebotPose);
        }
        if (event.type === "dobot_status") {
          setDobot((prev) => ({ ...prev, ...(event.data as DobotStatus) }));
        }
        if (event.type === "detection") {
          setStats((prev) => ({
            ...prev,
            session_total: Number(event.data.session_total ?? prev.session_total),
            session_defects: Number(event.data.session_defects ?? prev.session_defects),
            normal_count: Number(event.data.normal_count ?? prev.normal_count),
            defect_rate: Number(event.data.defect_rate ?? prev.defect_rate),
            defect_bin_load: Number(event.data.defect_bin_load ?? prev.defect_bin_load),
            defect_threshold: Number(event.data.defect_threshold ?? prev.defect_threshold),
          }));
        }
        if (event.type === "text_command" || event.type === "emergency_stop") {
          setResponses((prev) => [event, ...prev].slice(0, 8));
        }
      };
    }

    connect();
    return () => {
      closed = true;
      window.clearTimeout(reconnectTimer);
      ws?.close();
    };
  }, []);

  const marker = useMemo(() => {
    if (!map || !pose) return null;
    const px = (pose.x - map.origin.x) / map.resolution;
    const py = (pose.y - map.origin.y) / map.resolution;
    return {
      left: `${(px / map.width) * 100}%`,
      top: `${100 - (py / map.height) * 100}%`,
      transform: `translate(-50%, -50%) rotate(${pose.yaw}rad)`,
    };
  }, [map, pose]);

  const normalCount = stats.normal_count || Math.max(stats.session_total - stats.session_defects, 0);
  const binProgress = Math.min(100, (stats.defect_bin_load / Math.max(stats.defect_threshold, 1)) * 100);

  async function post(path: string, body?: unknown) {
    setPending(true);
    try {
      const response = await fetch(`${API_BASE}${path}`, {
        method: "POST",
        headers: body ? { "Content-Type": "application/json" } : undefined,
        body: body ? JSON.stringify(body) : undefined,
      });
      return await response.json();
    } finally {
      setPending(false);
    }
  }

  async function submitText(event: FormEvent) {
    event.preventDefault();
    const userText = text.trim();
    if (!userText) return;
    setText("");
    const result = await post("/api/text-command", { text: userText });
    setResponses((prev) => [{ type: "text_command", data: { ...result, user_text: userText } }, ...prev].slice(0, 8));
  }

  return (
    <main className="page">
      <header className="topbar">
        <div>
          <p>AQIS Real Monitoring</p>
          <h1>Smart Factory Operations</h1>
        </div>
        <div className="topStatus">
          <span className={`pill ${connected ? "ok" : "danger"}`}>{connected ? "WebSocket Live" : "Reconnecting"}</span>
          <span className={`pill ${process.running ? "ok" : "muted"}`}>{process.running ? `AQIS PID ${process.pid}` : "AQIS Stopped"}</span>
        </div>
      </header>

      <section className="controls" aria-label="AQIS controls">
        <button disabled={pending || process.running} onClick={() => post("/api/aqis/start")}>Start AQIS</button>
        <button disabled={pending || !process.running} className="secondary" onClick={() => post("/api/aqis/stop")}>Stop</button>
        <button disabled={pending} className="dangerButton" onClick={() => post("/api/emergency_stop")}>Emergency Stop</button>
      </section>

      <section className="statusGrid">
        <article className={`statusTile ${tone(stats.system_status)}`}>
          <span>System</span>
          <strong>{stats.system_status}</strong>
        </article>
        <article className={`statusTile ${stale(map?.stamp) ? "danger" : "ok"}`}>
          <span>Map</span>
          <strong>{ageLabel(map?.stamp)}</strong>
        </article>
        <article className={`statusTile ${stale(pose?.stamp) ? "danger" : "ok"}`}>
          <span>TurtleBot</span>
          <strong>{ageLabel(pose?.stamp)}</strong>
        </article>
        <article className={`statusTile ${stale(dobot.stamp) ? "danger" : "ok"}`}>
          <span>Dobot</span>
          <strong>{ageLabel(dobot.stamp)}</strong>
        </article>
      </section>

      <section className="mainGrid">
        <article className="panel mapPanel">
          <div className="panelHeader">
            <h2>Live SLAM Map</h2>
            <span>{pose ? `${fixed(pose.x)}, ${fixed(pose.y)}` : "waiting for pose"}</span>
          </div>
          <div className="mapStage">
            {map ? <img src={map.image} alt="Live occupancy grid map" /> : <div className="empty">Waiting for /map</div>}
            {marker && <span className="robotMarker" style={marker} title="TurtleBot pose" />}
          </div>
          <dl className="detailList compact">
            <div><dt>Source</dt><dd>{pose?.source ?? "-"}</dd></div>
            <div><dt>Yaw</dt><dd>{fixed(pose?.yaw)}</dd></div>
            <div><dt>Resolution</dt><dd>{map ? `${map.resolution} m/px` : "-"}</dd></div>
          </dl>
        </article>

        <article className="panel qualityPanel">
          <div className="panelHeader">
            <h2>Defect Monitoring</h2>
            <span>{percent(stats.defect_rate)}</span>
          </div>
          <div className="metricGrid">
            <div><span>Total</span><strong>{stats.session_total}</strong></div>
            <div><span>Normal</span><strong>{normalCount}</strong></div>
            <div><span>Defect</span><strong className="dangerText">{stats.session_defects}</strong></div>
            <div><span>Bin</span><strong>{stats.defect_bin_load}/{stats.defect_threshold}</strong></div>
          </div>
          <div className="progressTrack"><div style={{ width: `${binProgress}%` }} /></div>
          <div className="detectionList">
            {stats.recent_detections.length === 0 && <p className="empty small">No detection events</p>}
            {stats.recent_detections.slice(0, 6).map((item, index) => (
              <div className="detectionRow" key={`${item.part_id ?? index}-${index}`}>
                <span>{item.part_id ?? `part_${index + 1}`}</span>
                <b className={item.is_defect || item.result === "defect" ? "dangerText" : "okText"}>
                  {item.is_defect || item.result === "defect" ? "DEFECT" : "NORMAL"}
                </b>
              </div>
            ))}
          </div>
        </article>
      </section>

      <section className="cameraGrid">
        <article className="panel">
          <div className="panelHeader">
            <h2>TurtleBot View</h2>
            <span>MJPEG</span>
          </div>
          <img className="stream" src={config.turtlebot_view_url} alt="TurtleBot camera stream" />
        </article>
        <article className="panel">
          <div className="panelHeader">
            <h2>RealSense Inspection</h2>
            <span>MJPEG</span>
          </div>
          <img className="stream" src={config.realsense_stream_url} alt="RealSense inspection stream" />
        </article>
      </section>

      <section className="lowerGrid">
        <article className="panel">
          <div className="panelHeader">
            <h2>Dobot Magician</h2>
            <span>{dobot.gripper_status ?? "gripper unknown"}</span>
          </div>
          <dl className="detailList">
            <div><dt>TCP X</dt><dd>{fixed(dobot.tcp_pose?.x)}</dd></div>
            <div><dt>TCP Y</dt><dd>{fixed(dobot.tcp_pose?.y)}</dd></div>
            <div><dt>TCP Z</dt><dd>{fixed(dobot.tcp_pose?.z)}</dd></div>
            <div><dt>Alarms</dt><dd>{dobot.alarms?.length ? dobot.alarms.join(", ") : "clear"}</dd></div>
          </dl>
          <div className="jointList">
            {(dobot.joints ?? []).slice(0, 5).map((joint) => (
              <div className="jointRow" key={joint.name}>
                <span>{joint.name}</span>
                <meter min="-180" max="180" value={joint.position_deg} />
                <b>{fixed(joint.position_deg, 1)} deg</b>
              </div>
            ))}
            {!dobot.joints?.length && <p className="empty small">Waiting for /dobot_joint_states</p>}
          </div>
        </article>

        <article className="panel commandPanel">
          <div className="panelHeader">
            <h2>Text Control</h2>
            <span>Server proxy</span>
          </div>
          <form className="commandForm" onSubmit={submitText}>
            <input
              value={text}
              onChange={(event) => setText(event.target.value)}
              placeholder="예: AQIS 시작해, 불량률 알려줘, 도봇 상태 보여줘"
            />
            <button disabled={pending || !text.trim()} type="submit">Send</button>
          </form>
          <div className="responseList">
            {responses.length === 0 && <p className="empty small">No commands yet</p>}
            {responses.map((event, index) => (
              <div className="responseRow" key={`${event.type}-${index}`}>
                <span>{event.data.user_text ?? event.type}</span>
                <strong>{event.data.message ?? event.data.assistant_message ?? "-"}</strong>
              </div>
            ))}
          </div>
        </article>
      </section>

      <section className="eventPanel">
        {events.slice(0, 8).map((event, index) => (
          <span key={`${event.type}-${index}`}>{event.type}</span>
        ))}
      </section>
    </main>
  );
}
