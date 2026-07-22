#!/bin/bash
# =============================================================================
# Kernicle Crash Capture Setup Script
# =============================================================================
# This script sets up kdump/kexec for capturing kernel panics and hard crashes.
# Run with: sudo ./setup-crash-capture.sh
# =============================================================================

# Don't exit on first error - we want to handle them gracefully
# set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color
BOLD='\033[1m'

# Configuration
CRASHKERNEL_MEM="512M-:192M"  # Reserve 192M when RAM > 512M
CRASH_DIR="/var/crash"

echo -e "${CYAN}"
echo "╔════════════════════════════════════════════════════════════════════╗"
echo "║            KERNICLE CRASH CAPTURE SETUP                           ║"
echo "║     'Kernicle reads the CHAOS; shows the CLARITY'                 ║"
echo "╚════════════════════════════════════════════════════════════════════╝"
echo -e "${NC}"

# Check for root
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}ERROR: This script must be run as root (sudo)${NC}"
    echo "Usage: sudo $0"
    exit 1
fi

echo -e "${BOLD}This script will:${NC}"
echo "  1. Install kdump-tools and kexec-tools"
echo "  2. Configure crashkernel parameter in GRUB"
echo "  3. Enable and start kdump service"
echo "  4. Install Kernicle crash check service"
echo ""
echo -e "${YELLOW}⚠️  A REBOOT WILL BE REQUIRED after setup!${NC}"
echo ""
read -p "Continue? (y/N) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Aborted."
    exit 0
fi

# =============================================================================
# Step 1: Install packages
# =============================================================================
echo ""
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BOLD}Step 1: Installing required packages${NC}"
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

# Update package list (ignore errors from debug symbol repos)
apt-get update 2>&1 | grep -v "ddebs.ubuntu.com" || true

# Install kdump-tools (will prompt for configuration)
echo -e "${YELLOW}Installing kdump-tools...${NC}"
echo "Note: Select 'Yes' when asked to enable kdump"
DEBIAN_FRONTEND=noninteractive apt-get install -y kdump-tools kexec-tools crash makedumpfile linux-crashdump || {
    echo -e "${YELLOW}Some packages may already be installed, continuing...${NC}"
}

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Packages installed successfully${NC}"
else
    echo -e "${RED}✗ Package installation failed${NC}"
    exit 1
fi

# =============================================================================
# Step 2: Configure crashkernel in GRUB
# =============================================================================
echo ""
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BOLD}Step 2: Configuring crashkernel in GRUB${NC}"
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

GRUB_FILE="/etc/default/grub"

# Backup GRUB config
cp "$GRUB_FILE" "${GRUB_FILE}.bak.$(date +%Y%m%d%H%M%S)"
echo -e "${GREEN}✓ GRUB config backed up${NC}"

# Check if crashkernel already configured
if grep -q "crashkernel=" "$GRUB_FILE"; then
    echo -e "${YELLOW}Crashkernel already configured in GRUB${NC}"
    CURRENT=$(grep "GRUB_CMDLINE_LINUX_DEFAULT" "$GRUB_FILE" | grep -o "crashkernel=[^ \"]*" || echo "")
    echo "  Current: $CURRENT"
else
    # Add crashkernel parameter
    echo -e "${YELLOW}Adding crashkernel parameter...${NC}"
    
    if grep -q "^GRUB_CMDLINE_LINUX_DEFAULT=" "$GRUB_FILE"; then
        # Append to existing line
        sed -i "s/\(GRUB_CMDLINE_LINUX_DEFAULT=\"[^\"]*\)/\1 crashkernel=$CRASHKERNEL_MEM/" "$GRUB_FILE"
    else
        # Add new line
        echo "GRUB_CMDLINE_LINUX_DEFAULT=\"crashkernel=$CRASHKERNEL_MEM\"" >> "$GRUB_FILE"
    fi
    
    echo -e "${GREEN}✓ Crashkernel parameter added: $CRASHKERNEL_MEM${NC}"
fi

# Update GRUB
echo -e "${YELLOW}Updating GRUB...${NC}"
update-grub

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ GRUB updated successfully${NC}"
else
    echo -e "${RED}✗ GRUB update failed${NC}"
    exit 1
fi

# =============================================================================
# Step 3: Configure kdump
# =============================================================================
echo ""
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BOLD}Step 3: Configuring kdump service${NC}"
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

KDUMP_CONFIG="/etc/default/kdump-tools"

if [ -f "$KDUMP_CONFIG" ]; then
    # Enable kdump
    sed -i 's/USE_KDUMP=0/USE_KDUMP=1/' "$KDUMP_CONFIG"
    
    # Set crash directory
    if ! grep -q "^KDUMP_COREDIR=" "$KDUMP_CONFIG"; then
        echo "KDUMP_COREDIR=\"$CRASH_DIR\"" >> "$KDUMP_CONFIG"
    fi
    
    echo -e "${GREEN}✓ kdump configured${NC}"
else
    echo -e "${YELLOW}kdump config file not found, using defaults${NC}"
fi

# Create crash directory
mkdir -p "$CRASH_DIR"
chmod 700 "$CRASH_DIR"
echo -e "${GREEN}✓ Crash directory created: $CRASH_DIR${NC}"

# Enable kdump service
systemctl enable kdump-tools
echo -e "${GREEN}✓ kdump service enabled${NC}"

# =============================================================================
# Step 4: Install Kernicle crash check service
# =============================================================================
echo ""
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BOLD}Step 4: Installing Kernicle crash check service${NC}"
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

# Check if systemd service file exists in the script's directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVICE_FILE="$SCRIPT_DIR/systemd/kernicle-crash-check.service"

if [ -f "$SERVICE_FILE" ]; then
    cp "$SERVICE_FILE" /etc/systemd/system/
    systemctl daemon-reload
    systemctl enable kernicle-crash-check.service
    echo -e "${GREEN}✓ Kernicle crash check service installed${NC}"
else
    echo -e "${YELLOW}⚠ Service file not found at $SERVICE_FILE${NC}"
    echo "  You can manually run 'kernicle check-crashes' after reboots"
fi

# =============================================================================
# Summary
# =============================================================================
echo ""
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BOLD}Setup Complete!${NC}"
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo -e "${GREEN}✓ kdump-tools installed${NC}"
echo -e "${GREEN}✓ crashkernel configured in GRUB${NC}"
echo -e "${GREEN}✓ kdump service enabled${NC}"
echo -e "${GREEN}✓ Crash directory: $CRASH_DIR${NC}"
echo ""
echo -e "${YELLOW}╔════════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${YELLOW}║  ${BOLD}⚠️  IMPORTANT: YOU MUST REBOOT NOW!${NC}${YELLOW}                              ║${NC}"
echo -e "${YELLOW}║                                                                    ║${NC}"
echo -e "${YELLOW}║  The crash kernel needs to be loaded into memory.                  ║${NC}"
echo -e "${YELLOW}║  Run: ${CYAN}sudo reboot${NC}${YELLOW}                                                 ║${NC}"
echo -e "${YELLOW}║                                                                    ║${NC}"
echo -e "${YELLOW}║  After reboot, verify with:                                        ║${NC}"
echo -e "${YELLOW}║  ${CYAN}kernicle crash-status${NC}${YELLOW}                                             ║${NC}"
echo -e "${YELLOW}║                                                                    ║${NC}"
echo -e "${YELLOW}║  Or check manually:                                                ║${NC}"
echo -e "${YELLOW}║  ${CYAN}cat /sys/kernel/kexec_crash_loaded${NC}${YELLOW}  (should show 1)              ║${NC}"
echo -e "${YELLOW}╚════════════════════════════════════════════════════════════════════╝${NC}"
echo ""

read -p "Reboot now? (y/N) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "Rebooting..."
    reboot
fi
