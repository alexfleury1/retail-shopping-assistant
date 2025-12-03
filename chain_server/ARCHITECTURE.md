# Chain Server Architecture

The Chain Server is the orchestration layer of the Retail Shopping Assistant. It uses **LangGraph** to coordinate multiple specialized agents that handle different aspects of user queries.

## Overview

```
                                 ┌─────────────────┐
                                 │   User Query    │
                                 │ "show me dresses│
                                 └────────┬────────┘
                                          │
                                          ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                            CHAIN SERVER                                      │
│                         (FastAPI + LangGraph)                               │
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │                         LangGraph State Machine                        │ │
│  │                                                                        │ │
│  │    ┌──────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐   │ │
│  │    │ Memory   │────▶│ Planner  │────▶│Retriever │────▶│ Chatter  │   │ │
│  │    │  Node    │     │   Node   │     │   Node   │     │   Node   │   │ │
│  │    └──────────┘     └──────────┘     └──────────┘     └──────────┘   │ │
│  │         │                │                                    │       │ │
│  │         │                ▼                                    │       │ │
│  │         │          ┌──────────┐                               │       │ │
│  │         │          │   Cart   │                               │       │ │
│  │         │          │   Node   │───────────────────────────────┘       │ │
│  │         │          └──────────┘                                       │ │
│  │         │                                                             │ │
│  │         └──────────────────┬──────────────────────────────────────────┘ │
│  │                            │                                            │
│  │                    ┌───────▼───────┐                                   │ │
│  │                    │  Guardrails   │                                   │ │
│  │                    │ (Safety Check)│                                   │ │
│  │                    └───────────────┘                                   │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────┘
                                          │
                                          ▼
                                 ┌─────────────────┐
                                 │    Response     │
                                 │"Here are some..."│
                                 └─────────────────┘
```

## File Structure

```
chain_server/
├── src/
│   ├── main.py          # FastAPI app, /query/stream endpoint
│   ├── graph.py         # LangGraph state machine definition
│   ├── agenttypes.py    # State, Cart, Rail Pydantic models
│   ├── planner.py       # Query routing agent
│   ├── chatter.py       # Response generation agent
│   ├── cart.py          # Shopping cart operations agent
│   ├── retriever.py     # Product search agent
│   ├── summarizer.py    # Memory update agent
│   └── config.py        # Configuration loader
├── requirements.txt
├── Dockerfile
└── ARCHITECTURE.md      # This file
```

## Core Components

### 1. State Object (`agenttypes.py`)

The `State` object flows through all nodes, accumulating data:

```python
class State(BaseModel):
    user_id: int          # User identifier
    query: str            # User's input ("show me dresses")
    context: str          # Conversation history
    cart: Cart            # Shopping cart contents
    response: str         # Generated response
    image: str            # Base64 image (if uploaded)
    retrieved: Dict       # Products from search
    next_agent: str       # Routing decision
    guardrails: bool      # Safety checks enabled
    timings: Dict         # Performance metrics
```

### 2. LangGraph Flow (`graph.py`)

```
                                    START
                                      │
                                      ▼
                              ┌───────────────┐
                              │  memory_node  │
                              │               │
                              │ Fetches:      │
                              │ • User context│
                              │ • Cart state  │
                              └───────┬───────┘
                                      │
                    ┌─────────────────┴─────────────────┐
                    │           (PARALLEL)              │
                    ▼                                   ▼
          ┌─────────────────┐                ┌──────────────────┐
          │  planner_node   │                │ rails_input_node │
          │                 │                │                  │
          │ LLM decides:    │                │ Safety check on  │
          │ cart? search?   │                │ user input       │
          │ or chat?        │                │                  │
          └────────┬────────┘                └────────┬─────────┘
                   │                                  │
        ┌──────────┼──────────┐                       │
        ▼          ▼          ▼                       │
  ┌──────────┐ ┌──────────┐ ┌──────────────┐         │
  │cart_node │ │retriever │ │passthrough   │         │
  │          │ │  _node   │ │   _node      │         │
  │Add/remove│ │          │ │              │         │
  │from cart │ │Search    │ │(general chat)│         │
  └────┬─────┘ └────┬─────┘ └──────┬───────┘         │
       │            │              │                  │
       └────────────┴──────────────┘                  │
                    │                                 │
                    └────────────┬────────────────────┘
                                 │
                                 ▼
                        ┌────────────────┐
                        │ check_rail_node│
                        │                │
                        │ Join point for │
                        │ parallel paths │
                        └───────┬────────┘
                                │
                    ┌───────────┴───────────┐
                    │  decide_if_input_safe │
                    ▼                       ▼
            ┌─────────────┐         ┌──────────────┐
            │ chatter_node│         │ unsafe_output│
            │             │         │              │
            │ LLM generates         │ Returns      │
            │ response    │         │ rejection    │
            └──────┬──────┘         └──────┬───────┘
                   │                       │
                   ▼                       │
          ┌─────────────────┐              │
          │rails_output_node│              │
          │                 │              │
          │ Safety check on │              │
          │ LLM response    │              │
          └───────┬─────────┘              │
                  │                        │
       ┌──────────┴──────────┐             │
       ▼                     ▼             │
┌──────────────┐     ┌──────────────┐      │
│summarize_node│     │ unsafe_output│      │
│              │     │              │      │
│ Save to      │     │ Rejection    │      │
│ memory       │     │ message      │      │
└──────┬───────┘     └──────┬───────┘      │
       │                    │              │
       └────────────────────┴──────────────┘
                            │
                            ▼
                           END
```

### 3. Agents

#### Planner Agent (`planner.py`)
Routes queries to the appropriate specialist:

| Query Type | Routes To |
|------------|-----------|
| "add to cart", "remove item" | `cart_node` |
| "show me dresses", "find bags" | `retriever_node` |
| "hello", "tell me about this" | `chatter_node` |

#### Cart Agent (`cart.py`)
Handles shopping cart operations:
- Add items by name or index
- Remove items
- Clear cart
- Query cart contents

#### Retriever Agent (`retriever.py`)
Searches product catalog:
- Calls catalog-retriever service
- Passes text queries for semantic search
- Passes images for visual similarity search

#### Chatter Agent (`chatter.py`)
Generates natural language responses:
- Uses retrieved products as context
- Maintains conversation flow
- Streams response tokens

#### Summarizer Agent (`summarizer.py`)
Updates conversation memory:
- Saves context to memory-retriever service
- Enables multi-turn conversations

## External Service Dependencies

```
chain-server
     │
     ├──▶ catalog-retriever:8010   (product search)
     │         │
     │         └──▶ Milvus (vector DB)
     │         └──▶ NVIDIA NIM (embeddings)
     │
     ├──▶ memory-retriever:8011    (session state)
     │
     ├──▶ rails:8012               (guardrails)
     │         │
     │         └──▶ NVIDIA NIM (NemoGuard)
     │
     └──▶ NVIDIA API               (LLM inference)
               integrate.api.nvidia.com
               └──▶ meta/llama-3.1-70b-instruct
```

## Request Flow Example

**User**: "Show me summer dresses"

1. **main.py**: Receives POST `/query/stream`
2. **graph.py**: Creates `State(query="Show me summer dresses", ...)`
3. **memory_node**: Fetches user's conversation history and cart
4. **planner_node**: LLM decides → `"retriever"`
5. **rails_input_node**: (parallel) Checks input safety → `is_safe=True`
6. **retriever_node**: Calls catalog-retriever → returns 4 products
7. **check_rail_node**: Joins parallel paths
8. **chatter_node**: LLM generates response with product context
9. **rails_output_node**: Checks response safety
10. **summarize_node**: Saves conversation to memory
11. **main.py**: Streams response back to client

## Configuration

Configuration is loaded from `shared/configs/chain_server/config.yaml`:

```yaml
llm_port: "https://integrate.api.nvidia.com/v1"
llm_name: "meta/llama-3.1-70b-instruct"
retriever_port: "http://catalog-retriever:8010"
memory_port: "http://memory-retriever:8011"
rails_port: "http://rails:8012"
routing_prompt: |
  You are a retail store assistant that routes customer queries...
chatter_prompt: |
  You are a helpful shopping assistant...
```

## Observability

### LangSmith Integration

LangSmith tracing is available for observing graph execution:

```bash
# Enable tracing
export LANGCHAIN_TRACING_V2=true
export LANGCHAIN_API_KEY=lsv2_pt_xxx
```

Environment variables are passed via `docker-compose.yaml`:

```yaml
environment:
  - LANGCHAIN_TRACING_V2=${LANGCHAIN_TRACING_V2:-false}
  - LANGCHAIN_API_KEY=${LANGCHAIN_API_KEY:-}
  - LANGCHAIN_PROJECT=${LANGCHAIN_PROJECT:-retail-shopping-assistant}
```

### Logging

All agents log to stdout with timestamps:

```python
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)
```

View logs:
```bash
docker logs chain-server -f
```

## Key Design Decisions

1. **Parallel Safety Checks**: Input safety runs parallel to planning for lower latency
2. **Streaming Responses**: Uses SSE for real-time response generation
3. **Stateless Agents**: All state is in the `State` object, agents are pure functions
4. **Fallback Routing**: Invalid planner outputs default to `chatter`
5. **Microservices**: Each capability (search, memory, safety) is a separate service

## API Endpoint

### POST /query/stream

```bash
curl -X POST http://localhost:8009/query/stream \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Show me summer dresses",
    "user_id": "12345",
    "guardrails": true
  }'
```

Response: Server-Sent Events stream with JSON payloads:
```
data: {"type": "content", "payload": "Here are some", "timestamp": 1234567890}
data: {"type": "content", "payload": " summer dresses", "timestamp": 1234567891}
data: {"type": "products", "payload": [...], "timestamp": 1234567892}
```
