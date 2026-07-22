#!/bin/bash
# =============================================================================
# KERNICLE CRASH SIMULATION DEMO
# =============================================================================
# This script simulates a realistic crash scenario WITHOUT actually crashing
# your system. It demonstrates the complete Kernicle workflow.
#
# Run with: ./simulate-crash-scenario.sh
# =============================================================================

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
MAGENTA='\033[0;35m'
WHITE='\033[1;37m'
NC='\033[0m'
BOLD='\033[1m'
DIM='\033[2m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Activate virtual environment
if [ -f ".venv/bin/activate" ]; then
    source .venv/bin/activate
elif [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
fi

clear
echo -e "${RED}"
echo "╔════════════════════════════════════════════════════════════════════════╗"
echo "║  🔥 KERNICLE CRASH SCENARIO SIMULATION 🔥                              ║"
echo "║                                                                        ║"
echo "║  This simulates a REAL crash scenario to demonstrate Kernicle          ║"
echo "║  WITHOUT actually crashing your system.                                ║"
echo "╚════════════════════════════════════════════════════════════════════════╝"
echo -e "${NC}"

sleep 2

# =============================================================================
# PHASE 1: SYSTEM RUNNING NORMALLY - KERNICLE MONITORING
# =============================================================================
echo -e "\n${CYAN}═══════════════════════════════════════════════════════════════════════${NC}"
echo -e "${WHITE}${BOLD}PHASE 1: SYSTEM RUNNING NORMALLY${NC}"
echo -e "${CYAN}═══════════════════════════════════════════════════════════════════════${NC}"
echo -e "${DIM}Imagine your server is running production workloads...${NC}\n"

sleep 1

echo -e "${GREEN}▶ Starting Kernicle background monitoring...${NC}"
echo -e "${DIM}  Command: kernicle start -a --git${NC}\n"

# Start background session
kernicle start -a --git 2>/dev/null || true

sleep 2

echo -e "\n${GREEN}▶ Kernicle is now monitoring your system in the background${NC}"
echo -e "${DIM}  - Collecting logs every 10 seconds${NC}"
echo -e "${DIM}  - Creating archives every 2 minutes${NC}"
echo -e "${DIM}  - Pushing to GitHub automatically${NC}\n"

sleep 2

# =============================================================================
# PHASE 2: SIMULATING PROBLEMATIC ACTIVITY
# =============================================================================
echo -e "\n${CYAN}═══════════════════════════════════════════════════════════════════════${NC}"
echo -e "${WHITE}${BOLD}PHASE 2: SIMULATING SYSTEM STRESS${NC}"
echo -e "${CYAN}═══════════════════════════════════════════════════════════════════════${NC}"
echo -e "${DIM}Now let's generate some kernel-level events that Kernicle will capture...${NC}\n"

sleep 1

echo -e "${YELLOW}⚡ Generating kernel events (safe simulation)...${NC}\n"

# Generate some safe kernel messages using logger
echo -e "${DIM}  Simulating memory pressure warning...${NC}"
sudo logger -p kern.warning "kswapd0: page allocation failure: order:3, mode:0x26000c0(GFP_KERNEL)"
sleep 0.5

echo -e "${DIM}  Simulating CPU soft lockup warning...${NC}"
sudo logger -p kern.warning "watchdog: BUG: soft lockup - CPU#0 stuck for 22s! [stress:12345]"
sleep 0.5

echo -e "${DIM}  Simulating I/O error...${NC}"
sudo logger -p kern.err "Buffer I/O error on dev sda, logical block 12345678, async page read"
sleep 0.5

echo -e "${DIM}  Simulating memory error (ECC)...${NC}"
sudo logger -p kern.crit "EDAC MC0: 1 CE memory read error on CPU#0Channel#0_DIMM#0"
sleep 0.5

echo -e "${DIM}  Simulating thermal throttling...${NC}"
sudo logger -p kern.warning "CPU0: Package temperature above threshold, cpu clock throttled"
sleep 0.5

echo -e "${DIM}  Simulating USB disconnect...${NC}"
sudo logger -p kern.notice "usb 2-1: USB disconnect, device number 3"
sleep 0.5

echo -e "${DIM}  Simulating filesystem remount read-only...${NC}"
sudo logger -p kern.alert "EXT4-fs error (device sda1): ext4_journal_check_start:61: Detected aborted journal"
sudo logger -p kern.alert "EXT4-fs (sda1): Remounting filesystem read-only"
sleep 0.5

echo -e "\n${GREEN}✓ Kernel events generated${NC}\n"

sleep 2

# =============================================================================
# PHASE 3: CHECK KERNICLE STATUS
# =============================================================================
echo -e "\n${CYAN}═══════════════════════════════════════════════════════════════════════${NC}"
echo -e "${WHITE}${BOLD}PHASE 3: CHECKING KERNICLE CAPTURE${NC}"
echo -e "${CYAN}═══════════════════════════════════════════════════════════════════════${NC}\n"

echo -e "${GREEN}▶ Checking background session status...${NC}\n"
kernicle status

sleep 2

# =============================================================================
# PHASE 4: MANUAL CAPTURE WITH AI ANALYSIS
# =============================================================================
echo -e "\n${CYAN}═══════════════════════════════════════════════════════════════════════${NC}"
echo -e "${WHITE}${BOLD}PHASE 4: CAPTURING AND ANALYZING LOGS${NC}"
echo -e "${CYAN}═══════════════════════════════════════════════════════════════════════${NC}"
echo -e "${DIM}Now let's capture the last 5 minutes and see what Kernicle found...${NC}\n"

sleep 1

echo -e "${GREEN}▶ Running: kernicle push -r \"last:5m\" -a --git${NC}\n"

kernicle push -r "last:5m" -a --git

sleep 2

# =============================================================================
# PHASE 5: VIEW THE ANALYSIS
# =============================================================================
echo -e "\n${CYAN}═══════════════════════════════════════════════════════════════════════${NC}"
echo -e "${WHITE}${BOLD}PHASE 5: VIEWING KERNICLE ANALYSIS${NC}"
echo -e "${CYAN}═══════════════════════════════════════════════════════════════════════${NC}\n"

# Get latest session
LATEST_SESSION=$(ls -td ~/.kernicle/archives/session-* 2>/dev/null | head -1)

if [ -n "$LATEST_SESSION" ]; then
    SESSION_NAME=$(basename "$LATEST_SESSION")
    
    echo -e "${GREEN}▶ Latest session: ${CYAN}$SESSION_NAME${NC}\n"
    
    # Show findings
    if [ -f "$LATEST_SESSION/findings.json" ]; then
        FINDINGS_COUNT=$(cat "$LATEST_SESSION/findings.json" | python3 -c "import sys,json; print(len(json.load(sys.stdin)))" 2>/dev/null || echo "0")
        echo -e "${YELLOW}⚠ Findings detected: $FINDINGS_COUNT${NC}\n"
    fi
    
    # Show AI verdict if available
    if [ -f "$LATEST_SESSION/ai_verdict.md" ]; then
        echo -e "${MAGENTA}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
        echo -e "${WHITE}${BOLD}🤖 AI VERDICT:${NC}"
        echo -e "${MAGENTA}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
        head -80 "$LATEST_SESSION/ai_verdict.md"
        echo -e "\n${DIM}[... see full verdict in $LATEST_SESSION/ai_verdict.md]${NC}"
    fi
fi

sleep 2

# =============================================================================
# PHASE 6: EXPORT REPORT
# =============================================================================
echo -e "\n${CYAN}═══════════════════════════════════════════════════════════════════════${NC}"
echo -e "${WHITE}${BOLD}PHASE 6: EXPORTING HTML REPORT${NC}"
echo -e "${CYAN}═══════════════════════════════════════════════════════════════════════${NC}\n"

if [ -n "$SESSION_NAME" ]; then
    echo -e "${GREEN}▶ Exporting to HTML...${NC}\n"
    kernicle export "$SESSION_NAME" --format html --out ~/Desktop/crash-simulation-report.html
    
    echo -e "\n${GREEN}✓ Report saved to: ~/Desktop/crash-simulation-report.html${NC}"
    echo -e "${DIM}  Open with: xdg-open ~/Desktop/crash-simulation-report.html${NC}"
fi

# =============================================================================
# PHASE 7: STOP BACKGROUND SESSION
# =============================================================================
echo -e "\n${CYAN}═══════════════════════════════════════════════════════════════════════${NC}"
echo -e "${WHITE}${BOLD}PHASE 7: CLEANUP${NC}"
echo -e "${CYAN}═══════════════════════════════════════════════════════════════════════${NC}\n"

echo -e "${GREEN}▶ Stopping background session...${NC}\n"
kernicle stop 2>/dev/null || echo -e "${YELLOW}Session already stopped${NC}"

# =============================================================================
# PHASE 8: SIMULATING CRASH DUMP ANALYSIS (if we had a real crash)
# =============================================================================
echo -e "\n${CYAN}═══════════════════════════════════════════════════════════════════════${NC}"
echo -e "${WHITE}${BOLD}PHASE 8: CRASH DUMP ANALYSIS (DEMO)${NC}"
echo -e "${CYAN}═══════════════════════════════════════════════════════════════════════${NC}"
echo -e "${DIM}If your system had ACTUALLY crashed, here's what would happen...${NC}\n"

echo -e "${RED}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${WHITE}${BOLD}SIMULATED CRASH SCENARIO:${NC}"
echo -e "${RED}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "
${YELLOW}1. System crashes at 14:35:22 due to kernel panic${NC}
   ${DIM}Panic: BUG: unable to handle kernel NULL pointer dereference at 0000000000000008${NC}

${YELLOW}2. kdump captures the crash to /var/crash/202601041435/${NC}
   ${DIM}vmcore: 156 MB crash dump saved${NC}

${YELLOW}3. System reboots automatically${NC}

${YELLOW}4. After reboot, you run:${NC}
   ${CYAN}kernicle crash-check${NC}
   
   ${RED}╭──────────────────────── 🚨 Crashes Detected ────────────────────────╮${NC}
   ${RED}│ ⚠️ 1 UNANALYZED CRASH(ES) FOUND!                                   │${NC}
   ${RED}│                                                                    │${NC}
   ${RED}│ Your system experienced kernel panic(s).                           │${NC}
   ${RED}│ Run kernicle crash-analyze to investigate.                        │${NC}
   ${RED}╰────────────────────────────────────────────────────────────────────╯${NC}
     • 2026-01-04 14:35:22 - 156.3 MB

${YELLOW}5. You analyze the crash:${NC}
   ${CYAN}kernicle crash-analyze${NC}
   
   ${GREEN}✓ Crash information extracted${NC}
   ${GREEN}✓ AI verdict generated${NC}
   
   ${MAGENTA}╭──────────────────────── 📋 Crash Summary ──────────────────────────╮${NC}
   ${MAGENTA}│ Crash Time: 2026-01-04 14:35:22 UTC                               │${NC}
   ${MAGENTA}│ Kernel: 6.8.0-51-generic                                          │${NC}
   ${MAGENTA}│ Panic Message:                                                    │${NC}
   ${MAGENTA}│ BUG: unable to handle kernel NULL pointer dereference at 0x08    │${NC}
   ${MAGENTA}│                                                                   │${NC}
   ${MAGENTA}│ Call Trace: 28 frames captured                                   │${NC}
   ${MAGENTA}│ Kernel Log: 500 lines captured                                   │${NC}
   ${MAGENTA}╰───────────────────────────────────────────────────────────────────╯${NC}

${YELLOW}6. AI Analysis Result:${NC}
   ${WHITE}SEVERITY: CRITICAL${NC}
   ${WHITE}ROOT CAUSE: NULL pointer dereference in graphics driver (i915)${NC}
   ${WHITE}RECOMMENDATION: Update Intel graphics driver to latest version${NC}
   ${WHITE}COMMAND: sudo apt update && sudo apt install --reinstall linux-modules-extra-\$(uname -r)${NC}

${YELLOW}7. Capture surrounding logs for full context:${NC}
   ${CYAN}kernicle push -r \"last:1h\" -a --git${NC}
   
   ${GREEN}✓ Logs from BEFORE crash captured (survived in journald)${NC}
   ${GREEN}✓ Pushed to GitHub for backup${NC}
"

echo -e "${RED}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

# =============================================================================
# SUMMARY
# =============================================================================
echo -e "\n${GREEN}═══════════════════════════════════════════════════════════════════════${NC}"
echo -e "${WHITE}${BOLD}✅ SIMULATION COMPLETE!${NC}"
echo -e "${GREEN}═══════════════════════════════════════════════════════════════════════${NC}"

echo -e "
${WHITE}What we demonstrated:${NC}
  ${GREEN}✓${NC} Background monitoring with ${CYAN}kernicle start -a --git${NC}
  ${GREEN}✓${NC} Real kernel events captured and analyzed
  ${GREEN}✓${NC} AI verdict generation for detected issues
  ${GREEN}✓${NC} Automatic GitHub backup
  ${GREEN}✓${NC} HTML report export
  ${GREEN}✓${NC} How crash dump analysis would work

${WHITE}Your data is at:${NC}
  ${CYAN}~/.kernicle/archives/${NC}    - All session archives
  ${CYAN}~/.kernicle/git-backup/${NC}  - Git repository (pushed to GitHub)
  ${CYAN}~/Desktop/crash-simulation-report.html${NC} - Exported report

${WHITE}Key commands to remember:${NC}
  ${CYAN}kernicle start -a --git${NC}     - Start monitoring
  ${CYAN}kernicle push -r \"last:5m\" -a${NC} - Capture logs now
  ${CYAN}kernicle crash-check${NC}        - Check for crashes after reboot
  ${CYAN}kernicle crash-analyze${NC}      - Analyze crash dumps

${YELLOW}To test a REAL crash (VM ONLY!):${NC}
  ${RED}echo c | sudo tee /proc/sysrq-trigger${NC}
  ${DIM}⚠️ This will IMMEDIATELY crash your system!${NC}
"

echo -e "${CYAN}════════════════════════════════════════════════════════════════════════${NC}\n"
