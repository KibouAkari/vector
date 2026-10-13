"use client";


import {
  motion,
  useReducedMotion
} from "motion/react";


import VectorTooltip
  from "./vector-tooltip";


import {
  VECTOR_MOTION
} from "./vector-motion";


function hoverAnimation(
  animation
) {
  if (
    animation ===
    "send"
  ) {
    return {
      y:
        -1,

      scale:
        1.045
    };
  }


  if (
    animation ===
    "retry"
  ) {
    return {
      rotate:
        -12,

      scale:
        1.04
    };
  }


  if (
    animation ===
    "copy"
  ) {
    return {
      y:
        -1,

      scale:
        1.035
    };
  }


  return {
    y:
      -1,

    scale:
      1.03
  };
}


export default function VectorIconButton({
  label,
  children,
  className = "",
  animation = "default",
  tone = "default",
  disabled = false,
  type = "button",
  ...props
}) {
  const reduced =
    useReducedMotion();


  return (
    <VectorTooltip
      label={label}
    >

      <motion.button
        type={type}
        className={
          [
            "vx-icon-button",
            className
          ]
            .filter(
              Boolean
            )
            .join(
              " "
            )
        }
        aria-label={label}
        data-tone={tone}
        data-animation={animation}
        disabled={disabled}
        whileHover={
          reduced ||
          disabled
            ? undefined
            : hoverAnimation(
                animation
              )
        }
        whileTap={
          reduced ||
          disabled
            ? undefined
            : {
                scale:
                  0.94
              }
        }
        transition={
          VECTOR_MOTION.micro
        }
        {...props}
      >
        {children}
      </motion.button>

    </VectorTooltip>
  );
}
