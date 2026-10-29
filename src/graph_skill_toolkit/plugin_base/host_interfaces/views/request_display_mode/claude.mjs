import { unknown } from "../../../adapters/claude/mod/operations/shared.mjs";
// The page's Claude container is the Browser pane. The host can show or close
// that pane beside the conversation and collapse the sidebar; none of these
// places the page inline in the transcript, fullscreen, or picture-in-picture.
export const capability = () => unknown("Claude 的页面容器是 Browser 面板；宿主只能显示或关闭这个面板、折叠侧边栏，没有把页面放进对话内（inline）、全屏（fullscreen）或画中画（pip）的接口。");
