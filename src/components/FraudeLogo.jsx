export default function FraudeLogo({ size = 28 }) {
  const cx = size/2, cy = size/2, n = 12, or = size*.38, dr = size*.052, cd = size*.14;
  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} fill="none" style={{ flexShrink:0 }}>
      <circle cx={cx} cy={cy} r={size*.46} stroke="var(--accent)" strokeWidth="0.8" opacity="0.2" />
      {Array.from({length:n}).map((_,i) => {
        const a = (i/n)*2*Math.PI - Math.PI/2;
        const op = 0.3 + 0.7*(Math.sin((i/n)*Math.PI*1.5+0.5)*.5+.5);
        return <circle key={i} cx={cx+or*Math.cos(a)} cy={cy+or*Math.sin(a)} r={dr} fill="var(--accent)" opacity={op} />;
      })}
      <circle cx={cx} cy={cy} r={cd} fill="var(--accent)" />
      <circle cx={cx} cy={cy} r={cd*.42} fill="var(--bg)" />
    </svg>
  );
}
