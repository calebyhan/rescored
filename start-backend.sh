#!/bin/bash
set -e

echo "🔍 Checking DNS configuration..."

# Try to resolve youtube.com
if ! nslookup youtube.com > /dev/null 2>&1; then
    echo "⚠️ DNS resolution failed, attempting fixes..."
    
    # Check if we can ping Google's DNS
    if ping -c 1 8.8.8.8 > /dev/null 2>&1; then
        echo "✓ Network connectivity exists"
        echo "⚠️ DNS resolution issue - this may be a HF Spaces network policy"
    else
        echo "✗ No network connectivity"
    fi
    
    # Show current DNS config
    echo "Current DNS configuration:"
    cat /etc/resolv.conf || echo "Cannot read /etc/resolv.conf"
fi

echo ""
echo "🚀 Starting backend server..."
cd /app/backend && python -u main.py
