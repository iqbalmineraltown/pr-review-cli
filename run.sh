#!/bin/bash
# Wrapper script to run PR Review CLI or manage web servers

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_info() {
    echo -e "${BLUE}ℹ ${1}${NC}"
}

print_success() {
    echo -e "${GREEN}✓ ${1}${NC}"
}

print_error() {
    echo -e "${RED}✗ ${1}${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠ ${1}${NC}"
}

# Function to start backend
start_backend() {
    print_info "Starting FastAPI backend..."

    # Check if already running
    if lsof -ti:8000 > /dev/null 2>&1; then
        print_warning "Backend already running on port 8000"
        return 0
    fi

    cd "$(dirname "$0")"
    nohup python3 -m pr_review.web > /tmp/pr-review-be.log 2>&1 &
    local pid=$!

    # Wait for server to start
    sleep 2

    if lsof -ti:8000 > /dev/null 2>&1; then
        print_success "Backend started successfully (PID: ${pid})"
        print_info "   URL: http://127.0.0.1:8000"
        print_info "   Logs: /tmp/pr-review-be.log"
    else
        print_error "Backend failed to start. Check /tmp/pr-review-be.log"
        return 1
    fi
}

# Function to start frontend
start_frontend() {
    print_info "Starting Vite frontend..."

    # Check if already running
    if lsof -ti:5174 > /dev/null 2>&1; then
        print_warning "Frontend already running on port 5174"
        return 0
    fi

    cd "$(dirname "$0")/pr-review-web"

    # Check if node_modules exists
    if [ ! -d "node_modules" ]; then
        print_info "Installing dependencies..."
        npm install
    fi

    nohup npm run dev > /tmp/pr-review-fe.log 2>&1 &
    local pid=$!

    # Wait for server to start
    sleep 3

    if lsof -ti:5174 > /dev/null 2>&1; then
        print_success "Frontend started successfully (PID: ${pid})"
        print_info "   URL: http://localhost:5174"
        print_info "   Logs: /tmp/pr-review-fe.log"
    else
        print_error "Frontend failed to start. Check /tmp/pr-review-fe.log"
        return 1
    fi
}

# Function to stop backend
stop_backend() {
    print_info "Stopping FastAPI backend..."

    local pid=$(lsof -ti:8000 2>/dev/null)
    if [ -n "$pid" ]; then
        kill $pid 2>/dev/null
        sleep 1
        if lsof -ti:8000 > /dev/null 2>&1; then
            print_warning "Force killing backend..."
            kill -9 $pid 2>/dev/null
        fi
        print_success "Backend stopped"
    else
        print_warning "Backend not running"
    fi
}

# Function to stop frontend
stop_frontend() {
    print_info "Stopping Vite frontend..."

    local pid=$(lsof -ti:5174 2>/dev/null)
    if [ -n "$pid" ]; then
        kill $pid 2>/dev/null
        sleep 1
        if lsof -ti:5174 > /dev/null 2>&1; then
            print_warning "Force killing frontend..."
            kill -9 $pid 2>/dev/null
        fi
        print_success "Frontend stopped"
    else
        print_warning "Frontend not running"
    fi
}

# Function to check status
check_status() {
    echo ""
    echo "=== PR Review Web Servers Status ==="
    echo ""

    # Check backend
    if lsof -ti:8000 > /dev/null 2>&1; then
        local pid=$(lsof -ti:8000)
        print_success "Backend running (PID: ${pid})"
        echo "   URL: http://127.0.0.1:8000"
    else
        print_error "Backend not running"
    fi

    echo ""

    # Check frontend
    if lsof -ti:5174 > /dev/null 2>&1; then
        local pid=$(lsof -ti:5174)
        print_success "Frontend running (PID: ${pid})"
        echo "   URL: http://localhost:5174"
    else
        print_error "Frontend not running"
    fi

    echo ""
}

# Main command handling
case "$1" in
    start)
        echo ""
        echo "=== Starting PR Review Web Servers ==="
        echo ""

        start_backend
        echo ""
        start_frontend

        echo ""
        print_success "All servers started!"
        echo ""
        echo "Open http://localhost:5174 in your browser"
        echo ""
        ;;

    stop)
        echo ""
        echo "=== Stopping PR Review Web Servers ==="
        echo ""

        stop_backend
        stop_frontend

        echo ""
        print_success "All servers stopped"
        echo ""
        ;;

    restart)
        echo ""
        echo "=== Restarting PR Review Web Servers ==="
        echo ""

        stop_backend
        stop_frontend
        sleep 1
        start_backend
        echo ""
        start_frontend

        echo ""
        print_success "All servers restarted"
        echo ""
        ;;

    status)
        check_status
        ;;

    web)
        # Start both servers
        echo ""
        echo "=== Starting PR Review Web Servers ==="
        echo ""

        start_backend
        echo ""
        start_frontend

        echo ""
        print_success "All servers started!"
        echo ""
        echo "Open http://localhost:5174 in your browser"
        echo ""
        ;;

    *)
        # Default: Run CLI
        cd "$(dirname "$0")"
        PYTHONPATH="$PWD:$PYTHONPATH" python3 -m pr_review.main "$@"
        ;;
esac
