const paths = {
  inbox: <><path d="M4 4h16v16H4zM4 14h5l2 3h2l2-3h5"/></>,
  chart: <><path d="M4 3v17h17M8 15v-4m5 4V6m5 9V9"/></>,
  settings: <><path d="M4 7h16M4 17h16"/><circle cx="9" cy="7" r="3"/><circle cx="16" cy="17" r="3"/></>,
  arrow: <path d="M4 12h15m-6-6 6 6-6 6"/>,
  check: <path d="m5 12 4 4L19 6"/>,
  plus: <path d="M12 5v14M5 12h14"/>,
  search: <><circle cx="10" cy="10" r="6"/><path d="m15 15 5 5"/></>,
  file: <><path d="M6 3h8l4 4v14H6zM14 3v5h4M9 12h6M9 16h6"/></>,
  clock: <><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></>,
  spark: <><path d="m12 2 2.5 7.5L22 12l-7.5 2.5L12 22l-2.5-7.5L2 12l7.5-2.5z"/></>,
  close: <path d="m6 6 12 12M6 18 18 6"/>,
  flag: <><path d="M5 21V3h13l-3 5 3 5H5"/></>,
  pin: <><path d="M19 10c0 5-7 11-7 11S5 15 5 10a7 7 0 1 1 14 0Z"/><circle cx="12" cy="10" r="2"/></>,
  download: <><path d="M12 3v12m-5-5 5 5 5-5M5 16v5h14v-5"/></>,
  shield: <><path d="m12 2 8 4v6c0 5-8 10-8 10S4 17 4 12V6zM8 11l3 3 5-5"/></>,
  back: <path d="M20 12H5m6-6-6 6 6 6"/>,
};
export function Icon({ name, size = 18, ...props }) {
  return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" {...props}>{paths[name] || paths.file}</svg>;
}
export function Mark() {
  return <span className="brand-mark" aria-hidden="true"><svg width="26" height="26" viewBox="0 0 26 26"><path fill="currentColor" d="M3 3h8v8H3zm12 0h8v8h-8zM3 15h8v8H3zm12 0h8v8h-8z"/><path fill="var(--lime)" d="M15 15h8v8h-8z"/></svg></span>;
}
