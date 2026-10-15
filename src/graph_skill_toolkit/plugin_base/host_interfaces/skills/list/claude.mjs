// The Mod context summary is a host-owned Skill listing, not the Skill tool's invocation schema.
// It may omit entries once the host's context listing reaches its token budget.
// `facts.sessionUsage` comes from calling $.session.usage() once per session;
// the Mod engine accepts $ only in call position, so presence is probed by a call.
export function capability(_tools, facts = {}) {
  const usage = facts.sessionUsage;
  return {
    state: usage === undefined ? "unknown" : usage ? "available" : "unavailable",
    detail: usage === undefined ? "尚未核验当前会话的 Skill 清单接口。" : usage
      ? "读取当前会话上下文中的 Skill 名称；只有宿主确认全部名称均已列入时返回完整清单。"
      : "当前 Mod 会话未提供 Skill 清单所需的上下文用量接口。",
    scope: "session-context",
    constraints: { completeOnly: true },
  };
}

export async function invoke($, { guard }) {
  let usage;
  try { usage = await $.session.usage({ breakdown: "summary" }); }
  catch { return { status: "unsupported", message: "当前 Mod 会话没有上下文用量接口，无法查询 Skill 名称。" }; }
  await guard();
  const breakdown = usage?.context?.breakdown;
  if (!breakdown || typeof breakdown !== "object" || Array.isArray(breakdown)) {
    return { status: "error", message: "宿主未返回可核验的上下文清单。" };
  }
  // The native contract omits `skills` when the session lists none.
  if (breakdown.skills === undefined) {
    return { status: "completed", message: "当前会话没有列出的 Skill。", data: { scope: "session-context", complete: true, skills: [] } };
  }
  const listing = breakdown.skills;
  if (!listing || !Number.isSafeInteger(listing.totalSkills) || listing.totalSkills < 0 ||
      !Number.isSafeInteger(listing.includedSkills) || listing.includedSkills < 0 ||
      listing.includedSkills > listing.totalSkills || !Array.isArray(listing.skillFrontmatter) ||
      listing.skillFrontmatter.length !== listing.includedSkills ||
      listing.skillFrontmatter.some(skill => typeof skill?.name !== "string" || !skill.name)) {
    return { status: "error", message: "宿主返回了无法核验的 Skill 清单。" };
  }
  if (listing.includedSkills !== listing.totalSkills) return {
    status: "unsupported",
    message: "当前会话的 Skill 清单受上下文预算截断，无法返回完整名称。",
    data: { complete: false, totalSkills: listing.totalSkills, includedSkills: listing.includedSkills },
  };
  return { status: "completed", message: "已返回当前会话的完整 Skill 名称清单。",
    data: { scope: "session-context", complete: true, skills: listing.skillFrontmatter.map(skill => skill.name) } };
}
