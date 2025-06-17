#!/bin/bash

# Pulse Guard 一键部署脚本

set -e

# 颜色输出
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 显示帮助
show_help() {
    cat << EOF
Pulse Guard 一键部署

用法: $0 [命令]

命令:
  start       启动服务 (默认)
  stop        停止服务
  restart     重启服务
  logs        查看日志
  status      查看状态

示例:
  $0          # 启动服务
  $0 start    # 启动服务
  $0 stop     # 停止服务
  $0 logs     # 查看日志

EOF
}

# 检查依赖
check_dependencies() {
    if ! command -v docker &> /dev/null; then
        log_error "请先安装 Docker"
        exit 1
    fi

    if ! command -v docker-compose &> /dev/null; then
        log_error "请先安装 Docker Compose"
        exit 1
    fi
}

# 检查环境文件
check_env_file() {
    if [[ ! -f .env ]]; then
        if [[ -f .env.example ]]; then
            log_info "复制 .env.example 到 .env"
            cp .env.example .env
            log_info "请编辑 .env 文件并填入必要的配置"
        else
            log_error ".env 文件不存在"
            exit 1
        fi
    fi
}

# 启动服务
start_services() {
    log_info "启动 Pulse Guard 服务..."
    docker-compose up -d
    log_info "服务启动完成!"
    log_info "Web 服务: http://localhost:8000"
    log_info "查看日志: ./deploy.sh logs"
}

# 停止服务
stop_services() {
    log_info "停止服务..."
    docker-compose down
    log_info "服务已停止"
}

# 重启服务
restart_services() {
    log_info "重启服务..."
    docker-compose restart
    log_info "服务已重启"
}

# 查看日志
show_logs() {
    docker-compose logs -f
}

# 查看状态
show_status() {
    docker-compose ps
}

# 主函数
main() {
    local command="${1:-start}"

    case "$command" in
        -h|--help)
            show_help
            exit 0
            ;;
        start|"")
            check_dependencies
            check_env_file
            start_services
            ;;
        stop)
            stop_services
            ;;
        restart)
            restart_services
            ;;
        logs)
            show_logs
            ;;
        status)
            show_status
            ;;
        *)
            log_error "未知命令: $command"
            show_help
            exit 1
            ;;
    esac
}

# 执行主函数
main "$@"
