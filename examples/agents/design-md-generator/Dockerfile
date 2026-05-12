FROM alpine:3.20

RUN apk add --no-cache \
    chromium \
    xvfb \
    x11vnc \
    supervisor \
    novnc \
    websockify \
    socat \
    font-noto \
    font-noto-cjk \
    font-noto-emoji \
    dbus \
    && mkdir -p /var/log/supervisor

COPY supervisord.conf /etc/supervisord.conf

ENV DISPLAY=:99
ENV SCREEN_WIDTH=1920
ENV SCREEN_HEIGHT=1080

EXPOSE 9222 6080

CMD ["supervisord", "-c", "/etc/supervisord.conf"]
