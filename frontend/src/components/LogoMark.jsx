export default function LogoMark({ className }) {
  return (
    <svg className={className} viewBox="0 0 32 32" width="22" height="22" aria-hidden="true">
      <rect x="4" y="7" width="24" height="3.2" rx="1.6" fill="currentColor" />
      <rect x="4" y="14.4" width="16" height="3.2" rx="1.6" fill="currentColor" opacity="0.7" />
      <rect x="4" y="21.8" width="20" height="3.2" rx="1.6" fill="currentColor" opacity="0.45" />
    </svg>
  );
}
