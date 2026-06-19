// Package task 用 hibiken/asynq 提供异步任务(替代 Celery),复用现有 Redis。
package task

import (
	"context"
	"log/slog"

	"github.com/hibiken/asynq"
	"github.com/redis/go-redis/v9"
)

// 任务类型常量(命名沿用 module.action)。
const TypePing = "system:ping"

// RedisOpt 从 REDIS_URL 解析出 asynq 的连接配置。
func RedisOpt(url string) (asynq.RedisClientOpt, error) {
	o, err := redis.ParseURL(url)
	if err != nil {
		return asynq.RedisClientOpt{}, err
	}
	return asynq.RedisClientOpt{Addr: o.Addr, Password: o.Password, DB: o.DB}, nil
}

// NewClient 创建任务投递客户端。
func NewClient(opt asynq.RedisClientOpt) *asynq.Client { return asynq.NewClient(opt) }

// NewPing 构造一个示例任务(后续各模块在此注册自己的任务)。
func NewPing(msg string) *asynq.Task { return asynq.NewTask(TypePing, []byte(msg)) }

// Mux 注册全部任务处理器。
func Mux() *asynq.ServeMux {
	mux := asynq.NewServeMux()
	mux.HandleFunc(TypePing, handlePing)
	// TODO(port): 各模块(库存预警/考勤同步/webhook 投递/夜间报表预热…)在此注册 handler,
	// 定时项用 asynq.Scheduler 对齐 Celery beat_schedule。
	return mux
}

func handlePing(_ context.Context, t *asynq.Task) error {
	slog.Info("asynq ping", "payload", string(t.Payload()))
	return nil
}

// Run 启动 worker(阻塞)。
func Run(opt asynq.RedisClientOpt) error {
	srv := asynq.NewServer(opt, asynq.Config{Concurrency: 4})
	return srv.Run(Mux())
}

// RunWithJobs 启动 worker(handlers)+ 定时调度(cron)。
// jobs: 任务类型→处理函数;schedule: 任务类型→cron 表达式(支持 asynq 的 @every 等)。
func RunWithJobs(opt asynq.RedisClientOpt, jobs map[string]func(context.Context) error, schedule map[string]string) error {
	mux := Mux()
	for typ, fn := range jobs {
		fn := fn
		mux.HandleFunc(typ, func(ctx context.Context, _ *asynq.Task) error { return fn(ctx) })
	}
	if len(schedule) > 0 {
		sched := asynq.NewScheduler(opt, nil)
		for typ, spec := range schedule {
			if _, err := sched.Register(spec, asynq.NewTask(typ, nil)); err != nil {
				return err
			}
		}
		go func() { _ = sched.Run() }()
	}
	srv := asynq.NewServer(opt, asynq.Config{Concurrency: 4})
	return srv.Run(mux)
}
