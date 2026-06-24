import { type CSSProperties, useEffect, useMemo, useState } from "react";

type AqisEvent = {
  type: string;
  data: Record<string, any>;
};

type Detection = {
  part_id?: string;
  color?: string;
  result?: string;
  is_defect?: boolean;
  session_total?: number;
};

type SimStats = {
  system_status: string;
  conveyor_status: string;
  robodk_status: string;
  session_total: number;
  session_defects: number;
  normal_count: number;
  defect_rate: number;
  defect_bin_load: number;
  defect_threshold: number;
  agv_status: string;
  current_mission_id: string | null;
  completed_missions: number;
  agv_waypoint_index: number | null;
  agv_waypoint_total: number | null;
  agv_position: { x: number; y: number; z: number } | null;
  agv_message: string;
  recent_detections: Detection[];
};

const API_BASE = "http://localhost:8000";
const WS_URL = "ws://localhost:8000/ws";

const CONVEYOR_VIEW = {
  flowDuration: 16,
  parts: [
    { id: "bottlecap-normal-1", variant: "normal", startLeft: "10%" },
    { id: "bottlecap-defect-1", variant: "defect", startLeft: "24%" },
    { id: "bottlecap-normal-2", variant: "normal", startLeft: "38%" },
    { id: "bottlecap-normal-3", variant: "normal", startLeft: "52%" },
  ],
};

const initialStats: SimStats = {
  system_status: "STOPPED",
  conveyor_status: "OFF",
  robodk_status: "UNKNOWN",
  session_total: 0,
  session_defects: 0,
  normal_count: 0,
  defect_rate: 0,
  defect_bin_load: 0,
  defect_threshold: 3,
  agv_status: "IDLE",
  current_mission_id: null,
  completed_missions: 0,
  agv_waypoint_index: null,
  agv_waypoint_total: null,
  agv_position: null,
  agv_message: "",
  recent_detections: [],
};

function percent(value: number): string {
  return `${Math.round(value * 1000) / 10}%`;
}

function statusTone(status: string): string {
  if (status === "DISCONNECTED") return "danger";
  if (status === "PAUSED" || status.includes("RESET")) return "warn";
  if (["RUNNING", "CONNECTED", "ON", "IDLE", "MOVING_TO_DEFECT_BIN"].includes(status)) return "ok";
  return "muted";
}

function isDefectDetection(item: Detection): boolean {
  return item.is_defect || item.result === "defect";
}

function bottleCapLabel(item: Detection): string {
  return isDefectDetection(item) ? "병뚜껑 불량" : "병뚜껑 정상";
}

function bottleCapDisplayId(item: Detection, index: number): string {
  const raw = item.part_id ?? `bottlecap_${item.session_total ?? index + 1}`;
  const status = isDefectDetection(item) ? "defect" : "normal";
  return raw.replace(/^robodk_(red|yellow|green|blue)_/i, `bottlecap_${status}_`);
}

function partStyle(startLeft: string): CSSProperties & Record<string, string> {
  return {
    "--start-left": startLeft,
    "--flow-duration": `${CONVEYOR_VIEW.flowDuration}s`,
  };
}

export default function App() {
  const [connected, setConnected] = useState(false);
  const [events, setEvents] = useState<AqisEvent[]>([]);
  const [stats, setStats] = useState<SimStats>(initialStats);
  const [sorterPosition, setSorterPosition] = useState("normal");
  const [robodkStage, setRobodkStage] = useState("IDLE");
  const [robodkMessage, setRobodkMessage] = useState("RoboDK script has not reported yet.");
  const [flowResetKey, setFlowResetKey] = useState(0);
  const [pending, setPending] = useState(false);

  useEffect(() => {
    const ws = new WebSocket(WS_URL);

    ws.onopen = () => setConnected(true);
    ws.onclose = () => setConnected(false);
    ws.onerror = () => setConnected(false);

    ws.onmessage = (message) => {
      const event = JSON.parse(message.data) as AqisEvent;
      setEvents((prev) => [event, ...prev].slice(0, 10));

      if (event.type === "sim_status" || event.type === "system_status") {
        setStats((prev) => ({ ...prev, ...(event.data as Partial<SimStats>) }));
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
          agv_status: String(event.data.agv_status ?? prev.agv_status),
        }));
      }

      if (event.type === "conveyor_status") {
        setSorterPosition(String(event.data.sorter_position ?? "normal"));
      }

      if (event.type === "robodk_status") {
        const nextStage = String(event.data.stage ?? "IDLE");
        setRobodkStage(nextStage);
        setRobodkMessage(String(event.data.message ?? ""));
        setStats((prev) => ({
          ...prev,
          robodk_status: event.data.connected
            ? event.data.running
              ? "RUNNING"
              : "CONNECTED"
            : "DISCONNECTED",
        }));
      }

      if (event.type === "agv_mission") {
        setStats((prev) => ({
          ...prev,
          agv_status: String(event.data.status ?? prev.agv_status),
          defect_bin_load: Number(event.data.defect_bin_load ?? prev.defect_bin_load),
          completed_missions: Number(event.data.completed_missions ?? prev.completed_missions),
          current_mission_id: (event.data.mission_id as string | null) ?? prev.current_mission_id,
          agv_waypoint_index: event.data.waypoint_index ?? prev.agv_waypoint_index,
          agv_waypoint_total: event.data.waypoint_total ?? prev.agv_waypoint_total,
          agv_position: event.data.position ?? prev.agv_position,
          agv_message: String(event.data.message ?? prev.agv_message),
        }));
      }
    };

    return () => ws.close();
  }, []);

  const normalCount = useMemo(
    () => stats.normal_count || Math.max(stats.session_total - stats.session_defects, 0),
    [stats.normal_count, stats.session_total, stats.session_defects],
  );

  const agvProgress = useMemo(() => {
    if (!stats.agv_waypoint_total) return 0;
    return Math.min(100, ((stats.agv_waypoint_index ?? 0) / stats.agv_waypoint_total) * 100);
  }, [stats.agv_waypoint_index, stats.agv_waypoint_total]);

  const binProgress = Math.min(100, (stats.defect_bin_load / Math.max(stats.defect_threshold, 1)) * 100);
  const conveyorParts = CONVEYOR_VIEW.parts;
  const isRunning = stats.system_status === "RUNNING";
  const isPaused = stats.system_status === "PAUSED";
  const isStopped = stats.system_status === "STOPPED";
  const processClass = isRunning ? "running" : isPaused ? "paused" : "stopped";
  const lastEvent = events[0];
  const lastEventText = lastEvent
    ? String(lastEvent.data.stage ?? lastEvent.data.status ?? lastEvent.data.result ?? lastEvent.data.message ?? "-")
    : "No event";
  const statusItems = [
    ["System", stats.system_status],
    ["RoboDK", stats.robodk_status],
    ["Conveyor", stats.conveyor_status],
    ["TurtleBot", stats.agv_status],
  ];

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

  async function resetFlow() {
    await post("/api/sim/reset");
    setFlowResetKey((prev) => prev + 1);
  }

  return (
    <main className="page">
      <header className="topbar">
        <div>
          <p className="eyebrow">AQIS Monitoring</p>
          <h1>RoboDK 캔 리드 검사 모니터링</h1>
        </div>
        <div className={`connection ${connected ? "ok" : "danger"}`}>
          <span />
          {connected ? "Live" : "Offline"}
        </div>
      </header>

      <section className="controlBar" aria-label="simulation controls">
        <button disabled={pending} className={isRunning ? "active" : ""} onClick={() => post("/api/sim/start")}>Start</button>
        <button disabled={pending} className={`secondary ${isPaused ? "active" : ""}`} onClick={() => post("/api/sim/pause")}>Pause</button>
        <button disabled={pending} className={`secondary ${isStopped ? "active" : ""}`} onClick={() => post("/api/sim/stop")}>Stop</button>
        <button disabled={pending} className="secondary" onClick={resetFlow}>Reset</button>
      </section>

      <section className={`activityStrip ${processClass}`}>
        <div>
          <span>Current</span>
          <strong>{stats.system_status}</strong>
        </div>
        <div>
          <span>Last Event</span>
          <strong>{lastEvent ? lastEvent.type : "none"}</strong>
          <small>{lastEventText}</small>
        </div>
        <div>
          <span>Network</span>
          <strong>{connected ? "CONNECTED" : "OFFLINE"}</strong>
        </div>
      </section>

      <section className="statusGrid">
        {statusItems.map(([label, value]) => (
          <article className={`statusTile ${statusTone(value)}`} key={label}>
            <span>{label}</span>
            <strong>{value}</strong>
          </article>
        ))}
      </section>

      <section className="mainGrid">
        <article className={`panel processPanel ${processClass}`}>
          <div className="panelHeader">
            <h2>공정 상태</h2>
            <span className={`stage ${statusTone(robodkStage)}`}>{robodkStage}</span>
          </div>

          <div className={`factoryScene ${processClass}`}>
            <div
              className={`conveyor ${isRunning ? "running" : ""}`}
              key={flowResetKey}
            >
              {conveyorParts.map((part) => (
                <span
                  className="part canLid"
                  key={part.id}
                  style={partStyle(part.startLeft)}
                  title="Bottle cap"
                />
              ))}
            </div>
          </div>

          <div className="processFooter">
            <div>
              <span>Conveyor</span>
              <b className={statusTone(stats.conveyor_status)}>{stats.conveyor_status}</b>
            </div>
            <div>
              <span>Sorter</span>
              <b>{sorterPosition}</b>
            </div>
            <div>
              <span>Message</span>
              <b>{robodkMessage || stats.agv_message || "대기 중"}</b>
            </div>
          </div>
        </article>

        <article className="panel">
          <div className="panelHeader">
            <h2>캔 리드 검사 집계</h2>
            <span className="stage muted">Bottle Caps {stats.session_total}</span>
          </div>
          <div className="metricGrid">
            <div>
              <span>검사 수</span>
              <strong>{stats.session_total}</strong>
            </div>
            <div>
              <span>정상</span>
              <strong>{normalCount}</strong>
            </div>
            <div>
              <span>불량</span>
              <strong className="danger">{stats.session_defects}</strong>
            </div>
            <div>
              <span>불량률</span>
              <strong>{percent(stats.defect_rate)}</strong>
            </div>
          </div>

          <h3>최근 캔 리드 검사</h3>
          <div className="detectionList">
            {stats.recent_detections.length === 0 && <p className="empty">검사 이벤트 없음</p>}
            {stats.recent_detections.slice(0, 5).map((item, index) => (
              <div className="detectionRow" key={`${item.part_id ?? index}-${index}`}>
                <span className="colorDot can" />
                <div>
                  <strong>{bottleCapDisplayId(item, index)}</strong>
                  <small>{bottleCapLabel(item)}</small>
                </div>
                <b className={isDefectDetection(item) ? "danger" : "ok"}>
                  {isDefectDetection(item) ? "불량" : "정상"}
                </b>
              </div>
            ))}
          </div>
        </article>
      </section>

      <section className="lowerGrid">
        <article className="panel">
          <div className="panelHeader">
            <h2>AGV 진행</h2>
            <span className="stage muted">{stats.current_mission_id ?? "no mission"}</span>
          </div>
          <div className="progressBlock">
            <div className="progressLabel">
              <span>Waypoint</span>
              <b>{stats.agv_waypoint_index ?? 0} / {stats.agv_waypoint_total ?? 0}</b>
            </div>
            <div className="progressTrack"><div style={{ width: `${agvProgress}%` }} /></div>
          </div>
          <div className="progressBlock">
            <div className="progressLabel">
              <span>Defective Cap Bin</span>
              <b>{stats.defect_bin_load} / {stats.defect_threshold}</b>
            </div>
            <div className="progressTrack bin"><div style={{ width: `${binProgress}%` }} /></div>
          </div>
          <dl className="detailList">
            <div><dt>완료 미션</dt><dd>{stats.completed_missions}</dd></div>
            <div><dt>위치</dt><dd>{stats.agv_position ? `${Math.round(stats.agv_position.x)}, ${Math.round(stats.agv_position.y)}` : "-"}</dd></div>
          </dl>
        </article>

        <article className="panel">
          <div className="panelHeader">
            <h2>이벤트 로그</h2>
            <span className="stage muted">{events.length}</span>
          </div>
          <div className="eventList">
            {events.length === 0 && <p className="empty">이벤트 없음</p>}
            {events.map((event, index) => (
              <div className={`eventRow ${index === 0 ? "latest" : ""}`} key={`${event.type}-${index}`}>
                <span>{event.type}</span>
                <small>{event.data.stage ?? event.data.status ?? event.data.result ?? event.data.message ?? "-"}</small>
              </div>
            ))}
          </div>
        </article>
      </section>
    </main>
  );
}
