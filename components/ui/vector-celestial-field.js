"use client";

// Deterministic positions without another WebGL context.

const stars = Array.from(
  { length: 74 },
  (_, i) => ({
    x: (13 + i * 73.73) % 99,
    y: (7 + i * 41.41) % 98,
    size: i % 11 === 0 ? 2 : 1,
    alpha: 0.18 + (i % 6) * 0.07,
    twinkle: i % 9 === 0
  })
);

export default function VectorCelestialField({
  intro = false
}) {
  return (
    <div
      className={
        `vector-h4-celestial ${
          intro ? "vector-h4-celestial-intro" : ""
        }`
      }
      aria-hidden="true"
    >
      {stars.map((star, i) => (
        <i
          key={i}
          className={
            star.twinkle
              ? "vector-h4-star twinkle"
              : "vector-h4-star"
          }
          style={{
            left: `${star.x}%`,
            top: `${star.y}%`,
            width: star.size,
            height: star.size,
            opacity: star.alpha,
            animationDelay: `${-(i % 7)}s`
          }}
        />
      ))}

      <i className="vector-h4-orb vector-h4-moon" />
      <i className="vector-h4-orb vector-h4-planet" />
      <i className="vector-h4-orb vector-h4-distant" />
    </div>
  );
}
