import { useEffect, useMemo, useState } from "react";

type AqisEvent = {
  type: string;
  data: Record<string, any>;
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
  emergency_stop_active: boolean;
};

type LastDetection = {
  color: string;
  isDefect: boolean;
  confidence: number | null;
};

const API_BASE = "http://localhost:8000";
const WS_URL = "ws://localhost:8000/ws";

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
  emergency_stop_active: false,
};

function percent(value: number): string {
  return `${Math.round(value * 1000) / 10}%`;
}

function statusTone(status: string): "good" | "warn" | "danger" | "idle" {
  if (status.includes("EMERGENCY") || status === "DISCONNECTED") return "danger";
  if (status === "PAUSED") return "warn";
  if (["RUNNING", "ON", "IDLE", "CONNECTED", "MOVING_TO_DEFECT_BIN", "RETURNING"].includes(status)) return "good";
  return "idle";
}

export default function App() {
  const [connected, setConnected] = useState(false);
  const [stats, setStats] = useState<SimStats>(initialStats);
  const [sorterPosition, setSorterPosition] = useState("normal");
  const [lastDetection, setLastDetection] = useState<LastDetection | null>(null);
  const [pending, setPending] = useState(false);

  useEffect(() => {
    const ws = new WebSocket(WS_URL);

    ws.onopen = () => setConnected(true);
    ws.onclose = () => setConnected(false);
    ws.onerror = () => setConnected(false);

    ws.onmessage = (message) => {
      const event = JSON.parse(message.data) as AqisEvent;

      if (event.type === "sim_status") {
        setStats((prev) => ({ ...prev, ...(event.data as Partial<SimStats>) }));
      }

      if (event.type === "detection") {
        setLastDetection({
          color: String(event.data.color ?? "-"),
          isDefect: Boolean(event.data.is_defect),
          confidence: typeof event.data.confidence === "number" ? event.data.confidence : null,
        });
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

      if (event.type === "system_status") {
        setStats((prev) => ({ ...prev, ...(event.data as Partial<SimStats>) }));
      }

      if (event.type === "conveyor_status") {
        setSorterPosition(String(event.data.sorter_position ?? "normal"));
      }

      if (event.type === "robodk_status") {
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
        }));
      }
    };

    return () => ws.close();
  }, []);

  const normalCount = useMemo(
    () => stats.normal_count || Math.max(stats.session_total - stats.session_defects, 0),
    [stats.normal_count, stats.session_total, stats.session_defects],
  );

  const binPercent = Math.min(100, (stats.defect_bin_load / stats.defect_threshold) * 100);
  const isEmergency = stats.emergency_stop_active || stats.system_status.includes("EMERGENCY");

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

  return (
    <main className="page">
      <header className="topBar">
        <div>
          <p className="eyebrow">AQIS Smart Factory</p>
          <h1>검사 시뮬레이션 모니터</h1>
        </div>
        <div className={`connection ${connected ? "good" : "danger"}`}>
          <span />
          {connected ? "서버 연결됨" : "서버 연결 안 됨"}
        </div>
      </header>

      {isEmergency && (
        <section className="alert">
          비상 정지 상태입니다. Reset 후 다시 시작하세요.
        </section>
      )}

      <section className="statusStrip">
        <article>
          <span>시스템</span>
          <strong className={statusTone(stats.system_status)}>{stats.system_status}</strong>
        </article>
        <article>
          <span>컨베이어</span>
          <strong className={statusTone(stats.conveyor_status)}>{stats.conveyor_status}</strong>
        </article>
        <article>
          <span>RoboDK</span>
          <strong className={statusTone(stats.robodk_status)}>{stats.robodk_status}</strong>
        </article>
        <article>
          <span>AGV</span>
          <strong className={statusTone(stats.agv_status)}>{stats.agv_status}</strong>
        </article>
      </section>

      <section className="layout single">
        <article className="workspace panel">
          <div className="panelHeader">
            <div>
              <p className="eyebrow">Process View</p>
              <h2>검사 라인 흐름</h2>
            </div>
            <span className="pill">Sorter: {sorterPosition}</span>
          </div>

          <div className="lineAndResult">
            <div className={`factoryLine ${stats.conveyor_status === "ON" ? "running" : ""}`}>
              <div className="belt">
                <span className="part blue" />
                <span className="part green" />
                <span className="part red" />
                <span className="part yellow" />
              </div>
            </div>

            <div className={`resultBox ${lastDetection?.isDefect ? "defect" : ""}`}>
              <span>검사 결과</span>
              <strong>{lastDetection ? (lastDetection.isDefect ? "불량" : "정상") : "대기"}</strong>
              <p>
                {lastDetection
                  ? `${lastDetection.color} 부품${lastDetection.confidence ? ` / 신뢰도 ${percent(lastDetection.confidence)}` : ""}`
                  : "아직 검사된 부품이 없습니다."}
              </p>
            </div>
          </div>

          <div className="actions">
            <button disabled={pending} onClick={() => post("/api/sim/start")}>시작</button>
            <button disabled={pending} className="secondary" onClick={() => post("/api/sim/reset")}>초기화</button>
            <button disabled={pending} className="dangerButton" onClick={() => post("/api/emergency_stop")}>정지</button>
          </div>
        </article>
      </section>

      <section className="metricGrid">
        <article className="metric">
          <span>전체 검사</span>
          <strong>{stats.session_total}</strong>
        </article>
        <article className="metric">
          <span>정상</span>
          <strong>{normalCount}</strong>
        </article>
        <article className="metric dangerMetric">
          <span>불량</span>
          <strong>{stats.session_defects}</strong>
        </article>
        <article className="metric">
          <span>불량률</span>
          <strong>{percent(stats.defect_rate)}</strong>
        </article>
      </section>

      <section className="bottomGrid single">
        <article className="panel">
          <div className="panelHeader">
            <div>
              <p className="eyebrow">Defect Bin</p>
              <h2>불량함 적재 상태</h2>
            </div>
            <strong>{stats.defect_bin_load} / {stats.defect_threshold}</strong>
          </div>
          <div className="meter">
            <div style={{ width: `${binPercent}%` }} />
          </div>
          <div className="detailList">
            <span>현재 미션</span>
            <b>{stats.current_mission_id ?? "없음"}</b>
            <span>완료 미션</span>
            <b>{stats.completed_missions}</b>
          </div>
        </article>
      </section>
    </main>
  );
}
