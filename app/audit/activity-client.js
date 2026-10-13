"use client";

import { useMemo, useState } from "react";

function titleFor(action) {
  const names = {
    "project.created": "Project created",
    "project.updated": "Project updated",
    "project.deleted": "Project deleted",
    "file.uploaded": "File uploaded",
    "file.created": "File created",
    "file.updated": "File edited",
    "file.deleted": "File deleted",
    "project.ai.completed": "Project answer completed",
    "ai.request.completed": "Chat completed",
    "ai.request.failed": "Request failed",
    "privacy.vault.protected": "Sensitive values protected",
    "user.login": "Signed in"
  };

  return (
    names[action] ||
    String(action || "Activity")
      .replaceAll(".", " ")
      .replaceAll("_", " ")
      .replace(/\b\w/g, (character) => character.toUpperCase())
  );
}

function categoryFor(action) {
  const value = String(action || "");

  if (value.startsWith("project.")) return "Projects";
  if (value.startsWith("file.")) return "Files";
  if (value.includes("privacy")) return "Privacy";
  if (value.includes("login") || value.includes("user.")) return "Account";
  if (value.includes("ai.") || value.includes("chat")) return "Chat";

  return "Other";
}

function describe(item) {
  const details = item.details || {};
  const bits = [];

  if (details.name) bits.push(details.name);
  if (details.model) bits.push(details.model);

  if (details.filesRetrieved) {
    bits.push(`${details.filesRetrieved} project files`);
  }

  if (details.costChf !== undefined) {
    bits.push(`CHF ${Number(details.costChf).toFixed(3)}`);
  }

  return bits.join(" · ") || item.source || "";
}

export default function ActivityClient({
  items,
  owner
}) {
  const [sort, setSort] = useState("newest");
  const [type, setType] = useState("all");
  const [actor, setActor] = useState("all");
  const [query, setQuery] = useState("");

  const categories = useMemo(
    () => [
      ...new Set(
        items.map((item) => categoryFor(item.action))
      )
    ].sort(),
    [items]
  );

  const actors = useMemo(
    () => [
      ...new Set(
        items.map(
          (item) =>
            item.actorDisplay ||
            item.actor
        )
      )
    ].sort(),
    [items]
  );

  const visible = useMemo(() => {
    const search = query.trim().toLowerCase();

    const result = items.filter((item) => {
      if (
        type !== "all" &&
        categoryFor(item.action) !== type
      ) {
        return false;
      }

      if (
        owner &&
        actor !== "all" &&
        (item.actorDisplay || item.actor) !== actor
      ) {
        return false;
      }

      if (!search) return true;

      const haystack = [
        titleFor(item.action),
        describe(item),
        item.actorDisplay,
        item.actor,
        item.source
      ]
        .filter(Boolean)
        .join(" ")
        .toLowerCase();

      return haystack.includes(search);
    });

    result.sort((a, b) => {
      const left = new Date(a.createdAt).getTime();
      const right = new Date(b.createdAt).getTime();

      return sort === "oldest"
        ? left - right
        : right - left;
    });

    return result;
  }, [items, sort, type, actor, query, owner]);

  return (
    <>
      <div className="v55-activity-controls">
        <input
          type="search"
          placeholder="Search activity…"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
        />

        <select
          value={type}
          onChange={(event) => setType(event.target.value)}
        >
          <option value="all">All activity</option>
          {categories.map((category) => (
            <option key={category} value={category}>
              {category}
            </option>
          ))}
        </select>

        {owner && (
          <select
            value={actor}
            onChange={(event) => setActor(event.target.value)}
          >
            <option value="all">All users</option>
            {actors.map((name) => (
              <option key={name} value={name}>
                {name}
              </option>
            ))}
          </select>
        )}

        <select
          value={sort}
          onChange={(event) => setSort(event.target.value)}
        >
          <option value="newest">Newest first</option>
          <option value="oldest">Oldest first</option>
        </select>
      </div>

      <section className="v55-activity-list">
        {visible.length === 0 && (
          <div className="v55-empty">
            No matching activity.
          </div>
        )}

        {visible.map((item) => (
          <article
            key={item.id}
            className="v55-activity-row"
          >
            <div className="v55-activity-main">
              <div className="v55-activity-title">
                <strong>
                  {titleFor(item.action)}
                </strong>

                <span>
                  {categoryFor(item.action)}
                </span>

                {owner && (
                  <span>
                    {item.actorDisplay || item.actor}
                  </span>
                )}
              </div>

              {describe(item) && (
                <p>{describe(item)}</p>
              )}
            </div>

            <time dateTime={item.createdAt}>
              {new Date(item.createdAt).toLocaleString(
                [],
                {
                  day: "2-digit",
                  month: "short",
                  hour: "2-digit",
                  minute: "2-digit"
                }
              )}
            </time>
          </article>
        ))}
      </section>
    </>
  );
}
