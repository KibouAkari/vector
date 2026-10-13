"use client";


import * as Tooltip
  from "@radix-ui/react-tooltip";


export default function VectorTooltip({
  label,
  children,
  side = "top",
  delay = 320
}) {
  return (
    <Tooltip.Provider
      delayDuration={delay}
      skipDelayDuration={90}
    >

      <Tooltip.Root>

        <Tooltip.Trigger asChild>
          {children}
        </Tooltip.Trigger>

        <Tooltip.Portal>

          <Tooltip.Content
            className="vx-tooltip"
            side={side}
            sideOffset={7}
          >
            {label}

            <Tooltip.Arrow
              className="vx-tooltip-arrow"
              width={8}
              height={4}
            />
          </Tooltip.Content>

        </Tooltip.Portal>

      </Tooltip.Root>

    </Tooltip.Provider>
  );
}
