#!/bin/bash
# =============================================================================
# Kernicle Crash Capture Verification Script
# =============================================================================
# Quick script to verify crash capture is working
# Run with: ./verify-crash-capture.sh
# =============================================================================

set -e

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'
BOLD='\033[1m'

echo -e "${CYAN}"
echo "╔════════════════════════════════════════════════════════════════════╗"
echo "║         KERNICLE CRASH CAPTURE VERIFICATION                        ║"
echo "╚════════════════════════════════════════════════════════════════════╝"
echo -e "${NC}"

echo -e "${BOLD}Checking crash capture components...${NC}\n"

# 1. Check packages
echo -e "${CYAN}1. Packages:${NC}"
PACKAGES_OK=true
for pkg in kdump-tools kexec-tools crash makedumpfile; do
    if dpkg -s "$pkg" &>/dev/null; then
        echo -e "   ${GREEN}✓${NC} $pkg installed"
    else
        echo -e "   ${RED}✗${NC} $pkg NOT installed"
        PACKAGES_OK=false
    fi
done

# 2. Check crashkernel parameter
echo -e "\n${CYAN}2. Crashkernel Parameter:${NC}"
CRASHKERNEL=$(cat /proc/cmdline | grep -o 'crashkernel=[^ ]*' || echo "")
if [ -n "$CRASHKERNEL" ]; then
    echo -e "   ${GREEN}✓${NC} Crashkernel configured: $CRASHKERNEL"
else
    echo -e "   ${RED}✗${NC} Crashkernel NOT configured in boot parameters"
fi

# 3. Check crash kernel loaded
echo -e "\n${CYAN}3. Crash Kernel Loaded:${NC}"
KEXEC_LOADED=$(cat /sys/kernel/kexec_crash_loaded 2>/dev/null || echo "0")
if [ "$KEXEC_LOADED" = "1" ]; then
    echo -e "   ${GREEN}✓${NC} Crash kernel is LOADED and ready"
else
    echo -e "   ${RED}✗${NC} Crash kernel NOT loaded"
fi

# 4. Check kdump service
echo -e "\n${CYAN}4. kdump Service:${NC}"
if systemctl is-enabled kdump-tools &>/dev/null; then
    echo -e "   ${GREEN}✓${NC} kdump service enabled"
else
    echo -e "   ${YELLOW}⚠${NC} kdump service not enabled"
fi

if systemctl is-active kdump-tools &>/dev/null; then
    echo -e "   ${GREEN}✓${NC} kdump service running"
else
    echo -e "   ${YELLOW}⚠${NC} kdump service not running"
fi

# 5. Check crash directory
echo -e "\n${CYAN}5. Crash Directory:${NC}"
if [ -d "/var/crash" ]; then
    echo -e "   ${GREEN}✓${NC} /var/crash exists"
    CRASH_COUNT=$(find /var/crash -name "vmcore" 2>/dev/null | wc -l)
    echo -e "   ${CYAN}ℹ${NC} Found $CRASH_COUNT crash dump(s)"
else
    echo -e "   ${YELLOW}⚠${NC} /var/crash does not exist (will be created on first crash)"
fi

# Summary
echo -e "\n${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
if [ "$KEXEC_LOADED" = "1" ]; then
    echo -e "${BOLD}${GREEN}✅ CRASH CAPTURE IS FULLY OPERATIONAL!${NC}"
    echo -e ""
    echo -e "Your system will capture kernel panics and save them to /var/crash/"
    echo -e ""
    echo -e "To test (${RED}WILL CRASH YOUR SYSTEM${NC}):"
    echo -e "   ${CYAN}echo c | sudo tee /proc/sysrq-trigger${NC}"
    echo -e ""
    echo -e "After reboot, analyze with:"
    echo -e "   ${CYAN}kernicle check-crashes${NC}"
    echo -e "   ${CYAN}kernicle analyze-crash${NC}"
else
    echo -e "${BOLD}${RED}❌ CRASH CAPTURE NOT READY${NC}"
    echo -e ""
    echo -e "Missing components. Try:"
    echo -e "   ${CYAN}sudo ./setup-crash-capture.sh${NC}"
    echo -e "   Then reboot and run this script again."
fi
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
