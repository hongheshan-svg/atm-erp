#!/bin/bash
# SSL Certificate Generation Script
# For development: generates self-signed certificate
# For production: use Let's Encrypt with certbot

set -e

SSL_DIR="./nginx/ssl"
DOMAIN="${1:-localhost}"

echo "=== SSL Certificate Generator ==="
echo "Domain: $DOMAIN"

# Create SSL directory
mkdir -p "$SSL_DIR"

if [ "$DOMAIN" = "localhost" ] || [ "$DOMAIN" = "127.0.0.1" ]; then
    echo ""
    echo "Generating self-signed certificate for development..."
    
    # Generate self-signed certificate
    openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
        -keyout "$SSL_DIR/privkey.pem" \
        -out "$SSL_DIR/fullchain.pem" \
        -subj "/C=CN/ST=State/L=City/O=Organization/CN=$DOMAIN" \
        -addext "subjectAltName=DNS:$DOMAIN,DNS:www.$DOMAIN,IP:127.0.0.1"
    
    echo ""
    echo "✓ Self-signed certificate generated!"
    echo "  Certificate: $SSL_DIR/fullchain.pem"
    echo "  Private Key: $SSL_DIR/privkey.pem"
    echo ""
    echo "⚠ Note: Self-signed certificates will show browser warnings."
    echo "  For production, use Let's Encrypt (see below)."
    
else
    echo ""
    echo "For production domain: $DOMAIN"
    echo ""
    echo "Option 1: Use Let's Encrypt (recommended)"
    echo "==========================================="
    echo ""
    echo "1. Install certbot:"
    echo "   sudo apt install certbot"
    echo ""
    echo "2. Generate certificate:"
    echo "   sudo certbot certonly --standalone -d $DOMAIN -d www.$DOMAIN"
    echo ""
    echo "3. Copy certificates:"
    echo "   sudo cp /etc/letsencrypt/live/$DOMAIN/fullchain.pem $SSL_DIR/"
    echo "   sudo cp /etc/letsencrypt/live/$DOMAIN/privkey.pem $SSL_DIR/"
    echo ""
    echo "4. Set up auto-renewal:"
    echo "   sudo certbot renew --dry-run"
    echo ""
    echo "Option 2: Use certbot with nginx plugin"
    echo "========================================"
    echo ""
    echo "sudo apt install python3-certbot-nginx"
    echo "sudo certbot --nginx -d $DOMAIN -d www.$DOMAIN"
    echo ""
    echo "This will automatically configure nginx for SSL."
    echo ""
fi

# Generate DH parameters for extra security
if [ ! -f "$SSL_DIR/dhparam.pem" ]; then
    echo ""
    echo "Generating DH parameters (this may take a while)..."
    openssl dhparam -out "$SSL_DIR/dhparam.pem" 2048
    echo "✓ DH parameters generated!"
fi

echo ""
echo "=== SSL Setup Complete ==="
