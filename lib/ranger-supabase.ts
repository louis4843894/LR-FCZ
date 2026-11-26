import "server-only";

export type PublishedVersion = {
  snapshotId: string;
  sourceVersion: string;
  recordCount: number;
};

export type EquipLocalization = {
  snapshotId: string;
  dataCode: string;
  language: string;
  messageType: string | null;
  /** Original source string returned by Supabase; escape sequences remain intact. */
  message: string | null;
  /** One-pass display form of the source string. */
  displayMessage: string | null;
};

export type SearchResult = {
  totalCount: number;
  items: EquipLocalization[];
};

export class SupabaseDataError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "SupabaseDataError";
  }
}

type JsonRecord = Record<string, unknown>;

const REVALIDATE_SECONDS = 60;
const CACHE_TAG = "published-ranger-data";

function isJsonRecord(value: unknown): value is JsonRecord {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function readConfig(): { baseUrl: string; publishableKey: string } {
  const configuredUrl =
    process.env.SUPABASE_URL ?? process.env.NEXT_PUBLIC_SUPABASE_URL;
  const publishableKey = process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY;
  if (!configuredUrl || !publishableKey) {
    throw new SupabaseDataError(
      "尚未設定 Supabase 公開讀取連線資訊。",
    );
  }

  let baseUrl: URL;
  try {
    baseUrl = new URL(configuredUrl);
  } catch {
    throw new SupabaseDataError("Supabase 網址設定無效。");
  }
  if (baseUrl.protocol !== "https:" || baseUrl.username || baseUrl.password) {
    throw new SupabaseDataError("Supabase 網址必須是有效的 HTTPS 網址。");
  }
  return { baseUrl: baseUrl.origin, publishableKey };
}

async function getJson(endpoint: string, params: URLSearchParams): Promise<unknown> {
  const { baseUrl, publishableKey } = readConfig();
  let response: Response;
  try {
    response = await fetch(
      `${baseUrl}/rest/v1/${endpoint}?${params.toString()}`,
      {
        headers: {
          apikey: publishableKey,
          Accept: "application/json",
        },
        next: {
          revalidate: REVALIDATE_SECONDS,
          tags: [CACHE_TAG],
        },
      },
    );
  } catch {
    throw new SupabaseDataError(
      "目前無法連線 Supabase，請稍後再試。",
    );
  }

  if (!response.ok) {
    throw new SupabaseDataError(
      `Supabase 查詢失敗（HTTP ${response.status}）。請確認 migration、公開金鑰與 RLS 設定。`,
    );
  }

  try {
    const body: unknown = await response.json();
    return body;
  } catch {
    throw new SupabaseDataError("Supabase 回傳的資料格式無法讀取。");
  }
}

function parseLocalization(value: unknown): EquipLocalization {
  if (!isJsonRecord(value)) {
    throw new SupabaseDataError("Supabase 回傳的文字記錄格式不正確。");
  }
  const { snapshot_id, data_code, language, msg_type, message } = value;
  if (
    typeof snapshot_id !== "string" ||
    typeof data_code !== "string" ||
    typeof language !== "string" ||
    (msg_type !== null && typeof msg_type !== "string") ||
    (message !== null && typeof message !== "string")
  ) {
    throw new SupabaseDataError("Supabase 回傳的文字記錄欄位不完整。");
  }
  const displayMessage =
    message?.replace(/(^|[^\\])\\n/g, "$1\n") ?? null;
  return {
    snapshotId: snapshot_id,
    dataCode: data_code,
    language,
    messageType: msg_type,
    message,
    displayMessage,
  };
}

export async function getPublishedVersion(): Promise<PublishedVersion | null> {
  const params = new URLSearchParams({
    select: "snapshot_id,source_version,record_count",
    status: "eq.published",
    limit: "1",
  });
  const body = await getJson("ranger_dataset_versions", params);
  if (!Array.isArray(body)) {
    throw new SupabaseDataError("Supabase 版本資料格式不正確。");
  }
  if (body.length === 0) return null;

  const row = body[0];
  if (
    !isJsonRecord(row) ||
    typeof row.snapshot_id !== "string" ||
    typeof row.source_version !== "string" ||
    typeof row.record_count !== "number"
  ) {
    throw new SupabaseDataError("已發布版本資訊不完整。");
  }
  return {
    snapshotId: row.snapshot_id,
    sourceVersion: row.source_version,
    recordCount: row.record_count,
  };
}

export async function searchPublishedLocalizations(
  snapshotId: string,
  query: string,
  page: number,
  pageSize: number,
  language = "zh-Hant",
): Promise<SearchResult> {
  const params = new URLSearchParams({
    p_snapshot_id: snapshotId,
    p_language: language,
    p_query: query,
    p_page: String(page),
    p_page_size: String(pageSize),
  });
  const body = await getJson("rpc/ranger_search_equip_localizations", params);
  if (
    !isJsonRecord(body) ||
    typeof body.totalCount !== "number" ||
    !Array.isArray(body.items)
  ) {
    throw new SupabaseDataError("Supabase 搜尋結果格式不正確。");
  }
  return {
    totalCount: body.totalCount,
    items: body.items.map(parseLocalization),
  };
}

export async function getPublishedLocalization(
  snapshotId: string,
  dataCode: string,
  language: string,
): Promise<EquipLocalization | null> {
  const params = new URLSearchParams({
    select: "snapshot_id,data_code,language,msg_type,message",
    snapshot_id: `eq.${snapshotId}`,
    data_code: `eq.${dataCode}`,
    language: `eq.${language}`,
    limit: "1",
  });
  const body = await getJson("ranger_equip_localizations", params);
  if (!Array.isArray(body)) {
    throw new SupabaseDataError("Supabase 詳細資料格式不正確。");
  }
  if (body.length === 0) return null;
  return parseLocalization(body[0]);
}
