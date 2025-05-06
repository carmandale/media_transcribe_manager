#!/bin/bash
# Test script for legacy script aliases

# Set up colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}Testing legacy script aliases...${NC}"
echo "======================================"

# Function to test a script with arguments
test_script() {
    script_name=$1
    args=$2
    expected_cmd=$3
    
    echo -e "${BLUE}Testing ${script_name}...${NC}"
    # Use grep to find the command that would be executed
    output=$(python ${script_name} ${args} 2>&1 | grep "Forwarding to:")
    
    if [[ $output == *"$expected_cmd"* ]]; then
        echo -e "${GREEN}✓ PASSED: ${script_name} forwarded to expected command${NC}"
    else
        echo -e "${RED}✗ FAILED: ${script_name} did not forward correctly${NC}"
        echo "Expected: $expected_cmd"
        echo "Got: $output"
    fi
    echo ""
}

# Test each script
test_script "fix_stalled_files.py" "--timeout 60 --reset-all" "python scribe_manager.py fix stalled --timeout 60 --reset-all"
test_script "fix_path_issues.py" "--no-verify" "python scribe_manager.py fix paths --no-verify"
test_script "fix_transcript_status.py" "--batch-size 30" "python scribe_manager.py fix transcripts --batch-size 30"
test_script "fix_missing_transcripts.py" "--reset --batch-size 40" "python scribe_manager.py fix transcripts --batch-size 40"
test_script "fix_problem_translations.py" "--status qa_review --reason 'Format issues'" "python scribe_manager.py fix mark --status qa_review --reason 'Format issues'"
test_script "fix_hebrew_translations.py" "--model gpt-4-turbo --batch-size 15" "python scribe_manager.py fix hebrew --model gpt-4-turbo --batch-size 15"

echo -e "${BLUE}All tests completed!${NC}"