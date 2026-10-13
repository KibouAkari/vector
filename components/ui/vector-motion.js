/*
 * VECTOR_INTERACTION_MOTION_583B
 *
 * Productive motion:
 *   daily controls and navigation
 *
 * Expressive motion:
 *   reserved for intro and major transitions
 */

export const VECTOR_EASE = {
  productive:
    [
      0.2,
      0,
      0.38,
      0.9
    ],

  entrance:
    [
      0,
      0,
      0.38,
      0.9
    ],

  expressive:
    [
      0.4,
      0.14,
      0.3,
      1
    ]
};


export const VECTOR_MOTION = {
  micro: {
    duration:
      0.12,

    ease:
      VECTOR_EASE.productive
  },

  fast: {
    duration:
      0.18,

    ease:
      VECTOR_EASE.productive
  },

  enter: {
    duration:
      0.24,

    ease:
      VECTOR_EASE.entrance
  },

  expressive: {
    duration:
      0.42,

    ease:
      VECTOR_EASE.expressive
  }
};
