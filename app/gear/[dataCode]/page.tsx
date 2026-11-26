import Image from "next/image";
import { EquipmentReferencePanel } from "../../_components/equipment-reference-panel";
import Link from "next/link";
import { notFound } from "next/navigation";
import { getPublishedLocalization, getPublishedVersion, SupabaseDataError, type EquipLocalization, type PublishedVersion } from "../../../lib/ranger-supabase";
import { getLocalGearIconUrl } from "../../../lib/local-research-assets";
import { getVerifiedEquipment } from "../../../lib/verified-equipment";
import { displaySourceText } from "../../../lib/display-text";
import { DataState } from "../../_components/data-state";
import { SiteHeader } from "../../_components/site-header";
import { SiteFooter } from "../../_components/site-footer";
import {equipmentAvailability} from '../../../lib/template-availability';
export default async function GearDetailPage({ params, searchParams }: { params: Promise<{ dataCode: string }>; searchParams: Promise<{ level?: string }> }) {
  const { dataCode } = await params;
  const selected = Number((await searchParams).level ?? 0);
  const level = Number.isInteger(selected) && selected >= 0 && selected <= 5 ? selected : 0;
  const verified = await getVerifiedEquipment(dataCode);
  const availability=equipmentAvailability(verified?.reference);
  let version: PublishedVersion | null = null, item: EquipLocalization | null = null, errorMessage: string | null = null;
  if (verified) {
    const message = verified.names["zh-Hant"] ?? verified.names.en ?? verified.itemCode;
    version = { snapshotId: "verified-runtime-12.4.0", sourceVersion: verified.sourceVersion, recordCount: 1 };
    item = { snapshotId: version.snapshotId, dataCode, language: "zh-Hant", messageType: "name", message, displayMessage: displaySourceText(message) };
  } else {
    try { version = await getPublishedVersion(); if (version) item = await getPublishedLocalization(version.snapshotId, dataCode, "zh-Hant"); }
    catch (error: unknown) { errorMessage = error instanceof SupabaseDataError ? error.message : "讀取資料時發生錯誤，請稍後再試。"; }
  }
  if (errorMessage || !version) return <div className="page-shell"><SiteHeader /><main className="page-main"><DataState title="目前無法讀取資料" description={errorMessage ?? "尚無已發布資料版本。"} /></main><SiteFooter /></div>;
  if (!item) notFound();
  const iconUrl = await getLocalGearIconUrl(item.dataCode);
  return <div className="page-shell"><SiteHeader /><main className="page-main">
    <Link className="back-link" href="/gear">← 回到裝備列表</Link>
    <section className="page-intro detail-intro"><p className="eyebrow">{verified ? "裝備圖鑑" : "裝備翻譯文字"}</p><h1>裝備詳細資料</h1></section>
    <article className="detail-panel"><header className="detail-heading">
      {iconUrl ? <span className="gear-icon-candidate gear-icon-detail"><Image src={iconUrl} alt="" width={112} height={112} unoptimized /><small>圖示對應待確認</small></span> : <span className="gear-image-fallback" aria-label="圖片尚未取得">◇</span>}
      <div><h2>{item.displayMessage || "尚無名稱"}</h2><p>裝備 ID：{verified?.itemCode ?? item.dataCode}</p></div>
    </header><details className="detail-note catalog-fold" open><summary><h2>裝備模板資料</h2></summary>
      <p>{verified ? "模板效果列出可能範圍，個別裝備的實際詞條請查看玩家防禦配置。" : "目前僅有翻譯文字，其他裝備欄位尚未解析。"}</p>
      <dl className="equipment-field-status">
        <div><dt>星等</dt><dd>{verified ? `${verified.starCount} 星` : "尚未解析"}</dd></div>
        <div><dt>類型</dt><dd>{verified ? `${({ARMOR:"防具",WEAPON:"武器",ACC:"飾品"})[verified.equipType]}（${verified.equipType}）` : "尚未解析"}</dd></div>
        <div><dt>模板強化上限</dt><dd>{verified ? `+${verified.maxEnchant}` : "尚未解析"}</dd></div>
        <div><dt>模板詞條數</dt><dd>{verified ? `${verified.minAttributeCount}～${verified.maxAttributeCount}` : "尚未解析"}</dd></div>
        <div><dt>模板參考基本效果</dt><dd>{availability.normal==='present'?`已對照 ${verified?.reference?.normalOptions.length} 項`:availability.normal==='absent'?'此裝備沒有基本效果':'尚未取得'}</dd></div>
        <div><dt>模板高級效果</dt><dd>{availability.advanced==='present'?'已對照':availability.advanced==='absent'?'此裝備沒有高級效果':'尚未取得'}</dd></div>
        <div><dt>Skill+</dt><dd>{availability.skillPlus==='present'?'已對照':availability.skillPlus==='absent'?'此裝備沒有 Skill+':'尚未取得'}</dd></div>
        <div><dt>Spec+</dt><dd>{availability.specPlus==='present'?'已對照':availability.specPlus==='absent'?'此裝備沒有 Spec+':'尚未取得'}</dd></div>
        <div><dt>個別裝備實際詞條與強化數值</dt><dd>尚未取得</dd></div>
      </dl><p>遊戲版本：{version.sourceVersion}</p>
      {verified?.updatedAt && <p>資料取得時間：{new Date(verified.updatedAt).toLocaleString("zh-TW",{timeZone:"Asia/Taipei",hour12:false})}</p>}
    </details></article>
    {verified?.reference && <EquipmentReferencePanel reference={verified.reference} level={level} />}
  </main><SiteFooter /></div>;
}
