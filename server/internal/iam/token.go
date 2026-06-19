package iam

import (
	"errors"
	"time"

	"github.com/golang-jwt/jwt/v5"
)

// TokenManager 签发/校验 JWT,语义对齐 simplejwt(access/refresh、user_id claim、lifetime)。
// Phase 1 在此叠加 Redis jti 白/黑名单与刷新轮换(需先确立现状黑名单基线,见 50-gaps must_fix)。
type TokenManager struct {
	secret     []byte
	accessTTL  time.Duration
	refreshTTL time.Duration
}

func NewTokenManager(secret string, accessMinutes, refreshDays int) *TokenManager {
	return &TokenManager{
		secret:     []byte(secret),
		accessTTL:  time.Duration(accessMinutes) * time.Minute,
		refreshTTL: time.Duration(refreshDays) * 24 * time.Hour,
	}
}

type Claims struct {
	UserID    uint64 `json:"user_id"`
	TokenType string `json:"token_type"`
	jwt.RegisteredClaims
}

func (tm *TokenManager) issue(uid uint64, typ string, ttl time.Duration) (string, error) {
	now := time.Now()
	c := Claims{
		UserID:    uid,
		TokenType: typ,
		RegisteredClaims: jwt.RegisteredClaims{
			IssuedAt:  jwt.NewNumericDate(now),
			ExpiresAt: jwt.NewNumericDate(now.Add(ttl)),
		},
	}
	return jwt.NewWithClaims(jwt.SigningMethodHS256, c).SignedString(tm.secret)
}

func (tm *TokenManager) Access(uid uint64) (string, error) {
	return tm.issue(uid, "access", tm.accessTTL)
}
func (tm *TokenManager) Refresh(uid uint64) (string, error) {
	return tm.issue(uid, "refresh", tm.refreshTTL)
}

func (tm *TokenManager) Parse(token string) (*Claims, error) {
	claims := &Claims{}
	_, err := jwt.ParseWithClaims(token, claims, func(t *jwt.Token) (any, error) {
		if _, ok := t.Method.(*jwt.SigningMethodHMAC); !ok {
			return nil, errors.New("unexpected signing method")
		}
		return tm.secret, nil
	})
	if err != nil {
		return nil, err
	}
	return claims, nil
}
