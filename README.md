# SVCC HPE

Repository for the HPE BiBiFi contest submission.

## Layout

- `build/` - implementation source and build files
- `break/` - break test cases

## Build

The contest builds from the root-level `build/` directory. The required target is
32-bit Linux on Ubuntu 18.04, so use the provided Docker sandbox even on a newer
Ubuntu server.

Clone or update the repo first:

```sh
git clone git@github.com:kevwjin/svcc-hpe.git
cd svcc-hpe
```

If the repo already exists:

```sh
git pull --ff-only
```

Build the sandbox image:

```sh
docker build --platform linux/amd64 -t bibifi-sandbox -f Dockerfile.sandbox .
```

Run `make` inside the sandbox with `build/` mounted at `/connect`:

```sh
docker run --platform linux/amd64 --rm -it \
  -v "$PWD/build:/connect" \
  bibifi-sandbox
```

Inside the container:

```sh
make
```

For a one-shot noninteractive build:

```sh
docker run --platform linux/amd64 --rm \
  -v "$PWD/build:/connect" \
  bibifi-sandbox \
  -lc 'make clean >/dev/null 2>&1 || true; make'
```

## Manual Smoke Tests

After building, run commands inside the same container shell so `enc.db` is
created in `/connect`:

```sh
rm -f enc.db
./stor -u alice -k secret123 register
./stor -u alice -f notes create
./stor -u alice -k secret123 -f notes write "hello world"
./stor -u alice -k secret123 -f notes read
```

The provided functionality scenarios are in `tests.json`.
