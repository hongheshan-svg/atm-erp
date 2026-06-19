// Package config 用 viper 加载配置:env > 默认值,键名对齐现有 .env/.env.docker。
// 安全:SECRET_KEY / DB_PASSWORD 不设默认值;非 development 环境由 Validate() fail-closed。
package config

import (
	"errors"
	"strings"

	"github.com/spf13/viper"
)

type Config struct {
	AppEnv   string
	HTTPAddr string

	DBHost     string
	DBPort     string
	DBName     string
	DBUser     string
	DBPassword string
	DBSSLMode  string

	RedisURL string

	JWTSecret        string
	JWTAccessMinutes int
	JWTRefreshDays   int

	CORSAllowedOrigins []string
}

func Load() *Config {
	v := viper.New()
	v.SetEnvKeyReplacer(strings.NewReplacer("-", "_"))
	v.AutomaticEnv()

	// 非敏感默认值
	v.SetDefault("APP_ENV", "production")
	v.SetDefault("HTTP_ADDR", ":8000")
	v.SetDefault("DB_HOST", "postgres")
	v.SetDefault("DB_PORT", "5432")
	v.SetDefault("DB_NAME", "erp_db")
	v.SetDefault("DB_USER", "erp_user")
	v.SetDefault("REDIS_URL", "redis://redis:6379/1")
	v.SetDefault("JWT_ACCESS_MINUTES", 120)
	v.SetDefault("JWT_REFRESH_DAYS", 7)
	v.SetDefault("CORS_ALLOWED_ORIGINS", "http://localhost,http://127.0.0.1")
	// 注意:SECRET_KEY / DB_PASSWORD 故意不设默认值(安全);仅 development 兜底见下。

	appEnv := v.GetString("APP_ENV")
	secret := v.GetString("SECRET_KEY")
	dbPass := v.GetString("DB_PASSWORD")
	sslMode := v.GetString("DB_SSLMODE")

	if appEnv == "development" {
		// 仅本地开发兜底;Validate() 保证这些值绝不进入非 dev 环境。
		if secret == "" {
			secret = "dev-only-insecure-secret-do-not-use-in-prod"
		}
		if dbPass == "" {
			dbPass = "erp_password"
		}
		if sslMode == "" {
			sslMode = "disable"
		}
	} else if sslMode == "" {
		sslMode = "require"
	}

	return &Config{
		AppEnv:             appEnv,
		HTTPAddr:           v.GetString("HTTP_ADDR"),
		DBHost:             v.GetString("DB_HOST"),
		DBPort:             v.GetString("DB_PORT"),
		DBName:             v.GetString("DB_NAME"),
		DBUser:             v.GetString("DB_USER"),
		DBPassword:         dbPass,
		DBSSLMode:          sslMode,
		RedisURL:           v.GetString("REDIS_URL"),
		JWTSecret:          secret,
		JWTAccessMinutes:   v.GetInt("JWT_ACCESS_MINUTES"),
		JWTRefreshDays:     v.GetInt("JWT_REFRESH_DAYS"),
		CORSAllowedOrigins: splitCSV(v.GetString("CORS_ALLOWED_ORIGINS")),
	}
}

// Validate 在非 development 环境 fail-closed:拒绝默认/弱密钥与明文 DB 连接。
func (c *Config) Validate() error {
	if c.AppEnv == "development" {
		return nil
	}
	if c.JWTSecret == "" || len(c.JWTSecret) < 32 || strings.Contains(c.JWTSecret, "insecure") {
		return errors.New("生产环境必须设置强 SECRET_KEY(≥32 字节,且非默认/含 insecure 的占位值)")
	}
	if c.DBPassword == "" || c.DBPassword == "erp_password" {
		return errors.New("生产环境必须设置非默认 DB_PASSWORD")
	}
	if c.DBSSLMode == "disable" {
		return errors.New("生产环境禁止 DB_SSLMODE=disable,请设为 require/verify-full")
	}
	return nil
}

// DSN 显式设置 TimeZone=Asia/Shanghai,对齐 Django USE_TZ + Asia/Shanghai(防共库期 8 小时漂移)。
func (c *Config) DSN() string {
	return "host=" + c.DBHost + " port=" + c.DBPort + " user=" + c.DBUser +
		" password=" + c.DBPassword + " dbname=" + c.DBName +
		" sslmode=" + c.DBSSLMode + " TimeZone=Asia/Shanghai"
}

func splitCSV(s string) []string {
	if s == "" {
		return nil
	}
	parts := strings.Split(s, ",")
	out := make([]string, 0, len(parts))
	for _, p := range parts {
		if t := strings.TrimSpace(p); t != "" {
			out = append(out, t)
		}
	}
	return out
}
