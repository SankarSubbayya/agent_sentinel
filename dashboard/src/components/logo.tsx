// Geometric Sentinel mark — a tilted-square enclosing a centered diamond
// (gateway around a kernel). Single accent color, no gradient, no shield emoji.
export function SentinelMark({
  size = 18,
  className,
}: {
  size?: number;
  className?: string;
}) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
      aria-hidden
    >
      <path
        d="M12 2.5 21.5 12 12 21.5 2.5 12Z"
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinejoin="round"
      />
      <path
        d="M12 8.2 15.8 12 12 15.8 8.2 12Z"
        fill="currentColor"
      />
    </svg>
  );
}
