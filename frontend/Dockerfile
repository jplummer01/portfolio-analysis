# Stage 1: Build
FROM rust:1.87-slim AS builder

WORKDIR /app
RUN apt-get update && apt-get install -y pkg-config libssl-dev && rm -rf /var/lib/apt/lists/*

COPY Cargo.toml Cargo.lock ./
COPY src/ src/

RUN cargo build --release

# Stage 2: Runtime
FROM debian:bookworm-slim

RUN apt-get update && apt-get install -y ca-certificates libssl3 && rm -rf /var/lib/apt/lists/*

COPY --from=builder /app/target/release/portfolio-frontend /usr/local/bin/portfolio-frontend

ENV FRONTEND_HOST=0.0.0.0
ENV FRONTEND_PORT=3000
EXPOSE 3000

CMD ["portfolio-frontend"]
