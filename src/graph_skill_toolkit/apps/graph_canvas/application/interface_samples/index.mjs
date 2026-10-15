// Optional Graph Skill values for the generic laboratory. No adapter consumes
// these defaults or interprets the business context.
export function graphInterfaceSamples(snapshot, selectedNodeId) {
  if (!snapshot?.skillRoot) return {};
  const root = snapshot.skillRoot.replace(/[\\/]$/, '');
  const context = { skillRoot: snapshot.skillRoot, graphId: snapshot.graph.id, ...(selectedNodeId ? { nodeId: selectedNodeId } : {}) };
  return {
    'files.revealDirectory': { path: root },
    'files.openFile': { path: root + '/SKILL.md' },
    'context.set': { key: 'graphSkillSelection', content: context },
    'context.remove': { key: 'graphSkillSelection' },
    'tools.call': { tool: { server: 'graph-skill-canvas', name: 'inspect_graph' }, arguments: { skill_root: snapshot.skillRoot } },
    'views.open': { resource: { kind: 'file', path: root + '/SKILL.md' }, reuseKey: 'graph-skill-document', activate: true },
  };
}
