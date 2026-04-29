---
name: relic-capture
description: "Captures messages and tracks delivery for personality modeling"
metadata: {"hermes":{"emoji":"🧠","events":["message:received","message:sent"]}}
---

# Relic Message Capture & Delivery Hook

Handles both inbound and outbound message events for the Relic personality
modeling system.

## What It Does

### message:received
- Captures inbound Telegram messages the configured subject into `inbox.jsonl`
- Detects replies to pending check-in questions and triggers follow-up agent

### message:sent
- Tracks delivery success/failure for check-in messages
- Logs delivery status for monitoring

## Configuration

Enable with:

```bash
hermes hooks enable relic-capture
```
