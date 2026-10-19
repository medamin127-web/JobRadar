import type { CountryCount, View } from "../api";

const VIEWS: { key: View; label: string }[] = [
  { key: "ranking", label: "To look at" },
  { key: "applied", label: "Applied" },
  { key: "hidden", label: "Hidden" },
];

interface Props {
  view: View;
  onView: (view: View) => void;
  countries: CountryCount[];
  total: number;
  country: string | null;
  onCountry: (key: string | null) => void;
}

export function Sidebar({ view, onView, countries, total, country, onCountry }: Props) {
  return (
    <nav className="sidebar" aria-label="Filters">
      <div className="views" role="tablist" aria-label="Your jobs">
        {VIEWS.map((item) => (
          <button
            key={item.key}
            role="tab"
            aria-selected={view === item.key}
            className={view === item.key ? "view is-on" : "view"}
            onClick={() => onView(item.key)}
          >
            {item.label}
          </button>
        ))}
      </div>

      <h2 className="sidebar-title">Where</h2>
      <ul className="countries">
        <li>
          <button
            className={country === null ? "country is-on" : "country"}
            aria-pressed={country === null}
            onClick={() => onCountry(null)}
          >
            <span>Everywhere</span>
            <span className="count">{total}</span>
          </button>
        </li>
        {countries.map((item) => (
          <li key={item.key ?? "other"}>
            <button
              className={country === item.key ? "country is-on" : "country"}
              aria-pressed={country === item.key}
              onClick={() => onCountry(item.key)}
            >
              <span>{item.name}</span>
              <span className="count">{item.count}</span>
            </button>
          </li>
        ))}
      </ul>
    </nav>
  );
}