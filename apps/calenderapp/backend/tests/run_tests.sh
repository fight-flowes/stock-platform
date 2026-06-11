#!/bin/bash
# A股投研数据平台测试运行脚本

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TEST_DIR="$SCRIPT_DIR"
BACKEND_DIR="$(cd "${TEST_DIR}/.." && pwd)"
PROJECT_ROOT="$(cd "${BACKEND_DIR}/.." && pwd)"
CONDA_ENV="${CONDA_ENV:-stock}"

echo "=============================================="
echo "A股投研数据平台 v5.1 测试运行脚本"
echo "=============================================="
echo ""

# 检查 Conda 环境
echo ">>> 检查 Conda 环境..."
if ! command -v conda >/dev/null 2>&1; then
    echo "错误: 未找到 conda 命令"
    exit 1
fi

if ! conda info --envs | grep -q "$CONDA_ENV"; then
    echo "错误: Conda 环境 '$CONDA_ENV' 不存在"
    exit 1
fi

# 激活环境
echo ">>> 激活 Conda $CONDA_ENV 环境..."
source "$(conda info --base)/etc/profile.d/conda.sh"
conda activate "$CONDA_ENV"

# 检查服务状态
echo ">>> 检查服务状态..."
cd "$PROJECT_ROOT"
if [ -f backend/backend.pid ] && [ -f frontend/frontend.pid ]; then
    echo "服务已运行"
else
    echo ">>> 启动服务..."
    ./manage.sh start
    sleep 5
fi

# 运行 API 测试
echo ""
echo "=============================================="
echo ">>> 运行 API 接口测试..."
echo "=============================================="

cd "$BACKEND_DIR"

# 检查 pytest 是否安装
if ! pip show pytest > /dev/null 2>&1; then
    echo ">>> 安装 pytest..."
    pip install pytest pytest-cov requests
fi

# 运行测试
pytest tests/test_api.py -v --tb=short 2>&1 | tee test_api_results.txt

# 提取结果
PASS_COUNT=$(grep -c "PASSED" test_api_results.txt || echo 0)
FAIL_COUNT=$(grep -c "FAILED" test_api_results.txt || echo 0)
SKIP_COUNT=$(grep -c "SKIPPED" test_api_results.txt || echo 0)
TOTAL=$((PASS_COUNT + FAIL_COUNT + SKIP_COUNT))

echo ""
echo "API 测试结果:"
echo "  - 总用例: $TOTAL"
echo "  - 通过: $PASS_COUNT"
echo "  - 失败: $FAIL_COUNT"
echo "  - 跳过: $SKIP_COUNT"

# 运行数据验证测试
echo ""
echo "=============================================="
echo ">>> 运行数据验证测试..."
echo "=============================================="

pytest tests/test_data_validation.py -v --tb=short 2>&1 | tee test_validation_results.txt

VAL_PASS=$(grep -c "PASSED" test_validation_results.txt || echo 0)
VAL_FAIL=$(grep -c "FAILED" test_validation_results.txt || echo 0)
VAL_SKIP=$(grep -c "SKIPPED" test_validation_results.txt || echo 0)
VAL_TOTAL=$((VAL_PASS + VAL_FAIL + VAL_SKIP))

echo ""
echo "数据验证测试结果:"
echo "  - 总用例: $VAL_TOTAL"
echo "  - 通过: $VAL_PASS"
echo "  - 失败: $VAL_FAIL"
echo "  - 跳过: $VAL_SKIP"

# 生成测试报告
echo ""
echo "=============================================="
echo ">>> 生成测试报告..."
echo "=============================================="

REPORT_FILE="$PROJECT_ROOT/docs/test_report_$(date +%Y%m%d).md"

# 总计
TOTAL_PASS=$((PASS_COUNT + VAL_PASS))
TOTAL_FAIL=$((FAIL_COUNT + VAL_FAIL))
TOTAL_SKIP=$((SKIP_COUNT + VAL_SKIP))
TOTAL_ALL=$((TOTAL + VAL_TOTAL))
PASS_RATE=$(echo "scale=2; $TOTAL_PASS * 100 / $TOTAL_ALL" | bc)

cat > "$REPORT_FILE" << EOF
# A股投研数据平台 v5.1 测试报告

> **测试版本**: v5.1  
> **测试日期**: $(date +%Y-%m-%d)  
> **测试人员**: OpenClaw (投研助手)

---

## 1. 测试概述

### 1.1 测试范围

| 测试类型 | 覆盖模块 | 说明 |
|----------|----------|------|
| API 接口测试 | 系统/日历/事件/股票/涨停/分区 | 后端 REST API 功能验证 |
| 数据验证测试 | 参数解析/强度评分/数据结构 | 数据格式和业务逻辑验证 |

---

## 2. 测试结果汇总

### 2.1 总体统计

| 指标 | 数值 | 说明 |
|------|------|------|
| 测试用例总数 | $TOTAL_ALL | API + 数据验证 |
| 通过用例数 | $TOTAL_PASS | ✅ |
| 失败用例数 | $TOTAL_FAIL | ❌ |
| 跳过用例数 | $TOTAL_SKIP | ⏭️ |
| 通过率 | ${PASS_RATE}% | |

### 2.2 模块分布

| 模块 | 用例数 | 通过 | 失败 | 跳过 |
|------|--------|------|------|------|
| API 接口测试 | $TOTAL | $PASS_COUNT | $FAIL_COUNT | $SKIP_COUNT |
| 数据验证测试 | $VAL_TOTAL | $VAL_PASS | $VAL_FAIL | $VAL_SKIP |

---

## 3. 测试结论

### 3.1 总体评价

通过率: **${PASS_RATE}%**

$(if [ "$PASS_RATE" -ge 90 ]; then echo "✅ **建议通过测试验收**"; else echo "⚠️ **建议修复失败用例后重新测试**"; fi)

---

*报告生成时间: $(date '+%Y-%m-%d %H:%M:%S')*  
EOF

echo "测试报告已生成: $REPORT_FILE"

# 清理临时文件
rm -f test_api_results.txt test_validation_results.txt

echo ""
echo "=============================================="
echo "测试完成！"
echo "=============================================="
echo ""
echo "查看测试报告: $REPORT_FILE"
echo ""
