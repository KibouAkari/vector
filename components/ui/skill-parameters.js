"use client";
export default function SkillParameters({
  skill,
  values = {},
  onChange,
  disabled,
}) {
  const entries = Object.entries(skill.parameters || {});
  if (!entries.length) return null;
  return (
    <fieldset className="skill-parameters" disabled={disabled}>
      <legend>{skill.name} parameters</legend>
      {entries.map(([key, definition]) => {
        const value = Object.hasOwn(values, key)
          ? values[key]
          : definition.default;
        return (
          <label key={key}>
            {key}
            {definition.type === "boolean" ? (
              <input
                type="checkbox"
                checked={value}
                onChange={(event) =>
                  onChange({ ...values, [key]: event.target.checked })
                }
              />
            ) : (
              <input
                type={definition.type === "number" ? "number" : "text"}
                step={definition.type === "number" ? "any" : undefined}
                maxLength={1000}
                value={value}
                onChange={(event) =>
                  onChange({
                    ...values,
                    [key]:
                      definition.type === "number"
                        ? Number(event.target.value)
                        : event.target.value,
                  })
                }
              />
            )}
          </label>
        );
      })}
    </fieldset>
  );
}
