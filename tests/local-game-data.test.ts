import { afterEach, expect, it, vi } from "vitest";
import { mkdir, rm } from "node:fs/promises";
import path from "node:path";
import { DatabaseSync } from "node:sqlite";
vi.mock("server-only",()=>({}));
import { readNormalizedText,readCollectionTarget } from "../lib/local-game-data";
import { guildRefreshWindow } from "../lib/update-policy";

const testFile = `data/local/test-${process.pid}-${Date.now()}.private.sqlite`;
afterEach(async()=>{vi.unstubAllEnvs();await rm(testFile,{force:true});});

it("reads the active database version without relying on the JSON source file",async()=>{
  await mkdir(path.dirname(testFile),{recursive:true});
  const db=new DatabaseSync(testFile);
  db.exec("CREATE TABLE documents(sha256 TEXT PRIMARY KEY,payload TEXT); CREATE TABLE current_documents(filename TEXT PRIMARY KEY,sha256 TEXT);");
  db.prepare("INSERT INTO documents VALUES (?,?)").run("old",'{"version":"old"}');
  db.prepare("INSERT INTO documents VALUES (?,?)").run("new",'{"version":"new","value":444}');
  db.prepare("INSERT INTO current_documents VALUES (?,?)").run("verified-equipment.json","new");db.close();
  vi.stubEnv("NODE_ENV","development");vi.stubEnv("LR_LOCAL_DATABASE_PATH",testFile);
  expect(JSON.parse(await readNormalizedText("verified-equipment.json"))).toEqual({version:"new",value:444});
  await expect(readNormalizedText("guild-roster.private.json")).rejects.toThrow("尚未匯入");
});
it("rejects arbitrary files and database paths outside local storage",async()=>{
  vi.stubEnv("NODE_ENV","development");vi.stubEnv("LR_LOCAL_DATABASE_PATH","../other.sqlite");
  await expect(readNormalizedText("verified-equipment.json")).rejects.toThrow("data/local");
  await expect(readNormalizedText(".env.local")).rejects.toThrow("不支援");
});
it("uses Tuesday noon in Taiwan, independent of host time zone",()=>{
  expect(guildRefreshWindow("2026-11-24T03:59:59Z",new Date("2026-11-24T04:00:00Z"))).toEqual({due:true,nextUpdateAt:"2026-12-01T04:00:00.000Z"});
  expect(guildRefreshWindow("2026-11-24T04:00:00Z",new Date("2026-11-24T04:00:00Z"))).toEqual({due:false,nextUpdateAt:"2026-12-01T04:00:00.000Z"});
  expect(guildRefreshWindow("2026-11-23T04:00:00Z",new Date("2026-11-24T03:59:59Z"))).toEqual({due:false,nextUpdateAt:"2026-11-24T04:00:00.000Z"});
});
it("keeps the user-selected guild and ranking-only PVP policy outside game snapshots",async()=>{
  await mkdir(path.dirname(testFile),{recursive:true});const db=new DatabaseSync(testFile);
  db.exec("CREATE TABLE collection_targets(module TEXT PRIMARY KEY,target_name TEXT,source TEXT,selected_at TEXT)");
  db.prepare("INSERT INTO collection_targets VALUES (?,?,?,?)").run("guild","測試目標公會","user","2026-11-25T00:00:00Z");
  db.prepare("INSERT INTO collection_targets VALUES (?,?,?,?)").run("pvp","rankings","user","2026-11-25T00:00:00Z");db.close();
  vi.stubEnv("NODE_ENV","development");vi.stubEnv("LR_LOCAL_DATABASE_PATH",testFile);
  expect(await readCollectionTarget("guild")).toBe("測試目標公會");expect(await readCollectionTarget("pvp")).toBe("rankings");
});
