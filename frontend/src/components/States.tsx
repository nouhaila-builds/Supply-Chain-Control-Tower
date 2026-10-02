export function LoadingBlock({ label = "Loading slice" }: { label?: string }) {
  return <div className="state">{label}…</div>;
}

export function EmptyBlock({ label }: { label: string }) {
  return <div className="state">{label}</div>;
}

export function ErrorBlock({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="state error">
      <p>{message}</p>
      {onRetry && (
        <button className="text-btn" onClick={onRetry}>
          Retry
        </button>
      )}
    </div>
  );
}
