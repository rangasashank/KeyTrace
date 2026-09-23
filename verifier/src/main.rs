use axum::{extract::State, http::StatusCode, routing::post, Json, Router};
use jsonwebtoken::{decode, Algorithm, DecodingKey, Validation};
use serde::{Deserialize, Serialize};

#[derive(Debug, Serialize, Deserialize)]
struct Claims {
    sub: String,
    exp: u64,
    iss: String,
    aud: String,
    actions: Vec<String>,
}
#[derive(Deserialize)]
struct VerifyRequest {
    token: String,
}

fn verify(token: &str, secret: &str) -> Result<Claims, jsonwebtoken::errors::Error> {
    let mut validation = Validation::new(Algorithm::HS256);
    validation.set_issuer(&["keytrace"]);
    validation.set_audience(&["keytrace-proxy"]);
    validation.leeway = 0;
    let claims = decode::<Claims>(
        token,
        &DecodingKey::from_secret(secret.as_bytes()),
        &validation,
    )?
    .claims;
    if claims.sub.trim().is_empty() {
        return Err(jsonwebtoken::errors::ErrorKind::InvalidSubject.into());
    }
    Ok(claims)
}
async fn handler(
    State(secret): State<String>,
    Json(request): Json<VerifyRequest>,
) -> Result<Json<Claims>, StatusCode> {
    verify(&request.token, &secret)
        .map(Json)
        .map_err(|_| StatusCode::UNAUTHORIZED)
}
#[tokio::main]
async fn main() {
    let secret = std::env::var("TOKEN_SECRET").expect("TOKEN_SECRET is required");
    assert!(
        secret.len() >= 32,
        "TOKEN_SECRET must have at least 32 bytes"
    );
    let app = Router::new()
        .route("/verify", post(handler))
        .with_state(secret);
    let listener = tokio::net::TcpListener::bind("0.0.0.0:8081").await.unwrap();
    axum::serve(listener, app).await.unwrap();
}
#[cfg(test)]
mod tests {
    use super::*;
    use jsonwebtoken::{encode, EncodingKey, Header};
    const SECRET: &str = "test-secret-at-least-thirty-two-bytes";
    fn token(exp: u64, aud: &str, secret: &str) -> String {
        encode(
            &Header::default(),
            &Claims {
                sub: "agent-1".into(),
                exp,
                iss: "keytrace".into(),
                aud: aud.into(),
                actions: vec!["notes.create".into()],
            },
            &EncodingKey::from_secret(secret.as_bytes()),
        )
        .unwrap()
    }
    #[test]
    fn accepts_valid_and_rejects_invalid_credentials() {
        let future = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap()
            .as_secs()
            + 3600;
        assert!(verify(&token(future, "keytrace-proxy", SECRET), SECRET).is_ok());
        assert!(verify(&token(1, "keytrace-proxy", SECRET), SECRET).is_err());
        assert!(verify(&token(future, "other", SECRET), SECRET).is_err());
        assert!(verify(&token(future, "keytrace-proxy", "wrong"), SECRET).is_err());
        assert!(verify("malformed", SECRET).is_err());
    }
}
