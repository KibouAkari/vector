"use client";


import {
  useMemo,
  useState
} from "react";


import Link
  from "next/link";


import {
  motion,
  useReducedMotion
} from "motion/react";


import {
  Activity,
  ArrowUpRight,
  Coins,
  FolderKanban,
  MessageSquareText,
  Sparkles,
  WalletCards,
  Workflow
} from "lucide-react";


import {
  Area,
  AreaChart,
  CartesianGrid,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis
} from "recharts";


const MODEL_COLORS = [
  "#70d6ae",
  "#7697ff",
  "#e4ae67",
  "#ab8df0",
  "#66bfd0",
  "#d47f9c"
];


function compactNumber(
  value
) {
  return new Intl.NumberFormat(
    "en",
    {
      notation:
        "compact",

      maximumFractionDigits:
        1
    }
  ).format(
    Number(
      value ||
      0
    )
  );
}


function integer(
  value
) {
  return new Intl.NumberFormat(
    "en"
  ).format(
    Number(
      value ||
      0
    )
  );
}


function money(
  value,
  decimals = 2
) {
  return (
    "CHF " +
    Number(
      value ||
      0
    ).toFixed(
      decimals
    )
  );
}


function modelName(
  value
) {
  return String(
    value ||
    "Unknown"
  )
    .split(
      "-"
    )
    .map(
      part => {
        const lower =
          part.toLowerCase();


        if (
          lower ===
          "gpt"
        ) {
          return "GPT";
        }


        if (
          lower ===
          "gemini"
        ) {
          return "Gemini";
        }


        if (
          lower ===
          "claude"
        ) {
          return "Claude";
        }


        return (
          part.charAt(0)
            .toUpperCase() +
          part.slice(1)
        );
      }
    )
    .join(
      " "
    );
}


function relativeDate(
  value
) {
  if (
    !value
  ) {
    return "";
  }


  const date =
    new Date(
      value
    );


  const diff =
    Math.max(
      0,
      Date.now() -
      date.getTime()
    );


  const days =
    Math.floor(
      diff /
      86400000
    );


  if (
    days === 0
  ) {
    return "Updated today";
  }


  if (
    days === 1
  ) {
    return "Updated yesterday";
  }


  return (
    `Updated ${days}d ago`
  );
}


function MetricCard({
  label,
  value,
  detail,
  icon: Icon,
  reduced
}) {
  return (
    <motion.article
      className="vx85-stat-card"
      whileHover={
        reduced
          ? undefined
          : {
              y:
                -2
            }
      }
      transition={{
        duration:
          .16
      }}
    >

      <div className="vx85-stat-head">

        <span>
          {label}
        </span>

        <span className="vx85-stat-icon">
          <Icon
            aria-hidden="true"
          />
        </span>

      </div>


      <strong>
        {value}
      </strong>


      <small>
        {detail}
      </small>

    </motion.article>
  );
}


function TrendTooltip({
  active,
  payload,
  label
}) {
  if (
    !active ||
    !payload?.length
  ) {
    return null;
  }


  const item =
    payload[0]
      ?.payload;


  if (
    !item
  ) {
    return null;
  }


  return (
    <div className="vx85-chart-tooltip">

      <strong>
        {label}
      </strong>

      <span>
        {integer(item.requests)}
        {" "}
        requests
      </span>

      <span>
        {compactNumber(item.totalTokens)}
        {" "}
        tokens
      </span>

      <span>
        {money(item.spend, 4)}
      </span>

    </div>
  );
}


function DistributionTooltip({
  active,
  payload
}) {
  if (
    !active ||
    !payload?.length
  ) {
    return null;
  }


  const item =
    payload[0]
      ?.payload;


  if (
    !item
  ) {
    return null;
  }


  return (
    <div className="vx85-chart-tooltip vx85-model-tooltip">

      <strong>
        {modelName(item.model)}
      </strong>

      <span>
        {item.percent.toFixed(1)}
        %
      </span>

      <span>
        {integer(item.requests)}
        {" "}
        requests
      </span>

      <span>
        {compactNumber(item.totalTokens)}
        {" "}
        tokens
      </span>

      <span>
        {money(item.spend, 4)}
      </span>

    </div>
  );
}


export default function DashboardClient({
  displayName,
  totals,
  models,
  timeline,
  projects
}) {
  const reduced =
    useReducedMotion();


  const [
    trendMetric,
    setTrendMetric
  ] =
    useState(
      "spend"
    );


  const [
    distributionMetric,
    setDistributionMetric
  ] =
    useState(
      "requests"
    );


  const averageCost =
    totals.requests > 0
      ? totals.spend /
        totals.requests
      : 0;


  const chartData =
    useMemo(
      () =>
        timeline.map(
          row => ({
            ...row,

            chartValue:
              trendMetric ===
              "requests"
                ? row.requests
                : (
                    trendMetric ===
                    "tokens"
                      ? row.totalTokens
                      : row.spend
                  )
          })
        ),
      [
        timeline,
        trendMetric
      ]
    );


  const distribution =
    useMemo(
      () => {
        const total =
          models.reduce(
            (
              sum,
              model
            ) => {
              if (
                distributionMetric ===
                "tokens"
              ) {
                return (
                  sum +
                  model.totalTokens
                );
              }


              if (
                distributionMetric ===
                "spend"
              ) {
                return (
                  sum +
                  model.spend
                );
              }


              return (
                sum +
                model.requests
              );
            },
            0
          );


        return models.map(
          (
            model,
            index
          ) => {
            let value =
              model.requests;


            if (
              distributionMetric ===
              "tokens"
            ) {
              value =
                model.totalTokens;
            }


            if (
              distributionMetric ===
              "spend"
            ) {
              value =
                model.spend;
            }


            return {
              ...model,

              value,

              color:
                MODEL_COLORS[
                  index %
                  MODEL_COLORS.length
                ],

              percent:
                total > 0
                  ? (
                      value /
                      total
                    ) *
                    100
                  : 0
            };
          }
        );
      },
      [
        models,
        distributionMetric
      ]
    );


  const bestEconomics =
    useMemo(
      () => {
        const candidates =
          models
            .filter(
              model =>
                model.totalTokens >
                  0 &&
                model.spend >
                  0
            )
            .sort(
              (
                left,
                right
              ) =>
                left.effectiveCost -
                right.effectiveCost
            );


        return (
          candidates[0]
            ?.model ||
          null
        );
      },
      [
        models
      ]
    );


  const container =
    reduced
      ? undefined
      : {
          hidden: {
            opacity:
              0
          },

          visible: {
            opacity:
              1,

            transition: {
              staggerChildren:
                .045
            }
          }
        };


  const item =
    reduced
      ? undefined
      : {
          hidden: {
            opacity:
              0,

            y:
              10
          },

          visible: {
            opacity:
              1,

            y:
              0,

            transition: {
              duration:
                .32,

              ease: [
                .16,
                1,
                .3,
                1
              ]
            }
          }
        };


  return (
    <motion.div
      className="vx85-dashboard"
      variants={container}
      initial={
        reduced
          ? undefined
          : "hidden"
      }
      animate={
        reduced
          ? undefined
          : "visible"
      }
    >

      <motion.header
        className="vx85-dashboard-header"
        variants={item}
      >

        <div>

          <span className="vx85-dashboard-kicker">
            Overview
          </span>

          <h1>
            Good to see you,
            {" "}
            <strong>
              {displayName}
            </strong>
            .
          </h1>

          <p>
            Your Vector usage over the
            last 30 calendar days, in UTC.
          </p>

        </div>


        <motion.div
          whileHover={
            reduced
              ? undefined
              : {
                  y:
                    -2
                }
          }
          whileTap={
            reduced
              ? undefined
              : {
                  scale:
                    .97
                }
          }
        >
          <Link
            href="/chat"
            className="vx85-new-chat"
          >
            <MessageSquareText />

            <span>
              New chat
            </span>

            <ArrowUpRight />
          </Link>
        </motion.div>

      </motion.header>


      <motion.section
        className="vx85-stat-grid"
        variants={item}
      >

        <MetricCard
          label="Usage entries"
          value={
            integer(
              totals.requests
            )
          }
          detail={`${integer(totals.providerCalls || 0)} provider responses · ${integer(totals.legacyEntries || 0)} legacy entries`}
          icon={Activity}
          reduced={reduced}
        />


        <MetricCard
          label="Tokens"
          value={
            compactNumber(
              totals.totalTokens
            )
          }
          detail={
            `${compactNumber(
              totals.inputTokens
            )} input · ${compactNumber(
              totals.outputTokens
            )} output`
          }
          icon={Workflow}
          reduced={reduced}
        />


        <MetricCard
          label="Estimated spend"
          value={
            money(
              totals.spend
            )
          }
          detail={totals.incompleteCalls ? `${integer(totals.incompleteCalls)} entries need reconciliation` : "Recorded usage · configured prices"}
          icon={WalletCards}
          reduced={reduced}
        />


        <MetricCard
          label="Average"
          value={
            money(
              averageCost,
              3
            )
          }
          detail="Cost per recorded entry"
          icon={Coins}
          reduced={reduced}
        />

      </motion.section>


      <motion.section
        className="vx85-analytics-grid"
        variants={item}
      >

        <article className="vx85-panel vx85-trend-panel">

          <header className="vx85-panel-header">

            <div>

              <span>
                Performance
              </span>

              <strong>
                Usage trend
              </strong>

            </div>


            <div className="vx85-segmented">

              {
                [
                  [
                    "spend",
                    "Spend"
                  ],
                  [
                    "requests",
                    "Entries"
                  ],
                  [
                    "tokens",
                    "Tokens"
                  ]
                ].map(
                  (
                    [
                      value,
                      label
                    ]
                  ) => (
                    <button
                      key={value}
                      type="button"
                      className={
                        trendMetric ===
                        value
                          ? "active"
                          : ""
                      }
                      onClick={
                        () =>
                          setTrendMetric(
                            value
                          )
                      }
                    >
                      {label}
                    </button>
                  )
                )
              }

            </div>

          </header>


          <div className="vx85-trend-summary">

            <strong>
              {
                trendMetric ===
                "spend"
                  ? money(
                      totals.spend
                    )
                  : (
                      trendMetric ===
                      "requests"
                        ? integer(
                            totals.requests
                          )
                        : compactNumber(
                            totals.totalTokens
                          )
                    )
              }
            </strong>

            <span>
              {
                trendMetric ===
                "spend"
                  ? "total spend"
                  : (
                      trendMetric ===
                      "requests"
                        ? "entries"
                        : "tokens"
                    )
              }
              {" "}
              over 30 days
            </span>

          </div>


          <div className="vx85-trend-chart">

            <ResponsiveContainer
              width="100%"
              height="100%"
            >
              <AreaChart
                data={
                  chartData
                }
                margin={{
                  top:
                    12,

                  right:
                    6,

                  bottom:
                    0,

                  left:
                    0
                }}
              >

                <defs>

                  <linearGradient
                    id="vx85TrendFill"
                    x1="0"
                    y1="0"
                    x2="0"
                    y2="1"
                  >
                    <stop
                      offset="0%"
                      stopColor="#70d6ae"
                      stopOpacity=".30"
                    />

                    <stop
                      offset="100%"
                      stopColor="#70d6ae"
                      stopOpacity="0"
                    />
                  </linearGradient>

                </defs>


                <CartesianGrid
                  vertical={
                    false
                  }
                  stroke="rgba(255,255,255,.05)"
                />


                <XAxis
                  dataKey="label"
                  axisLine={
                    false
                  }
                  tickLine={
                    false
                  }
                  minTickGap={
                    38
                  }
                  tick={{
                    fill:
                      "#65717a",

                    fontSize:
                      10
                  }}
                />


                <YAxis
                  width={
                    38
                  }
                  axisLine={
                    false
                  }
                  tickLine={
                    false
                  }
                  tickFormatter={
                    value =>
                      trendMetric ===
                      "spend"
                        ? Number(
                            value
                          )
                            .toFixed(
                              1
                            )
                        : compactNumber(
                            value
                          )
                  }
                  tick={{
                    fill:
                      "#59656e",

                    fontSize:
                      9
                  }}
                />


                <Tooltip
                  content={
                    <TrendTooltip />
                  }
                  cursor={{
                    stroke:
                      "rgba(112,214,174,.18)",

                    strokeWidth:
                      1
                  }}
                />


                <Area
                  type="monotone"
                  dataKey="chartValue"
                  stroke="#70d6ae"
                  strokeWidth={
                    2
                  }
                  fill="url(#vx85TrendFill)"
                  dot={
                    false
                  }
                  activeDot={{
                    r:
                      4,

                    fill:
                      "#70d6ae",

                    stroke:
                      "#0b0f12",

                    strokeWidth:
                      2
                  }}
                  isAnimationActive={
                    !reduced
                  }
                  animationDuration={
                    850
                  }
                  animationEasing="ease-out"
                />

              </AreaChart>
            </ResponsiveContainer>

          </div>

        </article>


        <article className="vx85-panel vx85-distribution-panel">

          <header className="vx85-panel-header">

            <div>

              <span>
                AI models
              </span>

              <strong>
                Model distribution
              </strong>

            </div>


            <div className="vx85-segmented vx85-segmented-small">

              {
                [
                  [
                    "requests",
                    "Entries"
                  ],
                  [
                    "tokens",
                    "Tokens"
                  ],
                  [
                    "spend",
                    "Cost"
                  ]
                ].map(
                  (
                    [
                      value,
                      label
                    ]
                  ) => (
                    <button
                      key={value}
                      type="button"
                      className={
                        distributionMetric ===
                        value
                          ? "active"
                          : ""
                      }
                      onClick={
                        () =>
                          setDistributionMetric(
                            value
                          )
                      }
                    >
                      {label}
                    </button>
                  )
                )
              }

            </div>

          </header>


          <div className="vx85-donut-wrap">

            <div className="vx85-donut">

              <ResponsiveContainer
                width="100%"
                height="100%"
              >
                <PieChart>

                  <Pie
                    data={
                      distribution
                    }
                    dataKey="value"
                    nameKey="model"
                    innerRadius="67%"
                    outerRadius="91%"
                    paddingAngle={
                      2.5
                    }
                    cornerRadius={
                      4
                    }
                    stroke="none"
                    isAnimationActive={
                      !reduced
                    }
                    animationDuration={
                      900
                    }
                    animationEasing="ease-out"
                  >

                    {
                      distribution.map(
                        entry => (
                          <Cell
                            key={
                              `${entry.provider}-${entry.model}`
                            }
                            fill={
                              entry.color
                            }
                          />
                        )
                      )
                    }

                  </Pie>


                  <Tooltip
                    content={
                      <DistributionTooltip />
                    }
                    allowEscapeViewBox={{ x: true, y: true }}
                    wrapperStyle={{
                      zIndex: 30,
                      pointerEvents: "none"
                    }}
                  />

                </PieChart>
              </ResponsiveContainer>


              <div className="vx85-donut-center">

                <strong>
                  {
                    distributionMetric ===
                    "requests"
                      ? integer(
                          totals.requests
                        )
                      : (
                          distributionMetric ===
                          "tokens"
                            ? compactNumber(
                                totals.totalTokens
                              )
                            : money(
                                totals.spend
                              )
                        )
                  }
                </strong>

                <span>
                  {
                    distributionMetric ===
                    "requests"
                      ? "entries"
                      : (
                          distributionMetric ===
                          "tokens"
                            ? "tokens"
                            : "spend"
                        )
                  }
                </span>

              </div>

            </div>


            <div className="vx85-model-legend">

              {
                distribution.map(
                  entry => (
                    <div
                      className="vx85-model-legend-row"
                      key={
                        `${entry.provider}-${entry.model}`
                      }
                    >

                      <span
                        className="vx85-model-color"
                        style={{
                          background:
                            entry.color
                        }}
                      />


                      <div>

                        <strong>
                          {
                            modelName(
                              entry.model
                            )
                          }
                        </strong>

                        <span>
                          {
                            entry.percent
                              .toFixed(
                                1
                              )
                          }
                          %
                        </span>

                      </div>

                    </div>
                  )
                )
              }

            </div>

          </div>

        </article>

      </motion.section>


      <motion.section
        className="vx85-lower-grid"
        variants={item}
      >

        <article className="vx85-panel vx85-economics">

          <header className="vx85-panel-header">

            <div>

              <span>
                Model economics
              </span>

              <strong>
                Cost comparison
              </strong>

            </div>


            <div className="vx85-panel-note">
              Observed Vector usage
            </div>

          </header>


          <div className="vx85-model-table">

            <div className="vx85-model-table-head">

              <span>
                Model
              </span>

              <span>
                Entries
              </span>

              <span>
                Tokens
              </span>

              <span>
                Spend
              </span>

              <span>
                Avg / entry
              </span>

              <span>
                CHF / 1M
              </span>

            </div>


            {
              models.map(
                (
                  model,
                  index
                ) => (
                  <motion.div
                    className="vx85-model-table-row"
                    key={
                      `${model.provider}-${model.model}`
                    }
                    whileHover={
                      reduced
                        ? undefined
                        : {
                            x:
                              2
                          }
                    }
                  >

                    <div className="vx85-model-name">

                      <span
                        className="vx85-model-color"
                        style={{
                          background:
                            MODEL_COLORS[
                              index %
                              MODEL_COLORS.length
                            ]
                        }}
                      />

                      <div>

                        <strong>
                          {
                            modelName(
                              model.model
                            )
                          }
                        </strong>

                        <span>
                          {model.provider}

                          {
                            bestEconomics ===
                            model.model && (
                              <em>
                                Best observed
                              </em>
                            )
                          }
                        </span>

                      </div>

                    </div>


                    <span>
                      {
                        integer(
                          model.requests
                        )
                      }
                    </span>


                    <span>
                      {
                        compactNumber(
                          model.totalTokens
                        )
                      }
                    </span>


                    <span>
                      {
                        money(
                          model.spend,
                          3
                        )
                      }
                    </span>


                    <span>
                      {
                        money(
                          model.avgCost,
                          4
                        )
                      }
                    </span>


                    <span>
                      {
                        money(
                          model.effectiveCost,
                          3
                        )
                      }
                    </span>

                  </motion.div>
                )
              )
            }

          </div>


          <footer className="vx85-economics-footer">

            <span>
              Estimates use recorded provider tokens and configured prices.
              Provider invoices are not yet reconciled. Older entries may group multiple calls.
            </span>

            <span>
              CHF / 1M is an observed effective rate,
              not a provider list price.
            </span>

          </footer>

        </article>


        <article className="vx85-panel vx85-project-panel">

          <header className="vx85-panel-header">

            <div>

              <span>
                Workspace
              </span>

              <strong>
                Recent projects
              </strong>

            </div>


            <Link href="/projects">
              View all
              <ArrowUpRight />
            </Link>

          </header>


          <div className="vx85-project-list">

            {
              projects.length ===
              0
                ? (
                  <div className="vx85-empty">
                    No projects yet.
                  </div>
                )
                : projects.map(
                  project => (
                    <motion.div
                      key={
                        project.id
                      }
                      whileHover={
                        reduced
                          ? undefined
                          : {
                              x:
                                3
                            }
                      }
                    >

                      <Link
                        href={
                          `/projects/${project.id}`
                        }
                      >

                        <span className="vx85-project-icon">
                          <FolderKanban />
                        </span>


                        <div>

                          <strong>
                            {project.name}
                          </strong>

                          <span>
                            {
                              project.description ||
                              relativeDate(
                                project.updatedAt
                              ) ||
                              "Vector project"
                            }
                          </span>

                        </div>


                        <ArrowUpRight />

                      </Link>

                    </motion.div>
                  )
                )
            }

          </div>


          <div className="vx85-project-action">

            <Link href="/chat">
              <Sparkles />

              Ask Vector

              <ArrowUpRight />
            </Link>

          </div>

        </article>

      </motion.section>

    </motion.div>
  );
}

