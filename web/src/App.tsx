import { useEffect, useMemo, useState } from "react";

type AqisEvent = {
  type: string;
  data: any;
};

type Stats = {
  total: number;
  defects: number;
  defectRate: number;
};

const API_BASE = "http://localhost:8000";
const WS_URL = "ws://localhost:8000/ws";

function percent(value: number): string {
  return `${Math.round(value * 1000) / 10}%`;
}

export default function App() {
  const [connected, setConnected] = useState(false);
  const [events, setEvents] = useState<AqisEvent[]>([]);
  const [stats, setStats] = useState<Stats>({ total: 0, defects: 0, defectRate: 0 });
  const [mode, setMode] = useState<Record<string, string>>({});
  const [conveyorRunning, setConveyorRunning] = useState(false);
  const [sorterPosition, setSorterPosition] = useState("normal");

  useEffect(() => {
    const ws = new WebSocket(WS_URL);

    ws.onopen = () => setConnected(true);
    ws.onclose = () => setConnected(false);
    ws.onerror = () => setConnected(false);

    ws.onmessage = (message) => {
      const event = JSON.parse(message.data) as AqisEvent;
      setEvents((prev) => [event, ...prev].slice(0, 12));

      if (event.type === "detection") {
        setStats({
          total: event.data.session_total,
          defects: event.data.session_defects,
          defectRate: event.data.defect_rate,
        });
      }

      if (event.type === "system_status") {
        setMode(event.data.mode ?? {});
      }

      if (event.type === "conveyor_status") {
        setConveyorRunning(event.data.running);
        setSorterPosition(event.data.sorter_position);
      }
    };

    return () => ws.close();
  }, []);

  const normalCount = useMemo(() => stats.total - stats.defects, [stats]);

  async function post(path: string) {
    await fetch(`${API_BASE}${path}`, { method: "POST" });
  }

  return (
    <main className="page">
      <section className="hero">
        <div>
          <p className="eyebrow">AQIS Smart Factory</p>
          <h1>Mock-first Dashboard</h1>
          <p className="description">
            하드웨어 없이 Day 1 관통 흐름을 검증하는 대시보드입니다. Mock Detection 버튼을 누르면
            FastAPI 서버가 WebSocket으로 검출 이벤트를 전송합니다.
          </p>
        </div>
        <div className="statusBox">
          <span className={connected ? "dot ok" : "dot bad"} />
          WebSocket: {connected ? "Connected" : "Disconnected"}
        </div>
      </section>

      <section className="grid cards">
        <article className="card">
          <h2>총 검사 수</h2>
          <strong>{stats.total}</strong>
        </article>
        <article className="card">
          <h2>정상 수</h2>
          <strong>{normalCount}</strong>
        </article>
        <article className="card danger">
          <h2>불량 수</h2>
          <strong>{stats.defects}</strong>
        </article>
        <article className="card">
          <h2>불량률</h2>
          <strong>{percent(stats.defectRate)}</strong>
        </article>
      </section>

      <section className="panel">
        <h2>Controls</h2>
        <div className="buttons">
          <button onClick={() => post("/api/mock/detection")}>Mock Detection 발생</button>
          <button onClick={() => post("/api/mock/detection?color=red")}>Red Defect 발생</button>
          <button onClick={() => post("/api/conveyor/start")}>Conveyor Start</button>
          <button onClick={() => post("/api/conveyor/stop")}>Conveyor Stop</button>
          <button className="stop" onClick={() => post("/api/emergency_stop")}>Emergency STOP</button>
        </div>
      </section>

      <section className="grid two">
        <article className="panel">
          <h2>System Mode</h2>
          <dl className="modeList">
            <div><dt>Conveyor</dt><dd>{mode.conveyor ?? "unknown"}</dd></div>
            <div><dt>Vision</dt><dd>{mode.vision ?? "unknown"}</dd></div>
            <div><dt>Robot</dt><dd>{mode.robot ?? "unknown"}</dd></div>
            <div><dt>Voice</dt><dd>{mode.voice ?? "unknown"}</dd></div>
          </dl>
        </article>

        <article className="panel">
          <h2>Conveyor Status</h2>
          <p>Running: <b>{conveyorRunning ? "true" : "false"}</b></p>
          <p>Sorter Position: <b>{sorterPosition}</b></p>
          <div className={`belt ${conveyorRunning ? "running" : ""}`}>
            <span /> <span /> <span /> <span />
          </div>
        </article>
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
