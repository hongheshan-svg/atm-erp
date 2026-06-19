// Package config 用 viper 加载配置:env > 默认值,键名对齐现有 .env/.env.docker。
package config

import (
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

	v.SetDefault("APP_ENV", "production")
	v.SetDefault("HTTP_ADDR", ":8000")
	v.SetDefault("DB_HOST", "postgres")
	v.SetDefault("DB_PORT", "5432")
	v.SetDefault("DB_NAME", "erp_db")
	v.SetDefault("DB_USER", "erp_user")
	v.SetDefault("DB_PASSWORD", "erp_password")
	v.SetDefault("REDIS_URL", "redis://redis:6379/1")
	v.SetDefault("SECRET_KEY", "django-insecure-change-this-in-production-123456")
	v.SetDefault("JWT_ACCESS_MINUTES", 120)
	v.SetDefault("JWT_REFRESH_DAYS", 7)
	v.SetDefault("CORS_ALLOWED_ORIGINS", "http://localhost,http://127.0.0.1")

	return &Config{
		AppEnv:             v.GetString("APP_ENV"),
		HTTPAddr:           v.GetString("HTTP_ADDR"),
		DBHost:             v.GetString("DB_HOST"),
		DBPort:             v.GetString("DB_PORT"),
		DBName:             v.GetString("DB_NAME"),
		DBUser:             v.GetString("DB_USER"),
		DBPassword:         v.GetString("DB_PASSWORD"),
		RedisURL:           v.GetString("REDIS_URL"),
		JWTSecret:          v.GetString("SECRET_KEY"),
		JWTAccessMinutes:   v.GetInt("JWT_ACCESS_MINUTES"),
		JWTRefreshDays:     v.GetInt("JWT_REFRESH_DAYS"),
		CORSAllowedOrigins: splitCSV(v.GetString("CORS_ALLOWED_ORIGINS")),
	}
}

// DSN 显式设置 TimeZone=Asia/Shanghai,对齐 Django USE_TZ + Asia/Shanghai,
// 规避完备性评审指出的共库期 8 小时静默漂移风险(50-gaps-risks 必修项)。
func (c *Config) DSN() string {
	return "host=" + c.DBHost + " port=" + c.DBPort + " user=" + c.DBUser +
		" password=" + c.DBPassword + " dbname=" + c.DBName +
		" sslmode=disable TimeZone=Asia/Shanghai"
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
