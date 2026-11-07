# Interface Lab on the shared UI template

Date: 2026-11-01.

## Purpose

A person testing plugin interfaces reads each interface's state, calls it and compares its evidence on a page that has the same design and behaviour as the owner's other interfaces, in every host that shows the page.

## Terms

- **UI template**: the repository `SevenX77/ui-ux-template`. Its `core/` directory owns design tokens, styles and the interaction engine `core/behavior/ux.js`; `core/rules/UI-RULES.md` states the design rules.
- **Interface Lab**: the page built from `src/graph_skill_toolkit/apps/interface_lab/` into the single file `dist/interface-lab.html`.

## Decisions

1. **Reference by submodule.** The template is the submodule `vendor/ui-ux-template`, pinned to a commit. A design update reaches this project by moving the pin, because the template forbids copying its core.
2. **The page stays one file.** `ui/template/lab.html` names each stylesheet with an `INLINE_CSS` marker, and `scripts/build/main.mjs` inlines the named files. esbuild bundles `ux.js` with the page. The Codex host blocks external resources, so a page that loaded them would differ between hosts.
3. **Only what the page renders.** The page inlines `core/dist/tokens.css` and `core/styles/base.css`. The other four stylesheets hold samples that the page does not render.
4. **No web font.** The page uses the template's font stack without its font link, for the reason in decision 2. The stack falls through to the system fonts.
5. **Prism and Aurora.** The status of an interface is the data on this page and needs three distinct tones. In the Pure, Neon and Paper schemes, `--good` and `--bad` do not give three distinct tones with `--c3`. The page starts from `prefers-color-scheme`, and the switch in the top bar remembers the choice in `localStorage`.
6. **Attention surfaces follow reading.** The brief, the parameters and the call records are separate `data-scope` surfaces, so the pointer on the call button never dims the result that the call produces. Call records dim each other through the template's switch.
7. **Comparing stays one action.** The event log is a column at 1180 CSS pixels and wider, and a temporary overlay below that. The interface list is a column at 720 CSS pixels and wider, and a temporary overlay below that. The detail keeps its place in both cases, following the template's rule for temporary views.
8. **Page state stays as it was.** The change replaces the rendered view of `ui/index.tsx` and leaves its state, calls and record writing unchanged.

## Application state

The submodule, build step and continuous-integration checkout are committed. The view in `ui/index.tsx` and `ui/template/lab.html` sits on another session's uncommitted edits to the same files, so it lands together with them.

The template repository is private and this repository is public. The `toolkit-build` workflow reads the template with the secret `UI_TEMPLATE_READ_TOKEN`, so that workflow cannot pass until the secret holds a token with read access or the template becomes public.

## Acceptance

- `npm run typecheck`, `npm run build` and `npm test` pass from `src/graph_skill_toolkit/`.
- `dist/interface-lab.html` contains no `INLINE_CSS` marker, no `link` element and no external script.
- The page has no horizontal page scroll at 1294, 829 and 375 CSS pixels, in both schemes.
- A real call produces a record with its evidence; hovering the record shows the comparison tools; choosing a comparison writes the record file.
- A fresh Claude session opens the page through `open_interface_lab` and reports the result of each interface. Done once on 2026-11-01 before the fixes that its report caused. Open item: a fresh session has not yet exercised those fixes, including the Mod route's `skills.invoke` through `$.command.run`.
