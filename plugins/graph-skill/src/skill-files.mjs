import { readFile, realpath, stat } from "node:fs/promises";
import { dirname, isAbsolute, join, relative, sep } from "node:path";
import { parseDocument } from "yaml";

export async function isSkillRoot(path) {
  try {
    return (await stat(join(path, "SKILL.md"))).isFile() && (await stat(join(path, "graph.yaml"))).isFile();
  } catch { return false; }
}

export async function findSkillRoot(path) {
  let current = path;
  // Prefer the bundle root over subgraph/phase directories.
  while (true) {
    if (await isSkillRoot(current)) return realpath(current);
    const parent = dirname(current);
    if (parent === current) return null;
    current = parent;
  }
}

export async function loadSkill(skillRoot) {
  if (!isAbsolute(skillRoot)) throw new Error("skill_root must be an absolute directory path.");
  const root = await realpath(skillRoot);
  if (!await isSkillRoot(root)) throw new Error("The selected directory must contain SKILL.md and graph.yaml.");
  const file = join(root, "graph.yaml");
  // This bounds UI input, not runtime graph validity.
  if ((await stat(file)).size > 2 * 1024 * 1024) throw new Error("Canvas graph.yaml limit is 2 MiB.");
  const document = parseDocument(await readFile(file, "utf8"));
  if (document.errors.length) throw new Error(document.errors.map(error => error.message).join("; "));
  const data = document.toJS({ maxAliasCount: 100 });
  if (data?.schema_version !== "gskill.graph.v1" || typeof data.graph_id !== "string" || !Array.isArray(data.phases) || !data.phases.length) {
    throw new Error("Expected a portable gskill.graph.v1 graph with phases.");
  }
  const kinds = {};
  for (const phase of data.phases) {
    if (!/^[A-Za-z][A-Za-z0-9_-]*$/.test(phase?.id ?? "") || phase.id.toLowerCase() === "input") throw new Error("Invalid phase id.");
    const directory = await realpath(join(root, "phases", phase.id));
    const within = relative(root, directory);
    if (within === ".." || within.startsWith(`..${sep}`) || isAbsolute(within)) throw new Error("Phase directory must stay inside the selected Skill.");
    const found = [];
    for (const kind of ["LOGIC", "AGENT", "SUBGRAPH"]) {
      try { if ((await stat(join(directory, `${kind}.md`))).isFile()) found.push(kind); } catch { /* Missing type candidate. */ }
    }
    if (found.length !== 1) throw new Error(`Phase ${phase.id} must contain exactly one type file.`);
    kinds[phase.id] = found[0];
  }
  return { skillRoot: root, data, kinds };
}
