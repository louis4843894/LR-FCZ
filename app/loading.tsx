export default function Loading() {
  return (
    <main className="page-main" aria-live="polite" aria-busy="true">
      <div className="loading-panel">
        <span className="loading-spinner" aria-hidden="true" />
        <p>正在讀取已發布的遊戲文字資料…</p>
      </div>
    </main>
  );
}
