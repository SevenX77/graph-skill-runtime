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

Rank the evidence by who can re-check it. A page anyone can open at that URL supports a documented claim; record the URL beside the claim. A page that opened only because this person is signed in cannot be checked by anyone else — a different machine or account meets a login wall — so it is a documented starting point that still owes a real measurement, and it must be labelled that way rather than passed off as public documentation. Reading a claim is never the same as testing it: if the thing can be measured, the measurement outranks the page.

Do not conclude from a login wall, an empty result, or an unavailable capability that the fact does not exist; report the missing access instead. Never ask for a password, a verification code, or an exported cookie.

Use the [knowledge router](references/KB-00-hub.md) to identify which graph-skill owner should consume the findings, and follow [working discipline](references/KB-15-working-discipline.md) for separating fact from inference in the report. Do not call runtime-internal Python modules, invent host support, or treat a renderer's existence as proof that a real host discovered its projected assets.
