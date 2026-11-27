import { executionAccount } from "../access-controls";
import { listConnections, requestConnectionAction } from "./store";
export const CONNECTION_TOOLS = [
  {
    type: "function",
    name: "server_connections",
    strict: true,
    description:
      "Read the user-owned saved connection snapshots for Checkmk, Wazuh, PatchMon and workspace tools. Reports last sync time; does not refresh or change services. Secrets are never returned.",
    parameters: {
      type: "object",
      properties: {},
      required: [],
      additionalProperties: false,
    },
  },
  {
    type: "function",
    name: "server_connection_action",
    strict: true,
    description:
      "Prepare a GitHub issue or Slack message on a user-owned connection for exact owner approval. Does NOT execute the action. User must review and execute once in Connections.",
    parameters: {
      type: "object",
      properties: {
        connectionId: { type: "string" },
        action: { type: "string", enum: ["create-issue", "send-message"] },
        repository: { type: "string" },
        title: { type: "string" },
        body: { type: "string" },
        channel: { type: "string" },
        text: { type: "string" },
      },
      required: [
        "connectionId",
        "action",
        "repository",
        "title",
        "body",
        "channel",
        "text",
      ],
      additionalProperties: false,
    },
  },
];
export async function executeConnectionTool(name, args, userId) {
  const account = await executionAccount(userId);
  if (!["owner", "admin"].includes(account.role)) throw Error("FORBIDDEN");
  const session = { userId, role: account.role, username: userId };
  if (name === "server_connections") {
    const value = await listConnections(session);
    return {
      connections: value.connections.map(({ base, ...row }) => row),
      observed: true,
      warning: "Saved snapshots may be stale; sync explicitly in Connections.",
    };
  }
  if (name === "server_connection_action") {
    return {
      ...(await requestConnectionAction(session, args.connectionId, args)),
      execution: "not started",
      next: "Owner reviews exact content in Approvals, then the connection owner executes once in Connections.",
    };
  }
  throw Error("UNSUPPORTED_TOOL");
}
