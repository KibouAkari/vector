import Redis from "ioredis";

const globalForRedis = globalThis;

export const redis =
  globalForRedis.vectorRedis ||
  new Redis(process.env.REDIS_URL, {
    maxRetriesPerRequest: 2,
    enableReadyCheck: true,
    lazyConnect: true
  });

if (process.env.NODE_ENV !== "production") {
  globalForRedis.vectorRedis = redis;
}

export async function ensureRedis() {
  if (redis.status === "wait") {
    await redis.connect();
  }

  return redis;
}
