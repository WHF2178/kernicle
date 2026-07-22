#!/bin/bash
# =============================================================================
# KERNICLE KERNEL PANIC TESTING GUIDE
# =============================================================================
# ⚠️  WARNING: This will CRASH your system!
# Only run this in a VM or if you understand the consequences.
#
# Run with: ./test-kernel-panic.sh
# =============================================================================

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
MAGENTA='\033[0;35m'
NC='\033[0m'
BOLD='\033[1m'

echo -e "${RED}"
echo "╔════════════════════════════════════════════════════════════════════╗"
echo "║  ⚠️  KERNEL PANIC TEST - THIS WILL CRASH YOUR SYSTEM! ⚠️            ║"
echo "╚════════════════════════════════════════════════════════════════════╝"
echo -e "${NC}"

echo -e "${YELLOW}
This script will guide you through testing kernel panic capture.

WHAT WILL HAPPEN:
1. You trigger a kernel panic
2. Your system will CRASH immediately
3. kdump captures the crash to /var/crash/
4. System reboots automatically
5. You run kernicle to analyze the crash

PREREQUISITES:
- You're running in a VM (VirtualBox/VMware) - RECOMMENDED
- OR you've saved all your work and understand this will force reboot
- Crash capture is set up (check with: kernicle crash-status)
${NC}"

# Check if crash capture is ready
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BOLD}Pre-flight Check:${NC}"
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

# Check crash kernel loaded
KEXEC_LOADED=$(cat /sys/kernel/kexec_crash_loaded 2>/dev/null || echo "0")
if [ "$KEXEC_LOADED" = "1" ]; then
    echo -e "${GREEN}✓ Crash kernel is loaded - Ready to capture panics${NC}"
else
    echo -e "${RED}✗ Crash kernel NOT loaded!${NC}"
    echo -e "${YELLOW}  Run: sudo ./setup-crash-capture.sh${NC}"
    echo -e "${YELLOW}  Then REBOOT and try again${NC}"
    exit 1
fi

# Check kdump service
if systemctl is-active kdump-tools &>/dev/null; then
    echo -e "${GREEN}✓ kdump service is running${NC}"
else
    echo -e "${YELLOW}⚠ kdump service not running${NC}"
fi

# Show crashkernel param
CRASHKERNEL=$(cat /proc/cmdline | grep -o 'crashkernel=[^ ]*' || echo "Not set")
echo -e "${GREEN}✓ Crashkernel: $CRASHKERNEL${NC}"

echo -e ""
echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BOLD}IMPORTANT: Save all work before continuing!${NC}"
echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

echo -e "
${BOLD}Step-by-Step Instructions:${NC}

${CYAN}STEP 1: Before the crash${NC}
  Save this command somewhere you can access after reboot:
  ${GREEN}kernicle check-crashes && kernicle analyze-crash${NC}

${CYAN}STEP 2: Trigger the panic${NC}
  Run this command (requires sudo):
  ${RED}echo c | sudo tee /proc/sysrq-trigger${NC}

${CYAN}STEP 3: After reboot${NC}
  1. Open terminal
  2. Navigate to Kernicle directory
  3. Activate virtual environment:
     ${GREEN}source venv/bin/activate${NC}
  4. Check for crashes:
     ${GREEN}kernicle check-crashes${NC}
  5. Analyze the crash:
     ${GREEN}kernicle analyze-crash${NC}
  6. View the AI verdict:
     ${GREEN}cat ~/.kernicle/archives/session-*/ai_verdict.md${NC}

${CYAN}STEP 4: Export report for FYP${NC}
  ${GREEN}kernicle export <session-id> --format html --out crash-report.html${NC}
  ${GREEN}xdg-open crash-report.html${NC}
"

echo -e "${RED}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
read -p "Are you SURE you want to trigger a kernel panic? (type 'YES' to confirm): " CONFIRM

if [ "$CONFIRM" = "YES" ]; then
    echo -e ""
    echo -e "${RED}${BOLD}TRIGGERING KERNEL PANIC IN 5 SECONDS...${NC}"
    echo -e "${YELLOW}Press Ctrl+C to cancel!${NC}"
    sleep 1
    echo -e "${RED}5...${NC}"
    sleep 1
    echo -e "${RED}4...${NC}"
    sleep 1
    echo -e "${RED}3...${NC}"
    sleep 1
    echo -e "${RED}2...${NC}"
    sleep 1
    echo -e "${RED}1...${NC}"
    sleep 1
    echo -e "${RED}PANIC!${NC}"
    
    # Trigger the panic
    echo c | sudo tee /proc/sysrq-trigger
else
    echo -e "${GREEN}Cancelled. No panic triggered.${NC}"
    echo -e ""
    echo -e "${CYAN}To trigger manually later, run:${NC}"
    echo -e "  ${RED}echo c | sudo tee /proc/sysrq-trigger${NC}"
fi
