import type { Metadata } from "next";
import "../styles.css";
import "../styles/dark-catalog.css";
import "../styles/catalog-tools.css";

export const metadata: Metadata = {
  title: "Ranger Atlas｜LINE Rangers 資料站",
  description: "查詢 LINE Rangers 角色、裝備、PvP 排名與公會防禦配置。",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="zh-Hant">
      <body>{children}</body>
    </html>
  );
}
