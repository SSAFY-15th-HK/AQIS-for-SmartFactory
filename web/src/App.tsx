import { FormEvent, useEffect, useMemo, useState } from "react";

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

type TextMessage = {
  user: string;
  assistant: string;
  intent: string;
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

function statusClass(status: string): string {
  if (status.includes("EMERGENCY")) return "dangerText";
  if (status === "RUNNING" || status === "IDLE" || status === "CONNECTED" || status === "MOCK") return "okText";
  if (status === "PAUSED") return "warnText";
  return "mutedText";
}

export default function App() {
  const [connected, setConnected] = useState(false);
  const [events, setEvents] = useState<AqisEvent[]>([]);
  const [stats, setStats] = useState<SimStats>(initialStats);
  const [mode, setMode] = useState<Record<string, string>>({});
  const [sorterPosition, setSorterPosition] = useState("normal");
  const [command, setCommand] = useState("");
  const [messages, setMessages] = useState<TextMessage[]>([]);
  const [pending, setPending] = useState(false);

  useEffect(() => {
    const ws = new WebSocket(WS_URL);

    ws.onopen = () => setConnected(true);
    ws.onclose = () => setConnected(false);
    ws.onerror = () => setConnected(false);

    ws.onmessage = (message) => {
      const event = JSON.parse(message.data) as AqisEvent;
      setEvents((prev) => [event, ...prev].slice(0, 16));

      if (event.type === "sim_status") {
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

      if (event.type === "system_status") {
        setMode((event.data.mode ?? {}) as Record<string, string>);
        setStats((prev) => ({ ...prev, ...(event.data as Partial<SimStats>) }));
      }

      if (event.type === "conveyor_status") {
        setSorterPosition(String(event.data.sorter_position ?? "normal"));
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

      if (event.type === "text_command") {
        setMessages((prev) => [
          {
            user: String(event.data.user_text ?? ""),
            assistant: String(event.data.assistant_message ?? event.data.message ?? ""),
            intent: String(event.data.intent ?? "UNKNOWN"),
          },
          ...prev,
        ].slice(0, 6));
      }
    };

    return () => ws.close();
  }, []);

  const normalCount = useMemo(
    () => stats.normal_count || Math.max(stats.session_total - stats.session_defects, 0),
    [stats.normal_count, stats.session_total, stats.session_defects],
  );

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

  async function sendTextCommand(event: FormEvent) {
    event.preventDefault();
    const text = command.trim();
    if (!text) return;
    setCommand("");
    const result = await post("/api/text-command", { text });
    setMessages((prev) => [
      { user: text, assistant: String(result.message ?? ""), intent: String(result.intent ?? "UNKNOWN") },
      ...prev,
    ].slice(0, 6));
  }

  async function runDemoSequence() {
    const sequence = [
      { part_id: "part_001", color: "blue", result: "normal" },
      { part_id: "part_002", color: "green", result: "normal" },
      { part_id: "part_003", color: "red", result: "defect" },
      { part_id: "part_004", color: "yellow", result: "normal" },
      { part_id: "part_005", color: "red", result: "defect" },
      { part_id: "part_006", color: "red", result: "defect" },
    ];
    for (const item of sequence) {
      await post("/api/sim/detection", { ...item, source: "ui_demo" });
    }
  }

  return (
    <main className="page">
      <section className="hero">
        <div>
          <p className="eyebrow">AQIS Smart Factory</p>
          <h1>RoboDK Digital Twin Dashboard</h1>
          <p className="description">
            UI 버튼과 텍스트 명령으로 시뮬레이션을 제어하고, 불량품 3개 누적 시 AGV 출동 미션을 자동 실행하는 대시보드입니다.
          </p>
        </div>
        <div className="statusBox">
          <span className={connected ? "dot ok" : "dot bad"} />
          WebSocket: {connected ? "Connected" : "Disconnected"}
        </div>
      </section>

      <section className="grid statusGrid">
        <article className="statusCard">
          <span>System</span>
          <strong className={statusClass(stats.system_status)}>{stats.system_status}</strong>
        </article>
        <article className="statusCard">
          <span>Conveyor</span>
          <strong className={statusClass(stats.conveyor_status)}>{stats.conveyor_status}</strong>
        </article>
        <article className="statusCard">
          <span>RoboDK</span>
          <strong className={statusClass(stats.robodk_status)}>{stats.robodk_status}</strong>
        </article>
        <article className="statusCard">
          <span>AGV</span>
          <strong className={statusClass(stats.agv_status)}>{stats.agv_status}</strong>
        </article>
      </section>

      <section className="grid cards">
        <article className="card">
          <h2>총 검사 수</h2>
          <strong>{stats.session_total}</strong>
        </article>
        <article className="card">
          <h2>정상 수</h2>
          <strong>{normalCount}</strong>
        </article>
        <article className="card danger">
          <h2>불량 수</h2>
          <strong>{stats.session_defects}</strong>
        </article>
        <article className="card">
          <h2>불량률</h2>
          <strong>{percent(stats.defect_rate)}</strong>
        </article>
      </section>

      <section className="grid two">
        <article className="panel">
          <h2>Simulation Controls</h2>
          <div className="buttons">
            <button disabled={pending} onClick={() => post("/api/sim/start")}>Simulation Start</button>
            <button disabled={pending} className="secondary" onClick={() => post("/api/sim/pause")}>Pause</button>
            <button disabled={pending} className="secondary" onClick={() => post("/api/sim/stop")}>Stop</button>
            <button disabled={pending} className="secondary" onClick={() => post("/api/sim/reset")}>Reset</button>
            <button disabled={pending} className="stop" onClick={() => post("/api/emergency_stop")}>Emergency STOP</button>
          </div>
          <div className={`belt ${stats.conveyor_status === "ON" ? "running" : ""}`}>
            <span /> <span /> <span /> <span />
          </div>
          <p className="muted">Sorter Position: <b>{sorterPosition}</b></p>
        </article>

        <article className="panel">
          <h2>Mock / Demo Events</h2>
          <div className="buttons">
            <button disabled={pending} onClick={() => post("/api/mock/detection")}>Mock Detection</button>
            <button disabled={pending} onClick={() => post("/api/mock/detection?color=red")}>Red Defect</button>
            <button disabled={pending} onClick={() => post("/api/sim/detection", { color: "blue", result: "normal", source: "ui" })}>Normal Part</button>
            <button disabled={pending} onClick={runDemoSequence}>Run Demo Sequence</button>
            <button disabled={pending} onClick={() => post("/api/sim/agv/dispatch")}>AGV Dispatch</button>
          </div>
        </article>
      </section>

      <section className="grid two">
        <article className="panel">
          <h2>AGV Mission</h2>
          <div className="missionMeter">
            <div style={{ width: `${Math.min(100, (stats.defect_bin_load / stats.defect_threshold) * 100)}%` }} />
          </div>
          <dl className="modeList">
            <div><dt>Defect Bin Load</dt><dd>{stats.defect_bin_load} / {stats.defect_threshold}</dd></div>
            <div><dt>Mission ID</dt><dd>{stats.current_mission_id ?? "none"}</dd></div>
            <div><dt>AGV Status</dt><dd>{stats.agv_status}</dd></div>
            <div><dt>Completed</dt><dd>{stats.completed_missions}</dd></div>
          </dl>
        </article>

        <article className="panel">
          <h2>System Mode</h2>
          <dl className="modeList">
            <div><dt>Conveyor</dt><dd>{mode.conveyor ?? "mock"}</dd></div>
            <div><dt>Vision</dt><dd>{mode.vision ?? "mock"}</dd></div>
            <div><dt>Robot</dt><dd>{mode.robot ?? "mock"}</dd></div>
            <div><dt>Voice</dt><dd>{mode.voice ?? "text"}</dd></div>
          </dl>
        </article>
      </section>

      <section className="panel">
        <h2>Text Command</h2>
        <form className="commandForm" onSubmit={sendTextCommand}>
          <input
            value={command}
            onChange={(event) => setCommand(event.target.value)}
            placeholder="예: 컨베이어 시작해줘 / 불량품 비워줘 / 현재 불량률 알려줘 / 비상 정지"
          />
          <button disabled={pending || !command.trim()} type="submit">Send</button>
        </form>
        <div className="messages">
          {messages.length === 0 && <p className="muted">아직 텍스트 명령 이력이 없습니다.</p>}
          {messages.map((message, index) => (
            <div className="message" key={`${message.user}-${index}`}>
              <p><b>User:</b> {message.user}</p>
              <p><b>Assistant:</b> {message.assistant}</p>
              <small>{message.intent}</small>
            </div>
          ))}
        </div>
      </section>

      <section className="panel">
        <h2>Recent Events</h2>
        <div className="events">
          {events.length === 0 && <p className="muted">아직 이벤트가 없습니다.</p>}
          {events.map((event, index) => (
            <pre key={index}>{JSON.stringify(event, null, 2)}</pre>
          ))}
        </div>
      </section>
    </main>
  );
}
