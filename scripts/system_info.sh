#!/bin/bash
# System info script for Archon workflow test
set -euo pipefail

timestamp=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
hostname=$(hostname)
os=$(uname -s)
arch=$(uname -m)
user=$(whoami)

cat <<JSON
{
  "timestamp": "$timestamp",
  "hostname": "$hostname",
  "os": "$os",
  "architecture": "$arch",
  "user": "$user",
  "archon_test": "workflow-validation"
}
JSON