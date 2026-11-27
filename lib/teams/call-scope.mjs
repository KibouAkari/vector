import { AsyncLocalStorage } from "node:async_hooks";
const contexts = new AsyncLocalStorage();
export const withTeamCalls = (admit, execute) => contexts.run(admit, execute);
export async function admitTeamCall() {
  const admit = contexts.getStore();
  if (admit) await admit();
}
