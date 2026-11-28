export const NAVIGATION = [
  {
    label: "Workspace",
    items: [
      { href: "/", label: "Overview", icon: "LayoutDashboard" },
      { href: "/chat", label: "Chat", icon: "MessageSquare", feature: "chat" },
      {
        href: "/projects",
        label: "Projects",
        icon: "FolderKanban",
        feature: "projects",
      },
      {
        href: "/teams",
        label: "Agent teams",
        icon: "Workflow",
        feature: "projects",
      },
    ],
  },
  {
    label: "Knowledge",
    items: [
      { href: "/brain", label: "Brain", icon: "BrainCircuit" },
      {
        href: "/skills",
        label: "Skills",
        icon: "BookOpen",
        feature: "projects",
      },
    ],
  },
  {
    label: "Operations",
    items: [
      {
        href: "/server",
        label: "Infrastructure",
        icon: "Server",
        feature: "server",
      },
      {
        href: "/connections",
        label: "Connections",
        icon: "Cable",
        operator: true,
      },
      { href: "/traffic", label: "Traffic", icon: "Globe2", operator: true },
      {
        href: "/security",
        label: "Security",
        icon: "ShieldCheck",
        operator: true,
      },
    ],
  },
  {
    label: "Control",
    items: [
      {
        href: "/approvals",
        label: "Approvals",
        icon: "CheckCheck",
        owner: true,
      },
      {
        href: "/audit",
        label: "Activity",
        icon: "ScrollText",
        feature: "activity",
      },
      {
        href: "/models",
        label: "Models & keys",
        icon: "SlidersHorizontal",
        feature: "models",
      },
      { href: "/usage", label: "Usage & budgets", icon: "ChartNoAxesCombined" },
      {
        href: "/users",
        label: "People & access",
        icon: "UsersRound",
        owner: true,
      },
      {
        href: "/permissions",
        label: "Policies",
        icon: "Fingerprint",
        owner: true,
      },
    ],
  },
];
export function navigationFor(session) {
  return NAVIGATION.map((group) => ({
    ...group,
    items: group.items.filter(
      (item) =>
        session.role === "owner" ||
        (!item.owner &&
          (!item.operator || session.role === "admin") &&
          (!item.feature || session.features?.[item.feature])),
    ),
  })).filter((group) => group.items.length);
}
export function pageTitle(path) {
  return (
    NAVIGATION.flatMap((group) => group.items).find((item) =>
      item.href === "/"
        ? path === "/"
        : path === item.href || path.startsWith(item.href + "/"),
    )?.label || "Workspace"
  );
}
