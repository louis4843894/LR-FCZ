import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("server-only", () => ({}));

import {
  getPublishedLocalization,
  getPublishedVersion,
  searchPublishedLocalizations,
  SupabaseDataError,
} from "../lib/ranger-supabase";

const originalUrl = process.env.NEXT_PUBLIC_SUPABASE_URL;
const originalKey = process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY;
const mockFetch = vi.fn<typeof fetch>();

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  });
}

describe("Supabase published localization reads", () => {
  beforeEach(() => {
    process.env.NEXT_PUBLIC_SUPABASE_URL = "https://example.supabase.co";
    process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY =
      "sb_publishable_test_only";
    vi.stubGlobal("fetch", mockFetch);
    mockFetch.mockReset();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    if (originalUrl === undefined) {
      delete process.env.NEXT_PUBLIC_SUPABASE_URL;
    } else {
      process.env.NEXT_PUBLIC_SUPABASE_URL = originalUrl;
    }
    if (originalKey === undefined) {
      delete process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY;
    } else {
      process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY = originalKey;
    }
  });

  it("requests only the newest published dataset version", async () => {
    mockFetch.mockResolvedValue(
      jsonResponse([
        {
          snapshot_id: "snapshot-test",
          source_version: "test-version",
          record_count: 1,
        },
      ]),
    );

    await expect(getPublishedVersion()).resolves.toEqual({
      snapshotId: "snapshot-test",
      sourceVersion: "test-version",
      recordCount: 1,
    });

    const requestUrl = new URL(String(mockFetch.mock.calls[0]?.[0]));
    expect(requestUrl.pathname).toBe("/rest/v1/ranger_dataset_versions");
    expect(requestUrl.searchParams.get("status")).toBe("eq.published");
    expect(requestUrl.searchParams.get("select")).toBe(
      "snapshot_id,source_version,record_count",
    );
    expect(requestUrl.searchParams.get("limit")).toBe("1");
  });

  it("sends search and pagination to the database RPC", async () => {
    mockFetch.mockResolvedValue(
      jsonResponse({
        totalCount: 1,
        items: [
          {
            snapshot_id: "snapshot-test",
            data_code: "CODE_TEST",
            language: "zh-Hant",
            msg_type: "EQUIP",
            message: "僅供單元測試",
          },
        ],
      }),
    );

    await expect(
      searchPublishedLocalizations(
        "snapshot-test",
        "測試 & 搜尋",
        2,
        10,
      ),
    ).resolves.toEqual({
      totalCount: 1,
      items: [
        {
          snapshotId: "snapshot-test",
          dataCode: "CODE_TEST",
          language: "zh-Hant",
          messageType: "EQUIP",
          message: "僅供單元測試",
          displayMessage: "僅供單元測試",
        },
      ],
    });

    const requestUrl = new URL(String(mockFetch.mock.calls[0]?.[0]));
    expect(requestUrl.pathname).toBe(
      "/rest/v1/rpc/ranger_search_equip_localizations",
    );
    expect(requestUrl.searchParams.get("p_query")).toBe("測試 & 搜尋");
    expect(requestUrl.searchParams.get("p_page")).toBe("2");
    expect(requestUrl.searchParams.get("p_page_size")).toBe("10");
  });

  it("decodes literal newline escapes once for display while preserving the source", async () => {
    const rawMessage = "[YSH]\\n日暮永遠的制服\n實際換行\\\\n保留字面內容";
    mockFetch.mockResolvedValue(
      jsonResponse([
        {
          snapshot_id: "snapshot-test",
          data_code: "eq_2202_amr_06_nm",
          language: "zh-Hant",
          msg_type: "EQUIP",
          message: rawMessage,
        },
      ]),
    );

    await expect(
      getPublishedLocalization(
        "snapshot-test",
        "eq_2202_amr_06_nm",
        "zh-Hant",
      ),
    ).resolves.toEqual({
      snapshotId: "snapshot-test",
      dataCode: "eq_2202_amr_06_nm",
      language: "zh-Hant",
      messageType: "EQUIP",
      message: rawMessage,
      displayMessage: "[YSH]\n日暮永遠的制服\n實際換行\\\\n保留字面內容",
    });
  });

  it("returns null when the published record is not found", async () => {
    mockFetch.mockResolvedValue(jsonResponse([]));

    await expect(
      getPublishedLocalization("snapshot-test", "MISSING_TEST_CODE", "zh-Hant"),
    ).resolves.toBeNull();
  });

  it("surfaces non-successful Supabase responses without response-body leakage", async () => {
    mockFetch.mockResolvedValue(jsonResponse({ message: "private test body" }, 401));

    await expect(getPublishedVersion()).rejects.toThrow(
      new SupabaseDataError(
        "Supabase 查詢失敗（HTTP 401）。請確認 migration、公開金鑰與 RLS 設定。",
      ),
    );
  });
});
