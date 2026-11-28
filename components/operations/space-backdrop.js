"use client";
export default function SpaceBackdrop() {
  return (
    <div className="ob-space" aria-hidden="true">
      <div className="ob-space-grain" />
      <div className="ob-space-orbit" />
      <div className="ob-space-planet planet-near" />
      <div className="ob-space-planet planet-far" />
      <div className="ob-space-sun" />
      {Array.from({ length: 24 }, (_, i) => (
        <i
          key={i}
          style={{
            left: ((i * 73 + 17) % 99) + "%",
            top: ((i * 47 + 13) % 97) + "%",
            opacity: 0.1 + (i % 3) * 0.07,
            width: i % 7 === 0 ? 2 : 1,
            height: i % 7 === 0 ? 2 : 1,
          }}
        />
      ))}
    </div>
  );
}
