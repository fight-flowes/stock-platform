# A股投研数据平台 v5.1 技术文档

> **v5.1 版本在 v4.1 基础上完成路径与版本标识统一** —— 启动脚本、运行元信息、前端展示和主文档现已全部对齐到 `calenderappv5.1`。

---

## 目录

- [1. 项目概述](#1-项目概述)
- [2. 版本历史](#2-版本历史)
- [3. 技术架构](#3-技术架构)
- [4. 功能模块](#4-功能模块)
- [5. 数据库设计](#5-数据库设计)
- [6. API 接口](#6-api-接口)
- [7. 部署运维](#7-部署运维)
- [8. 开发规范](#8-开发规范)
- [9. 未来规划](#9-未来规划)

---

## 1. 项目概述

### 1.1 项目定位

A股投研数据平台是一个面向 A 股投资者的数据管理和分析系统，核心功能包括：

| 功能模块 | 说明 |
|---------|------|
| 交易日历 | 交易日/休息日标记、农历日期、节假日管理 |
| 事件管理 | 投研事件记录、重要性分级、关联股票 |
| 涨停股分析 | 涨停数据、连板榜、资金流向、概念热度 |
| 股票信息 | 股票基础数据、交易所分类 |

### 1.2 项目目录

```
calenderappv5.1/
├── backend/                 # 后端服务
│   ├── app/
│   │   ├── api/            # API 路由
│   │   ├── models/         # 数据模型
│   │   ├── services/       # 业务逻辑
│   │   └── db.py           # 数据库连接
│   ├── migrations/         # 数据库迁移脚本
│   ├── main.py             # 入口文件
│   └── .env                # 环境配置
├── frontend/                # 前端服务
│   ├── src/
│   │   ├── views/          # 页面组件
│   │   ├── api/            # API 调用
│   │   ├── router/         # 路由配置
│   │   └── styles/         # 样式文件
│   ├── index.html
│   └── package.json
├── docs/                    # 文档
├── manage.sh                # 服务管理脚本
└── README.md
```

---

## 2. 版本历史

### 2.1 v5.1（当前版本）- 2026-05-29

| 改进项 | 说明 |
|--------|------|
| 启动路径统一 | `manage.sh`、定时脚本、测试脚本全部切换到 `calenderappv5.1` |
| 版本标识统一 | 前端标题、登录页、API 文档、健康检查、包名统一升级到 `v5.1` |
| 文档同步 | README 当前版本、目录结构、示例 Token 与启动路径已更新 |

### 2.2 v4.1 - 2026-04-03

**由 OpenClaw (GLM-5) 参与研发**

| 改进项 | 说明 |
|--------|------|
| 分区表架构 | 涨停股表按月分区，解决数据膨胀问题 |
| 服务管理脚本 | `manage.sh` 一键启动/停止/状态检查 |
| 分区管理 API | `/api/partition` 接口管理分区 |
| 项目重命名 | 股票日历事件管理系统 → A股投研数据平台 |
| **涨停股分析** | **读取 MinIO 中已产出的 Markdown 报告并展示** |
| **K线走势图** | **近60日K线、分时线图表展示** |
| **登录认证** | **Token 认证机制** |
| 文档完善 | 分区设计文档、技术文档整合 |

### 2.3 v3.2（v2.1）

| 改进项 | 说明 |
|--------|------|
| 主题切换 | 亮色/暗色一键切换，持久化存储 |
| 股票管理页 | 股票列表分页、交易所筛选、搜索、创建/更新 |
| 筛选体验 | 关键词/股票输入防抖，减少频繁请求 |

### 2.4 v3.1

| 改进项 | 说明 |
|--------|------|
| UI 框架升级 | Element Plus + FullCalendar |
| 事件 CRUD | 创建/编辑/删除闭环 |
| 日历视图 | 月/周/日/列表视图 |

---

## 3. 技术架构

### 3.1 技术栈

| 层级 | 技术 | 版本 |
|------|------|------|
| 前端框架 | Vue 3 | 3.3.4 |
| 构建工具 | Vite | 4.4.5 |
| UI 组件 | Element Plus | 2.13.2 |
| 日历组件 | FullCalendar | 6.1.20 |
| 后端框架 | Flask + Flask-RESTX | - |
| 数据库 | PostgreSQL | 15 |
| 容器化 | Docker | - |
| Python 环境 | Conda (stock) | 3.11 |

### 3.2 系统架构图

```
┌─────────────────────────────────────────────────────────────┐
│                        前端 (Vue3)                          │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐    │
│  │ 日历视图  │  │ 股票管理  │  │ 涨停分析  │  │ 主题切换  │    │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘    │
└─────────────────────────────────────────────────────────────┘
                              │ HTTP/REST
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                     后端 (Flask RESTX)                       │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐    │
│  │ Calendar │  │  Events  │  │ Stocks   │  │Limit Up  │    │
│  │   API    │  │   API    │  │   API    │  │   API    │    │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘    │
│  ┌──────────┐  ┌──────────┐                                 │
│  │Partition │  │  System  │                                 │
│  │   API    │  │   API    │                                 │
│  └──────────┘  └──────────┘                                 │
└─────────────────────────────────────────────────────────────┘
                              │ SQLAlchemy
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                   PostgreSQL (Docker)                        │
│  ┌──────────────────────────────────────────────────────┐  │
│  │                    Schema: sc                         │  │
│  │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────────┐ │  │
│  │  │ stocks  │ │calendar_│ │ events  │ │limit_up_    │ │  │
│  │  │         │ │  days   │ │         │ │stocks(分区) │ │  │
│  │  └─────────┘ └─────────┘ └─────────┘ └─────────────┘ │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

---

## 4. 功能模块

### 4.1 交易日历模块

**页面**: `CalendarView.vue`

| 功能 | 说明 |
|------|------|
| 多视图切换 | 月/周/日/列表视图 |
| 日期点击 | 打开当日事件抽屉 |
| 事件渲染 | 颜色标识重要性，显示标题和关联股票 |
| 筛选功能 | 关键词搜索、股票筛选、类型筛选 |
| 防抖优化 | 输入框防抖，减少请求频率 |

### 4.2 股票管理模块

**页面**: `StocksView.vue`

| 功能 | 说明 |
|------|------|
| 股票列表 | 分页展示，支持交易所筛选 |
| 搜索 | 按代码/名称搜索 |
| 创建/更新 | Upsert 模式，代码唯一 |

### 4.3 涨停股模块

**页面**: `LimitUpView.vue`

| 功能 | API | 说明 |
|------|-----|------|
| 涨停列表 | GET /api/limit-up | 分页、筛选、排序 |
| 连板榜 | GET /api/limit-up/consecutive | 按日期查询连板股 |
| 龙头股 | GET /api/limit-up/dragon-head | 当日龙头列表 |
| 区间统计 | GET /api/limit-up/statistics | 涨停数量、行业分布 |
| 资金流向 | GET /api/limit-up/fund-flow | 机构/游资净买入排行 |
| 概念热度 | GET /api/limit-up/concept-hot | 概念出现频率统计 |
| CSV 导入 | POST /api/limit-up/import | 批量导入涨停数据 |
| 快速同步 | POST /api/limit-up/sync-tushare | 从 Tushare 同步涨停 |
| **完整同步** | POST /api/limit-up/sync-full | 涨停+龙虎榜+概念+龙头 |
| **批量同步** | POST /api/limit-up/sync-range | 按日期范围批量同步 |
| **热门概念** | GET /api/limit-up/hot-concepts | 当日热门概念板块 |
| **股票概念** | GET /api/limit-up/stock-concepts/{code} | 查询股票所属概念 |
| **龙头识别** | POST /api/limit-up/identify-dragon | 自动识别龙头股 |

#### 涨停数据来源（Tushare）

| 数据类型 | Tushare 接口 | 说明 |
|---------|-------------|------|
| 涨停列表 | limit_list_d | 每日涨停股详情 |
| 龙虎榜 | top_inst | 机构/游资买卖明细 |
| 概念板块 | concept_detail | 股票所属概念 |
| 交易日历 | trade_cal | 交易日查询 |

#### 涨停数据范围

**重要**：只要涨停过的股票都纳入分析，包括：

| limit_type | 类型 | 说明 |
|------------|------|------|
| U | 涨停封住 | 收盘时仍封住涨停价 |
| Z | 炸板 | 盘中涨停但收盘开板 |

#### limit_up_type 分类

| 值 | 说明 |
|-----|------|
| `first_board` | 首板（首次涨停，收盘封住） |
| `multi_board` | 连板（连续涨停≥2天，收盘封住） |
| `broken_board` | 炸板（盘中涨停但收盘开板） |

#### 龙头自动识别规则

1. **总龙头**：当日最高连板股（≥3板），强度评分最高
2. **板块龙头**：每个行业最高连板股（≥2板），强度评分最高

### 4.4 涨停股分析模块

从 MinIO 中读取单只涨停股票的 Markdown 分析报告，并导入本地展示链路。

| 功能 | API | 说明 |
|------|-----|------|
| 分析涨停股 | POST /api/limit-up/analyze | 调用分析服务 |
| 获取分析结果 | GET /api/limit-up/analysis/{code} | 查询历史分析 |

#### 分析内容

| 维度 | 说明 |
|------|------|
| 涨停原因 | 概念催化、资金推动、公告利好、技术特征、事件驱动 |
| 资金动向 | 机构/游资/北向资金分析，龙虎榜席位追踪 |
| 技术特征 | K线形态、量价关系、封板强度评分 |
| 公司画像 | 主营业务、核心概念、所属行业 |
| 综合结论 | 强度评级（1-5星）、龙头判断 |

#### 分析报告示例

```markdown
# 📈 中超控股 (002471.SZ) 涨停分析报告

## 一、基本信息
- 涨停日期: 2026-04-02
- 连板数: 1 板
- 封板时间: 09:36:09
- 封单金额: 0 万元
- 换手率: 33.89%

## 二、资金动向
- 资金特征: 游资主导
- 游资净买: 65388 万元

## 三、涨停原因分析
- 主要原因: 资金推动 (权重: 40%)

## 四、综合结论
- 强度评级: ★★★☆☆
- 龙头地位: 否
```

#### 数据存储

分析结果自动保存到 `sc.limit_up_analysis` 表，支持：
- 历史分析查询
- 同一股票同一天只保留一条记录
- 支持强制重新分析

### 4.5 主题切换模块

**实现文件**: `theme.js`, `theme.scss`

| 功能 | 说明 |
|------|------|
| 亮色/暗色切换 | 一键切换，localStorage 持久化 |
| Element Plus 适配 | 自动应用 Element 暗色主题 |
| FullCalendar 适配 | 自定义暗色样式 |

---

## 5. 数据库设计

### 5.1 Schema 设计

所有业务表位于 `sc` Schema 下。

### 5.2 表结构

#### 5.2.1 stocks - 股票基础信息表

| 字段 | 类型 | 说明 |
|------|------|------|
| id | SERIAL | 主键 |
| code | VARCHAR(32) | 股票代码（唯一） |
| name | VARCHAR(128) | 股票名称 |
| exchange | VARCHAR(16) | 交易所（SH/SZ/BJ） |
| created_at | TIMESTAMPTZ | 创建时间 |
| updated_at | TIMESTAMPTZ | 更新时间 |

#### 5.2.2 calendar_days - 交易日历表

| 字段 | 类型 | 说明 |
|------|------|------|
| day | DATE | 日期（主键） |
| lunar_day | VARCHAR(32) | 农历日期 |
| holiday_name | VARCHAR(64) | 节假日名称 |
| is_rest | BOOLEAN | 是否休息日 |
| is_work | BOOLEAN | 是否工作日 |
| created_at | TIMESTAMPTZ | 创建时间 |
| updated_at | TIMESTAMPTZ | 更新时间 |

#### 5.2.3 events - 日历事件表

| 字段 | 类型 | 说明 |
|------|------|------|
| id | SERIAL | 主键 |
| event_date | DATE | 事件日期 |
| title | VARCHAR(512) | 事件标题 |
| importance | INTEGER | 重要性等级（1-5） |
| event_type | VARCHAR(64) | 事件类型 |
| source | VARCHAR(256) | 来源 |
| description | TEXT | 描述 |
| stock_list | JSONB | 关联股票列表 |
| created_at | TIMESTAMPTZ | 创建时间 |
| updated_at | TIMESTAMPTZ | 更新时间 |

#### 5.2.4 limit_up_stocks - 涨停股表（按月分区）

**主键**: `(id, limit_up_date)` - 复合主键，包含分区键

| 字段分组 | 字段 | 类型 | 说明 |
|---------|------|------|------|
| 基本信息 | id | SERIAL | 主键 |
| | limit_up_date | DATE | 涨停日期（分区键） |
| | stock_code | VARCHAR(32) | 股票代码 |
| | stock_name | VARCHAR(128) | 股票名称 |
| 涨停特征 | consecutive_days | INTEGER | 连板数 |
| | limit_up_type | VARCHAR(32) | 涨停类型 |
| | seal_amount | DOUBLE | 封单金额（万元） |
| | seal_ratio | DOUBLE | 封单比 |
| | turnover_rate | DOUBLE | 换手率 |
| 时间信息 | first_limit_time | TIME | 首次涨停时间 |
| | last_limit_time | TIME | 最后涨停时间 |
| | open_count | INTEGER | 开板次数 |
| 板块概念 | industry | VARCHAR(64) | 所属行业 |
| | concept_tags | JSONB | 概念标签 |
| 资金动向 | institution_net_buy | DOUBLE | 机构净买入（万元） |
| | hot_money_net_buy | DOUBLE | 游资净买入（万元） |
| | north_net_buy | DOUBLE | 北向净买入（万元） |
| | total_net_buy | DOUBLE | 总净买入（万元） |
| 涨停原因 | reason_category | VARCHAR(32) | 原因分类 |
| | reason_detail | TEXT | 原因详情 |
| 强度评级 | strength_level | INTEGER | 强度等级（1-5） |
| | strength_score | DOUBLE | 强度评分 |
| 龙头判断 | is_dragon_head | BOOLEAN | 是否龙头 |
| | dragon_rank | INTEGER | 龙头排名 |
| 元数据 | source | VARCHAR(32) | 数据来源 |
| | created_at | TIMESTAMPTZ | 创建时间 |
| | updated_at | TIMESTAMPTZ | 更新时间 |

#### 5.2.5 limit_up_analysis - 涨停股分析报告表

**用途**: 存储从 MinIO 导入的涨停分析报告

| 字段分组 | 字段 | 类型 | 说明 |
|---------|------|------|------|
| 基本信息 | id | SERIAL | 主键 |
| | limit_up_id | INTEGER | 关联涨停记录 ID |
| | stock_code | VARCHAR(32) | 股票代码 |
| | stock_name | VARCHAR(128) | 股票名称 |
| | analysis_date | DATE | 分析日期 |
| 原因分析 | primary_reason | VARCHAR(32) | 主要原因 |
| | primary_reason_weight | DOUBLE | 主要原因权重 |
| | secondary_reason | VARCHAR(32) | 次要原因 |
| | secondary_reason_weight | DOUBLE | 次要原因权重 |
| 概念催化 | trigger_concepts | TEXT | 触发概念（JSON） |
| | concept_news | TEXT | 概念相关新闻 |
| 资金分析 | fund_character | VARCHAR(64) | 资金特征 |
| | institution_analysis | TEXT | 机构分析 |
| | hot_money_analysis | TEXT | 游资分析 |
| 技术特征 | kline_pattern | VARCHAR(64) | K线形态 |
| | volume_price | VARCHAR(64) | 量价关系 |
| | seal_strength | DOUBLE | 封板强度评分 |
| 公司画像 | main_business | TEXT | 主营业务 |
| | core_concepts | TEXT | 核心概念（JSON） |
| | industry | VARCHAR(64) | 所属行业 |
| 综合评估 | strength_rating | INTEGER | 强度评级（1-5） |
| | is_dragon | BOOLEAN | 是否龙头 |
| | dragon_type | VARCHAR(32) | 龙头类型 |
| 报告 | full_report | TEXT | 完整分析报告（Markdown） |
| 元数据 | analysis_source | VARCHAR(32) | 分析来源 |
| | created_at | TIMESTAMPTZ | 创建时间 |
| | updated_at | TIMESTAMPTZ | 更新时间 |

**唯一约束**: `(stock_code, analysis_date)` - 同一股票同一天只有一条分析记录

### 5.3 分区设计

涨停股表采用 **按月分区** 策略：

```sql
-- 主表定义
CREATE TABLE sc.limit_up_stocks (
    ...
    PRIMARY KEY (id, limit_up_date)
) PARTITION BY RANGE (limit_up_date);

-- 月分区示例
CREATE TABLE sc.limit_up_stocks_202604 
    PARTITION OF sc.limit_up_stocks 
    FOR VALUES FROM ('2026-04-01') TO ('2026-05-01');
```

**分区优势**：
- 查询只扫描相关分区，跳过历史数据
- 每日数据只写入当月分区，写入性能稳定
- 旧分区可单独归档或删除

**详细文档**: `docs/partition-design.md`

---

## 6. API 接口

### 6.1 接口概览

| 模块 | 路径前缀 | 说明 |
|------|---------|------|
| 系统 | /api/system | 健康检查、版本信息 |
| 日历 | /api/calendar | 交易日历查询 |
| 事件 | /api/events | 事件 CRUD |
| 股票 | /api/stocks | 股票管理 |
| 涨停股 | /api/limit-up | 涨停数据分析 |
| 分区 | /api/partition | 分区管理 |

### 6.2 涨停股接口详情

#### GET /api/limit-up

涨停股列表，支持分页和多条件筛选。

**Query 参数**:

| 参数 | 类型 | 说明 |
|------|------|------|
| page | int | 页码，默认 1 |
| page_size | int | 每页数量，默认 20 |
| start_date | string | 开始日期 |
| end_date | string | 结束日期 |
| consecutive_min | int | 最小连板数 |
| consecutive_max | int | 最大连板数 |
| industry | string | 行业筛选 |
| concept | string | 概念筛选 |
| strength_min | int | 最小强度等级 |
| strength_max | int | 最大强度等级 |
| is_dragon_head | bool | 仅龙头 |
| q | string | 搜索关键词 |

**响应示例**:

```json
{
  "code": 200,
  "message": "Success",
  "data": {
    "items": [...],
    "total": 200,
    "page": 1,
    "page_size": 20
  }
}
```

#### POST /api/limit-up/sync-tushare

从 Tushare 同步指定日期的涨停数据。

**Query 参数**:

| 参数 | 类型 | 说明 |
|------|------|------|
| date | string | 交易日期（YYYY-MM-DD） |

### 6.3 分区管理接口

#### GET /api/partition/status

获取分区状态，包括各分区大小、数据量。

#### POST /api/partition/create

创建指定月份的分区。

**Query 参数**:

| 参数 | 类型 | 说明 |
|------|------|------|
| year | int | 年份 |
| month | int | 月份 |

#### POST /api/partition/detach/{name}

分离指定分区（用于归档）。

### 6.4 涨停股分析接口

| 接口 | 方法 | 说明 |
|------|------|------|
| /api/limit-up/analyze | POST | 分析涨停股票 |
| /api/limit-up/analysis/{stock_code} | GET | 获取分析结果 |

#### POST /api/limit-up/analyze

分析涨停股票，优先从 MinIO 导入现有 Markdown 报告。

**Query 参数**:

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| stock_code | string | 是 | 股票代码（如 002471.SZ） |
| date | string | 是 | 分析日期（YYYY-MM-DD） |
| force | boolean | 否 | 强制重新分析，默认 false |

**返回示例**:

```json
{
  "code": 200,
  "message": "分析完成",
  "data": {
    "id": 1,
    "stock_code": "002471.SZ",
    "stock_name": "中超控股",
    "analysis_date": "2026-04-02",
    "primary_reason": "fund",
    "primary_reason_weight": 40.0,
    "fund_character": "游资主导",
    "kline_pattern": "首板启动",
    "seal_strength": 40.0,
    "strength_rating": 3,
    "full_report": "# 📈 中超控股涨停分析报告..."
  }
}
```

#### GET /api/limit-up/analysis/{stock_code}

获取已保存的分析结果。

**Query 参数**:

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| date | string | 是 | 分析日期（YYYY-MM-DD） |

### 6.5 认证说明

系统使用 Token 认证，默认 Token 配置在 `frontend/.env`：

```bash
# 默认 Token（生产环境请修改）
VITE_AUTH_TOKEN=research2024,stock123,a-stock-v5.1
```

**修改 Token**：

编辑 `frontend/.env` 文件，设置自己的 Token（多个用逗号分隔）。

**登录流程**：
1. 访问 http://127.0.0.1:3000 自动跳转到登录页
2. 输入正确的 Token 即可进入系统
3. 点击右上角用户图标可退出登录

---

## 7. 部署运维

### 7.1 环境要求

| 组件 | 要求 |
|------|------|
| Docker | 已安装并运行 |
| Conda | stock 环境（Python 3.11） |
| Node.js | 18+ |
| PostgreSQL | 15（Docker 容器） |

### 7.2 快速启动

```bash
# 进入项目目录
cd /home/leisaihua/workspace/stock_info/stock-platform/apps/calenderapp

# 启动所有服务
./manage.sh start

# 查看状态
./manage.sh status
```

### 7.3 服务管理脚本

| 命令 | 说明 |
|------|------|
| `./manage.sh start` | 启动所有服务 |
| `./manage.sh stop` | 停止所有服务 |
| `./manage.sh restart` | 重启所有服务 |
| `./manage.sh status` | 查看服务状态 |
| `./manage.sh backend-only` | 仅启动后端 |
| `./manage.sh frontend-only` | 仅启动前端 |

### 7.4 访问地址

| 服务 | 地址 |
|------|------|
| 前端 | http://127.0.0.1:3000 |
| 后端 | http://127.0.0.1:5000 |
| API 文档 | http://127.0.0.1:5000/api/docs/ |
| 健康检查 | http://127.0.0.1:5000/health |

### 7.5 PostgreSQL 容器管理

```bash
# 查看容器状态
docker ps | grep postgres-calendar

# 启动容器
docker start postgres-calendar

# 停止容器
docker stop postgres-calendar

# 进入容器执行 SQL
docker exec -it postgres-calendar psql -U postgres -d calenderdb
```

### 7.6 数据库备份

```bash
# 备份
docker exec postgres-calendar pg_dump -U postgres calenderdb > backup_$(date +%Y%m%d).sql

# 恢复
cat backup.sql | docker exec -i postgres-calendar psql -U postgres calenderdb
```

---

## 8. 开发规范

### 8.1 后端开发

**Conda 环境激活**:

```bash
conda activate stock
cd backend
python main.py
```

**新增 API 模块**:

1. 在 `app/api/` 创建路由文件
2. 在 `app/services/` 创建服务文件
3. 在 `app/__init__.py` 注册 Namespace

**数据库模型**:

- 所有模型位于 `app/models/`
- 使用 SQLAlchemy 2.0 语法
- 必须包含 `to_dict()` 方法

### 8.2 前端开发

**安装依赖**:

```bash
cd frontend
npm install
npm run dev
```

**新增页面**:

1. 在 `src/views/` 创建 Vue 组件
2. 在 `src/api/` 创建 API 调用文件
3. 在 `src/router/index.js` 注册路由

**样式规范**:

- 使用 `theme.scss` 定义的变量
- 避免内联样式
- 支持亮色/暗色主题

### 8.3 代码验证

```bash
# 运行验证脚本
./verify_local.sh
```

此脚本会：
- 编译检查所有 Python 文件
- 构建前端项目

---

## 9. 未来规划

### 9.1 P0 - 体验打磨

| 任务 | 说明 |
|------|------|
| 涨停页面完善 | 涨停列表、连板榜、资金流向页面 |
| 日历图例 | 显示重要性颜色规则 |
| 事件渲染升级 | 自定义 eventContent，显示更多信息 |
| Loading/Empty/Error | 统一三态展示 |

### 9.2 P1 - 效率增强

| 任务 | 说明 |
|------|------|
| 拖拽改期 | FullCalendar eventDrop |
| 批量操作 | 当日事件多选、批量删除/修改 |
| 缓存策略 | eventSource function + 内存缓存 |
| 涨停强度优化 | 完善评分算法 |

### 9.3 P2 - 增值功能

| 任务 | 说明 |
|------|------|
| CSV/ICS 导出 | 数据导出功能 |
| 批量导入增强 | 去重校验、dry-run |
| 审计日志 | 变更记录与回滚 |
| 数据归档 | 历史分区自动归档到 MinIO |

---

## 附录

### A. 相关文档

| 文档 | 路径 | 说明 |
|------|------|------|
| 分区设计文档 | `docs/partition-design.md` | 涨停股表分区策略 |
| 涨停模块技术报告 | `docs/涨停股票模块技术报告.md` | 涨停模块技术说明 |

### B. 更新日志

| 日期 | 版本 | 更新内容 |
|------|------|----------|
| 2026-04-03 | v4.1.1 | 涨停股分析功能、K线走势图、登录认证、封单比计算修复、行业名称映射 |
| 2026-04-03 | v4.1 | 分区表架构、服务管理脚本、项目重命名 |
| 2026-02-27 | v3.2 | 主题切换、股票管理页、筛选优化 |
| - | v3.1 | Element Plus + FullCalendar 升级 |

---

*文档更新时间: 2026-05-29*
