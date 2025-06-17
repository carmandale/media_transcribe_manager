# The PLAN→EXECUTE→SUMMARIZE→SUPERVISE Workflow

## Overview

The Manifesto Engine enforces a disciplined workflow that ensures quality, maintains vision alignment, and provides full accountability. This workflow consists of four distinct phases that must be followed for every task.

## The Four Phases

### 1. PLAN Phase
**What:** Worker analyzes the task and outputs a numbered plan
**Key Points:**
- Concrete, actionable steps
- No execution yet
- Identifies risks and dependencies
- **STOPS and waits for approval**

### 2. EXECUTE Phase  
**What:** Worker implements exactly as planned
**Trigger:** Human types "EXECUTE"
**Key Points:**
- Follows plan precisely
- Documents any deviations
- Captures proof of work
- No improvisation

### 3. SUMMARIZE Phase
**What:** Worker documents what was done
**Required Elements:**
- Actions taken
- Proof of completion
- Vision alignment statement
- Metrics impact
- Issues encountered
- **STOPS and waits for review**

### 4. SUPERVISE Phase
**What:** Supervisor reviews and provides verdict
**Verdicts:**
- APPROVED ✅ - Work meets all criteria
- NEEDS_REVISION ⚠️ - Specific changes required
- REJECTED ❌ - Fundamental issues, stop work

## Quick Start Guide

### For Workers (AI Agents)

1. **Receive a task** with the worker prompt template
2. **Output your PLAN** - numbered steps only
3. **WAIT** for "EXECUTE" command
4. **Implement** exactly as planned
5. **Summarize** with proof
6. **WAIT** for supervisor review

### For Supervisors

1. **Review** worker's summary against original request
2. **Check** the review checklist
3. **Provide verdict** with specific feedback
4. **Guide** next steps

## Template Usage

### Worker Template
```bash
# Copy the worker template
cat src/manifesto/templates/worker_prompt.md

# Fill in variables:
# - {{ task_id }} 
# - {{ task_title }}
# - {{ task_description }}
# - {{ vision }}
# - {{ vision_link }}
# - {{ acceptance_criteria }}

# Give to AI agent
```

### Supervisor Template
```bash
# Copy the supervisor template  
cat src/manifesto/templates/supervisor_review.md

# Fill in:
# - {{ task_id }}
# - {{ worker_summary }}
# - Review checklist results

# Provide verdict
```

## Best Practices

### For Quality Plans
- **Be Specific:** "Create logger.py" not "make logging"
- **Include Paths:** Full file paths prevent confusion
- **Show Verification:** How to prove each step worked
- **Think Ahead:** Identify dependencies and risks

### For Execution
- **Follow the Plan:** Don't improvise
- **Document Changes:** If you must deviate, explain why
- **Capture Everything:** Commands, outputs, errors
- **Stop if Blocked:** Don't guess, ask for help

### For Summaries  
- **Be Comprehensive:** Cover all acceptance criteria
- **Show Your Work:** Include actual outputs
- **Connect to Vision:** Explain HOW this helps
- **Be Honest:** Report issues encountered

### For Supervision
- **Be Thorough:** Check every requirement
- **Be Specific:** Vague feedback helps no one
- **Be Fair:** Acknowledge good work
- **Be Clear:** State exact revisions needed

## Common Patterns

### Pattern: Multi-Step Implementation
```
PLAN:
1. Create module structure
2. Implement core functionality  
3. Add tests
4. Integrate with existing code
5. Update documentation
```

### Pattern: Debugging Task
```
PLAN:
1. Reproduce the issue
2. Identify root cause
3. Implement fix
4. Verify fix works
5. Add regression test
```

### Pattern: Feature Addition
```
PLAN:
1. Design API/interface
2. Implement feature
3. Add comprehensive tests
4. Update relevant docs
5. Add example usage
```

## Troubleshooting

### Worker Proceeded Without Approval
**Issue:** Worker executed without "EXECUTE" command
**Fix:** Remind about workflow, restart task

### Plan Too Vague
**Issue:** Plan lacks specific steps
**Fix:** Request concrete actions with file paths

### Missing Proof
**Issue:** Summary lacks verification
**Fix:** Request command outputs, test results

### Vision Drift
**Issue:** Work doesn't align with vision
**Fix:** Review vision_link, may need task revision

## Benefits of This Workflow

1. **Predictability:** Everyone knows what happens when
2. **Quality:** Multiple checkpoints catch issues
3. **Alignment:** Vision checked at every phase  
4. **Learning:** Clear feedback improves agents
5. **Trust:** Full transparency builds confidence

## Example Workflow

See `src/manifesto/templates/workflow_example.md` for a complete example showing all four phases in action.

## Key Commands

```bash
# Check available templates
ls src/manifesto/templates/

# View worker template
cat src/manifesto/templates/worker_prompt.md

# View supervisor template  
cat src/manifesto/templates/supervisor_review.md

# See complete example
cat src/manifesto/templates/workflow_example.md
```

Remember: **Quality comes from discipline.** Follow the workflow, and success follows.