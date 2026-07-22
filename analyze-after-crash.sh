#!/bin/bash
# =============================================================================
# KERNICLE POST-CRASH ANALYSIS
# =============================================================================
# Run this script AFTER your system reboots from a kernel panic
# It will automatically find, analyze, and report on the crash
#
# Run with: ./analyze-after-crash.sh
# =============================================================================

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
MAGENTA='\033[0;35m'
NC='\033[0m'
BOLD='\033[1m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo -e "${CYAN}"
echo "╔════════════════════════════════════════════════════════════════════╗"
echo "║           KERNICLE POST-CRASH ANALYSIS                             ║"
echo "║       'Kernicle reads the CHAOS; shows the CLARITY'                ║"
echo "╚════════════════════════════════════════════════════════════════════╝"
echo -e "${NC}"

# Activate virtual environment
if [ -z "$VIRTUAL_ENV" ]; then
    if [ -f "venv/bin/activate" ]; then
        echo -e "${CYAN}Activating virtual environment...${NC}"
        source venv/bin/activate
    else
        echo -e "${RED}Error: Virtual environment not found!${NC}"
        echo -e "Run: python3 -m venv venv && source venv/bin/activate && pip install -e ."
        exit 1
    fi
fi

# =============================================================================
# Step 1: Check for crash dumps
# =============================================================================
echo -e "\n${BOLD}Step 1: Checking for crash dumps...${NC}"
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

kernicle check-crashes

# Check if /var/crash has anything
if [ -d "/var/crash" ]; then
    CRASH_COUNT=$(find /var/crash -name "vmcore*" -o -name "*.crash" 2>/dev/null | wc -l)
    
    if [ "$CRASH_COUNT" -gt 0 ]; then
        echo -e "\n${GREEN}Found $CRASH_COUNT crash dump(s)!${NC}"
        echo -e "${CYAN}Contents of /var/crash:${NC}"
        ls -la /var/crash/
    else
        echo -e "\n${YELLOW}No crash dumps found in /var/crash/${NC}"
        echo -e "${YELLOW}The crash may not have been captured, or crash capture wasn't set up.${NC}"
    fi
else
    echo -e "\n${YELLOW}/var/crash directory does not exist${NC}"
fi

# =============================================================================
# Step 2: Analyze crash
# =============================================================================
echo -e "\n${BOLD}Step 2: Analyzing crash dump...${NC}"
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

# Create output directory for this analysis
ANALYSIS_DIR="$SCRIPT_DIR/crash-analysis-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$ANALYSIS_DIR"

echo -e "${CYAN}Analysis output directory: $ANALYSIS_DIR${NC}"

# Run kernicle analyze-crash
kernicle analyze-crash --output "$ANALYSIS_DIR" 2>&1 || {
    echo -e "${YELLOW}⚠ kernicle analyze-crash had issues. Trying alternative analysis...${NC}"
    
    # Alternative: Check dmesg for crash info
    echo -e "\n${CYAN}Checking dmesg for crash information:${NC}"
    dmesg | grep -i -E "panic|oops|bug|crash|error" | tail -50 > "$ANALYSIS_DIR/dmesg-errors.txt"
    
    # Check systemd journal for boot messages
    echo -e "\n${CYAN}Checking journal for previous boot:${NC}"
    journalctl -b -1 2>/dev/null | grep -i -E "panic|oops|bug|crash" > "$ANALYSIS_DIR/journal-previous-boot.txt" || true
}

# =============================================================================
# Step 3: Generate reports
# =============================================================================
echo -e "\n${BOLD}Step 3: Generating reports...${NC}"
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

# Get latest session
LATEST_SESSION=$(ls -t ~/.kernicle/archives/ 2>/dev/null | head -1)

if [ -n "$LATEST_SESSION" ]; then
    echo -e "${GREEN}Latest session: $LATEST_SESSION${NC}"
    
    # Export HTML report
    echo -e "\n${CYAN}Exporting HTML report...${NC}"
    kernicle export "$LATEST_SESSION" --format html --out "$ANALYSIS_DIR/crash-report.html" 2>/dev/null || true
    
    # Export Markdown report
    echo -e "${CYAN}Exporting Markdown report...${NC}"
    kernicle export "$LATEST_SESSION" --format md --out "$ANALYSIS_DIR/crash-report.md" 2>/dev/null || true
    
    # Copy AI verdict
    if [ -f ~/.kernicle/archives/$LATEST_SESSION/ai_verdict.md ]; then
        cp ~/.kernicle/archives/$LATEST_SESSION/ai_verdict.md "$ANALYSIS_DIR/"
        echo -e "${GREEN}✓ AI verdict copied${NC}"
    fi
    
    # Copy crash report if exists
    if [ -f ~/.kernicle/archives/$LATEST_SESSION/crash_report.txt ]; then
        cp ~/.kernicle/archives/$LATEST_SESSION/crash_report.txt "$ANALYSIS_DIR/"
        echo -e "${GREEN}✓ Crash report copied${NC}"
    fi
fi

# =============================================================================
# Step 4: Show results
# =============================================================================
echo -e "\n${BOLD}Step 4: Analysis Results${NC}"
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

echo -e "\n${CYAN}Files generated:${NC}"
ls -la "$ANALYSIS_DIR/"

# Show AI verdict if exists
if [ -f "$ANALYSIS_DIR/ai_verdict.md" ]; then
    echo -e "\n${MAGENTA}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BOLD}🤖 AI VERDICT:${NC}"
    echo -e "${MAGENTA}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    cat "$ANALYSIS_DIR/ai_verdict.md"
fi

# =============================================================================
# Summary
# =============================================================================
echo -e "\n${CYAN}"
echo "╔════════════════════════════════════════════════════════════════════╗"
echo "║                    ANALYSIS COMPLETE                               ║"
echo "╚════════════════════════════════════════════════════════════════════╝"
echo -e "${NC}"

echo -e "${GREEN}✓ Crash analysis complete!${NC}"
echo -e ""
echo -e "${BOLD}Analysis saved to:${NC}"
echo -e "  ${CYAN}$ANALYSIS_DIR/${NC}"
echo -e ""
echo -e "${BOLD}To view the HTML report:${NC}"
echo -e "  ${CYAN}xdg-open $ANALYSIS_DIR/crash-report.html${NC}"
echo -e ""
echo -e "${BOLD}To view the AI verdict:${NC}"
echo -e "  ${CYAN}cat $ANALYSIS_DIR/ai_verdict.md${NC}"
echo -e ""

# Ask to open HTML report
read -p "Open HTML report in browser? (y/N): " OPEN_REPORT
if [[ $OPEN_REPORT =~ ^[Yy]$ ]]; then
    xdg-open "$ANALYSIS_DIR/crash-report.html" 2>/dev/null || \
    firefox "$ANALYSIS_DIR/crash-report.html" 2>/dev/null || \
    google-chrome "$ANALYSIS_DIR/crash-report.html" 2>/dev/null || \
    echo "Please open $ANALYSIS_DIR/crash-report.html manually"
fi
