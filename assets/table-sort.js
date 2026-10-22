// Sortable registry tables. Progressive enhancement: without this script the
// tables stay readable in their built order.

export function compareValues(a, b, type) {
  if (type === "number") return Number(a) - Number(b);
  return a.toLowerCase().localeCompare(b.toLowerCase());
}

// Returns row indices in display order. Empty values always go last.
// Array.prototype.sort is stable, so ties keep their original order.
export function sortOrder(values, type, direction) {
  const sign = direction === "desc" ? -1 : 1;
  return values
    .map((value, index) => ({ value, index }))
    .sort((x, y) => {
      if (x.value === "" || y.value === "") {
        return (x.value === "") - (y.value === "");
      }
      return sign * compareValues(x.value, y.value, type);
    })
    .map((item) => item.index);
}

function enhance(table) {
  const headers = [...table.querySelectorAll("thead th")];
  const tbody = table.tBodies[0];
  if (!tbody) return;

  headers.forEach((th, column) => {
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = th.textContent;
    th.textContent = "";
    th.append(button);

    button.addEventListener("click", () => {
      const direction = th.getAttribute("aria-sort") === "ascending" ? "descending" : "ascending";
      headers.forEach((other) => other.removeAttribute("aria-sort"));
      th.setAttribute("aria-sort", direction);

      const rows = [...tbody.rows];
      const values = rows.map((row) => row.cells[column].dataset.sort ?? "");
      const type = th.dataset.sortType === "number" ? "number" : "text";
      const order = sortOrder(values, type, direction === "ascending" ? "asc" : "desc");
      tbody.append(...order.map((index) => rows[index]));
    });
  });
}

if (typeof document !== "undefined") {
  document.querySelectorAll("table[data-sortable]").forEach(enhance);
}
