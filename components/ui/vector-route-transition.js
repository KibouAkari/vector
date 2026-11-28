"use client";

import {useState,useEffect} from "react";


import {
  motion,
  useReducedMotion
} from "motion/react";


import {
  usePathname
} from "next/navigation";


export default function VectorRouteTransition() {
  const pathname =
    usePathname();


  const preference = useReducedMotion();
  const [reduced,setReduced]=useState(false);
  useEffect(()=>setReduced(Boolean(preference)),[preference]);


  return (
    <motion.div
      key={pathname}
      className="vector-route-transition"
      aria-hidden="true"
      initial={
        reduced
          ? {
              opacity:
                0
            }
          : {
              opacity:
                .42
            }
      }
      animate={{
        opacity:
          0
      }}
      transition={{
        duration:
          reduced
            ? .05
            : .48,

        ease: [
          .16,
          1,
          .3,
          1
        ]
      }}
    >
      {
        !reduced && (
          <motion.div
            className="vector-route-transition-line"
            initial={{
              scaleX:
                0,

              opacity:
                .8
            }}
            animate={{
              scaleX:
                1,

              opacity:
                0
            }}
            transition={{
              duration:
                .55,

              ease: [
                .16,
                1,
                .3,
                1
              ]
            }}
          />
        )
      }
    </motion.div>
  );
}
