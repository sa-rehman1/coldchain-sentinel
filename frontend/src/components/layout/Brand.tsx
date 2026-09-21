import { Link } from 'react-router-dom';

export function Brand({ compact = false }: { compact?: boolean }) {
  return <Link to="/" className="brand" aria-label="Go to Command Center">
    <svg className="brand-mark" viewBox="0 0 40 40" aria-hidden="true">
      <path d="M20 3 34 11v18L20 37 6 29V11Z" fill="none" stroke="currentColor" strokeWidth="2" />
      <path d="M20 9v22M10.5 14.5l19 11M29.5 14.5l-19 11" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
      <circle cx="20" cy="20" r="4" fill="currentColor" />
    </svg>
    {!compact && <div><strong>ColdChain Sentinel</strong><span>Control tower</span></div>}
  </Link>;
}
