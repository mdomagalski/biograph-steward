#!/usr/bin/env bash
# Executed only after CloudFormation downloads and SHA256-verifies this release.
set -euo pipefail
umask 077

: "${BIOGRAPH_AWS_REGION:?}"
: "${BIOGRAPH_ARTIFACT_BUCKET:?}"
: "${BIOGRAPH_AWS_STACK_NAME:?}"
: "${BIOGRAPH_DATA_VOLUME_ID:?}"
: "${BIOGRAPH_RELEASE_SHA256:?}"
: "${BIOGRAPH_PYTHON_IMAGE:?}"

dnf install -y docker e2fsprogs util-linux
systemctl enable --now docker amazon-ssm-agent

# Nitro NVMe enumeration is not stable. Match the selected EBS volume's serial,
# then record its filesystem UUID; never assume /dev/nvme1n1 is the data disk.
expected_serial="${BIOGRAPH_DATA_VOLUME_ID//-/}"
data_device=''
for attempt in $(seq 1 120); do
  while read -r name serial; do
    if [[ "$serial" == "$expected_serial" ]]; then data_device="/dev/$name"; break; fi
  done < <(lsblk -dn -o NAME,SERIAL)
  [[ -n "$data_device" ]] && break
  sleep 5
done
[[ -b "$data_device" ]] || { echo 'Selected data volume did not attach.' >&2; exit 1; }
[[ -z "$(lsblk -nr -o MOUNTPOINT "$data_device" | tr -d '[:space:]')" ]] || {
  echo 'Selected data disk already has a mounted filesystem; refusing to format it.' >&2; exit 1;
}
filesystem=$(blkid -o value -s TYPE "$data_device" || true)
if [[ -z "$filesystem" ]]; then
  # This template provisions a new empty data volume. Refuse partitions or any
  # other existing signature rather than guessing that missing TYPE means empty.
  [[ "$(lsblk -nr -o NAME "$data_device" | wc -l)" -eq 1 ]] || {
    echo 'Selected disk has partitions; refusing to format it.' >&2; exit 1;
  }
  [[ -z "$(wipefs --no-act --noheadings --output TYPE "$data_device")" ]] || {
    echo 'Selected disk has an existing signature; refusing to format it.' >&2; exit 1;
  }
  mkfs.ext4 -L biograph-data "$data_device"
elif [[ "$filesystem" != 'ext4' ]]; then
  echo 'Selected data disk is not the expected ext4 filesystem.' >&2
  exit 1
fi
mkdir -p /srv/biograph-data
filesystem_uuid=$(blkid -o value -s UUID "$data_device")
printf 'UUID=%s /srv/biograph-data ext4 defaults,nofail 0 2\n' "$filesystem_uuid" >> /etc/fstab
mount /srv/biograph-data
mountpoint -q /srv/biograph-data
mkdir -p /srv/biograph-data/runs /srv/biograph-data/cache
chown 10001:10001 /srv/biograph-data /srv/biograph-data/runs /srv/biograph-data/cache

install -d -m 0700 /etc/biograph
python3 - <<'PY'
import json, os, pathlib, secrets
root = pathlib.Path('/etc/biograph')
token = secrets.token_urlsafe(32)
(root / 'access-token').write_text(token + '\n')
(root / 'runtime.env').write_text(
    'BIOGRAPH_HOST=127.0.0.1\nBIOGRAPH_PORT=8766\nBIOGRAPH_DATA_DIR=/data\n'
    + 'BIOGRAPH_ACCESS_TOKEN=' + token + '\n')
(root / 'deployment.json').write_text(json.dumps({
    'region': os.environ['BIOGRAPH_AWS_REGION'],
    'bucket': os.environ['BIOGRAPH_ARTIFACT_BUCKET'],
    'backup_prefix': 'backups/' + os.environ['BIOGRAPH_AWS_STACK_NAME'] + '/',
    'data_volume_id': os.environ['BIOGRAPH_DATA_VOLUME_ID'],
    'release_sha256': os.environ['BIOGRAPH_RELEASE_SHA256'],
}, indent=2) + '\n')
for path in root.iterdir():
    path.chmod(0o600)
PY

image_tag="biograph-steward:${BIOGRAPH_RELEASE_SHA256:0:16}"
docker build --build-arg "PYTHON_IMAGE=$BIOGRAPH_PYTHON_IMAGE" --build-arg INSTALL_AWS=1 \
  --iidfile /etc/biograph/image-id --tag "$image_tag" /opt/biograph/app
cat > /etc/systemd/system/biograph.service <<UNIT
[Unit]
Description=BioGraph Steward evidence workbench
After=docker.service network-online.target
Requires=docker.service
RequiresMountsFor=/srv/biograph-data

[Service]
Type=simple
ExecStartPre=-/usr/bin/docker rm -f biograph-steward
ExecStart=/usr/bin/docker run --rm --name biograph-steward --network host --env-file /etc/biograph/runtime.env --mount type=bind,src=/srv/biograph-data,dst=/data $image_tag
ExecStop=/usr/bin/docker stop --time 20 biograph-steward
Restart=on-failure
RestartSec=5
TimeoutStopSec=30

[Install]
WantedBy=multi-user.target
UNIT
systemctl daemon-reload
systemctl enable --now biograph.service
python3 - <<'PY'
import json, time
from urllib.request import ProxyHandler, build_opener
opener = build_opener(ProxyHandler({}))
for attempt in range(60):
    try:
        with opener.open('http://127.0.0.1:8766/healthz', timeout=3) as response:
            if json.load(response).get('status') == 'ok':
                break
    except (OSError, ValueError):
        pass
    time.sleep(2)
else:
    raise SystemExit('The local workbench did not become healthy.')
PY
echo 'BioGraph Steward is ready on loopback port 8766. Access uses Session Manager.'
