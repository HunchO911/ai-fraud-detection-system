/** "Showing 26–50 of 112" with Previous / Next. `size` must match the page size the server uses. */
export default function Pagination({ page, count, size = 25, onPage }) {
  const pages = Math.max(1, Math.ceil(count / size));
  if (count === 0) return null;
  const from = (page - 1) * size + 1;
  const to = Math.min(count, page * size);
  return (
    <div className="pager">
      <span className="num">Showing {from}–{to} of {count}</span>
      <div>
        <button className="btn btn-sm" disabled={page <= 1} onClick={() => onPage(page - 1)}>Previous</button>
        <button className="btn btn-sm" disabled={page >= pages} onClick={() => onPage(page + 1)}>Next</button>
      </div>
    </div>
  );
}
