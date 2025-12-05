# Evaluation Framework

A deterministic evaluation suite for the Retail Shopping Assistant, inspired by [τ²-bench](https://arxiv.org/abs/2406.12045).

## Quick Start

```bash
# 1. Start the application
docker-compose up -d

# 2. Wait for services to be ready
docker-compose ps   # All should show "Up"

# 3. Activate Python environment
source .venv/bin/activate

# 4. Run evals
python -m evals.run_eval
```

## What This Does

The eval framework tests the shopping assistant by:

1. **Loading test tasks** from YAML files
2. **Setting up initial state** (cart, conversation context)
3. **Sending queries** to the assistant
4. **Verifying responses** against expected criteria
5. **Computing metrics** (pass@k, routing accuracy, latency)

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   Task YAML     │────▶│   Eval Runner   │────▶│    Results      │
│                 │     │                 │     │                 │
│ - user query    │     │ 1. Initialize   │     │ - pass@1: 85%   │
│ - expected      │     │ 2. Execute      │     │ - pass@4: 100%  │
│   routing       │     │ 3. Verify       │     │ - latency: 1.2s │
│ - cart check    │     │ 4. Report       │     │                 │
└─────────────────┘     └─────────────────┘     └─────────────────┘
```

## Directory Structure

```
evals/
├── README.md              # This file
├── run_eval.py            # CLI entry point
├── core/                  # Framework code
│   ├── __init__.py        # Public exports
│   ├── schemas.py         # Pydantic data models
│   ├── task_loader.py     # YAML parser
│   ├── initializer.py     # State setup (cart/context)
│   ├── verifier.py        # Result checking
│   └── runner.py          # Orchestrator
└── tasks/                 # Test definitions
    ├── atomic/            # Single-turn tests
    │   ├── cart/          # Cart operations
    │   ├── search/        # Product search
    │   ├── details/       # Product details
    │   └── routing/       # Agent routing
    ├── composed/          # Multi-turn conversations
    └── edge_cases/        # Error handling, guardrails
```

## Running Evals

### Basic Usage

```bash
# Run all tasks with 1 trial (quick test)
python -m evals.run_eval

# Run all tasks with 4 trials (full evaluation)
python -m evals.run_eval --trials 4

# Verbose output
python -m evals.run_eval -v
```

### Filtering Tasks

```bash
# Run only cart tests
python -m evals.run_eval --pattern "atomic/cart/*.yaml"

# Run only search tests
python -m evals.run_eval --pattern "atomic/search/*.yaml"

# Run only composed (multi-turn) tests
python -m evals.run_eval --pattern "composed/*.yaml"

# Run tasks with specific tag
python -m evals.run_eval --tag cart
```

### Custom Endpoints

```bash
# Use different server URLs
python -m evals.run_eval \
    --chain-url http://localhost:8009 \
    --memory-url http://localhost:8011
```

### Saving Results

```bash
# Save full report as JSON
python -m evals.run_eval --output results.json
```

## Understanding Results

```
============================================================
RESULTS
============================================================
Total tasks:     13
Total attempts:  13
Duration:        45.2s

PASS@K METRICS:
  Pass@1: 85.0%      # First attempt success rate
  Pass@2: 92.0%      # Success within 2 attempts
  Pass@4: 100.0%     # Success within 4 attempts

Routing Accuracy: 95.0%   # Correct agent selection

BY CATEGORY:
  cart: 100.0%
  search: 80.0%
  routing: 100.0%

TASK RESULTS:
  ✓ cart_add_001: Add item to cart by name
  ✓ search_text_001: Search for skirts
  ✗ edge_guardrail_001: Reject theft-related query
      └─ response_failure
```

### Metrics Explained

| Metric | Meaning |
|--------|---------|
| **Pass@1** | Task succeeded on first attempt |
| **Pass@4** | Task succeeded within 4 attempts |
| **Routing Accuracy** | Correct agent was selected |
| **Avg Latency** | Mean response time |
| **P95 Latency** | 95th percentile response time |

## Writing New Tasks

Tasks are YAML files that define test scenarios.

### Atomic Task (Single Turn)

```yaml
# evals/tasks/atomic/cart/add_item.yaml

task_id: "cart_add_001"
name: "Add item to cart by name"
type: "atomic"
category: "cart"

# Initial state setup
init:
  cart: []  # Start with empty cart
  context: "Previously shown: Satin Effect Midi Skirt priced at $45.90"

# The conversation
turns:
  - user: "Add the Satin Effect Midi Skirt to my cart"

# What to verify
verify:
  routing:
    expected: "cart"           # Should route to cart agent
  cart:
    length: 1                  # Cart should have 1 item
  response:
    not_empty: true
    contains_any:              # Response should mention adding
      - "added"
      - "Added"
      - "cart"

tags:
  - "cart"
  - "add"
```

### Composed Task (Multi-Turn)

```yaml
# evals/tasks/composed/browse_and_buy.yaml

task_id: "composed_browse_001"
name: "Browse products and add to cart"
type: "composed"
category: "end_to_end"

init:
  cart: []
  context: ""

turns:
  - user: "Show me some skirts"
    verify:
      routing:
        expected: "retriever"
      retrieved:
        min_count: 1

  - user: "Add the first one to my cart"
    verify:
      routing:
        expected: "cart"

# Final verification after all turns
final_verify:
  cart:
    length: 1
  response:
    not_empty: true

max_turns: 3
timeout_seconds: 45

tags:
  - "end_to_end"
  - "browse"
```

### Verification Options

```yaml
verify:
  # Check which agent handled the query
  routing:
    expected: "retriever"  # or "cart" or "chatter"

  # Check retrieved products
  retrieved:
    min_count: 1           # At least N products found

  # Check cart state
  cart:
    length: 1              # Exact number of items
    contains:              # Must contain these items
      - "Skirt"

  # Check response text
  response:
    not_empty: true
    contains_any:          # At least one must match
      - "skirt"
      - "Skirt"
    contains_all:          # All must match
      - "added"
      - "cart"
    not_contains:          # None should match
      - "error"
      - "sorry"
```

## Architecture

### How It Works

```
┌─────────────────────────────────────────────────────────────────────────┐
│ YOUR MAC (Host)                                                         │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │ EVAL FRAMEWORK (Python)                                         │    │
│  │                                                                 │    │
│  │  TaskLoader ──▶ EvalInitializer ──▶ EvalRunner ──▶ EvalVerifier │    │
│  │      │               │                  │              │        │    │
│  │      │               │                  │              │        │    │
│  │  Load YAML      Setup cart/        Call API        Check        │    │
│  │  tasks          context            endpoint        results      │    │
│  └──────┼───────────────┼──────────────────┼──────────────┼────────┘    │
│         │               │                  │              │             │
│         │      HTTP     │        HTTP      │              │             │
│         │               ▼                  ▼              │             │
└─────────┼───────────────┬──────────────────┬──────────────┼─────────────┘
          │               │                  │              │
          │    ┌──────────┴──────────────────┴─────────┐    │
          │    │ DOCKER NETWORK                        │    │
          │    │                                       │    │
          │    │  memory-retriever:8011                │    │
          │    │  (cart/context storage)               │    │
          │    │                                       │    │
          │    │  chain-server:8009                    │    │
          │    │  (LangGraph orchestrator)             │    │
          │    │                                       │    │
          │    └───────────────────────────────────────┘    │
          │                                                 │
          └─────────────────────────────────────────────────┘
```

### Components

| Component | Purpose |
|-----------|---------|
| **TaskLoader** | Parse YAML files into Task objects |
| **EvalInitializer** | Set up cart/context via memory-retriever API |
| **EvalRunner** | Execute tasks, call /query/eval endpoint |
| **EvalVerifier** | Check responses against criteria |

### API Endpoints Used

| Endpoint | Service | Purpose |
|----------|---------|---------|
| `POST /query/eval` | chain-server:8009 | Execute query, get full state |
| `POST /user/{id}/cart/clear` | memory-retriever:8011 | Clear cart |
| `POST /user/{id}/context/clear` | memory-retriever:8011 | Clear context |
| `POST /user/{id}/context/replace` | memory-retriever:8011 | Set context |
| `POST /user/{id}/cart/add` | memory-retriever:8011 | Add cart item |
| `GET /user/{id}/cart` | memory-retriever:8011 | Read cart |

## Troubleshooting

### "Connection refused" error

```
Make sure Docker services are running:
  docker-compose up -d
  docker-compose ps
```

### Tasks not loading

```bash
# Check task files are valid YAML
python -c "
from evals.core import TaskLoader
loader = TaskLoader()
tasks = loader.load_all()
print(f'Loaded {len(tasks)} tasks')
for t in tasks:
    print(f'  {t.task_id}')
"
```

### Verification failures

Run with verbose mode to see details:
```bash
python -m evals.run_eval -v
```

### Check specific task

```python
import asyncio
from evals.core import TaskLoader, EvalRunner, EvalConfig

async def test_one():
    loader = TaskLoader()
    task = loader.load_task("atomic/cart/add_by_name.yaml")

    runner = EvalRunner(config=EvalConfig())
    result = await runner.run_task(task, trials=1)

    print(f"Passed: {result.pass_at_1}")
    if result.attempts:
        for turn in result.attempts[0].turn_results:
            print(f"  Turn: {turn.query[:50]}...")
            print(f"  Agent: {turn.next_agent}")
            print(f"  Passed: {turn.verify_result.success if turn.verify_result else 'N/A'}")

asyncio.run(test_one())
```

## Current Tasks

| Category | Count | Description |
|----------|-------|-------------|
| atomic/cart | 1 | Cart operations |
| atomic/search | 3 | Product search |
| atomic/details | 1 | Product details |
| atomic/routing | 3 | Agent routing |
| composed | 2 | Multi-turn conversations |
| edge_cases | 3 | Guardrails, error handling |
| **Total** | **13** | |

## Adding More Tasks

1. Create a new YAML file in the appropriate folder
2. Follow the schema (see examples above)
3. Run to verify: `python -m evals.run_eval --pattern "path/to/your/task.yaml"`

## Design Philosophy

- **Deterministic**: No LLM-as-judge, purely programmatic verification
- **Fast**: Sub-second verification, no API calls for checking
- **Isolated**: Uses user IDs 9000+ to avoid production conflicts
- **Reproducible**: Same task = same verification criteria every time
