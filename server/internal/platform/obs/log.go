// Package obs 提供结构化日志(slog)。后续阶段在此接 OpenTelemetry + Prometheus + Sentry。
package obs

import (
	"log/slog"
	"os"
)

func Setup(env string) *slog.Logger {
	var h slog.Handler
	if env == "development" {
		h = slog.NewTextHandler(os.Stdout, &slog.HandlerOptions{Level: slog.LevelDebug})
	} else {
		h = slog.NewJSONHandler(os.Stdout, &slog.HandlerOptions{Level: slog.LevelInfo})
	}
	l := slog.New(h)
	slog.SetDefault(l)
	return l
}
