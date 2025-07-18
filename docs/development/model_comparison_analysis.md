# Model Comparison Analysis for Hebrew Translation Project

## Critical Finding: Current Model Usage

Based on code analysis, the system is currently using:
1. **Translation**: `gpt-4-turbo-preview` ($10/$30 per 1M tokens)
2. **Evaluation**: `gpt-4.1` default, but `gpt-4.5-preview` for batch ($75/$150 per 1M tokens!)
3. **GPT-4.5 is retiring July 14, 2025** - less than a month away!

## Cost Analysis for 379 Files

Assumptions:
- Average file: ~10,000 characters (~2,500 tokens)
- Total per file: ~5,000 tokens (input + output)
- Total project: 379 × 5,000 = 1,895,000 tokens (~1.9M)

### Translation Costs (379 files)

| Model | Input Cost | Output Cost | Total Cost | Cost per File |
|-------|------------|-------------|------------|---------------|
| **Current (GPT-4-Turbo)** | $9.50 | $28.50 | **$38.00** | $0.100 |
| GPT-4.5 (retiring!) | $71.25 | $142.50 | **$213.75** | $0.564 |
| GPT-4.1 | $1.90 | $7.60 | **$9.50** | $0.025 |
| GPT-4.1-mini | $0.38 | $1.52 | **$1.90** | $0.005 |
| GPT-4.1-nano | $0.095 | $0.38 | **$0.48** | $0.001 |
| GPT-4o | $4.75 | $19.00 | **$23.75** | $0.063 |
| GPT-4o-mini | $0.57 | $2.28 | **$2.85** | $0.008 |

### Evaluation Costs (if evaluating all 379 files)

| Model | Input Cost | Output Cost | Total Cost | Cost per File |
|-------|------------|-------------|------------|---------------|
| **Current (GPT-4.5)** | $71.25 | $142.50 | **$213.75** | $0.564 |
| GPT-4.1 | $1.90 | $7.60 | **$9.50** | $0.025 |
| GPT-4o | $4.75 | $19.00 | **$23.75** | $0.063 |

## Quality Comparison

### For Translation Tasks:
1. **GPT-4.5** - Most capable but unnecessarily expensive for translation
2. **GPT-4.1** - Flagship text model, excellent quality, 4x cheaper than current
3. **GPT-4-Turbo** - Current model, good quality but expensive
4. **GPT-4o** - Multimodal capabilities (not needed), slightly cheaper
5. **GPT-4.1-mini** - Good for straightforward translations, 20x cheaper
6. **GPT-4.1-nano** - Budget option, may compromise quality

### For Evaluation Tasks:
1. **GPT-4.5** - Currently used, overkill and retiring soon
2. **GPT-4.1** - Ideal balance of quality and cost
3. **GPT-4o** - Good alternative but more expensive than GPT-4.1

## Critical Recommendations

### Immediate Actions:
1. **STOP using GPT-4.5 for evaluation** - It's 22x more expensive than GPT-4.1!
2. **Replace GPT-4.5 with GPT-4.1** before July 14 retirement
3. **Switch translation from GPT-4-Turbo to GPT-4.1** - Same quality, 75% cheaper

### Recommended Configuration:

#### Option 1: Quality Priority (Recommended)
- **Translation**: GPT-4.1 ($9.50 total)
- **Evaluation**: GPT-4.1 ($9.50 total)
- **Total Cost**: ~$19 for all 379 files
- **Savings**: $232 vs current approach!

#### Option 2: Balanced Approach
- **Translation**: GPT-4.1-mini ($1.90 total)
- **Evaluation**: GPT-4.1 (sample 50 files = $1.25)
- **Total Cost**: ~$3.15
- **Quality Check**: Translate 10 files first to verify quality

#### Option 3: Budget Conscious
- **Translation**: GPT-4.1-nano ($0.48 total)
- **Evaluation**: Skip or spot-check only
- **Total Cost**: <$1
- **Risk**: Quality may not meet standards

## Cost Breakdown by Phase

### Current Approach (DO NOT USE):
- Phase 1: Translate 379 files with GPT-4-Turbo: $38
- Phase 2: Evaluate all with GPT-4.5: $213.75
- **Total: $251.75**

### Recommended Approach:
- Phase 1: Test 10 files with GPT-4.1: $0.25
- Phase 2: Evaluate test batch with GPT-4.1: $0.25
- Phase 3: If quality good, complete remaining 369 files: $9.25
- Phase 4: Spot-check evaluate 50 files: $1.25
- **Total: $11.00** (95% cost reduction!)

## Model Migration Plan

1. **Immediate** (before Task 5):
   ```python
   # In openai_integration.py
   model: str = "gpt-4.1"  # Replace gpt-4o-mini
   
   # In scribe/translate.py
   model="gpt-4.1",  # Replace gpt-4-turbo-preview
   
   # In evaluation scripts
   default='gpt-4.1'  # Replace gpt-4.5-preview
   ```

2. **Testing Protocol**:
   - Translate 5 files with each model
   - Compare quality side-by-side
   - Verify Hebrew character accuracy
   - Check for cultural/historical nuance preservation

3. **Fallback Strategy**:
   - If GPT-4.1 quality insufficient, try GPT-4o
   - Never fall back to GPT-4.5 (retiring soon)
   - Document quality differences for future reference 