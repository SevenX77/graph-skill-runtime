/** What each permission mode takes away from the page's host operations, as measured on Claude Code 2.1.309.
 * The operations still run when called, so a later engine that lifts a limit shows in the call's own result.
 * Effect: "blocked" means the operation's purpose cannot be reached; "partial" means it depends on the tool. */
export const MODE_LIMITS = Object.freeze({
  auto: Object.freeze({
    "tools.call": Object.freeze({ effect: "partial", detail: "只读工具可以调用（get_session 实测成功）；需要询问权限的工具被自动模式的判定拒绝（lab_echo 实测被拒）。" }),
    "views.open": Object.freeze({ effect: "blocked", detail: "打开新标签要调用 preview_start，自动模式的判定不给结论，调用被拒绝，没有新标签。" }),
    "views.close": Object.freeze({ effect: "blocked", detail: "只能关闭本页面用 views.open 打开的标签，而自动模式下 views.open 打不开标签。切到自动模式前已打开的标签能否关闭未实测。" }),
  }),
});
