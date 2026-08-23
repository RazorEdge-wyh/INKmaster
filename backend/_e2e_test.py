import httpx, json, os

# 可通过环境变量覆盖，如 $env:INKMASTER_TEST_BASE="http://127.0.0.1:8000"
B = os.environ.get("INKMASTER_TEST_BASE", "http://127.0.0.1:8000")
c = httpx.Client(timeout=30)

# 1. 创建书
r = c.post(f"{B}/api/v1/books", json={"title": "测试书", "concept": "被家族抛弃的少年觉醒血脉", "genre": "玄幻", "targetWords": 500000})
r.raise_for_status()
book = r.json()
bid = book["id"]
print("创建书:", book["title"], bid)

# 2. 创建章节
r = c.post(f"{B}/api/v1/books/{bid}/chapters", json={"number": 1, "title": "第一章", "content": "这是测试正文内容。", "source": "manual"})
r.raise_for_status()
ch = r.json()
print("创建章节:", ch["title"], "字数", ch["wordCount"])

# 3. 章节列表 + 单章
r = c.get(f"{B}/api/v1/books/{bid}/chapters")
print("章节列表:", len(r.json()))
r = c.get(f"{B}/api/v1/books/{bid}/chapters/{ch['id']}")
print("单章:", r.json()["title"])

# 4. 导出 txt
r = c.get(f"{B}/api/v1/books/{bid}/export", params={"format": "txt"})
print("导出txt前缀:", r.text[:40])
print("Content-Disposition:", r.headers.get("content-disposition"))

# 5. 导出 json
r = c.get(f"{B}/api/v1/books/{bid}/export", params={"format": "json"})
print("导出json:", r.json()["chapters"][0]["title"])

# 6. token-stats
r = c.get(f"{B}/api/v1/books/{bid}/token-stats")
print("token-stats:", r.json())

# 7. model-config 加密存储
r = c.post(f"{B}/api/v1/model-configs", json={"provider": "deepseek", "model": "deepseek-v4-pro", "apiKey": "sk-test-1234567890"})
cid = r.json()["id"]
print("创建配置:", r.json())
r = c.get(f"{B}/api/v1/model-configs")
print("配置列表(hasKey应为true,不含明文):", r.json())

# 8. 删除配置 + 删除书
c.delete(f"{B}/api/v1/model-configs/{cid}")
r = c.delete(f"{B}/api/v1/books/{bid}")
print("删除书:", r.json())

# 9. 验证级联删除：书籍删除后，其下的章节应为空（列表端点返回 200 空数组）
r = c.get(f"{B}/api/v1/books/{bid}/chapters")
print("删除后章节列表(应为空数组200):", r.status_code, r.json())
assert r.status_code == 200 and r.json() == []

print("\n全部通过 ✅")