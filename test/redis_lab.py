"""Redis 五类型动手实验（fakeredis 内存版，命令与真 Redis 完全一致）。

用法：PYTHONPATH=. .venv/bin/python test/redis_lab.py
学习法：每个类型锚一个你业务里的用途——不背类型，记"问题→类型"的映射。
"""

import fakeredis

r = fakeredis.FakeRedis(decode_responses=True)

print("=" * 60)
print("String --- 并网任务项的应用")
print("=" * 60)
r.set("binNetProcess:1234501", '{"task01": "wait","task02": "success","task03": "fail","task04": "wait","task05": "success"}', ex=3600)
print("get binNetProcess:1234501->", r.get("binNetProcess:1234501"))
r.set("binNetProcess:1234501", '{"task01": "success","task02": "success","task03": "fail","task04": "wait","task05": "success"}', ex=3600)
print("get binNetProcess:1234501->", r.get("binNetProcess:1234501"))

print("=" * 60)
print("① String —— 万能口袋：缓存对象、计数器")
print("=" * 60)
# 场景：缓存一条报警记录 + 统计本周报警数
r.set("alarm:10086", '{"service": "merchant-kernel", "level": "P1"}', ex=3600)
print("get alarm:10086 →", r.get("alarm:10086"))
r.incr("alarm:count:week")   # incr 是原子计数，不用读改写
r.incr("alarm:count:week")
print("incr alarm:count:week ×2 →", r.get("alarm:count:week"))
print("ttl alarm:10086 →", r.ttl("alarm:10086"), "秒（ex=过期时间）")

print()
print("=" * 60)
print("② Hash —— 对象字段级存储：不用整存整取整个 JSON")
print("=" * 60)
# 场景：商户信息，可以只改一个字段
r.hset("merchant:1001", mapping={"name": "测试商户", "status": "合作中", "store_count": 3})
r.hincrby("merchant:1001", "store_count", 1)   # 只更新一个字段，不用读出整个对象
print("hget name →", r.hget("merchant:1001", "name"))
print("hincrby store_count +1 →", r.hget("merchant:1001", "store_count"))
print("hgetall →", r.hgetall("merchant:1001"))

print()
print("=" * 60)
print("③ Set —— 去重集合：天然防重")
print("=" * 60)
# 场景：报警去重（同一条报警重复推送只记一次）
r.sadd("alarm:pushed", "alarm:10086")
r.sadd("alarm:pushed", "alarm:10086")   # 重复添加自动去重
r.sadd("alarm:pushed", "alarm:10087")
print("sadd 同一报警两次 + 另一条 →", r.smembers("alarm:pushed"))
print("sismember alarm:10086 →", r.sismember("alarm:pushed", "alarm:10086"), "（判断推没推过）")

print()
print("=" * 60)
print("④ ZSet —— 带分数的排序：排行榜专用")
print("=" * 60)
# 场景：报警治理的周报排名（你的真实场景！）
r.zadd("alarm:rank:weekly", {"merchant-kernel": 25, "fund-service": 12, "merchant-admin": 8})
r.zincrby("alarm:rank:weekly", 3, "fund-service")   # fund 又来 3 条
print("zrevrange 排名 →", r.zrevrange("alarm:rank:weekly", 0, -1, withscores=True))

print()
print("=" * 60)
print("⑤ List —— 队列：左进右出就是任务队列")
print("=" * 60)
# 场景：待跟进的报警任务队列
r.rpush("alarm:queue", "alarm:10086", "alarm:10087", "alarm:10088")
print("rpush 三条 →", r.lrange("alarm:queue", 0, -1))
print("lpop 取一条处理 →", r.lpop("alarm:queue"), "| 剩余:", r.lrange("alarm:queue", 0, -1))

print()
print("=" * 60)
print("记忆图（问题 → 类型）：")
print("  缓存一个东西/数数        → String")
print("  一个对象的字段要单独改   → Hash")
print("  去重/推没推过            → Set")
print("  排名/按分数排序          → ZSet")
print("  排队                     → List")
