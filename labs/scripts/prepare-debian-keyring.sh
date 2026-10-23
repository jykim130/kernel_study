#!/usr/bin/env bash
source "$(dirname -- "${BASH_SOURCE[0]}")/common.sh"
if [[ ${1:-} == --help ]]; then
    echo 'Usage: bash labs/scripts/prepare-debian-keyring.sh'
    exit 0
fi
(( $# == 0 )) || die 'Unexpected argument. Use --help.'
require_linux
[[ $ROOTFS_SUITE == bookworm ]] || die 'This keyring is specifically for Debian Bookworm.'
need curl gpg awk
mkdir -p "$CACHE_DIR"
key_work=$(mktemp -d "$CACHE_DIR/debian-keys.XXXXXX")
cleanup_keys() {
    # Only remove this invocation's private, generated work directory.
    if [[ $key_work == "$CACHE_DIR"/debian-keys.* && -d $key_work ]]; then
        rm -rf -- "$key_work"
    fi
}
trap cleanup_keys EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

# Primary fingerprints published by the Debian FTP team:
# https://ftp-master.debian.org/keys.html
key_specs=(
    'archive-key-12.asc:B8B80B5B623EAB6AD8775C45B7C5D7D6350947F8'
    'archive-key-12-security.asc:05AB90340C0C5E797F44A8C8254CF3B5AEC0A8F0'
    'release-12.asc:4D64FEC119C2029067D6E791F8D2585B8783D481'
)
key_files=()
for spec in "${key_specs[@]}"; do
    IFS=: read -r key_name expected_fingerprint <<< "$spec"
    log "Fetching Debian Bookworm signing key: $key_name"
    curl --fail --location --retry 3 --proto '=https' --proto-redir '=https' \
        "https://ftp-master.debian.org/keys/$key_name" --output "$key_work/$key_name"
    actual_fingerprint=$(gpg --batch --no-options --homedir "$key_work" \
        --with-colons --show-keys "$key_work/$key_name" |
        awk -F: '$1 == "pub" { primary = 1; next } primary && $1 == "fpr" { print $10; primary = 0 }')
    [[ $actual_fingerprint == "$expected_fingerprint" ]] ||
        die "Unexpected fingerprint for $key_name; refusing to install this key."
    gpg --batch --no-options --homedir "$key_work" --dearmor \
        --output "$key_work/$key_name.gpg" "$key_work/$key_name"
    key_files+=("$key_work/$key_name.gpg")
done
cat "${key_files[@]}" > "$key_work/bookworm.gpg"
chmod 644 "$key_work/bookworm.gpg"
mv -f -- "$key_work/bookworm.gpg" "$DEBIAN_KEYRING"
log "Bookworm keyring ready: $DEBIAN_KEYRING"
