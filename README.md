# SVCC HPE

Repository for the HPE BiBiFi contest submission.

## Layout

- `build/` - implementation source and build files
- `break/` - break test cases

## Build

The contest builds from the root-level `build/` directory. The required target is
32-bit Linux, so native builds may fail on macOS, especially on Apple Silicon.

In the contest-style environment, `make` should run from `build/`:

```sh
cd build
make
```

If native `make` fails locally, use an amd64 Ubuntu 18.04 container:

```sh
docker run --platform linux/amd64 --rm \
  -v "$PWD/build:/connect" \
  ubuntu:18.04 \
  bash -lc 'apt-get update >/dev/null &&
    dpkg --add-architecture i386 &&
    apt-get update >/dev/null &&
    DEBIAN_FRONTEND=noninteractive apt-get install -y build-essential gcc-multilib libssl-dev:i386 >/dev/null &&
    cd /connect &&
    gcc -O0 -g -m32 -fno-stack-protector -o stor stor.c malloc-2.7.2.c -lssl -lcrypto &&
    test -x stor'
```

That verifies the same compile command used by `build/Makefile`. It does not run
the `execstack` post-step, but the contest environment runs `make`, which includes
that step.

## Manual Smoke Tests

After building, run commands from `build/` so `enc.db` is created there:

```sh
rm -f enc.db
./stor -u alice -k secret123 register
./stor -u alice -f notes create
./stor -u alice -k secret123 -f notes write "hello world"
./stor -u alice -k secret123 -f notes read
```

The current starter `stor.c` is still a stub, so these commands are expected to
print `invalid` until the implementation is filled in. The provided functionality
scenarios are in `tests.json`.
