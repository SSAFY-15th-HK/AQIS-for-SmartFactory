import { FormEvent, useEffect, useState } from "react";
import { DobotUrdfView } from "./DobotUrdfView";

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

type HeroView = "dobot" | "turtlebot" | "inspection";

const API_BASE =
  import.meta.env.VITE_API_BASE ?? `${window.location.protocol}//${window.location.hostname}:8000`;
const WS_URL = API_BASE.replace(/^http/, "ws") + "/ws";

const initialStats: Stats = {
  system_status: "STOPPED",
  session_total: 0,
  session_defects: 0,
  normal_count: 0,
  defect_rate: 0,
  agv_status: "IDLE",
  recent_detections: [],
};

function ageLabel(stamp?: number, nowMs = Date.now()): string {
  if (!stamp) return "no signal";
  const age = Math.max(0, nowMs / 1000 - stamp);
  if (age < 1) return "live";
  return `${age.toFixed(0)}s ago`;
}

function stale(stamp?: number, limit = 5, nowMs = Date.now()): boolean {
  if (!stamp) return true;
  return nowMs / 1000 - stamp > limit;
}

function percent(value: number): string {
  return `${(value * 100).toFixed(1)}%`;
}

function fixed(value: number | null | undefined, digits = 2): string {
  return typeof value === "number" && Number.isFinite(value) ? value.toFixed(digits) : "-";
}

function tuple(value: unknown, digits = 2): string {
  if (!Array.isArray(value) || value.length === 0) return "-";
  return value
    .map((item) => (typeof item === "number" && Number.isFinite(item) ? item.toFixed(digits) : String(item)))
    .join(", ");
}

function tone(value: string): string {
  const normalized = value.toLowerCase();
  if (normalized.includes("error") || normalized.includes("stop") || normalized.includes("offline")) return "danger";
  if (normalized.includes("running") || normalized.includes("live") || normalized.includes("idle")) return "ok";
  return "muted";
}

function browserReachableUrl(url: string): string {
  try {
    const parsed = new URL(url);
    const pageHost = window.location.hostname;
    const pageIsLocal = pageHost === "localhost" || pageHost === "127.0.0.1";
    const urlIsLocal = parsed.hostname === "localhost" || parsed.hostname === "127.0.0.1";
    if (urlIsLocal && !pageIsLocal) {
      parsed.hostname = pageHost;
    }
    return parsed.toString();
  } catch {
    return url;
  }
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
  const [realsenseSignal, setRealsenseSignal] = useState<"waiting" | "online" | "offline">("waiting");
  const [pending, setPending] = useState(false);
  const [text, setText] = useState("");
  const [responses, setResponses] = useState<AqisEvent[]>([]);
  const [clock, setClock] = useState(Date.now());
  const [activeHero, setActiveHero] = useState<HeroView>("dobot");

  useEffect(() => {
    const timer = window.setInterval(() => setClock(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, []);

  useEffect(() => {
    let cancelled = false;

    fetch(`${API_BASE}/api/runtime/config`)
      .then((response) => response.json())
      .then((runtimeConfig: RuntimeConfig) => {
        if (!cancelled) {
          setConfig((prev) => ({ ...prev, ...runtimeConfig }));
        }
      })
      .catch(() => {
        // The WebSocket will still provide runtime config after reconnect.
      });

    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    let closed = false;
    let reconnectTimer = 0;
    let heartbeatTimer = 0;
    let ws: WebSocket | null = null;

    function connect() {
      ws = new WebSocket(WS_URL);
      ws.onopen = () => {
        setConnected(true);
        window.clearInterval(heartbeatTimer);
        heartbeatTimer = window.setInterval(() => {
          if (ws?.readyState === WebSocket.OPEN) {
            ws.send("ping");
          }
        }, 5000);
      };
      ws.onerror = () => setConnected(false);
      ws.onclose = () => {
        setConnected(false);
        window.clearInterval(heartbeatTimer);
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
      window.clearInterval(heartbeatTimer);
      ws?.close();
    };
  }, []);

  const normalCount = stats.normal_count || Math.max(stats.session_total - stats.session_defects, 0);
  const turtlebotStale = stale(pose?.stamp, 5, clock);
  const dobotStale = stale(dobot.stamp, 5, clock);
  const turtlebotStreamUrl = browserReachableUrl(config.turtlebot_view_url);
  const realsenseStreamUrl = browserReachableUrl(config.realsense_stream_url);
  const shiftTime = new Date(clock).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
  const systemHealth = connected && process.running ? "SYSTEM OPTIMAL" : connected ? "STANDBY LINK" : "LINK LOST";
  const latestDetections = stats.recent_detections.slice(0, 5);
  const latestDetection = latestDetections[0];
  const commandEvents = events.slice(0, 5);
  const dobotJoints = dobot.joints ?? [];
  const liveLinkCount = [connected, realsenseSignal === "online", !turtlebotStale, !dobotStale].filter(Boolean).length;
  const heroTitle =
    activeHero === "dobot" ? "Live Feed" : activeHero === "turtlebot" ? "TurtleBot View" : "RealSense Inspection";
  const heroModeLabel = activeHero === "dobot" ? "Dobot" : activeHero === "turtlebot" ? "TurtleBot" : "Inspection";
  const heroSignal =
    activeHero === "dobot"
      ? dobot.stamp ? ageLabel(dobot.stamp, clock) : "Waiting"
      : activeHero === "turtlebot"
        ? ageLabel(pose?.stamp, clock)
        : realsenseSignal;

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
    if (pending) return;
    const userText = text.trim();
    if (!userText) return;
    setText("");
    const result = await post("/api/text-command", { text: userText });
    if (!connected) {
      setResponses((prev) => [{ type: "text_command", data: { ...result, user_text: userText } }, ...prev].slice(0, 8));
    }
  }

  function viewTitle(view: HeroView): string {
    if (view === "dobot") return "Dobot Action Monitor";
    if (view === "turtlebot") return "TurtleBot View";
    return "RealSense Inspection";
  }

  function viewSignal(view: HeroView): string {
    if (view === "dobot") return dobot.stamp ? ageLabel(dobot.stamp, clock) : "waiting";
    if (view === "turtlebot") return ageLabel(pose?.stamp, clock);
    return realsenseSignal;
  }

  function viewSignalClass(view: HeroView): string {
    if (view === "dobot") return dobotStale ? "dangerText" : "okText";
    if (view === "turtlebot") return turtlebotStale ? "dangerText" : "okText";
    return realsenseSignal === "online" ? "okText" : "dangerText";
  }

  function renderSecondaryView(view: HeroView) {
    if (view === "dobot") {
      return <DobotUrdfView status={dobot} />;
    }
    if (view === "turtlebot") {
      return <img className="stream" src={turtlebotStreamUrl} alt="TurtleBot camera stream" />;
    }
    return (
      <img
        className="stream"
        src={realsenseStreamUrl}
        alt="RealSense inspection stream"
        onLoad={() => setRealsenseSignal("online")}
        onError={() => setRealsenseSignal("offline")}
      />
    );
  }

  const secondaryViews = (["dobot", "inspection", "turtlebot"] as HeroView[]).filter((view) => view !== activeHero);

  return (
    <main className="opsShell">
      <aside className="leftRail">
        <div className="brandMark">
          <span>AQIS</span>
          <strong>RealOps</strong>
        </div>
        <div className="railControlBlock">
          <p>Operations</p>
          <button className="controlButton start" disabled={pending || process.running} onClick={() => post("/api/aqis/start")}>Start</button>
          <button className="controlButton stop" disabled={pending || !process.running} onClick={() => post("/api/aqis/stop")}>Stop</button>
          <button className="controlButton emergency" disabled={pending} onClick={() => post("/api/emergency_stop")}>E-Stop</button>
        </div>
        <div className="railBlock">
          <p>Monitor</p>
          <button className={`railItem ${activeHero === "dobot" ? "active" : ""}`} type="button" onClick={() => setActiveHero("dobot")}>Live Operations</button>
          <button className={`railItem ${activeHero === "turtlebot" ? "active" : ""}`} type="button" onClick={() => setActiveHero("turtlebot")}>TurtleBot</button>
          <button className={`railItem ${activeHero === "inspection" ? "active" : ""}`} type="button" onClick={() => setActiveHero("inspection")}>Inspection</button>
        </div>
        <div className="railCommandPanel">
          <div className="railCommandHeader">
            <p>System Logs</p>
            <span>LLM</span>
          </div>
          <div className="responseList">
            {responses.length === 0 && <p className="empty small">No commands yet</p>}
            {responses.map((event, index) => (
              <div className="responseRow" key={`${event.type}-${index}`}>
                <span>{event.data.user_text ?? event.type}</span>
                <strong>{event.data.message ?? event.data.assistant_message ?? "-"}</strong>
              </div>
            ))}
          </div>
          <form className="commandForm railCommandForm" onSubmit={submitText}>
            <input
              value={text}
              onChange={(event) => setText(event.target.value)}
              placeholder="Enter command..."
            />
            <button disabled={pending || !text.trim()} type="submit">Send</button>
          </form>
        </div>
      </aside>

      <section className="commandDeck">
        <header className="deckHeader">
          <div>
            <p>Dashboard / Manufacturing / Sector 7G</p>
            <h1>Smart Factory Operations</h1>
          </div>
          <div className="headerCluster">
            <span className={`statusChip ${connected ? "ok" : "danger"}`}>{systemHealth}</span>
            <span className="shiftBadge">SHIFT 2<br />{shiftTime}</span>
          </div>
        </header>

        <section className="kpiStrip">
          <article>
            <span>AQIS State</span>
            <strong className={tone(stats.system_status) === "danger" ? "dangerText" : "okText"}>{stats.system_status}</strong>
            <em>{process.running ? `PID ${process.pid}` : "monitoring stopped"}</em>
          </article>
          <article>
            <span>Inspected</span>
            <strong>{stats.session_total}</strong>
            <em>{normalCount} normal</em>
          </article>
          <article>
            <span>Defects</span>
            <strong className={stats.session_defects ? "dangerText" : "okText"}>{stats.session_defects}</strong>
            <em>{percent(stats.defect_rate)} defect rate</em>
          </article>
          <article>
            <span>Live Links</span>
            <strong className={liveLinkCount >= 3 ? "okText" : "dangerText"}>{liveLinkCount}<small>/4</small></strong>
            <em>ws / cam / turtle / dobot</em>
          </article>
        </section>

        <section className="liveGrid">
          <article className="opsPanel heroPanel">
            <div className="panelHeader">
              <h2><span className="recordDot" /> {heroTitle}</h2>
              <div className="tabSet">
                <span>{heroModeLabel}</span>
                <span>{heroSignal}</span>
              </div>
            </div>
            {activeHero === "dobot" && (
              <>
                <DobotUrdfView status={dobot} />
                <div className="heroTelemetry">
                  <div><span>Tool</span><strong>{dobot.gripper_status ? `Suction ${dobot.gripper_status}` : "Suction Cup"}</strong></div>
                  <div><span>TCP X</span><strong>{fixed(dobot.tcp_pose?.x)}</strong></div>
                  <div><span>TCP Y</span><strong>{fixed(dobot.tcp_pose?.y)}</strong></div>
                  <div><span>TCP Z</span><strong>{fixed(dobot.tcp_pose?.z)}</strong></div>
                  <div><span>Yaw</span><strong>{fixed(dobot.tcp_pose?.yaw)}</strong></div>
                </div>
              </>
            )}
            {activeHero === "turtlebot" && (
              <>
                <img className="heroStream" src={turtlebotStreamUrl} alt="TurtleBot camera stream" />
                <div className="heroTelemetry">
                  <div><span>Source</span><strong>{pose?.source ?? "-"}</strong></div>
                  <div><span>X</span><strong>{fixed(pose?.x)}</strong></div>
                  <div><span>Y</span><strong>{fixed(pose?.y)}</strong></div>
                  <div><span>Yaw</span><strong>{fixed(pose?.yaw)}</strong></div>
                  <div><span>Map</span><strong>{ageLabel(map?.stamp, clock)}</strong></div>
                </div>
              </>
            )}
            {activeHero === "inspection" && (
              <>
                <img
                  className="heroStream"
                  src={realsenseStreamUrl}
                  alt="RealSense inspection stream"
                  onLoad={() => setRealsenseSignal("online")}
                  onError={() => setRealsenseSignal("offline")}
                />
                <div className="heroTelemetry">
                  <div><span>Total</span><strong>{stats.session_total}</strong></div>
                  <div><span>Normal</span><strong>{normalCount}</strong></div>
                  <div><span>Defect</span><strong className="dangerText">{stats.session_defects}</strong></div>
                  <div><span>Rate</span><strong>{percent(stats.defect_rate)}</strong></div>
                  <div><span>Latest</span><strong>{latestDetections[0]?.result ?? "-"}</strong></div>
                </div>
              </>
            )}
          </article>

          <aside className="opsStack">
            <article className="opsPanel qualityPanel">
              <div className="panelHeader">
                <h2>Quality Queue</h2>
                <div className="panelActions">
                  <span>{percent(stats.defect_rate)}</span>
                  <button disabled={pending} className="miniButton secondary" onClick={() => post("/api/stats/reset")}>Reset</button>
                </div>
              </div>
              <div className="metricGrid compactMetrics">
                <div><span>Total</span><strong>{stats.session_total}</strong></div>
                <div><span>Normal</span><strong>{normalCount}</strong></div>
                <div><span>Defect</span><strong className="dangerText">{stats.session_defects}</strong></div>
              </div>
              <div className="detectionList">
                {latestDetections.length === 0 && <p className="empty small">No detection events</p>}
                {latestDetections.map((item, index) => (
                  <div className="detectionRow" key={`${item.part_id ?? index}-${index}`}>
                    <span>{item.part_id ?? `part_${index + 1}`}</span>
                    <b className={item.is_defect || item.result === "defect" ? "dangerText" : "okText"}>
                      {item.is_defect || item.result === "defect" ? "DEFECT" : "NORMAL"}
                    </b>
                  </div>
                ))}
              </div>
            </article>

            <article className="opsPanel detailPanel">
              {activeHero === "dobot" && (
                <>
                  <div className="panelHeader">
                    <h2>Joint Status</h2>
                    <span>{dobotJoints.length ? "tracking" : "waiting"}</span>
                  </div>
                  <div className="jointList">
                    {dobotJoints.slice(0, 5).map((joint) => (
                      <div className="jointRow" key={joint.name}>
                        <span>{joint.name}</span>
                        <meter min="-180" max="180" value={joint.position_deg} />
                        <b>{fixed(joint.position_deg, 1)} deg</b>
                      </div>
                    ))}
                    {!dobotJoints.length && <p className="empty small">Waiting for /dobot_joint_states</p>}
                  </div>
                </>
              )}

              {activeHero === "turtlebot" && (
                <>
                  <div className="panelHeader">
                    <h2>TurtleBot Details</h2>
                    <span className={turtlebotStale ? "dangerText" : "okText"}>{ageLabel(pose?.stamp, clock)}</span>
                  </div>
                  <div className="detailGrid">
                    <div><span>Source</span><strong>{pose?.source ?? "-"}</strong></div>
                    <div><span>Map</span><strong>{ageLabel(map?.stamp, clock)}</strong></div>
                    <div><span>X</span><strong>{fixed(pose?.x)}</strong></div>
                    <div><span>Y</span><strong>{fixed(pose?.y)}</strong></div>
                    <div><span>Yaw</span><strong>{fixed(pose?.yaw)}</strong></div>
                    <div><span>Frame</span><strong>{pose ? "base_footprint" : "-"}</strong></div>
                  </div>
                </>
              )}

              {activeHero === "inspection" && (
                <>
                  <div className="panelHeader">
                    <h2>Inspection Details</h2>
                    <span className={latestDetection ? "okText" : "dangerText"}>{latestDetection ? "tracking" : "waiting"}</span>
                  </div>
                  <div className="detailGrid inspectionDetailGrid">
                    <div><span>Label</span><strong>{latestDetection?.label ?? latestDetection?.defect_class ?? "-"}</strong></div>
                    <div><span>Result</span><strong className={latestDetection?.is_defect ? "dangerText" : "okText"}>{latestDetection?.result ?? "-"}</strong></div>
                    <div><span>Confidence</span><strong>{fixed(latestDetection?.confidence, 3)}</strong></div>
                    <div><span>ROI Hit</span><strong>{typeof latestDetection?.roi_hit === "boolean" ? (latestDetection.roi_hit ? "yes" : "no") : "-"}</strong></div>
                    <div><span>Center</span><strong>{tuple(latestDetection?.center, 0)}</strong></div>
                    <div><span>Depth</span><strong>{fixed(latestDetection?.depth_m, 3)} m</strong></div>
                    <div className="wideDetail"><span>Camera Point</span><strong>{tuple(latestDetection?.camera_point_m, 4)}</strong></div>
                    <div className="wideDetail"><span>ROI</span><strong>{tuple(latestDetection?.roi, 0)}</strong></div>
                  </div>
                </>
              )}
            </article>
          </aside>
        </section>

        <section className="mediaGrid">
          {secondaryViews.map((view) => (
            <article
              className="opsPanel mediaSwapPanel"
              key={view}
              role="button"
              tabIndex={0}
              onClick={() => setActiveHero(view)}
              onKeyDown={(event) => {
                if (event.key === "Enter" || event.key === " ") {
                  event.preventDefault();
                  setActiveHero(view);
                }
              }}
            >
              <div className="panelHeader">
                <h2>{viewTitle(view)}</h2>
                <span className={viewSignalClass(view)}>{viewSignal(view)}</span>
              </div>
              {renderSecondaryView(view)}
            </article>
          ))}
        </section>

      </section>

      <aside className="rightRail">
        <section className="railPanel">
          <h2>System Health</h2>
          <div className={`healthRow ${connected ? "ok" : "danger"}`}><span>WebSocket</span><b>{connected ? "LIVE" : "LOST"}</b></div>
          <div className={`healthRow ${realsenseSignal === "online" ? "ok" : "danger"}`}><span>RealSense</span><b>{realsenseSignal}</b></div>
          <div className={`healthRow ${turtlebotStale ? "danger" : "ok"}`}><span>TurtleBot</span><b>{ageLabel(pose?.stamp, clock)}</b></div>
          <div className={`healthRow ${dobotStale ? "danger" : "ok"}`}><span>Dobot</span><b>{ageLabel(dobot.stamp, clock)}</b></div>
        </section>

        <section className="railPanel turtlePanel">
          <h2>TurtleBot Status</h2>
          <dl>
            <div><dt>Source</dt><dd>{pose?.source ?? "-"}</dd></div>
            <div><dt>Map</dt><dd>{ageLabel(map?.stamp, clock)}</dd></div>
            <div><dt>X</dt><dd>{fixed(pose?.x)}</dd></div>
            <div><dt>Y</dt><dd>{fixed(pose?.y)}</dd></div>
            <div><dt>Yaw</dt><dd>{fixed(pose?.yaw)}</dd></div>
          </dl>
        </section>

        <section className="railPanel">
          <h2>Event Stream</h2>
          <div className="eventList">
            {commandEvents.length === 0 && <p className="empty small">No websocket events</p>}
            {commandEvents.map((event, index) => (
              <div key={`${event.type}-${index}`}>
                <b>{event.type}</b>
                <span>{JSON.stringify(event.data).slice(0, 86)}</span>
              </div>
            ))}
          </div>
        </section>
      </aside>
    </main>
  );
}
