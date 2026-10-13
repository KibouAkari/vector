"use client";

const pause = ms =>
  new Promise(resolve =>
    window.setTimeout(resolve, ms)
  );

const reduceMotion = () =>
  window.matchMedia(
    "(prefers-reduced-motion: reduce)"
  ).matches;

const smooth = x =>
  x * x * (3 - 2 * x);

const clamp = x =>
  Math.max(0, Math.min(1, x));

/*
 * Create an inert visual projection of the full login panel.
 * The actual password is never copied into this projection.
 */

function createProjection(original) {
  const rect = original.getBoundingClientRect();

  const stage = document.createElement("div");

  stage.className =
    "vector-gravity-stage vector-login-premium";

  stage.setAttribute("aria-hidden", "true");
  stage.inert = true;

  // SVG gravitational distortion filter.

  const svg = document.createElementNS(
    "http://www.w3.org/2000/svg",
    "svg"
  );

  svg.setAttribute("aria-hidden", "true");

  svg.style.cssText =
    "position:absolute;width:0;height:0;overflow:hidden";

  svg.innerHTML = `
    <defs>
      <filter
        id="vector-h5-lensing"
        x="-50%"
        y="-50%"
        width="200%"
        height="200%"
        color-interpolation-filters="sRGB"
      >
        <feTurbulence
          type="fractalNoise"
          baseFrequency="0.012 0.029"
          numOctaves="2"
          seed="7"
          result="noise"
        />
        <feDisplacementMap
          in="SourceGraphic"
          in2="noise"
          scale="0"
          xChannelSelector="R"
          yChannelSelector="G"
        />
      </filter>
    </defs>
  `;

  stage.appendChild(svg);

  // Clone the entire window, not individual elements.

  const clone = original.cloneNode(true);

  clone.querySelectorAll("[id]").forEach(
    el => el.removeAttribute("id")
  );

  const sourceInputs = original.querySelectorAll("input");
  const copiedInputs = clone.querySelectorAll("input");

  copiedInputs.forEach((input, index) => {
    const source = sourceInputs[index];

    const isPassword =
      source?.type === "password" ||
      source?.name === "password";

    input.type = "text";

    input.value = isPassword
      ? "••••••••••"
      : (source?.value || "");

    input.setAttribute("readonly", "");
    input.tabIndex = -1;
  });

  clone.querySelectorAll("button").forEach(
    button => {
      button.tabIndex = -1;
    }
  );

  clone.classList.add("vector-gravity-projection");

  Object.assign(clone.style, {
    position: "fixed",
    left: `${rect.left}px`,
    top: `${rect.top}px`,
    width: `${rect.width}px`,
    height: `${rect.height}px`,
    maxWidth: "none",
    margin: "0",
    transform: "translate3d(0,0,0)",
    transformOrigin: "50% 50%",
    filter: "none",
    willChange: "transform,filter,opacity",
    pointerEvents: "none",
    opacity: "1"
  });

  stage.appendChild(clone);
  document.body.appendChild(stage);

  return {
    stage,
    clone,
    lens: svg.querySelector("feDisplacementMap"),
    rect
  };
}

export async function runVectorGravityTransition({
  playSound
} = {}) {
  if (typeof window === "undefined") return;

  const original = document.querySelector(
    ".vector-login-premium-panel"
  );

  if (!original) {
    await pause(500);
    return;
  }

  if (reduceMotion()) {
    await pause(300);

    document.documentElement.classList.add(
      "vector-gravity-black"
    );

    await pause(90);
    return;
  }

  // Keep the real login window visible after success.
  await pause(950);

  const {
    stage,
    clone,
    lens,
    rect
  } = createProjection(original);

  const mobile = window.innerWidth < 700;

  // Approximate position of Gargantua in the composition.
  const targetX =
    window.innerWidth * (mobile ? 0.53 : 0.70);

  const targetY =
    window.innerHeight * (mobile ? 0.40 : 0.49);

  const dx =
    targetX - (rect.left + rect.width / 2);

  const dy =
    targetY - (rect.top + rect.height / 2);

  const duration = mobile ? 2850 : 3250;

  const start = performance.now();

  // Hide the real panel only when the complete
  // visual projection is ready.

  original.classList.add(
    "vector-gravity-original-hidden"
  );

  document.documentElement.classList.add(
    "vector-gravity-active"
  );

  try {
    playSound?.();
  } catch {}

  try {
    document.querySelector(
      ".vector-login-space iframe"
    )?.contentWindow?.postMessage(
      { type: "vector:warp" },
      "*"
    );
  } catch {}

  const darkness = document.createElement("div");

  darkness.className = "vector-gravity-curtain";

  stage.appendChild(darkness);

  await new Promise(resolve => {
    function tick(now) {
      const progress = clamp(
        (now - start) / duration
      );

      // Accelerating gravitational attraction.

      const travel =
        Math.pow(progress, 2.15);

      const shrink =
        Math.pow(1 - progress, 1.5);

      const scaleX = Math.max(
        0.004,
        1 - 0.994 * Math.pow(progress, 1.65)
      );

      const scaleY = Math.max(
        0.004,
        shrink
      );

      // Nonuniform bend, twist and compression.

      const bend =
        16 *
        Math.sin(Math.PI * progress) *
        Math.pow(progress, 0.6);

      const twist =
        14 * Math.pow(progress, 2);

      clone.style.transform = `
        translate3d(
          ${dx * travel}px,
          ${dy * travel}px,
          0
        )
        perspective(900px)
        rotate(${twist}deg)
        skewY(${bend}deg)
        scale(${scaleX},${scaleY})
      `;

      // Increasing SVG displacement as the window
      // approaches the event horizon.

      lens?.setAttribute(
        "scale",
        String(
          72 * smooth(
            clamp((progress - 0.16) / 0.78)
          )
        )
      );

      if (progress > 0.18) {
        clone.style.filter =
          "url(#vector-h5-lensing)";
      }

      clone.style.opacity = String(
        1 - smooth(
          clamp((progress - 0.78) / 0.22)
        )
      );

      darkness.style.opacity = String(
        smooth(
          clamp((progress - 0.75) / 0.25)
        )
      );

      if (progress < 1) {
        requestAnimationFrame(tick);
      } else {
        resolve();
      }
    }

    requestAnimationFrame(tick);
  });

  // Preserve complete darkness during page navigation.

  document.documentElement.classList.add(
    "vector-gravity-black"
  );

  stage.remove();

  await pause(140);
}
