package main

import (
	"bytes"
	"context"
	"crypto/rand"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net/http"
	"os"
	"strings"
	"time"

	"github.com/segmentio/kafka-go"
)

type claims struct {
	Sub     string   `json:"sub"`
	Actions []string `json:"actions"`
}
type action struct {
	Action string `json:"action"`
	Text   string `json:"text"`
}
type event struct {
	ID       string `json:"event_id"`
	Time     string `json:"timestamp"`
	Agent    string `json:"agent"`
	Action   string `json:"action"`
	Decision string `json:"decision"`
	Reason   string `json:"reason"`
}
type server struct {
	client                 *http.Client
	verifyURL, upstreamURL string
	publish                func(context.Context, event) error
}

func permitted(c claims, a string) bool {
	if a != "notes.create" && a != "notes.list" {
		return false
	}
	for _, allowed := range c.Actions {
		if a == allowed {
			return true
		}
	}
	return false
}
func (s *server) handle(w http.ResponseWriter, r *http.Request) {
	ctx, cancel := context.WithTimeout(r.Context(), 10*time.Second)
	defer cancel()
	var a action
	decoder := json.NewDecoder(http.MaxBytesReader(w, r.Body, 4096))
	decoder.DisallowUnknownFields()
	if decoder.Decode(&a) != nil || decoder.Decode(&struct{}{}) != io.EOF || a.Action == "" {
		http.Error(w, "invalid request", 400)
		return
	}
	id := make([]byte, 16)
	if _, err := rand.Read(id); err != nil {
		http.Error(w, "internal error", 500)
		return
	}
	e := event{ID: hex.EncodeToString(id), Time: time.Now().UTC().Format(time.RFC3339Nano), Agent: "anonymous", Action: a.Action, Decision: "deny", Reason: "invalid_token"}
	status := http.StatusUnauthorized
	auth := r.Header.Get("Authorization")
	if strings.HasPrefix(auth, "Bearer ") {
		body, _ := json.Marshal(map[string]string{"token": strings.TrimPrefix(auth, "Bearer ")})
		req, _ := http.NewRequestWithContext(ctx, "POST", s.verifyURL, bytes.NewReader(body))
		req.Header.Set("Content-Type", "application/json")
		res, err := s.client.Do(req)
		if err != nil {
			e.Reason = "verifier_unavailable"
			status = 503
		} else {
			var c claims
			if res.StatusCode == 200 && json.NewDecoder(res.Body).Decode(&c) == nil {
				e.Agent = c.Sub
				e.Reason = "policy_denied"
				status = 403
				if permitted(c, a.Action) {
					e.Decision = "allow"
					e.Reason = "policy_allowed"
					status = 200
				}
			} else if res.StatusCode != 401 {
				e.Reason = "verifier_unavailable"
				status = 503
			}
			res.Body.Close()
		}
	}
	// Record the authorization decision before allowing any upstream side effect.
	if err := s.publish(ctx, e); err != nil {
		log.Printf("audit unavailable: %v", err)
		http.Error(w, "audit unavailable; action not executed", 503)
		return
	}
	w.Header().Set("X-KeyTrace-Event", e.ID)
	if status != 200 {
		http.Error(w, e.Reason, status)
		return
	}
	body, _ := json.Marshal(a)
	req, _ := http.NewRequestWithContext(ctx, "POST", s.upstreamURL, bytes.NewReader(body))
	req.Header.Set("Content-Type", "application/json")
	res, err := s.client.Do(req)
	if err != nil {
		http.Error(w, "upstream unavailable", 502)
		return
	}
	defer res.Body.Close()
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(res.StatusCode)
	io.Copy(w, io.LimitReader(res.Body, 1<<20))
}
func main() {
	writer := &kafka.Writer{Addr: kafka.TCP(os.Getenv("KAFKA_BROKER")), Topic: "keytrace.audit", RequiredAcks: kafka.RequireAll, WriteTimeout: 5 * time.Second}
	defer writer.Close()
	s := &server{client: &http.Client{Timeout: 5 * time.Second}, verifyURL: os.Getenv("VERIFIER_URL"), upstreamURL: os.Getenv("UPSTREAM_URL"), publish: func(ctx context.Context, e event) error {
		b, err := json.Marshal(e)
		if err != nil {
			return err
		}
		return writer.WriteMessages(ctx, kafka.Message{Key: []byte(e.ID), Value: b})
	}}
	mux := http.NewServeMux()
	mux.HandleFunc("POST /actions", s.handle)
	mux.HandleFunc("GET /health", func(w http.ResponseWriter, r *http.Request) { fmt.Fprintln(w, "ok") })
	log.Println("KeyTrace listening on :8080")
	log.Fatal((&http.Server{Addr: ":8080", Handler: mux, ReadHeaderTimeout: 5 * time.Second, ReadTimeout: 10 * time.Second, WriteTimeout: 15 * time.Second}).ListenAndServe())
}
