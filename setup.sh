#!/bin/bash

# ╔═══════════════════════════════════════════════════════════════╗
# ║  Kernicle - Setup Script                                      ║
# ║  "reads the CHAOS; shows the CLARITY"                         ║
# ║                                                                ║
# ║  This script sets up Kernicle and the optional AI plugin      ║
# ╚═══════════════════════════════════════════════════════════════╝

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

print_header() {
    echo ""
    echo -e "${CYAN}═══════════════════════════════════════════════════════════${NC}"
    echo -e "${CYAN}  🔍 Kernicle Setup${NC}"
    echo -e "${CYAN}  \"reads the CHAOS; shows the CLARITY\"${NC}"
    echo -e "${CYAN}═══════════════════════════════════════════════════════════${NC}"
    echo ""
}

print_step() {
    echo -e "${BLUE}[$1/$TOTAL_STEPS]${NC} $2"
}

print_success() {
    echo -e "    ${GREEN}✓${NC} $1"
}

print_warning() {
    echo -e "    ${YELLOW}⚠${NC} $1"
}

print_error() {
    echo -e "    ${RED}✗${NC} $1"
}

# Determine total steps based on AI plugin availability
if [ -d "kernicle-ai" ]; then
    TOTAL_STEPS=8
else
    TOTAL_STEPS=6
fi

print_header

# ─────────────────────────────────────────────────────────────────
# Step 1: Check Python version
# ─────────────────────────────────────────────────────────────────
print_step 1 "Checking Python version..."

if ! command -v python3 &> /dev/null; then
    print_error "Python 3 is not installed"
    echo "    Please install Python 3.10 or higher:"
    echo "    Ubuntu/Debian: sudo apt install python3 python3-pip python3-venv"
    echo "    Fedora: sudo dnf install python3 python3-pip"
    exit 1
fi

PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
PYTHON_MAJOR=$(echo $PYTHON_VERSION | cut -d. -f1)
PYTHON_MINOR=$(echo $PYTHON_VERSION | cut -d. -f2)

if [ "$PYTHON_MAJOR" -lt 3 ] || ([ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -lt 10 ]); then
    print_error "Python 3.10+ required, found $PYTHON_VERSION"
    exit 1
fi

print_success "Python $PYTHON_VERSION found"

# ─────────────────────────────────────────────────────────────────
# Step 2: Check system dependencies
# ─────────────────────────────────────────────────────────────────
print_step 2 "Checking system dependencies..."

# Check journalctl
if ! command -v journalctl &> /dev/null; then
    print_warning "journalctl not found - log capture won't work"
else
    print_success "journalctl available"
fi

# Check if user can access journal
if groups | grep -qE "(systemd-journal|wheel|adm)"; then
    print_success "User has journal access"
else
    print_warning "Add user to systemd-journal group for non-sudo access:"
    echo "         sudo usermod -aG systemd-journal \$USER && newgrp systemd-journal"
fi

# ─────────────────────────────────────────────────────────────────
# Step 3: Create virtual environment
# ─────────────────────────────────────────────────────────────────
print_step 3 "Setting up virtual environment..."

if [ -d "venv" ]; then
    print_warning "Virtual environment exists, reusing..."
else
    python3 -m venv venv
    print_success "Virtual environment created"
fi

# Activate virtual environment
source venv/bin/activate
print_success "Virtual environment activated"

# ─────────────────────────────────────────────────────────────────
# Step 4: Upgrade pip
# ─────────────────────────────────────────────────────────────────
print_step 4 "Upgrading pip..."
pip install --upgrade pip --quiet
print_success "pip upgraded"

# ─────────────────────────────────────────────────────────────────
# Step 5: Install Kernicle
# ─────────────────────────────────────────────────────────────────
print_step 5 "Installing Kernicle..."
pip install -e ".[dev]" --quiet
print_success "Kernicle installed"

# ─────────────────────────────────────────────────────────────────
# Step 6: Install kernicle-ai plugin (if available)
# ─────────────────────────────────────────────────────────────────
if [ -d "kernicle-ai" ]; then
    print_step 6 "Installing kernicle-ai plugin..."
    pip install -e "./kernicle-ai[dev]" --quiet
    print_success "kernicle-ai plugin installed"
    
    # Step 7: Configure API keys
    print_step 7 "Configuring AI providers..."
    
    if [ -z "$GROQ_API_KEY" ]; then
        print_warning "GROQ_API_KEY not set"
        echo ""
        echo -e "    ${YELLOW}To enable AI analysis, get a FREE API key:${NC}"
        echo "    1. Visit: https://console.groq.com"
        echo "    2. Sign up and create an API key"
        echo "    3. Add to ~/.bashrc:"
        echo "       export GROQ_API_KEY=\"your_key_here\""
        echo ""
    else
        print_success "GROQ_API_KEY configured"
    fi
    
    if [ -z "$GEMINI_API_KEY" ]; then
        print_warning "GEMINI_API_KEY not set (optional fallback)"
    else
        print_success "GEMINI_API_KEY configured"
    fi
    
    NEXT_STEP=8
else
    NEXT_STEP=6
fi

# ─────────────────────────────────────────────────────────────────
# Final Step: Run tests
# ─────────────────────────────────────────────────────────────────
print_step $NEXT_STEP "Running tests..."

if pytest tests/ -q --tb=no; then
    MAIN_TESTS=$(pytest tests/ --collect-only -q 2>/dev/null | tail -1 | grep -oE '[0-9]+' | head -1)
    print_success "$MAIN_TESTS kernicle tests passed"
else
    print_error "Some tests failed"
    exit 1
fi

if [ -d "kernicle-ai" ]; then
    if (cd kernicle-ai && pytest tests/ -q --tb=no); then
        AI_TESTS=$(cd kernicle-ai && pytest tests/ --collect-only -q 2>/dev/null | tail -1 | grep -oE '[0-9]+' | head -1)
        print_success "$AI_TESTS kernicle-ai tests passed"
    fi
fi

# ─────────────────────────────────────────────────────────────────
# Setup Complete
# ─────────────────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}═══════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}  ✅ Setup Complete!${NC}"
echo -e "${GREEN}═══════════════════════════════════════════════════════════${NC}"
echo ""
echo -e "${CYAN}Quick Start:${NC}"
echo ""
echo "  1. Activate the virtual environment:"
echo -e "     ${YELLOW}source venv/bin/activate${NC}"
echo ""
echo "  2. Verify installation:"
echo -e "     ${YELLOW}kernicle --version${NC}"
echo ""
echo "  3. Capture logs from the last 5 minutes:"
echo -e "     ${YELLOW}kernicle push --range 'last:5m' --all${NC}"
echo ""
echo "  4. View your sessions:"
echo -e "     ${YELLOW}kernicle show${NC}"
echo ""
echo "  5. Export a beautiful HTML report:"
echo -e "     ${YELLOW}kernicle export <session-id> --format html${NC}"
echo ""

if [ -d "kernicle-ai" ]; then
    echo -e "${CYAN}AI Analysis:${NC}"
    if [ -n "$GROQ_API_KEY" ]; then
        echo -e "  ${GREEN}✓${NC} AI analysis is enabled and will auto-enhance your reports!"
    else
        echo "  Set GROQ_API_KEY to enable AI-powered diagnostics in exports."
    fi
    echo ""
fi

echo -e "${CYAN}Documentation:${NC} See README.md and QUICKSTART.md"
echo ""
