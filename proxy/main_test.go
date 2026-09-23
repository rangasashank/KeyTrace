package main

import (
	"context"
	"errors"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
)

func TestAuthorizationAndAuditFailure(t *testing.T) {
	for _, test := range []struct {
		name, action string
		auditFail    bool
		want         int
		forwarded    bool
	}{
		{"allowed", "notes.create", false, 200, true},
		{"denied", "shell.execute", false, 403, false},
		{"audit failure", "notes.create", true, 503, false},
	} {
		t.Run(test.name, func(t *testing.T) {
			verify := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
				w.Write([]byte(`{"sub":"agent-1","actions":["notes.create"]}`))
			}))
			defer verify.Close()
			called := false
			upstream := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) { called = true; w.Write([]byte(`{"ok":true}`)) }))
			defer upstream.Close()
			recorded := false
			s := server{client: http.DefaultClient, verifyURL: verify.URL, upstreamURL: upstream.URL, publish: func(ctx context.Context, e event) error {
				recorded = true
				if test.auditFail {
					return errors.New("offline")
				}
				return nil
			}}
			req := httptest.NewRequest("POST", "/actions", strings.NewReader(`{"action":"`+test.action+`"}`))
			req.Header.Set("Authorization", "Bearer test")
			res := httptest.NewRecorder()
			s.handle(res, req)
			if res.Code != test.want || called != test.forwarded || !recorded {
				t.Fatalf("status=%d forwarded=%v recorded=%v", res.Code, called, recorded)
			}
		})
	}
}
