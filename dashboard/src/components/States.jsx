/** Loading, empty and error states, written as directions rather than moods. */

export function Loading({ text = "Loading…" }) {
  return (
    <div className="state" role="status">
      <div className="spinner" />
      <span>{text}</span>
    </div>
  );
}

export function Empty({ title, children }) {
  return (
    <div className="state">
      <strong>{title}</strong>
      {children && <span>{children}</span>}
    </div>
  );
}

export function ErrorNotice({ error, onRetry }) {
  if (!error) return null;
  return (
    <div className="notice error" role="alert">
      {error.message}{" "}
      {onRetry && (
        <button className="btn btn-sm" onClick={onRetry} style={{ marginLeft: 8 }}>Try again</button>
      )}
    </div>
  );
}
