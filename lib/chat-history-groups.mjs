/**
 * Presentation-only grouping of a user's already scoped chat list.
 * Dates are compared in the viewer's local timezone.
 * This helper never fetches or broadens conversation access.
 */
export function conversationGroups(conversations, now = new Date()) {
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const yesterday = new Date(today);
  yesterday.setDate(today.getDate() - 1);
  const lastWeek = new Date(today);
  lastWeek.setDate(today.getDate() - 7);

  const groups = new Map();
  for (const conversation of conversations || []) {
    const value = conversation.updated_at || conversation.created_at;
    const date = value ? new Date(value) : null;
    let label = "Earlier";

    if (date && !Number.isNaN(date.getTime())) {
      if (date >= today) label = "Today";
      else if (date >= yesterday) label = "Yesterday";
      else if (date >= lastWeek) label = "Previous 7 days";
      else label = date.toLocaleDateString("en", {
        month: "long", year: "numeric"
      });
    }

    if (!groups.has(label)) groups.set(label, []);
    groups.get(label).push(conversation);
  }

  return [...groups.entries()].map(([label, items]) => ({
    label, items
  }));
}
