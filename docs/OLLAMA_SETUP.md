# Ollama Configuration Guide

## Overview

The Horus ATC system can work with **three different Ollama deployment scenarios**:

1. **Local Ollama** - Running on your machine
2. **Shared Ollama** - Running in Docker or on another port
3. **Remote Ollama** - Running on a different server

---

## Scenario 1: Local Ollama (Default)

### Setup
```bash
# Install Ollama
curl -fsSL https://ollama.ai/install.sh | sh

# Start Ollama server
ollama serve

# Pull the model
ollama pull llama3.2:3b
```

### Configuration
```bash
# backend/.env
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_LLM_MODEL=llama3.2:3b
```

### Verify
```bash
# Check service
curl http://localhost:11434/api/tags

# List models
ollama list
```

---

## Scenario 2: Shared Ollama (Docker/Different Port)

### If Using Docker
```bash
# Run Ollama in Docker
docker run -d -v ollama:/root/.ollama -p 11434:11434 --name ollama ollama/ollama

# Pull model into container
docker exec -it ollama ollama pull llama3.2:3b

# Check it's running
docker ps | grep ollama
curl http://localhost:11434/api/tags
```

### If Running on Different Port
```bash
# Check what port Ollama is on
netstat -tlnp | grep ollama
# or
lsof -i -P | grep ollama
```

### Configuration
```bash
# backend/.env
# If on same host, different port
OLLAMA_BASE_URL=http://localhost:YOUR_PORT

# Example:
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_LLM_MODEL=llama3.2:3b
```

### Verify
```bash
# Check via API (works without ollama command installed)
curl http://localhost:11434/api/tags

# Check specific model
curl http://localhost:11434/api/tags | grep "llama3.2:3b"

# Or with jq
curl http://localhost:11434/api/tags | jq '.models[].name'
```

---

## Scenario 3: Remote Ollama (Network Server)

### Setup
Your Ollama is running on a different machine (e.g., GPU server, cloud instance).

### Configuration
```bash
# backend/.env
OLLAMA_BASE_URL=http://192.168.1.100:11434
# or
OLLAMA_BASE_URL=http://ollama.yourcompany.com:11434

OLLAMA_LLM_MODEL=llama3.2:3b
```

### Network Requirements
- Port 11434 must be accessible from your backend
- Firewall rules allow connection
- No SSL? Use `http://` (or configure HTTPS)

### Verify
```bash
# Test connection from backend machine
curl http://192.168.1.100:11434/api/tags

# Check latency
time curl http://192.168.1.100:11434/api/tags

# Test model availability
curl http://192.168.1.100:11434/api/tags | grep "llama3.2:3b"
```

---

## Checking Ollama Without CLI Command

If you **don't have the `ollama` command** installed (e.g., using Docker or remote), you can still check everything via the API:

### Check Service Status
```bash
curl http://localhost:11434/api/tags
```

### List Available Models
```bash
# Raw JSON
curl http://localhost:11434/api/tags

# With jq (pretty print)
curl http://localhost:11434/api/tags | jq '.'

# Just model names
curl http://localhost:11434/api/tags | jq '.models[].name'
```

### Check Specific Model
```bash
# Check if llama3.2:3b exists
curl http://localhost:11434/api/tags | grep "llama3.2:3b"

# With jq
curl http://localhost:11434/api/tags | jq '.models[] | select(.name=="llama3.2:3b")'
```

### Pull Model via API
```bash
# If ollama command not available, pull via API
curl -X POST http://localhost:11434/api/pull -d '{
  "name": "llama3.2:3b"
}'
```

---

## Setup Script Detection

The `setup.sh` script now detects Ollama properly:

### What It Checks
1. **Service availability**: `curl http://localhost:11434/api/tags`
2. **Model existence**: Via API or `ollama list` if available
3. **Fallback**: Works even without `ollama` command

### Example Output
```bash
# If service is accessible
✓ Ollama service is accessible (http://localhost:11434)
✓ llama3.2:3b model found via API

# If only command exists but service not running
! Ollama command found but service not running
  Please start Ollama: ollama serve

# If using remote
✓ Ollama service is accessible (http://localhost:11434)
! llama3.2:3b model not detected
  If using shared/remote Ollama, ensure the model is available
```

---

## Common Configurations

### Development (Local)
```bash
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_LLM_MODEL=llama3.2:3b
```

### Docker Compose
```yaml
# docker-compose.yml
services:
  ollama:
    image: ollama/ollama
    ports:
      - "11434:11434"
    volumes:
      - ollama:/root/.ollama

  backend:
    environment:
      - OLLAMA_BASE_URL=http://ollama:11434
      - OLLAMA_LLM_MODEL=llama3.2:3b
```

### Kubernetes
```yaml
# backend deployment env
- name: OLLAMA_BASE_URL
  value: "http://ollama-service.default.svc.cluster.local:11434"
- name: OLLAMA_LLM_MODEL
  value: "llama3.2:3b"
```

### Cloud/Remote GPU Server
```bash
OLLAMA_BASE_URL=http://gpu-server.internal:11434
OLLAMA_LLM_MODEL=llama3.2:3b
```

---

## Troubleshooting

### "Connection refused"
```bash
# Check if service is running
curl http://localhost:11434/api/tags

# Check what's listening on port
sudo netstat -tlnp | grep 11434

# Start Ollama
ollama serve
# or
docker start ollama
```

### "Model not found"
```bash
# Check available models via API
curl http://localhost:11434/api/tags | jq '.models[].name'

# Pull model
ollama pull llama3.2:3b
# or via API
curl -X POST http://localhost:11434/api/pull -d '{"name":"llama3.2:3b"}'
```

### "Cannot resolve hostname"
```bash
# Test DNS resolution
ping ollama-server

# Use IP instead
OLLAMA_BASE_URL=http://192.168.1.100:11434
```

### Firewall Issues
```bash
# Check if port is open (from backend machine)
telnet ollama-server 11434
# or
nc -zv ollama-server 11434

# Allow port in firewall (on Ollama server)
sudo ufw allow 11434/tcp
```

---

## Performance Notes

### Local Ollama
- ✅ Lowest latency
- ✅ No network overhead
- ⚠️ Requires local GPU/CPU resources

### Shared Ollama (Docker)
- ✅ Isolated environment
- ✅ Easy deployment
- ⚠️ Slight Docker overhead

### Remote Ollama
- ✅ Centralized GPU resources
- ✅ Multiple clients can share
- ⚠️ Network latency (50-200ms typically)
- ⚠️ Requires stable network

---

## Summary

✅ **Check service**: `curl http://localhost:11434/api/tags`  
✅ **No CLI needed**: Everything works via HTTP API  
✅ **Flexible deployment**: Local, Docker, or remote  
✅ **Setup script updated**: Detects all scenarios  

The system will work with **any accessible Ollama instance** - just update `OLLAMA_BASE_URL` in `backend/.env`! 🚀
