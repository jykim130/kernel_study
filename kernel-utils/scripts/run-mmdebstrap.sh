#!/usr/bin/env bash
source "$(dirname -- "${BASH_SOURCE[0]}")/common.sh"
require_linux
need mmdebstrap mktemp mkdir cp chmod basename env gpg awk

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
keyring_files=()
stage_keyring() {
    local source=$1 destination="$bootstrap_work/keyring-$keyring_index" key
    mkdir -m 755 -- "$destination"
    if [[ -f $source ]]; then
        staged_keyring="$destination/$(basename -- "$source")"
        cp -L -- "$source" "$staged_keyring"
        chmod 644 "$staged_keyring"
        keyring_files+=("$staged_keyring")
    elif [[ -d $source ]]; then
        staged_keyring=$destination
        for key in "$source"/*.gpg "$source"/*.asc; do
            [[ -f $key ]] || continue
            cp -L -- "$key" "$destination/"
            chmod 644 "$destination/$(basename -- "$key")"
            keyring_files+=("$destination/$(basename -- "$key")")
        done
    else
        die "Keyring does not exist or cannot be read: $source"
    fi
    keyring_index=$((keyring_index + 1))
}

bootstrap_args=()
bootstrap_components=(main)
components_given=no
while (( $# )); do
    case $1 in
        --) bootstrap_args+=("$@"); break ;;
        --components=*)
            if [[ $components_given == no ]]; then bootstrap_components=(); components_given=yes; fi
            bootstrap_components+=("${1#--components=}")
            bootstrap_args+=("$1")
            shift
            ;;
        --components)
            (( $# >= 2 )) || die '--components requires a value.'
            if [[ $components_given == no ]]; then bootstrap_components=(); components_given=yes; fi
            bootstrap_components+=("$2")
            bootstrap_args+=("$1" "$2")
            shift 2
            ;;
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

# mmdebstrap 0.8.4 can auto-select an old host keyring even with --keyring.
# Pin the supplied keys in an explicit repository entry. Fingerprints keep
# the guest's sources independent of the temporary host keyring path.
if (( ${#keyring_files[@]} > 0 && ${#bootstrap_args[@]} >= 3 )); then
    bootstrap_mirror=${bootstrap_args[-1]}
    bootstrap_suite=${bootstrap_args[-3]}
    if [[ $bootstrap_suite == "$ROOTFS_SUITE" && $bootstrap_mirror == http*://* ]]; then
        mkdir -m 700 "$bootstrap_work/gnupg"
        signing_fingerprints=$(gpg --batch --quiet --no-options \
            --homedir "$bootstrap_work/gnupg" --with-colons --show-keys "${keyring_files[@]}" |
            awk -F: '$1 == "pub" { primary = 1; next }
                primary && $1 == "fpr" { printf "%s%s", separator, $10; separator = ","; primary = 0 }
                END { print "" }')
        [[ -n $signing_fingerprints ]] || die 'No signing keys found in the supplied keyrings.'
        bootstrap_component_list=${bootstrap_components[*]}
        bootstrap_component_list=${bootstrap_component_list//,/ }
        bootstrap_args[-1]="deb [signed-by=$signing_fingerprints] $bootstrap_mirror $bootstrap_suite $bootstrap_component_list"
        log "Using explicit signing keys for the $bootstrap_suite repository."
    fi
fi

# The child should not try to read ~/.dpkg.cfg from the private host home.
env HOME="$bootstrap_work" mmdebstrap "${bootstrap_args[@]}"
