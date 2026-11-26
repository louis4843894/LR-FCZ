import mitmproxy.http
import json

class LineRangersInterceptor:
    def response(self, flow: mitmproxy.http.HTTPFlow):
        # 假設網域包含 linegame，實際需根據你抓包觀察到的網域修改
        if "linegame.jp" in flow.request.pretty_url:
            try:
                # 嘗試解析回應的 JSON
                data = json.loads(flow.response.get_text())

                # 將攔截到的資料寫入你本地的 json 檔案，供前端讀取
                with open("rangers_api_dump.json", "a", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False)
                    f.write("\n")

                print(f"✅ 成功攔截並儲存資料: {flow.request.pretty_url}")
            except json.JSONDecodeError:
                pass # 若非 JSON 格式則忽略

addons = [LineRangersInterceptor()]