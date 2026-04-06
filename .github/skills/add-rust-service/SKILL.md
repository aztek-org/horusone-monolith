---
name: Add Rust Service
description: >
  Step-by-step guide to scaffold a new Rust microservice for the Horus
  real-time layer, including Cargo project, Axum server, Dockerfile, and tests.
---

# Add a New Rust Realtime Service

Use this skill when creating a new Rust microservice in the `realtime/` directory.

## Steps

### 1. Scaffold the Cargo Project

```bash
cd realtime/
cargo init <service-name>
cd <service-name>
```

### 2. Configure `Cargo.toml`

```toml
[package]
name = "<service-name>"
version = "0.1.0"
edition = "2021"
rust-version = "1.75"

[dependencies]
axum = { version = "0.7", features = ["ws"] }
tokio = { version = "1", features = ["full"] }
serde = { version = "1", features = ["derive"] }
serde_json = "1"
tracing = "0.1"
tracing-subscriber = { version = "0.3", features = ["env-filter", "json"] }
tower-http = { version = "0.5", features = ["cors", "trace"] }
thiserror = "1"
anyhow = "1"

[dev-dependencies]
tokio-test = "0.4"
```

### 3. Create `src/main.rs` Entry Point

```rust
use axum::{routing::get, Router, Json};
use std::net::SocketAddr;
use tracing_subscriber::EnvFilter;

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    tracing_subscriber::fmt()
        .with_env_filter(EnvFilter::from_default_env())
        .json()
        .init();

    let app = Router::new()
        .route("/health", get(health));

    let addr = SocketAddr::from(([0, 0, 0, 0], 8080));
    tracing::info!("listening on {}", addr);
    let listener = tokio::net::TcpListener::bind(addr).await?;
    axum::serve(listener, app).await?;
    Ok(())
}

async fn health() -> Json<serde_json::Value> {
    Json(serde_json::json!({"status": "ok"}))
}
```

### 4. Create Dockerfile

```dockerfile
FROM rust:1.75-slim AS builder
WORKDIR /app
COPY Cargo.toml Cargo.lock ./
RUN mkdir src && echo "fn main() {}" > src/main.rs && cargo build --release && rm -rf src
COPY src/ src/
RUN cargo build --release

FROM debian:bookworm-slim
RUN apt-get update && apt-get install -y ca-certificates && rm -rf /var/lib/apt/lists/*
COPY --from=builder /app/target/release/<service-name> /usr/local/bin/
USER 1000:1000
EXPOSE 8080
HEALTHCHECK CMD curl -f http://localhost:8080/health || exit 1
CMD ["<service-name>"]
```

### 5. Write Basic Tests

```rust
#[cfg(test)]
mod tests {
    use super::*;
    use axum::http::StatusCode;
    use axum::body::Body;
    use tower::ServiceExt;

    #[tokio::test]
    async fn test_health_returns_ok() {
        let app = Router::new().route("/health", get(health));
        let response = app
            .oneshot(
                axum::http::Request::builder()
                    .uri("/health")
                    .body(Body::empty())
                    .unwrap(),
            )
            .await
            .unwrap();
        assert_eq!(response.status(), StatusCode::OK);
    }
}
```

### 6. Add to Docker Compose

Add the service to `backend/docker-compose.yml` with Traefik labels and health check.

### 7. Verify

```bash
cargo clippy -- -W clippy::pedantic
cargo fmt --check
cargo test
cargo build --release
```
