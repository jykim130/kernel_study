#!/usr/bin/env bash
source "$(dirname -- "${BASH_SOURCE[0]}")/common.sh"
require_linux
need mmdebstrap mktemp mkdir cp chmod basename env

# apt's verification UID cannot traverse a private project/home directory.
# Stage only public keyrings outside that tree for this invocation.
bootstrap_work=$(mktemp -d /tmp/kernel-study-bootstrap.XXXXXX)
cleanup_bootstrap() {
    if [[ $bootstrap_work == /tmp/kernel-study-bootstrap.* && -d $bootstrap_work ]]; then
        rm -rf -- "$bootstrap_work"
    fi
}
trap cleanup_bootstrap EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
chmod 755 "$bootstrap_work"

keyring_index=0
stage_keyring() {
    local source=$1 destination="$bootstrap_work/keyring-$keyring_index" key
    mkdir -m 755 -- "$destination"
    if [[ -f $source ]]; then
        staged_keyring="$destination/$(basename -- "$source")"
        cp -L -- "$source" "$staged_keyring"
        chmod 644 "$staged_keyring"
    elif [[ -d $source ]]; then
        staged_keyring=$destination
        for key in "$source"/*.gpg "$source"/*.asc; do
            [[ -f $key ]] || continue
            cp -L -- "$key" "$destination/"
            chmod 644 "$destination/$(basename -- "$key")"
        done
    else
        die "Keyring does not exist or cannot be read: $source"
    fi
    keyring_index=$((keyring_index + 1))
}

bootstrap_args=()
while (( $# )); do
    case $1 in
        --) bootstrap_args+=("$@"); break ;;
        --keyring=*)
            stage_keyring "${1#--keyring=}"
            bootstrap_args+=("--keyring=$staged_keyring")
            shift
            ;;
        --keyring)
            (( $# >= 2 )) || die '--keyring requires a path.'
            stage_keyring "$2"
            bootstrap_args+=("--keyring=$staged_keyring")
            shift 2
            ;;
        *) bootstrap_args+=("$1"); shift ;;
    esac
done

# The child should not try to read ~/.dpkg.cfg from the private host home.
env HOME="$bootstrap_work" mmdebstrap "${bootstrap_args[@]}"
