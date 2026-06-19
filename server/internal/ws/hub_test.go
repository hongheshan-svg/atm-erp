package ws

import (
	"net/http"
	"testing"
)

// bearerSubprotocol 是 WS 鉴权的安全关键路径:仅当客户端按 ["access_token", <jwt>]
// 提供子协议时取出 token;缺哨兵/缺 token 一律拒绝(返回 false → 握手 401)。
func TestBearerSubprotocol(t *testing.T) {
	mk := func(values ...string) *http.Request {
		r, _ := http.NewRequest(http.MethodGet, "/ws/notifications", nil)
		for _, v := range values {
			r.Header.Add("Sec-WebSocket-Protocol", v)
		}
		return r
	}

	cases := []struct {
		name      string
		req       *http.Request
		wantToken string
		wantOK    bool
	}{
		{"标准两段", mk("access_token, eyJhbGciOi.J.K"), "eyJhbGciOi.J.K", true},
		{"含多余空白", mk("  access_token ,  abc.def.ghi  "), "abc.def.ghi", true},
		{"无哨兵", mk("chat, abc.def"), "", false},
		{"仅哨兵无 token", mk("access_token"), "", false},
		{"哨兵后为空", mk("access_token, "), "", false},
		{"无该头", mk(), "", false},
	}
	for _, c := range cases {
		t.Run(c.name, func(t *testing.T) {
			got, ok := bearerSubprotocol(c.req)
			if ok != c.wantOK || got != c.wantToken {
				t.Errorf("bearerSubprotocol = (%q, %v),期望 (%q, %v)", got, ok, c.wantToken, c.wantOK)
			}
		})
	}
}
