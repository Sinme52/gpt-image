"""Tests for scripts/gpt_image.py against a local mock of the OpenAI images API (no network, no cost).

Run: python3 -m unittest discover -s tests
"""
import base64
import io
import json
import os
import struct
import subprocess
import sys
import tempfile
import threading
import unittest
import zlib
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "gpt-image" / "scripts" / "gpt_image.py"


def png_bytes(w, h):
    raw = b"".join(b"\x00" + b"\x00\x00\x00" * w for _ in range(h))
    def chunk(t, d):
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))


TINY_B64 = base64.b64encode(png_bytes(4, 4)).decode()


class Mock(BaseHTTPRequestHandler):
    requests = []

    def do_POST(self):
        body = self.rfile.read(int(self.headers["Content-Length"]))
        ctype = self.headers["Content-Type"]
        rec = {"path": self.path, "auth": self.headers.get("Authorization"), "ctype": ctype}
        if ctype.startswith("multipart/form-data"):
            boundary = ctype.split("boundary=")[1].encode()
            fields, images = {}, []
            for part in body.split(b"--" + boundary)[1:-1]:
                head, _, data = part.partition(b"\r\n\r\n")
                data = data[:-2]
                name = head.split(b'name="')[1].split(b'"')[0].decode()
                if b"filename=" in head:
                    images.append({"filename": head.split(b'filename="')[1].split(b'"')[0].decode(),
                                   "type": head.split(b"Content-Type: ")[1].strip().decode(), "data": data})
                else:
                    fields[name] = data.decode()
            rec.update(fields=fields, images=images)
            n = int(fields.get("n", "1"))
        else:
            rec["json"] = json.loads(body)
            n = rec["json"].get("n", 1)
        Mock.requests.append(rec)
        out = json.dumps({"data": [{"b64_json": TINY_B64} for _ in range(n)], "usage": {"total_tokens": 1}}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("x-request-id", "req_test")
        self.send_header("Content-Length", str(len(out)))
        self.end_headers()
        self.wfile.write(out)

    def log_message(self, *a):
        pass


class GptImageCli(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = HTTPServer(("127.0.0.1", 0), Mock)
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()
        cls.env = dict(os.environ, OPENAI_IMAGE_API_KEY="sk-test", OPENAI_IMAGE_BASE_URL=f"http://127.0.0.1:{cls.server.server_port}/v1",
                       NO_PROXY="127.0.0.1,localhost", no_proxy="127.0.0.1,localhost")

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()

    def setUp(self):
        Mock.requests.clear()
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def run_cli(self, *args):
        r = subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True, env=self.env, cwd=self.dir)
        return r.returncode, r.stdout, r.stderr

    def test_edit_sends_every_image_in_order(self):
        a = self.dir / "character.png"
        a.write_bytes(png_bytes(1024, 1024))
        b = self.dir / "pose.webp"
        b.write_bytes(b"RIFF\x00\x00\x00\x00WEBPVP8 ")
        c = self.dir / "frame.jpg"
        c.write_bytes(b"\xff\xd8\xff\xd9")
        meta = self.dir / "meta.json"
        meta.write_text(json.dumps({"pose": {"name": "walk"}, "prompt": "must not overwrite"}))
        code, out, err = self.run_cli("edit", "--image", str(a), "--image", str(b), "--image", str(c), "--prompt", "Draw IMAGE 1 in the pose of IMAGE 2",
                                      "--n", "2", "--background", "transparent", "--name", "walk", "--out-dir", str(self.dir / "out"),
                                      "--release-prompt", "a knight walking", "--meta-json", str(meta))
        self.assertEqual(code, 0, err)
        req = Mock.requests[0]
        self.assertEqual(req["path"], "/v1/images/edits")
        self.assertEqual(req["auth"], "Bearer sk-test")
        self.assertEqual([i["type"] for i in req["images"]], ["image/png", "image/webp", "image/jpeg"])
        self.assertEqual(req["images"][0]["data"], a.read_bytes())
        self.assertEqual(req["fields"]["prompt"], "Draw IMAGE 1 in the pose of IMAGE 2")
        self.assertEqual(req["fields"]["quality"], "medium")
        self.assertEqual(req["fields"]["size"], "1024x1024")  # from the first image
        self.assertEqual(req["fields"]["n"], "2")
        self.assertEqual(req["fields"]["background"], "transparent")
        files = json.loads(out)["files"]
        self.assertEqual([Path(f).name for f in files], ["walk_1.png", "walk_2.png"])
        side = json.loads((self.dir / "out" / "walk_1.json").read_text())
        self.assertEqual(side["kind"], "edit")
        self.assertEqual(side["input_images"], [str(a), str(b), str(c)])
        self.assertEqual(side["release_prompt"], "a knight walking")
        self.assertEqual(side["prompt"], "Draw IMAGE 1 in the pose of IMAGE 2")
        self.assertEqual(side["pose"], {"name": "walk"})

    def test_edit_size_falls_back_to_auto(self):
        a = self.dir / "small.png"
        a.write_bytes(png_bytes(100, 100))
        code, out, err = self.run_cli("edit", "--image", str(a), "--prompt", "x", "--out-dir", str(self.dir))
        self.assertEqual(code, 0, err)
        self.assertEqual(Mock.requests[0]["fields"]["size"], "auto")

    def test_edit_errors(self):
        code, _, err = self.run_cli("edit", "--image", str(self.dir / "missing.png"), "--prompt", "x")
        self.assertEqual(code, 1)
        self.assertIn("Image not found", json.loads(err)["error"])
        bad = self.dir / "a.gif"
        bad.write_bytes(b"GIF89a")
        code, _, err = self.run_cli("edit", "--image", str(bad), "--prompt", "x")
        self.assertIn("Unsupported image type", json.loads(err)["error"])
        self.assertEqual(Mock.requests, [])

    def test_release_of_an_edit_uses_its_release_prompt(self):
        a = self.dir / "c.png"
        a.write_bytes(png_bytes(1024, 1024))
        code, out, err = self.run_cli("edit", "--image", str(a), "--prompt", "IMAGE 1 walking", "--name", "d", "--out-dir", str(self.dir),
                                      "--release-prompt", "a knight walking to the left")
        self.assertEqual(code, 0, err)
        draft = json.loads(out)["files"][0]
        Path(draft).write_bytes(png_bytes(1024, 1024))
        code, out, err = self.run_cli("release", "--image", draft)
        self.assertEqual(code, 0, err)
        rel = Mock.requests[-1]
        self.assertEqual(rel["fields"]["quality"], "xhigh")
        self.assertTrue(rel["fields"]["prompt"].endswith("Image description: a knight walking to the left"))
        self.assertEqual(len(rel["images"]), 1)

    def test_generate_still_works(self):
        code, out, err = self.run_cli("generate", "--prompt", "a cat", "--out-dir", str(self.dir), "--name", "cat")
        self.assertEqual(code, 0, err)
        self.assertEqual(Mock.requests[0]["path"], "/v1/images/generations")
        self.assertEqual(Mock.requests[0]["json"]["quality"], "medium")

    def test_generate_and_edit_default_to_low_complexity(self):
        code, _, err = self.run_cli("generate", "--prompt", "a cat", "--out-dir", str(self.dir), "--name", "cat")
        self.assertEqual(code, 0, err)
        self.assertEqual(Mock.requests[0]["json"]["model"], "gpt-image-2.6-sunburst")
        self.assertEqual(Mock.requests[0]["json"]["complexity"], "low")
        self.assertEqual(json.loads((self.dir / "cat.json").read_text())["complexity"], "low")
        a = self.dir / "c.png"
        a.write_bytes(png_bytes(1024, 1024))
        code, _, err = self.run_cli("edit", "--image", str(a), "--prompt", "x", "--out-dir", str(self.dir), "--name", "e")
        self.assertEqual(code, 0, err)
        self.assertEqual(Mock.requests[1]["fields"]["model"], "gpt-image-2.6-sunburst")
        self.assertEqual(Mock.requests[1]["fields"]["complexity"], "low")
        self.assertEqual(json.loads((self.dir / "e.json").read_text())["complexity"], "low")

    def test_edit_complexity_can_be_overridden(self):
        a = self.dir / "c.png"
        a.write_bytes(png_bytes(1024, 1024))
        code, _, err = self.run_cli("edit", "--image", str(a), "--prompt", "x", "--complexity", "high", "--out-dir", str(self.dir), "--name", "e")
        self.assertEqual(code, 0, err)
        self.assertEqual(Mock.requests[0]["fields"]["complexity"], "high")

    def test_model_accepts_any_id_and_complexity_is_sent(self):
        code, _, err = self.run_cli("generate", "--prompt", "a cat", "--model", "gpt-image-2.6-flare", "--complexity", "medium",
                                    "--out-dir", str(self.dir), "--name", "cat")
        self.assertEqual(code, 0, err)
        self.assertEqual(Mock.requests[0]["json"]["model"], "gpt-image-2.6-flare")
        self.assertEqual(Mock.requests[0]["json"]["complexity"], "medium")
        self.assertEqual(json.loads((self.dir / "cat.json").read_text())["complexity"], "medium")

    def make_draft(self, model=None):
        draft = self.dir / "draft-x.png"
        draft.write_bytes(png_bytes(1024, 1024))
        side = {"prompt": "a cat", "output_format": "png"}
        if model:
            side["model"] = model
        (self.dir / "draft-x.json").write_text(json.dumps(side))
        return draft

    def test_release_plans_low_complexity_on_the_default_model(self):
        code, _, err = self.run_cli("release", "--image", str(self.make_draft()))
        self.assertEqual(code, 0, err)
        fields = Mock.requests[0]["fields"]
        self.assertEqual(fields["model"], "gpt-image-2.6-sunburst")
        self.assertEqual(fields["complexity"], "low")
        self.assertEqual(json.loads((self.dir / "release-x.json").read_text())["complexity"], "low")

    def test_release_complexity_can_be_overridden(self):
        code, _, err = self.run_cli("release", "--image", str(self.make_draft()), "--complexity", "high")
        self.assertEqual(code, 0, err)
        self.assertEqual(Mock.requests[0]["fields"]["complexity"], "high")

    def test_release_of_an_old_draft_keeps_its_model_with_low_complexity(self):
        code, _, err = self.run_cli("release", "--image", str(self.make_draft("gpt-image-2.5-sunburst")))
        self.assertEqual(code, 0, err)
        fields = Mock.requests[0]["fields"]
        self.assertEqual(fields["model"], "gpt-image-2.5-sunburst")
        self.assertEqual(fields["complexity"], "low")

    def test_release_does_not_inherit_the_drafts_complexity(self):
        draft = self.make_draft()
        (self.dir / "draft-x.json").write_text(json.dumps({"prompt": "a cat", "complexity": "high"}))
        code, _, err = self.run_cli("release", "--image", str(draft))
        self.assertEqual(code, 0, err)
        self.assertEqual(Mock.requests[0]["fields"]["complexity"], "low")

    def test_release_regenerate_defaults_to_low_complexity(self):
        code, _, err = self.run_cli("release", "--image", str(self.make_draft()), "--mode", "regenerate")
        self.assertEqual(code, 0, err)
        self.assertEqual(Mock.requests[0]["path"], "/v1/images/generations")
        self.assertEqual(Mock.requests[0]["json"]["complexity"], "low")
        code, _, err = self.run_cli("release", "--image", str(self.make_draft()), "--mode", "regenerate", "--complexity", "medium")
        self.assertEqual(code, 0, err)
        self.assertEqual(Mock.requests[1]["json"]["complexity"], "medium")


if __name__ == "__main__":
    unittest.main()
