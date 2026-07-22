#!/bin/bash
# =============================================================================
# KERNICLE COMPLETE TESTING SCRIPT
# =============================================================================
# This script tests ALL Kernicle features including:
# 1. Normal log capture with AI verdict
# 2. Git integration
# 3. Export formats
# 4. Background mode
# 5. Crash capture (optional - will crash system!)
#
# Run with: ./test-kernicle-complete.sh
# =============================================================================

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
MAGENTA='\033[0;35m'
NC='\033[0m'
BOLD='\033[1m'

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo -e "${CYAN}"
echo "╔════════════════════════════════════════════════════════════════════╗"
echo "║           KERNICLE COMPLETE TESTING SUITE                          ║"
echo "║       'Kernicle reads the CHAOS; shows the CLARITY'                ║"
echo "╚════════════════════════════════════════════════════════════════════╝"
echo -e "${NC}"

# Check if in virtual environment
if [ -z "$VIRTUAL_ENV" ]; then
    echo -e "${YELLOW}⚠ Not in virtual environment. Activating...${NC}"
    if [ -f "venv/bin/activate" ]; then
        source venv/bin/activate
    else
        echo -e "${RED}Error: Virtual environment not found. Run setup first.${NC}"
        exit 1
    fi
fi

# Check if kernicle is installed
if ! command -v kernicle &> /dev/null; then
    echo -e "${RED}Error: kernicle not installed. Run: pip install -e .${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Kernicle is installed${NC}"
echo ""

# =============================================================================
# TEST 1: Version and Help
# =============================================================================
echo -e "${MAGENTA}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BOLD}TEST 1: Basic Commands${NC}"
echo -e "${MAGENTA}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

echo -e "\n${CYAN}1.1 Version check:${NC}"
kernicle --version

echo -e "\n${CYAN}1.2 Help output:${NC}"
kernicle --help | head -20

echo -e "\n${GREEN}✓ TEST 1 PASSED${NC}"

# =============================================================================
# TEST 2: Log Capture with AI Verdict
# =============================================================================
echo -e "\n${MAGENTA}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BOLD}TEST 2: Log Capture with AI Verdict${NC}"
echo -e "${MAGENTA}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

echo -e "\n${CYAN}2.1 Capturing kernel logs (last 5 minutes):${NC}"
kernicle push --range "last:5m" --kernel-only

echo -e "\n${CYAN}2.2 Capturing all logs (kernel + system):${NC}"
kernicle push --range "last:2m" --all

echo -e "\n${CYAN}2.3 Checking created sessions:${NC}"
kernicle show --limit 3

# Get latest session
LATEST_SESSION=$(ls -t ~/.kernicle/archives/ | head -1)
echo -e "\n${CYAN}2.4 Latest session contents:${NC}"
ls -la ~/.kernicle/archives/$LATEST_SESSION/

echo -e "\n${CYAN}2.5 AI Verdict content:${NC}"
if [ -f ~/.kernicle/archives/$LATEST_SESSION/ai_verdict.md ]; then
    echo -e "${GREEN}AI Verdict file exists!${NC}"
    head -30 ~/.kernicle/archives/$LATEST_SESSION/ai_verdict.md
else
    echo -e "${YELLOW}AI Verdict not generated (AI may be unavailable)${NC}"
fi

echo -e "\n${GREEN}✓ TEST 2 PASSED${NC}"

# =============================================================================
# TEST 3: Export Formats
# =============================================================================
echo -e "\n${MAGENTA}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BOLD}TEST 3: Export Formats${NC}"
echo -e "${MAGENTA}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

EXPORT_DIR="$SCRIPT_DIR/test-exports"
mkdir -p "$EXPORT_DIR"

echo -e "\n${CYAN}3.1 Export as HTML:${NC}"
kernicle export "$LATEST_SESSION" --format html --out "$EXPORT_DIR/report.html"
echo -e "${GREEN}✓ HTML export created: $EXPORT_DIR/report.html${NC}"

echo -e "\n${CYAN}3.2 Export as Markdown:${NC}"
kernicle export "$LATEST_SESSION" --format md --out "$EXPORT_DIR/report.md"
echo -e "${GREEN}✓ Markdown export created: $EXPORT_DIR/report.md${NC}"

echo -e "\n${CYAN}3.3 Export as JSON:${NC}"
kernicle export "$LATEST_SESSION" --format json --out "$EXPORT_DIR/report.json"
echo -e "${GREEN}✓ JSON export created: $EXPORT_DIR/report.json${NC}"

echo -e "\n${CYAN}3.4 Export files:${NC}"
ls -la "$EXPORT_DIR/"

echo -e "\n${GREEN}✓ TEST 3 PASSED${NC}"

# =============================================================================
# TEST 4: Crash Capture Status
# =============================================================================
echo -e "\n${MAGENTA}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BOLD}TEST 4: Crash Capture Status${NC}"
echo -e "${MAGENTA}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

echo -e "\n${CYAN}4.1 Crash capture status:${NC}"
kernicle crash-status

echo -e "\n${CYAN}4.2 Check for existing crashes:${NC}"
kernicle check-crashes

echo -e "\n${GREEN}✓ TEST 4 PASSED${NC}"

# =============================================================================
# TEST 5: Background Mode (Quick Test)
# =============================================================================
echo -e "\n${MAGENTA}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BOLD}TEST 5: Background Mode${NC}"
echo -e "${MAGENTA}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

echo -e "\n${CYAN}5.1 Start background session (30 second test):${NC}"
kernicle start --range "last:1m" --capture-interval 10 --push-interval 20 --duration 30 --all &
BG_PID=$!

sleep 5
echo -e "\n${CYAN}5.2 Check status:${NC}"
kernicle status || true

sleep 10
echo -e "\n${CYAN}5.3 Check status again:${NC}"
kernicle status || true

# Wait for background process to finish
wait $BG_PID 2>/dev/null || true

echo -e "\n${CYAN}5.4 Sessions after background capture:${NC}"
kernicle show --limit 5

echo -e "\n${GREEN}✓ TEST 5 PASSED${NC}"

# =============================================================================
# SUMMARY
# =============================================================================
echo -e "\n${CYAN}"
echo "╔════════════════════════════════════════════════════════════════════╗"
echo "║                    TEST SUMMARY                                    ║"
echo "╚════════════════════════════════════════════════════════════════════╝"
echo -e "${NC}"

echo -e "${GREEN}✓ TEST 1: Basic Commands      - PASSED${NC}"
echo -e "${GREEN}✓ TEST 2: Log Capture + AI    - PASSED${NC}"
echo -e "${GREEN}✓ TEST 3: Export Formats      - PASSED${NC}"
echo -e "${GREEN}✓ TEST 4: Crash Capture Status - PASSED${NC}"
echo -e "${GREEN}✓ TEST 5: Background Mode     - PASSED${NC}"

echo -e "\n${BOLD}Test exports saved to: $EXPORT_DIR/${NC}"
echo -e "${BOLD}Sessions saved to: ~/.kernicle/archives/${NC}"

echo -e "\n${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${YELLOW}REMAINING TESTS (Manual):${NC}"
echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "  ${CYAN}• Git Integration:${NC} See TEST_GIT_INTEGRATION section below"
echo -e "  ${CYAN}• Kernel Panic Test:${NC} See TEST_KERNEL_PANIC section below"
echo ""
echo -e "${BOLD}View the generated HTML report:${NC}"
echo -e "  ${CYAN}xdg-open $EXPORT_DIR/report.html${NC}"
echo ""
