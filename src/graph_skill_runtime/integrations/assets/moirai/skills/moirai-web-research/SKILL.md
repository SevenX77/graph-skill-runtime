---
name: moirai-web-research
description: Research current external facts for graph-skill decisions while preserving source provenance and separating fact from inference.
---

# MoirAI web research

Use this skill only when a graph-skill decision depends on current external information, official format documentation, or evidence not present in the supplied files.

The Graph Skill Runtime does not provide a web or search tool. Use the current host's web/search capability only if it is available and authorized. If it is unavailable, stop and identify the missing evidence instead of implying that research occurred.

1. State the exact question and freshness requirement.
2. Prefer primary sources and official documentation.
3. Record each source title, direct URL, publication or update date when available, and access date.
4. Extract only facts supported by the source. Label synthesis or design consequences as inference.
5. Note conflicts, uncertainty, and facts that could not be verified.
6. Return a compact evidence packet that another host or specialist can consume without conversation history.

Use the [knowledge router](references/KB-00-hub.md) to identify which graph-skill owner should consume the findings. Do not call runtime-internal Python modules, invent host support, or treat a renderer's existence as proof that a real host discovered its projected assets.
