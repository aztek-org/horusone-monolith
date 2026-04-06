---
name: Add Go Service
description: >
  Step-by-step guide to scaffold a new Go microservice for the Horus
  real-time layer, including Go module, HTTP server, Dockerfile, and tests.
---

# Add a New Go Realtime Service

Use this skill when creating a new Go microservice in the `realtime/` directory.

## Steps

### 1. Scaffold the Go Module

```bash
mkdir -p realtime/<service-name>/cmd/server
cd realtime/<service-name>
go mod init github.com/horusone/horus-mvp/realtime/<service-name>
```

### 2. Create Directory Structure

```bash
mkdir -p internal/{config,handler,service,repository,model}
mkdir -p pkg
```

### 3. Create `cmd/server/main.go`

```go
package main

import (
    "context"
    "encoding/json"
    "log/slog"
    "net/http"
    "os"
    "os/signal"
    "syscall"
    "time"
)

func main() {
    logger := slog.New(slog.NewJSONHandler(os.Stdout, nil))
    slog.SetDefault(logger)

    mux := http.NewServeMux()
    mux.HandleFunc("GET /health", healthHandler)

    server := &http.Server{
        Addr:         ":8081",
        Handler:      mux,
        ReadTimeout:  10 * time.Second,
        WriteTimeout: 10 * time.Second,
    }

    go func() {
        slog.Info("starting server", "addr", server.Addr)
        if err := server.ListenAndServe(); err != http.ErrServerClosed {
            slog.Error("server error", "error", err)
            os.Exit(1)
        }
    }()

    quit := make(chan os.Signal, 1)
    signal.Notify(quit, syscall.SIGINT, syscall.SIGTERM)
    <-quit

    ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
    defer cancel()
    server.Shutdown(ctx)
    slog.Info("server stopped")
}

func healthHandler(w http.ResponseWriter, r *http.Request) {
    w.Header().Set("Content-Type", "application/json")
    json.NewEncoder(w).Encode(map[string]string{"status": "ok"})
}
```

### 4. Create Dockerfile

```dockerfile
FROM golang:1.22-alpine AS builder
WORKDIR /app
COPY go.mod go.sum ./
RUN go mod download
COPY . .
RUN CGO_ENABLED=0 GOOS=linux go build -ldflags="-s -w" -o /server ./cmd/server

FROM alpine:3.19
RUN apk --no-cache add ca-certificates
COPY --from=builder /server /usr/local/bin/server
USER 1000:1000
EXPOSE 8081
HEALTHCHECK CMD wget -qO- http://localhost:8081/health || exit 1
CMD ["server"]
```

### 5. Create Makefile

```makefile
.PHONY: build test lint run

build:
	go build -o bin/server ./cmd/server

test:
	go test -v -race ./...

lint:
	golangci-lint run ./...

run:
	go run ./cmd/server
```

### 6. Write Basic Tests

```go
// cmd/server/main_test.go
package main

import (
    "net/http"
    "net/http/httptest"
    "testing"

    "github.com/stretchr/testify/assert"
)

func TestHealthHandler(t *testing.T) {
    req := httptest.NewRequest(http.MethodGet, "/health", nil)
    w := httptest.NewRecorder()
    healthHandler(w, req)

    assert.Equal(t, http.StatusOK, w.Code)
    assert.Contains(t, w.Body.String(), `"status":"ok"`)
}
```

### 7. Add to Docker Compose

Add the service to `backend/docker-compose.yml` with Traefik labels and health check.

### 8. Verify

```bash
go vet ./...
golangci-lint run ./...
go test -v -race ./...
go build ./cmd/server
```
