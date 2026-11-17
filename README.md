# 棠原试验室碳因子结算册

合成用电/燃料/出行活动→因子核算与差异说明→站内周期结算；范围声明与缺因子拒绝

## 业务场景与工作流
模拟客户：棠原研究协作组，12位业务与分析人员。每月研究明细先从`carbon-factors-202611.csv`录入底稿，经口径冻结、Python核算、负责人复核后向业务阅读者交付站内CSV。原有流程依靠人工表格抄算，痛点为口径版本难追溯、重复计算易错、复核与交付脱节。

模块：业务总览、业务底稿、新建口径版本、异步核算与复核、定时交付、站内收件箱、审计。底稿可新增/修改/删除；口径仅新增版本；报告提交时冻结来源与版本并保存SHA256。定时交付引用已复核报告快照，worker到期写入数据库，业务阅读者下载。

## 算法口径
单位转换、因子版本冻结、用量×因子与部门透视。kWh/MWh单位换算手算；缺单位因子拒绝；因子更新旧报告不变。

活动量 × 因子 · 单位与范围随报告保存。输入：业务底稿与口径JSON；输出：summary、透视rows、method、warnings。算法实现在`backend/src/services/calculation.py`，输入校验在`validation.py`。固定seed=42，240条合成数据；未对接真实业务系统。修改源数据和新建因子/口径不会改变已提交报告。

## 一天的验收剧本
1. 09:00 admin查看240条seed底稿与具名业务期间。
2. 09:10 analyst添加`carbon-factors-202611.csv`的一条具名业务记录。
3. 09:20 admin在口径版本页登记新版本；旧版本保留。
4. 09:30 analyst命名“十一月核算”并选择期间/版本排队。
5. 09:31 Redis worker真实执行Python计算，展示汇总/透视与口径边界。
6. 09:40 admin核对数值后填写至少4字复核说明。
7. 09:45 admin建立60秒周期计划，worker到期生成站内持久化交付。
8. 09:46 viewer在站内收件箱下载交付CSV；审计页查看操作者与时间。

## 快速启动
```sh
cp .env.example .env
docker compose up -d --build
docker compose exec -T backend python -m scripts.seed_demo
```
前端 http://localhost:18254 ，后端 http://localhost:19254/docs ，数据库宿主端口17754。中文父目录可用。恰好5服务frontend/backend/worker/db/redis；均有真实healthcheck。停止并清空演示数据：`docker compose down -v --remove-orphans`。

|角色|邮箱|密码|权限|
|---|---|---|---|
|admin|admin@demo.local|Demo2026!|全部底稿、口径版本、核算、复核、调度|
|analyst|analyst@demo.local|Demo2026!|底稿增改删、核算、导出；无复核/调度/口径写权限|
|viewer|viewer@demo.local|Demo2026!|只读；仅可下载已复核报告与站内交付|

## 工程结构与开发
Python3.11/FastAPI/SQLAlchemy/Redis，PostgreSQL16；前端原生HTML/CSS/JS ES modules，Nginx代理`/api/`剥前缀至后端。`frontend/src`按api/stores/pages/components/hooks/utils/router/constants/types拆分；`backend/src`按models/schemas/services/controllers/routes/middlewares/config/utils/constants拆分；`backend/scripts/seed_demo.py`自然键幂等且不覆盖用户修改。SQLAlchemy启动创建初始结构，迁移说明在backend/migrations。

后端开发：在backend安装requirements，设置DATABASE_URL/REDIS_URL/JWT_SECRET，`uvicorn src.main:app --reload`；前端可用Nginx或带同等代理的静态开发服务器。前后端全部业务计算在Python。

环境变量：COMPOSE_PROJECT_NAME、FRONTEND_PORT、BACKEND_PORT、DB_PORT、JWT_SECRET（部署替换）、DATABASE_URL、REDIS_URL、SEED_DEMO。`.env`不入Git。数据库/Redis/共享产物为命名卷。共享角色枚举admin/analyst/viewer与状态queued/running/completed/failed分别定义于backend/src/constants/enums.py和frontend/src/constants/enums.js。两个中间件：统一可恢复校验错误、每IP每分钟360请求限流。

## 已知边界
定时分发为站内收件箱；一名worker轮询执行，无外部邮件。调度发送已复核固定报告快照，不自动重算新数据。时间显示Asia/Shanghai。报告导出适合小型数据；底稿全量加载240行演示数据。Google Fonts不可用时回退serif。后端API以专属字段对象收发，页面通过业务输入控件编辑，不要求用户写JSON。新增来源期间自动可选；专属字段和算法严格校验。JWT演示有效期2小时。

MIT License。

## 实际实体映射
来源记录（Source，专属业务字段校验）、口径版本（Policy）、核算报告（Run）、交付计划（Schedule）、交付（Delivery）均经数据库→模型→请求schema→service→route/controller→frontend API→store→page。Period为已有来源期间字典，在任务期间选择器使用；不单独作为复杂度计数。底稿JSON为小型多字段单记录存储，不虚构未落库的子实体。

实际表：期间字典 activity_periods；专属来源 activities；冻结口径 emission_factors；异步报告 carbon_runs。

## 限额绿电凭证用电核算（green 模块）

绿电凭证按 凭证编号、适用月份、适用部门、凭证排放因子(kgCO₂e/kWh)、登记电量(kWh) 登记，余额跨报告共用。用电报告登记 月份、部门、用电量、电网因子。仅当凭证与报告的月份、部门同时匹配时该凭证才可用于该报告。

分配目标为字典序：①先最大化被绿电覆盖的电量；②在覆盖最大的前提下最小化总排放。算法在 `backend/src/services/mcmf.py` 用最小费用最大流一次求解（费用=凭证因子−电网因子），不是逐条贪心；`exhaustive.py` 提供小规模穷举 oracle，`scripts/verify_green.py` 与 `tests/` 用穷举对照验证最优解（逐条贪心在“最小化排放”上会漏配，测试有反例）。

事务与额度生命周期：发起核算即排队，冻结底稿、因子与最优分配（保存 SHA256）并**预占额度**（余额立即扣减，写 green_reservations 与 reserve 流水）；worker 认领（claim，条件更新做围栏）后计算，**成功才核销**（预占转正、删除预占行、写 consume，余额不再变动）；**失败或取消则释放**（余额还原、写 release）。已完成报告与交付保留原分配，不可重新核算。

可靠性：`green_reports.attempt` 为行版本围栏，旧执行者晚到、消息重试/重复投递均无法重复扣额（claim/run 条件不匹配即跳过）。worker 认领后崩溃由看门狗 `recover_stale`（心跳超时）释放旧预占并按当前余额重新排队，余额同成同败。并发排队在 PostgreSQL 用 `pg_advisory_xact_lock`、SQLite 用进程内 RLock + `BEGIN IMMEDIATE` 串行化。额度恒等式 `登记额−可用余额 = 在途预占 + 已核销` 由 `/green/conservation` 与核销前守恒校验保证，全部余额变动落 `green_ledger` 流水可逐条追查。Redis 不可用时绿电任务自动回退数据库轮询。

新增表：green_certificates、green_reports、green_reservations、green_ledger（启动 create_all 自动建表，详见 backend/migrations/001_schema.md）。前端“绿电凭证核算”页可登记凭证、登记用电并发起/取消核算、追查每张凭证余额、每份报告的预占/核销分配与完整额度流水。穷举与守恒验证：`cd backend && PYTHONPATH=.pydeps python3 -m scripts.verify_green`，单测 `python3 -m unittest discover -s tests`。
