#!/usr/bin/env python
"""Focused security regression tests for stor.

Run after building build/stor. Each case gets a fresh temporary directory.
"""

from __future__ import print_function

import os
import shutil
import struct
import subprocess
import sys
import tempfile


ROOT = os.path.dirname(os.path.abspath(__file__))
STOR = os.path.join(ROOT, "build", "stor")


def run(td, args):
    argv = ["./stor"] + args
    p = subprocess.Popen(
        argv,
        cwd=td,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    out, err = p.communicate()
    return p.returncode, out, err


def expect(td, args, code, stdout=None):
    got_code, got_out, got_err = run(td, args)
    if stdout is not None and got_out.endswith(b"\n"):
        got_out = got_out[:-1]
    if got_code != code or (stdout is not None and got_out != stdout):
        return False, "argv=%r exit=%r stdout=%r stderr=%r" % (
            args,
            got_code,
            got_out,
            got_err,
        )
    return True, ""


def read_u32(data, off):
    if off + 4 > len(data):
        raise ValueError("truncated u32")
    return struct.unpack(">I", data[off : off + 4])[0], off + 4


def read_field(data, off):
    n, off = read_u32(data, off)
    if off + n > len(data):
        raise ValueError("truncated field")
    return data[off : off + n], off + n


def field_bytes(value):
    return struct.pack(">I", len(value)) + value


def parse_db(data):
    off = 0
    magic = data[off : off + 8]
    off += 8
    version, off = read_u32(data, off)
    user_count, off = read_u32(data, off)
    file_count, off = read_u32(data, off)

    users_start = off
    for _ in range(user_count):
        _, off = read_field(data, off)
        off += 16 + 32
        if off > len(data):
            raise ValueError("truncated user")
    users_raw = data[users_start:off]

    files = []
    files_start = off
    for _ in range(file_count):
        record_start = off
        owner, off = read_field(data, off)
        name, off = read_field(data, off)
        nonce = data[off : off + 16]
        off += 16
        cipher_len, off = read_u32(data, off)
        cipher = data[off : off + cipher_len]
        off += cipher_len
        tag = data[off : off + 32]
        off += 32
        if len(nonce) != 16 or len(cipher) != cipher_len or len(tag) != 32:
            raise ValueError("truncated file")
        files.append(
            {
                "raw": data[record_start:off],
                "owner": owner,
                "name": name,
                "nonce": nonce,
                "cipher": cipher,
                "tag": tag,
            }
        )

    if off != len(data):
        raise ValueError("trailing bytes")

    return {
        "magic": magic,
        "version": version,
        "user_count": user_count,
        "file_count": file_count,
        "users_raw": users_raw,
        "files_raw": data[files_start:off],
        "files": files,
    }


def write_db(td, db):
    with open(os.path.join(td, "enc.db"), "wb") as f:
        f.write(db)


def build_header(parsed, file_count):
    return (
        parsed["magic"]
        + struct.pack(">I", parsed["version"])
        + struct.pack(">I", parsed["user_count"])
        + struct.pack(">I", file_count)
        + parsed["users_raw"]
    )


def zero_cipher_record(file_record):
    return (
        field_bytes(file_record["owner"])
        + field_bytes(file_record["name"])
        + file_record["nonce"]
        + struct.pack(">I", 0)
        + (b"\x00" * 32)
    )


def prepare_written_db(td):
    ok, msg = expect(td, ["-u", "alice", "-k", "secret123", "register"], 0)
    if not ok:
        raise AssertionError(msg)
    ok, msg = expect(td, ["-u", "alice", "-f", "notes", "create"], 0)
    if not ok:
        raise AssertionError(msg)
    ok, msg = expect(
        td,
        ["-u", "alice", "-k", "secret123", "-f", "notes", "write", "private"],
        0,
    )
    if not ok:
        raise AssertionError(msg)


def test_duplicate_register_rejected(td):
    ok, msg = expect(td, ["-u", "alice", "-k", "secret123", "register"], 0)
    if not ok:
        return False, msg
    return expect(td, ["-u", "alice", "-k", "attacker", "register"], 255, b"invalid")


def test_zero_cipher_tamper_rejected(td):
    prepare_written_db(td)
    with open(os.path.join(td, "enc.db"), "rb") as f:
        parsed = parse_db(f.read())
    forged = build_header(parsed, 1) + zero_cipher_record(parsed["files"][0])
    write_db(td, forged)
    return expect(td, ["-u", "alice", "-k", "secret123", "-f", "notes", "read"], 255, b"invalid")


def test_duplicate_file_shadow_rejected(td):
    prepare_written_db(td)
    with open(os.path.join(td, "enc.db"), "rb") as f:
        parsed = parse_db(f.read())
    shadow = zero_cipher_record(parsed["files"][0])
    forged = build_header(parsed, parsed["file_count"] + 1) + shadow + parsed["files_raw"]
    write_db(td, forged)
    return expect(td, ["-u", "alice", "-k", "secret123", "-f", "notes", "read"], 255, b"invalid")


def test_ciphertext_byte_tamper_rejected(td):
    prepare_written_db(td)
    with open(os.path.join(td, "enc.db"), "rb") as f:
        data = bytearray(f.read())
    # Flip a byte before the final tag. This should invalidate the tag.
    data[-40] ^= 0x01
    write_db(td, bytes(data))
    return expect(td, ["-u", "alice", "-k", "secret123", "-f", "notes", "read"], 255, b"invalid")


TESTS = [
    ("duplicate_register_rejected", test_duplicate_register_rejected),
    ("zero_cipher_tamper_rejected", test_zero_cipher_tamper_rejected),
    ("duplicate_file_shadow_rejected", test_duplicate_file_shadow_rejected),
    ("ciphertext_byte_tamper_rejected", test_ciphertext_byte_tamper_rejected),
]


def main():
    if not os.path.exists(STOR):
        print("missing build/stor; run make first", file=sys.stderr)
        return 2

    failures = 0
    for name, fn in TESTS:
        td = tempfile.mkdtemp(prefix="stor-security-")
        try:
            shutil.copy2(STOR, os.path.join(td, "stor"))
            os.chmod(os.path.join(td, "stor"), 0o755)
            ok, msg = fn(td)
            if ok:
                print("ok %s" % name)
            else:
                failures += 1
                print("FAIL %s: %s" % (name, msg))
        finally:
            shutil.rmtree(td)

    print("FAILURES %d" % failures)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
