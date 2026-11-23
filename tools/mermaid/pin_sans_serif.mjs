// Mermaid 量文字时会同时测通用 sans-serif 与主题字体，取尺寸更大的分支；
// CI 与本机的 Arial 版本不同，时序图的换行与坐标会跟着漂移。这里在建页
// 后用 CDP 把 sans-serif 映射到主题字体，让两条分支得到同一份度量。
import { Page } from "puppeteer";

const sansSerif = process.env.NEEDLEFISH_MERMAID_SANS;
if (!sansSerif) {
  throw new Error("NEEDLEFISH_MERMAID_SANS 未设置，无法固定 Mermaid 测量字体");
}

const originalGoto = Page.prototype.goto;

Page.prototype.goto = async function (...args) {
  const response = await originalGoto.apply(this, args);
  const client = await this.createCDPSession();
  try {
    await client.send("Page.setFontFamilies", { fontFamilies: { sansSerif } });
  } catch (error) {
    await client.detach();
    throw new Error(`固定 Mermaid 测量字体失败：${error.message}`);
  }
  // 断开 CDP 会话后，下一次导航会丢掉字体映射；保留到页面关闭。
  this.__needlefishFontClient = client;
  return response;
};
