#!/bin/sh
# No shell tracing, token output or nginx -T. ECS supplies one public-only token.
set -eu
case "${BIOGRAPH_SERVER_TOKEN-}" in
    ''|*[!A-Za-z0-9_-]*) echo 'Public gateway token is missing or invalid.' >&2; exit 1 ;;
esac
if [ "${#BIOGRAPH_SERVER_TOKEN}" -lt 24 ] || [ "${#BIOGRAPH_SERVER_TOKEN}" -gt 256 ]; then
    echo 'Public gateway token is missing or invalid.' >&2
    exit 1
fi
# Do not support config dumps, alternate configs or debug-log arguments.
if [ "$#" -eq 1 ] && [ "$1" = '-t' ]; then
    :
elif [ "$#" -eq 2 ] && [ "$1" = '-g' ] && [ "$2" = 'daemon off;' ]; then
    :
else
    echo 'Use only the checked NGINX startup or syntax-check command.' >&2
    exit 1
fi
umask 077
config_dir=$(mktemp -d /tmp/biograph-public-nginx.XXXXXX)
config=$config_dir/nginx.conf
# Refuse an existing file/symlink. The token never enters an image layer.
set -C
envsubst '${BIOGRAPH_SERVER_TOKEN}' < /etc/nginx/nginx.public.conf.template > "$config"
set +C
chmod 600 "$config"
unset BIOGRAPH_SERVER_TOKEN
exec nginx -c "$config" "$@"
