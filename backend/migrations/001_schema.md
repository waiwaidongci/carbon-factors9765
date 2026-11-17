# 初始结构

SQLAlchemy启动创建以下业务表：activity_periods, activities, emission_factors, carbon_runs, delivery_schedules, deliveries、users、audits。Source专属JSON字段由对应validation严格校验；Policy为不可覆盖的版本记录；Run保存source/policy冻结快照；Period仅用于已有期间选择器，不计入核心复杂度。已有数据库升级需先备份，后续字段演进应以独立迁移执行。

# 002 绿电凭证用电核算（随启动 create_all 自动建表）

新增四表，均由 SQLAlchemy `Base.metadata.create_all` 在应用/worker 启动时创建，已有库无需手工 DDL：

- `green_certificates`：绿电凭证登记。字段 code(唯一)、month 适用月份、department 适用部门、factor 凭证排放因子(kgCO₂e/kWh)、kwh_total 登记电量、kwh_remaining 可用余额、created。
- `green_reports`：用电核算报告。登记 month/department/kwh/grid_factor；status 取 draft/queued/running/completed/failed；attempt 为行版本围栏；frozen 为排队时冻结的底稿、因子、最优分配与 SHA256；result 为核销结果；heartbeat 用于看门狗判定认领后崩溃。
- `green_reservations`：预占记录（report_id, attempt, certificate_id, kwh），(report_id,attempt,certificate_id) 唯一。排队即写入并扣减余额；核销成功后删除转正；失败/取消/看门狗恢复时释放。
- `green_ledger`：额度流水 register/reserve/release/consume，带 balance_after，支持逐条追查与额度守恒核对。

额度守恒恒等式：`kwh_total - kwh_remaining = 在途预占(reservations) + 已核销(completed 报告 result.allocations)`，由 `/green/conservation` 与核销前校验共同保证。并发写在 PostgreSQL 用 `pg_advisory_xact_lock` 串行化，SQLite 用进程内 RLock + `BEGIN IMMEDIATE`；`attempt` 围栏保证旧执行者/重复消息晚到不重复扣额。
