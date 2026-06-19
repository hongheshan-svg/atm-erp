package notify

import (
	"context"
	"encoding/json"
	"time"

	"gorm.io/gorm"
)

// Pusher 实时推送站内信(WebSocket Hub);可选,nil 时仅落库。
// *ws.Hub 的 SendToUser(ctx, uid, []byte) 直接满足本接口(无需适配器)。
type Pusher interface {
	SendToUser(ctx context.Context, userID uint64, msg []byte)
}

type Service struct {
	db     *gorm.DB
	pusher Pusher
}

func NewService(db *gorm.DB) *Service { return &Service{db: db} }

// SetPusher 注入实时推送器(WebSocket),返回自身便于链式调用。
func (s *Service) SetPusher(p Pusher) *Service { s.pusher = p; return s }

// wsEnvelope 与前端约定的 WS 消息信封。
type wsEnvelope struct {
	Type string        `json:"type"`
	Data *Notification `json:"data"`
}

// Notify 落一条站内信。ntype 缺省 INFO。失败返回 error(调用方据非关键性决定是否忽略)。
// 落库成功后若配置了 pusher,实时推送给该用户(best-effort,推送失败不影响落库)。
func (s *Service) Notify(ctx context.Context, userID uint64, ntype, title, message string) (*Notification, error) {
	if ntype == "" {
		ntype = TypeInfo
	}
	n := &Notification{UserID: userID, Type: ntype, Title: title, Message: message}
	if err := s.db.WithContext(ctx).Create(n).Error; err != nil {
		return nil, err
	}
	if s.pusher != nil {
		if msg, err := json.Marshal(wsEnvelope{Type: "notification", Data: n}); err == nil {
			s.pusher.SendToUser(ctx, userID, msg)
		}
	}
	return n, nil
}

// List 返回某用户的通知(onlyUnread 仅未读),按创建时间倒序。
func (s *Service) List(ctx context.Context, userID uint64, onlyUnread bool, offset, limit int) ([]Notification, int64, error) {
	tx := s.db.WithContext(ctx).Model(&Notification{}).Where("user_id = ?", userID)
	if onlyUnread {
		tx = tx.Where("is_read = ?", false)
	}
	var total int64
	if err := tx.Count(&total).Error; err != nil {
		return nil, 0, err
	}
	var items []Notification
	if err := tx.Order("created_at DESC").Order("id DESC").Offset(offset).Limit(limit).Find(&items).Error; err != nil {
		return nil, 0, err
	}
	return items, total, nil
}

// UnreadCount 返回某用户未读数。
func (s *Service) UnreadCount(ctx context.Context, userID uint64) (int64, error) {
	var n int64
	err := s.db.WithContext(ctx).Model(&Notification{}).
		Where("user_id = ? AND is_read = ?", userID, false).Count(&n).Error
	return n, err
}

// MarkRead 标记某用户自己的一条通知为已读(限本人,防越权)。
func (s *Service) MarkRead(ctx context.Context, userID, id uint64) error {
	now := time.Now()
	return s.db.WithContext(ctx).Model(&Notification{}).
		Where("id = ? AND user_id = ? AND is_read = ?", id, userID, false).
		Updates(map[string]any{"is_read": true, "read_at": now}).Error
}

// MarkAllRead 标记某用户全部未读为已读。
func (s *Service) MarkAllRead(ctx context.Context, userID uint64) error {
	now := time.Now()
	return s.db.WithContext(ctx).Model(&Notification{}).
		Where("user_id = ? AND is_read = ?", userID, false).
		Updates(map[string]any{"is_read": true, "read_at": now}).Error
}
