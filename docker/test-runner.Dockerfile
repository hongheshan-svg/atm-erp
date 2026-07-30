# 本地测试预检专用镜像(scripts/precheck-tests.sh 自动构建,不参与部署)。
#
# 生产镜像只装 requirements.txt,不含 dev 依赖,因此没有 pytest,跑不了
# CI 的 "Backend / integration" 那个 job。这里在其之上补最小依赖。
#
# 版本由脚本从 backend/requirements-dev.txt 解析后经 build-arg 传入,
# 不在此写死 —— 依赖一变,镜像 tag 随之变化并自动重建。
ARG BASE_IMAGE
FROM ${BASE_IMAGE}

ARG PYTEST_SPEC
RUN pip install --no-cache-dir ${PYTEST_SPEC}
