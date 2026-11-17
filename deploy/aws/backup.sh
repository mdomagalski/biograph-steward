#!/usr/bin/env bash
# Byte-preserving workspace archive using the instance's restricted IAM role.
# The access token and model credentials live outside this data directory.
set -euo pipefail
umask 077
[[ "${EUID}" -eq 0 ]] || { echo 'Run this installed backup with sudo.' >&2; exit 1; }
exec 9>/run/biograph-backup.lock
flock -n 9 || { echo 'A workspace backup is already running.' >&2; exit 1; }
mountpoint -q /srv/biograph-data
readarray -t config < <(python3 - <<'PY'
import json
value=json.load(open('/etc/biograph/deployment.json'))
for key in ('region','bucket','backup_prefix'):
    text=value[key]
    if not isinstance(text,str) or not text or '\n' in text:
        raise SystemExit('Invalid deployment configuration.')
    print(text)
PY
)
[[ "${#config[@]}" -eq 3 ]] || { echo 'Invalid deployment configuration.' >&2; exit 1; }
region="${config[0]}"; bucket="${config[1]}"; prefix="${config[2]}"
# Stage the complete archive locally; reject insufficient space before downtime.
# Apparent bytes account for sparse source files that tar may expand.
python3 - <<'PY'
import shutil
import subprocess
size=int(subprocess.check_output(['du','--summarize','--apparent-size','--block-size=1',
                                  '/srv/biograph-data']).split()[0])
required=size+max(size//20,64*1024*1024)
if shutil.disk_usage('/var/tmp').free < required:
    raise SystemExit('Insufficient /var/tmp space for a conservative full backup. '
                     'Use a larger staging filesystem before retrying.')
PY
temporary=$(mktemp -d /var/tmp/biograph-backup.XXXXXX)
resume=false
cleanup() {
  local result=$?
  if $resume; then systemctl start biograph.service || result=1; fi
  rm -rf -- "$temporary"
  exit "$result"
}
trap cleanup EXIT
if systemctl is-active --quiet biograph.service; then
  resume=true
  systemctl stop biograph.service
fi
# Do not run separate write-producing CLI jobs while this archive is captured.
tar -C /srv/biograph-data -czf "$temporary/workspace.tar.gz" .
if $resume; then systemctl start biograph.service; resume=false; fi
(cd "$temporary" && sha256sum workspace.tar.gz > workspace.sha256)
stamp=$(date -u +%Y%m%dT%H%M%SZ)
suffix=$(python3 -c 'import secrets; print(secrets.token_hex(4))')
destination="s3://$bucket/${prefix#/}$stamp-$suffix/"
aws s3 cp "$temporary/workspace.tar.gz" "${destination}workspace.tar.gz" \
  --region "$region" --sse AES256 --checksum-algorithm SHA256 --only-show-errors
aws s3 cp "$temporary/workspace.sha256" "${destination}workspace.sha256" \
  --region "$region" --sse AES256 --checksum-algorithm SHA256 --only-show-errors
printf 'Workspace backup saved under %s\n' "$destination"
