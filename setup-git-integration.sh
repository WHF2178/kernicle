#!/bin/bash
# =============================================================================
# KERNICLE GIT INTEGRATION SETUP & TESTING
# =============================================================================
# This script helps you set up Git integration for Kernicle
# Your session archives will be automatically backed up to a Git repository
#
# Run with: ./setup-git-integration.sh
# =============================================================================

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'
BOLD='\033[1m'

echo -e "${CYAN}"
echo "╔════════════════════════════════════════════════════════════════════╗"
echo "║           KERNICLE GIT INTEGRATION SETUP                           ║"
echo "╚════════════════════════════════════════════════════════════════════╝"
echo -e "${NC}"

# =============================================================================
# STEP 1: Check Prerequisites
# =============================================================================
echo -e "${BOLD}Step 1: Checking Prerequisites${NC}"
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

# Check if git is installed
if command -v git &> /dev/null; then
    echo -e "${GREEN}✓ Git is installed: $(git --version)${NC}"
else
    echo -e "${RED}✗ Git is not installed. Installing...${NC}"
    sudo apt-get install -y git
fi

# Check if SSH key exists
if [ -f ~/.ssh/id_rsa ] || [ -f ~/.ssh/id_ed25519 ]; then
    echo -e "${GREEN}✓ SSH key exists${NC}"
else
    echo -e "${YELLOW}⚠ No SSH key found. Creating one...${NC}"
    ssh-keygen -t ed25519 -C "kernicle-backup" -f ~/.ssh/id_ed25519 -N ""
    echo -e "${GREEN}✓ SSH key created${NC}"
fi

# =============================================================================
# STEP 2: Create GitHub Repository (Manual Step)
# =============================================================================
echo -e "\n${BOLD}Step 2: Create GitHub Repository${NC}"
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

echo -e "
${YELLOW}MANUAL STEP REQUIRED:${NC}

1. Go to ${CYAN}https://github.com/new${NC}

2. Create a new repository:
   - Name: ${CYAN}kernicle-logs${NC} (or any name you prefer)
   - Visibility: ${YELLOW}Private${NC} (IMPORTANT for security!)
   - DO NOT initialize with README

3. Copy the SSH URL, it will look like:
   ${CYAN}git@github.com:YOUR_USERNAME/kernicle-logs.git${NC}

4. Add your SSH key to GitHub:
   - Go to ${CYAN}https://github.com/settings/keys${NC}
   - Click 'New SSH key'
   - Paste your public key:
"

echo -e "${CYAN}Your SSH public key:${NC}"
if [ -f ~/.ssh/id_ed25519.pub ]; then
    cat ~/.ssh/id_ed25519.pub
elif [ -f ~/.ssh/id_rsa.pub ]; then
    cat ~/.ssh/id_rsa.pub
fi

echo ""
read -p "Press Enter after you've created the GitHub repository and added your SSH key..."

# =============================================================================
# STEP 3: Configure Kernicle Git Settings
# =============================================================================
echo -e "\n${BOLD}Step 3: Configure Kernicle Git Settings${NC}"
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

read -p "Enter your GitHub repository SSH URL (e.g., git@github.com:user/kernicle-logs.git): " GIT_REMOTE

if [ -z "$GIT_REMOTE" ]; then
    echo -e "${RED}No URL provided. Using example...${NC}"
    GIT_REMOTE="git@github.com:YOUR_USERNAME/kernicle-logs.git"
fi

# Set environment variables
export KERNICLE_GIT_REMOTE="$GIT_REMOTE"
export KERNICLE_GIT_REPO_DIR="$HOME/.kernicle/git-backup"
export KERNICLE_GIT_BRANCH="main"

echo -e "\n${GREEN}✓ Git settings configured:${NC}"
echo -e "  KERNICLE_GIT_REMOTE=$KERNICLE_GIT_REMOTE"
echo -e "  KERNICLE_GIT_REPO_DIR=$KERNICLE_GIT_REPO_DIR"
echo -e "  KERNICLE_GIT_BRANCH=$KERNICLE_GIT_BRANCH"

# =============================================================================
# STEP 4: Add to .bashrc for Persistence
# =============================================================================
echo -e "\n${BOLD}Step 4: Save Settings to .bashrc${NC}"
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

# Check if already in .bashrc
if grep -q "KERNICLE_GIT_REMOTE" ~/.bashrc; then
    echo -e "${YELLOW}Git settings already in .bashrc. Updating...${NC}"
    sed -i '/KERNICLE_GIT_REMOTE/d' ~/.bashrc
    sed -i '/KERNICLE_GIT_REPO_DIR/d' ~/.bashrc
    sed -i '/KERNICLE_GIT_BRANCH/d' ~/.bashrc
fi

cat >> ~/.bashrc << EOF

# Kernicle Git Integration
export KERNICLE_GIT_REMOTE="$GIT_REMOTE"
export KERNICLE_GIT_REPO_DIR="\$HOME/.kernicle/git-backup"
export KERNICLE_GIT_BRANCH="main"
EOF

echo -e "${GREEN}✓ Settings saved to ~/.bashrc${NC}"

# =============================================================================
# STEP 5: Test Git Integration
# =============================================================================
echo -e "\n${BOLD}Step 5: Test Git Integration${NC}"
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

echo -e "\n${CYAN}Testing SSH connection to GitHub...${NC}"
ssh -T git@github.com 2>&1 || true

echo -e "\n${CYAN}Running kernicle push with --git flag...${NC}"

# Activate virtual environment if needed
if [ -z "$VIRTUAL_ENV" ] && [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
fi

# Run push with git
kernicle push --range "last:2m" --all --git

echo -e "\n${CYAN}Checking Git backup directory:${NC}"
if [ -d "$HOME/.kernicle/git-backup" ]; then
    ls -la "$HOME/.kernicle/git-backup/"
    
    echo -e "\n${CYAN}Git log:${NC}"
    cd "$HOME/.kernicle/git-backup"
    git log --oneline -5 2>/dev/null || echo "No commits yet"
    cd - > /dev/null
else
    echo -e "${YELLOW}Git backup directory not created yet${NC}"
fi

# =============================================================================
# Summary
# =============================================================================
echo -e "\n${CYAN}"
echo "╔════════════════════════════════════════════════════════════════════╗"
echo "║                    GIT INTEGRATION COMPLETE                        ║"
echo "╚════════════════════════════════════════════════════════════════════╝"
echo -e "${NC}"

echo -e "${GREEN}✓ Git integration is set up!${NC}"
echo -e ""
echo -e "${BOLD}How to use:${NC}"
echo -e "  ${CYAN}kernicle push --range \"last:5m\" --all --git${NC}"
echo -e ""
echo -e "${BOLD}Your backups are pushed to:${NC}"
echo -e "  ${CYAN}$GIT_REMOTE${NC}"
echo -e ""
echo -e "${BOLD}Local Git repo:${NC}"
echo -e "  ${CYAN}$HOME/.kernicle/git-backup/${NC}"
echo -e ""
echo -e "${BOLD}To view on GitHub:${NC}"
echo -e "  ${CYAN}https://github.com/$(echo $GIT_REMOTE | sed 's/.*://' | sed 's/\.git$//')${NC}"
echo ""
