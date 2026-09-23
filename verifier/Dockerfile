FROM rust:1.90-bookworm AS build
WORKDIR /app
COPY Cargo.* ./
COPY src ./src
RUN cargo test --locked && cargo build --release --locked
FROM debian:bookworm-slim
COPY --from=build /app/target/release/keytrace-verifier /usr/local/bin/verifier
USER 65534:65534
CMD ["verifier"]
