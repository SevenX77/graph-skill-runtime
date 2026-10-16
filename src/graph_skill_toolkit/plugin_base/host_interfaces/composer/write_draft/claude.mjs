export const capability = () => ({ state: "available", detail: "调用 Mod 输入框接口，不发送", constraints: { modes: ["append", "replace"] } });
export async function invoke($, { args, guard }) {
  await guard();
  const result = await $.prompt.fill({ text: args.text, mode: args.mode });
  if (result?.isFilled === true) return { status: "completed", message: "草稿已写入，未发送。", data: { mode: args.mode } };
  if (result?.isFilled === false) {
    const reason = result.refusal === "no_composer" ? "会话没有绑定输入框（无窗口或无头运行）" : result.refusal === "dialog" ? "有对话框占用输入" : "宿主输入框未接受草稿，原因未知";
    return { status: "rejected", message: reason + "。", data: { refusal: result.refusal ?? null }, evidence: { receipt: result } };
  }
  throw new Error("宿主草稿回执无法确认输入框效果；请检查输入框，避免重复写入。");
}
